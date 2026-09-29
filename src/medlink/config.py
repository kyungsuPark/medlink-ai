from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

DIMENSIONS = 384


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://medlink:medlink_local_only@localhost:5432/medlink"
    embedding_model: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    embedding_revision: str = "e8f8c211226b894fcb81acc59f3b34ba3efd5f42"

    @property
    def embedding_key(self) -> str:
        return f"{self.embedding_model}@{self.embedding_revision}"


@lru_cache
def settings() -> Settings:
    return Settings()
