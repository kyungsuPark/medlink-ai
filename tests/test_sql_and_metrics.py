from sqlalchemy.dialects import postgresql

from medlink.evaluation import metrics
from medlink.retrieval import vector_statement
from medlink.sample import AS_OF
from medlink.schemas import VectorRequest


def test_postgres_query_is_parameterized_and_filters_before_limit(embedder):
    request = VectorRequest(as_of=AS_OF, query="infection", top_k=2, note_kind="consult")
    compiled = vector_statement(
        request, embedder.encode(["infection"])[0], embedder.key, ["A001", "A006"]
    ).compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "<=>" in sql
    assert "row_number() OVER (PARTITION BY encounters.id" in sql
    assert sql.index("encounters.id IN") < sql.index("LIMIT")
    assert "A001" not in sql


def test_evaluation_metrics():
    result = metrics(["P003", "P001", "P004"], ["P001", "P006"], 3)
    assert result["precision_at_k"] == 1 / 3
    assert result["recall_at_k"] == 0.5
    assert result["reciprocal_rank"] == 0.5
    assert result["exact_set"] is False
    assert metrics([], [], 1)["exact_set"] is True
