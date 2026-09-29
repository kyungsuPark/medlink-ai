from copy import deepcopy

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from medlink.ingest import LegacySnapshot, chunk_text, ingest
from medlink.models import Chunk, Lab, Patient
from medlink.sample import synthetic_export


def test_export_valid_and_repeatable():
    assert synthetic_export() == synthetic_export()
    raw = LegacySnapshot.model_validate(synthetic_export())
    assert len(raw.patients) == 12
    assert len(raw.admissions) == 13


@pytest.mark.parametrize("mutation", ["duplicate", "missing", "unit", "timezone", "overlap"])
def test_bad_exports_rejected(mutation):
    raw = deepcopy(synthetic_export())
    if mutation == "duplicate":
        raw["patients"].append(raw["patients"][0])
    elif mutation == "missing":
        raw["labs"][0]["ADM_NO"] = "MISSING"
    elif mutation == "unit":
        raw["labs"][0]["UNIT"] = "unknown"
    elif mutation == "timezone":
        raw["labs"][0]["COLLECT_DTM"] = "2026-09-27T08:00:00"
    else:
        raw["admissions"][-1]["OUT_DTM"] = None
    with pytest.raises(ValidationError):
        LegacySnapshot.model_validate(raw)


def test_normalization_idempotence_and_source_evidence(sqlite_engine, snapshot, embedder):
    with Session(sqlite_engine) as session:
        assert ingest(session, snapshot, embedder)["status"] == "created"
        assert ingest(session, snapshot, embedder)["status"] == "unchanged"
        lab = session.get(Lab, "L-A006-2")
        assert (lab.value, lab.unit, lab.source_value, lab.source_unit) == (30, "mg/L", 3, "mg/dL")
        assert session.get(Lab, "L-A008-pending") is None
        assert session.get(Lab, "L-A008-cancelled") is None
        assert session.scalar(select(func.count()).select_from(Patient)) == 12


def test_changed_export_is_rejected(sqlite_engine, snapshot, embedder):
    with Session(sqlite_engine) as session:
        ingest(session, snapshot, embedder)
        snapshot.patients[0].PT_NM = "Changed"
        with pytest.raises(ValueError, match="different export"):
            ingest(session, snapshot, embedder)


def test_embedding_failure_leaves_no_partial_data(sqlite_engine, snapshot, embedder):
    def fail(_):
        raise RuntimeError("Embedding provider unavailable")

    embedder.encode = fail
    with Session(sqlite_engine) as session:
        with pytest.raises(RuntimeError):
            ingest(session, snapshot, embedder)
        assert session.scalar(select(func.count()).select_from(Patient)) == 0
        assert session.scalar(select(func.count()).select_from(Chunk)) == 0


def test_invalid_vector_rejected(sqlite_engine, snapshot, embedder):
    embedder.encode = lambda texts: [[0.0] * 384 for _ in texts]
    with Session(sqlite_engine) as session:
        with pytest.raises(ValueError, match="Zero embeddings"):
            ingest(session, snapshot, embedder)


def test_chunking_preserves_content_with_overlap():
    source = "가나다라마바사아자차" * 30
    chunks = chunk_text(source)
    restored = chunks[0] + "".join(part[12:] for part in chunks[1:])
    assert restored == source
    assert all(len(part) <= 80 for part in chunks)
    with pytest.raises(ValueError):
        chunk_text(" ")
