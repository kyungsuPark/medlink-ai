"""One immutable legacy export, validated and ingested atomically."""

import hashlib
import json
from datetime import datetime, timezone
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from medlink.embeddings import Embedder, validate_vectors
from medlink.models import Chunk, Dataset, Encounter, Lab, Note, Patient
from medlink.schemas import StrictModel


class RawPatient(StrictModel):
    PT_NO: str = Field(pattern=r"^P[0-9]{3,6}$")
    PT_NM: str = Field(min_length=1, max_length=100)


class RawEncounter(StrictModel):
    ADM_NO: str = Field(min_length=1, max_length=40)
    PT_NO: str
    IN_DTM: AwareDatetime
    OUT_DTM: AwareDatetime | None = None
    WARD_CD: str = Field(min_length=1, max_length=40)

    @model_validator(mode="after")
    def dates(self):
        if self.OUT_DTM and self.OUT_DTM < self.IN_DTM:
            raise ValueError("Discharge precedes admission")
        return self


class RawLab(StrictModel):
    RSLT_NO: str = Field(min_length=1, max_length=40)
    ADM_NO: str
    ITEM_CD: Literal["CRP"]
    RSLT_VAL: float = Field(ge=0)
    UNIT: Literal["mg/L", "mg/dL"]
    COLLECT_DTM: AwareDatetime
    VERIFY_DTM: AwareDatetime
    STATUS: Literal["F", "P", "C"] = "F"

    @model_validator(mode="after")
    def dates(self):
        if self.VERIFY_DTM < self.COLLECT_DTM:
            raise ValueError("Verification precedes collection")
        return self


class RawNote(StrictModel):
    DOC_NO: str = Field(min_length=1, max_length=40)
    ADM_NO: str
    DOC_KIND: Literal["progress", "consult"]
    SIGN_DTM: AwareDatetime
    BODY: str = Field(min_length=1, max_length=20000)


class LegacySnapshot(StrictModel):
    dataset_id: str = Field(pattern=r"^synthetic-[a-z0-9-]+$", max_length=80)
    synthetic: Literal[True]
    patients: list[RawPatient] = Field(min_length=1, max_length=1000)
    admissions: list[RawEncounter] = Field(min_length=1, max_length=2000)
    labs: list[RawLab] = Field(max_length=20000)
    documents: list[RawNote] = Field(max_length=5000)

    @model_validator(mode="after")
    def references(self):
        for rows, key in [
            (self.patients, "PT_NO"),
            (self.admissions, "ADM_NO"),
            (self.labs, "RSLT_NO"),
            (self.documents, "DOC_NO"),
        ]:
            ids = [getattr(row, key) for row in rows]
            if len(ids) != len(set(ids)):
                raise ValueError(f"Duplicate source key: {key}")
        patients = {p.PT_NO for p in self.patients}
        admissions = {a.ADM_NO: a for a in self.admissions}
        for admission in self.admissions:
            if admission.PT_NO not in patients:
                raise ValueError("Admission references missing patient")
        for row in [*self.labs, *self.documents]:
            if row.ADM_NO not in admissions:
                raise ValueError("Record references missing admission")
            event = row.COLLECT_DTM if isinstance(row, RawLab) else row.SIGN_DTM
            adm = admissions[row.ADM_NO]
            if event < adm.IN_DTM or (adm.OUT_DTM and event > adm.OUT_DTM):
                raise ValueError("Record falls outside its admission")
        for patient_id in patients:
            rows = sorted(
                [a for a in self.admissions if a.PT_NO == patient_id], key=lambda a: a.IN_DTM
            )
            for previous, current in zip(rows, rows[1:], strict=False):
                if previous.OUT_DTM is None or previous.OUT_DTM > current.IN_DTM:
                    raise ValueError("Overlapping admissions are not supported")
        return self


def chunk_text(value: str, size: int = 80, overlap: int = 12) -> list[str]:
    if not 0 <= overlap < size:
        raise ValueError("Chunk overlap must be smaller than size")
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("Empty note")
    result = []
    for start in range(0, len(cleaned), size - overlap):
        result.append(cleaned[start : start + size])
        if start + size >= len(cleaned):
            break
    return result


def ingest(session: Session, raw: LegacySnapshot, embedder: Embedder) -> dict:
    """Caller supplies an idle session. Failure rolls back the whole export."""
    canonical = json.dumps(raw.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
    checksum = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    with session.begin():
        if session.bind.dialect.name == "postgresql":
            session.execute(text("SELECT pg_advisory_xact_lock(734921)"))
        existing = session.scalar(select(Dataset))
        if existing:
            if (existing.id, existing.checksum, existing.embedding_key) == (
                raw.dataset_id,
                checksum,
                embedder.key,
            ):
                return {"status": "unchanged", "dataset_id": raw.dataset_id}
            raise ValueError("Database already contains a different export/model; use a fresh DB")

        chunks = [
            (note.DOC_NO, position, part)
            for note in raw.documents
            for position, part in enumerate(chunk_text(note.BODY))
        ]
        vectors = embedder.encode([part for _, _, part in chunks]) if chunks else []
        if chunks:
            validate_vectors(vectors, len(chunks))
        session.add_all([Patient(id=p.PT_NO, display_name=p.PT_NM) for p in raw.patients])
        session.flush()
        session.add_all(
            [
                Encounter(
                    id=a.ADM_NO,
                    patient_id=a.PT_NO,
                    admitted_at=a.IN_DTM,
                    discharged_at=a.OUT_DTM,
                    ward=a.WARD_CD,
                )
                for a in raw.admissions
            ]
        )
        session.flush()
        session.add_all(
            [
                Lab(
                    id=r.RSLT_NO,
                    encounter_id=r.ADM_NO,
                    code=r.ITEM_CD,
                    value=r.RSLT_VAL * (10 if r.UNIT == "mg/dL" else 1),
                    unit="mg/L",
                    source_value=r.RSLT_VAL,
                    source_unit=r.UNIT,
                    collected_at=r.COLLECT_DTM,
                    available_at=r.VERIFY_DTM,
                )
                for r in raw.labs
                if r.STATUS == "F"
            ]
        )
        session.add_all(
            [
                Note(
                    id=n.DOC_NO,
                    encounter_id=n.ADM_NO,
                    kind=n.DOC_KIND,
                    recorded_at=n.SIGN_DTM,
                    text=" ".join(n.BODY.split()),
                )
                for n in raw.documents
            ]
        )
        session.flush()
        session.add_all(
            [
                Chunk(
                    id=f"{note_id}:{position}",
                    note_id=note_id,
                    position=position,
                    text=part,
                    embedding=vector,
                    embedding_key=embedder.key,
                )
                for (note_id, position, part), vector in zip(chunks, vectors, strict=True)
            ]
        )
        session.add(
            Dataset(
                id=raw.dataset_id,
                checksum=checksum,
                embedding_key=embedder.key,
                ingested_at=datetime.now(timezone.utc),
            )
        )
    return {
        "status": "created",
        "dataset_id": raw.dataset_id,
        "patients": len(raw.patients),
        "chunks": len(chunks),
    }
