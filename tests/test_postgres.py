import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from medlink.api import app, embedding_dependency
from medlink.db import get_session
from medlink.models import Chunk
from medlink.retrieval import IndexNotReady, structured_search, vector_search
from medlink.sample import AS_OF
from medlink.schemas import StructuredRequest, VectorRequest

pytestmark = pytest.mark.integration


def test_actual_postgres_crp_and_vector_storage(pg_session):
    hits = structured_search(pg_session, StructuredRequest(as_of=AS_OF))
    assert [hit.patient_id for hit in hits] == ["P001", "P006", "P003"]
    assert pg_session.scalar(select(func.vector_dims(Chunk.embedding)).limit(1)) == 384


def test_vector_patient_filter_and_deduplication(pg_session, embedder):
    request = VectorRequest(as_of=AS_OF, query="infection", patient_id="P001", top_k=50)
    hits = vector_search(pg_session, request, embedder)
    assert [hit.patient_id for hit in hits] == ["P001"]
    assert hits[0].evidence.note_id == "N001"
    assert hits[0].evidence.similarity == pytest.approx(1)


def test_hybrid_filters_before_top_k_and_returns_both_evidence_types(pg_session, embedder):
    # P002 has a perfect vector match but falling CRP; P004 is discharged;
    # P003 has a perfect FUTURE note match. They must not crowd out P006.
    request = VectorRequest(as_of=AS_OF, query="infection", top_k=2, min_similarity=0.5)
    hits = vector_search(pg_session, request, embedder, hybrid=True)
    assert [hit.patient_id for hit in hits] == ["P001", "P006"]
    assert all(hit.crp.delta_mg_l == 20 for hit in hits)
    assert all(hit.evidence.note_id in ("N001", "N006") for hit in hits)


def test_negative_and_temporal_filters(pg_session, embedder):
    for patient in ["P004", "P012"]:
        request = VectorRequest(as_of=AS_OF, query="infection", patient_id=patient)
        assert vector_search(pg_session, request, embedder) == []
    request = VectorRequest(as_of=AS_OF, query="infection", patient_id="P009")
    assert vector_search(pg_session, request, embedder)[0].evidence.note_id == "N009"
    request = VectorRequest(as_of=AS_OF, query="infection", patient_id="P003", min_similarity=0.5)
    assert vector_search(pg_session, request, embedder) == []


def test_note_kind_and_empty_hybrid(pg_session, embedder):
    request = VectorRequest(as_of=AS_OF, query="infection", note_kind="consult", top_k=50)
    assert {hit.patient_id for hit in vector_search(pg_session, request, embedder)} == {
        "P001",
        "P006",
    }
    request = VectorRequest(as_of=AS_OF, query="infection", min_delta_mg_l=1000)
    assert vector_search(pg_session, request, embedder, hybrid=True) == []


def test_mismatched_embedding_space_rejected(pg_session, embedder):
    embedder.key = "other-model"
    with pytest.raises(IndexNotReady):
        vector_search(pg_session, VectorRequest(as_of=AS_OF, query="infection"), embedder)


def test_hybrid_http_on_real_database(pg_session, embedder):
    app.dependency_overrides[get_session] = lambda: pg_session
    app.dependency_overrides[embedding_dependency] = lambda: embedder
    try:
        with TestClient(app) as client:
            response = client.post(
                "/search/hybrid",
                json={"as_of": AS_OF, "query": "infection", "top_k": 2, "min_similarity": 0.5},
            )
        assert response.status_code == 200
        assert response.json()["count"] == 2
        assert response.json()["hits"][1]["crp"]["latest"]["source_unit"] == "mg/dL"
    finally:
        app.dependency_overrides.clear()
