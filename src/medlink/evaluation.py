import json
from pathlib import Path
from statistics import mean
from time import perf_counter

from sqlalchemy.orm import Session

from medlink.embeddings import Embedder
from medlink.retrieval import structured_search, vector_search
from medlink.schemas import StructuredRequest, VectorRequest


def metrics(actual: list[str], expected: list[str], k: int) -> dict:
    retrieved = actual[:k]
    relevant = set(expected)
    matched = len(set(retrieved) & relevant)
    reciprocal_rank = next(
        (1 / i for i, value in enumerate(retrieved, 1) if value in relevant), 0.0
    )
    return {
        "precision_at_k": matched / k,
        "recall_at_k": matched / len(relevant) if relevant else float(not retrieved),
        "reciprocal_rank": reciprocal_rank,
        "exact_set": set(actual) == relevant,
    }


def evaluate(session: Session, embedder: Embedder, path: Path) -> dict:
    cases = json.loads(path.read_text(encoding="utf-8"))
    results = []
    for case in cases:
        start = perf_counter()
        mode = case["mode"]
        if mode == "structured":
            hits = structured_search(session, StructuredRequest(**case["request"]))
        else:
            hits = vector_search(
                session, VectorRequest(**case["request"]), embedder, hybrid=mode == "hybrid"
            )
        actual = [hit.patient_id for hit in hits]
        k = case["request"].get("top_k", max(1, len(case["expected"])))
        results.append(
            {
                "id": case["id"],
                "mode": mode,
                "actual": actual,
                "expected": case["expected"],
                "k": k,
                "elapsed_ms": round((perf_counter() - start) * 1000, 2),
                **metrics(actual, case["expected"], k),
            }
        )
    semantic = [r for r in results if r["mode"] != "structured"]
    return {
        "embedding_model": embedder.key,
        "cases": results,
        "semantic_macro_recall_at_k": mean(r["recall_at_k"] for r in semantic),
        "semantic_mrr": mean(r["reciprocal_rank"] for r in semantic),
        "note": "Hand-written synthetic relevance labels; not clinical validation. "
        "Similarity ranks mentions and may retrieve negated statements.",
    }
