from datetime import timedelta

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, aliased

from medlink.embeddings import Embedder, validate_vectors
from medlink.models import Chunk, Dataset, Encounter, Lab, Note
from medlink.schemas import (
    LabEvidence,
    NoteEvidence,
    StructuredHit,
    StructuredRequest,
    VectorHit,
    VectorRequest,
)


class IndexNotReady(ValueError):
    pass


def active_conditions(request: StructuredRequest):
    conditions = [
        Encounter.admitted_at <= request.as_of,
        or_(Encounter.discharged_at.is_(None), Encounter.discharged_at > request.as_of),
    ]
    if request.patient_id:
        conditions.append(Encounter.patient_id == request.patient_id)
    return conditions


def structured_statement(request: StructuredRequest):
    cutoff = request.as_of - timedelta(hours=request.lookback_hours)
    ranked = (
        select(
            Lab.id.label("lab_id"),
            Lab.encounter_id,
            func.row_number()
            .over(
                partition_by=Lab.encounter_id,
                order_by=(Lab.collected_at.desc(), Lab.available_at.desc(), Lab.id.desc()),
            )
            .label("rank"),
        )
        .where(
            Lab.code == "CRP",
            Lab.unit == "mg/L",
            Lab.collected_at >= cutoff,
            Lab.collected_at <= request.as_of,
            Lab.available_at <= request.as_of,
        )
        .subquery()
    )
    latest_rank, previous_rank = aliased(ranked), aliased(ranked)
    latest, previous = aliased(Lab), aliased(Lab)
    return (
        select(Encounter, latest, previous)
        .join(
            latest_rank, and_(latest_rank.c.encounter_id == Encounter.id, latest_rank.c.rank == 1)
        )
        .join(
            previous_rank,
            and_(previous_rank.c.encounter_id == Encounter.id, previous_rank.c.rank == 2),
        )
        .join(latest, latest.id == latest_rank.c.lab_id)
        .join(previous, previous.id == previous_rank.c.lab_id)
        .where(
            *active_conditions(request),
            latest.value - previous.value > request.min_delta_mg_l,
            latest.collected_at > previous.collected_at,
        )
        .order_by((latest.value - previous.value).desc(), Encounter.id)
    )


def lab_evidence(lab: Lab) -> LabEvidence:
    return LabEvidence(
        id=lab.id,
        value_mg_l=lab.value,
        collected_at=lab.collected_at,
        available_at=lab.available_at,
        source_value=lab.source_value,
        source_unit=lab.source_unit,
    )


def structured_search(session: Session, request: StructuredRequest) -> list[StructuredHit]:
    return [
        StructuredHit(
            patient_id=enc.patient_id,
            encounter_id=enc.id,
            ward=enc.ward,
            previous=lab_evidence(previous),
            latest=lab_evidence(latest),
            delta_mg_l=round(latest.value - previous.value, 6),
        )
        for enc, latest, previous in session.execute(structured_statement(request))
    ]


def vector_statement(
    request: VectorRequest, vector: list[float], key: str, eligible: list[str] | None = None
):
    distance = Chunk.embedding.cosine_distance(vector)
    conditions = [
        *active_conditions(request),
        Chunk.embedding_key == key,
        Note.recorded_at <= request.as_of,
        Note.recorded_at >= request.as_of - timedelta(hours=request.lookback_hours),
    ]
    if request.note_kind:
        conditions.append(Note.kind == request.note_kind)
    if eligible is not None:
        conditions.append(Encounter.id.in_(eligible))
    ranked = (
        select(
            Chunk.id.label("chunk_id"),
            distance.label("distance"),
            func.row_number()
            .over(partition_by=Encounter.id, order_by=(distance, Chunk.id))
            .label("rank"),
        )
        .join(Note, Note.id == Chunk.note_id)
        .join(Encounter, Encounter.id == Note.encounter_id)
        .where(*conditions)
        .subquery()
    )
    return (
        select(Encounter, Note, Chunk, ranked.c.distance)
        .join(Note, Note.encounter_id == Encounter.id)
        .join(Chunk, Chunk.note_id == Note.id)
        .join(ranked, ranked.c.chunk_id == Chunk.id)
        .where(ranked.c.rank == 1, ranked.c.distance <= 1 - request.min_similarity)
        .order_by(ranked.c.distance, Encounter.id)
        .limit(request.top_k)
    )


def vector_search(
    session: Session, request: VectorRequest, embedder: Embedder, *, hybrid: bool = False
) -> list[VectorHit]:
    dataset = session.scalar(select(Dataset))
    if not dataset or dataset.embedding_key != embedder.key:
        raise IndexNotReady("Seed the database using the configured embedding model first")
    crp = {hit.encounter_id: hit for hit in structured_search(session, request)} if hybrid else {}
    if hybrid and not crp:
        return []
    vectors = embedder.encode([request.query])
    validate_vectors(vectors, 1)
    statement = vector_statement(request, vectors[0], embedder.key, list(crp) if hybrid else None)
    return [
        VectorHit(
            patient_id=enc.patient_id,
            encounter_id=enc.id,
            ward=enc.ward,
            evidence=NoteEvidence(
                chunk_id=chunk.id,
                note_id=note.id,
                note_kind=note.kind,
                recorded_at=note.recorded_at,
                excerpt=chunk.text,
                similarity=round(max(-1.0, min(1.0, 1 - float(distance))), 6),
            ),
            crp=crp.get(enc.id),
        )
        for enc, note, chunk, distance in session.execute(statement)
    ]
