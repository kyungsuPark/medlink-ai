from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from medlink.config import settings


@lru_cache
def engine():
    value = create_engine(
        settings().database_url,
        pool_pre_ping=True,
        isolation_level="REPEATABLE READ",
        connect_args={"connect_timeout": 5, "options": "-cstatement_timeout=10000"},
    )
    if value.dialect.name != "postgresql":
        raise ValueError("The application requires PostgreSQL with pgvector")
    return value


def get_session():
    with Session(engine()) as session:
        yield session
