import pytest

from medlink.retrieval import structured_search
from medlink.sample import AS_OF
from medlink.schemas import StructuredRequest


def test_rising_crp_excludes_all_temporal_and_status_negatives(seeded_session):
    hits = structured_search(seeded_session, StructuredRequest(as_of=AS_OF))
    assert [hit.patient_id for hit in hits] == ["P001", "P006", "P003"]
    assert [hit.delta_mg_l for hit in hits] == [20, 20, 10]
    assert hits[1].latest.source_unit == "mg/dL"


@pytest.mark.parametrize(
    "patient_id", ["P002", "P004", "P005", "P007", "P008", "P009", "P010", "P011", "P012"]
)
def test_exclusion_cases(seeded_session, patient_id):
    assert (
        structured_search(seeded_session, StructuredRequest(as_of=AS_OF, patient_id=patient_id))
        == []
    )


def test_both_results_must_be_in_lookback(seeded_session):
    assert (
        structured_search(seeded_session, StructuredRequest(as_of=AS_OF, lookback_hours=12)) == []
    )


def test_delta_is_strictly_greater_than_threshold(seeded_session):
    hits = structured_search(seeded_session, StructuredRequest(as_of=AS_OF, min_delta_mg_l=10))
    assert {hit.patient_id for hit in hits} == {"P001", "P006"}


def test_discharge_boundary_is_exclusive(seeded_session):
    before = StructuredRequest(as_of="2026-09-28T09:59:59Z", patient_id="P004")
    boundary = StructuredRequest(as_of="2026-09-28T10:00:00Z", patient_id="P004")
    assert len(structured_search(seeded_session, before)) == 1
    assert structured_search(seeded_session, boundary) == []


def test_korean_timezone_is_same_instant(seeded_session):
    request = StructuredRequest(as_of="2026-09-28T21:00:00+09:00")
    assert [hit.patient_id for hit in structured_search(seeded_session, request)] == [
        "P001",
        "P006",
        "P003",
    ]
