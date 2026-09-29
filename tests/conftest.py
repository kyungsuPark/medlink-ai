import os
import uuid

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from medlink.config import DIMENSIONS
from medlink.ingest import LegacySnapshot, ingest
from medlink.models import Base
from medlink.sample import synthetic_export


class TestEmbedder:
    """Test-only vectors. Does NOT measure semantic model quality."""

    key = "test-only-fixed-v1"
    __test__ = False

    def encode(self, texts):
        result = []
        for value in texts:
            # Fixed, deliberately high-scoring negatives expose filter/order mistakes.
            infection = any(word in value for word in ("감염", "폐렴", "Infection", "infection"))
            vector = [0.0] * DIMENSIONS
            vector[0 if infection else 1] = 1.0
            result.append(vector)
        return result


@pytest.fixture
def embedder():
    return TestEmbedder()


@pytest.fixture
def snapshot():
    return LegacySnapshot.model_validate(synthetic_export())


@pytest.fixture
def sqlite_engine():
    engine = create_engine(
        "sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def enforce_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()


@pytest.fixture
def seeded_session(sqlite_engine, snapshot, embedder):
    with Session(sqlite_engine) as session:
        ingest(session, snapshot, embedder)
        yield session


@pytest.fixture
def pg_engine():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to run real PostgreSQL/pgvector integration tests")
    # Isolate in a uniquely named schema; never drop public or any existing user schema.
    admin = create_engine(url)
    schema = "test_" + uuid.uuid4().hex
    with admin.begin() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema},public"})
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()


@pytest.fixture
def pg_session(pg_engine, snapshot, embedder):
    with Session(pg_engine) as session:
        ingest(session, snapshot, embedder)
        yield session
