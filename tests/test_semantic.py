import os

import pytest
from sqlalchemy.orm import Session

from medlink.embeddings import get_embedder
from medlink.evaluation import evaluate
from medlink.ingest import ingest

pytestmark = [pytest.mark.integration, pytest.mark.semantic]


def test_real_model_golden_cases(pg_engine, snapshot, tmp_path):
    if os.getenv("RUN_SEMANTIC_TESTS") != "1":
        pytest.skip("Set RUN_SEMANTIC_TESTS=1 to download the real embedding model")
    from pathlib import Path

    embedder = get_embedder()
    with Session(pg_engine) as session:
        ingest(session, snapshot, embedder)
        report = evaluate(session, embedder, Path("data/evaluation.json"))
    assert all(case["exact_set"] for case in report["cases"] if case["mode"] == "structured")
    # Initial development targets, not a claim that they have already been achieved.
    assert report["semantic_macro_recall_at_k"] >= 0.7
    assert report["semantic_mrr"] >= 0.8
