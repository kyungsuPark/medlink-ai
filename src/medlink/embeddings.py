from functools import lru_cache
from typing import Protocol

import numpy as np

from medlink.config import DIMENSIONS, settings


class Embedder(Protocol):
    key: str

    def encode(self, texts: list[str]) -> list[list[float]]: ...


def validate_vectors(vectors: list[list[float]], count: int) -> None:
    arr = np.asarray(vectors, dtype=float)
    if arr.shape != (count, DIMENSIONS) or not np.isfinite(arr).all():
        raise ValueError("Embedding shape or values are invalid")
    if (np.linalg.norm(arr, axis=1) < 1e-8).any():
        raise ValueError("Zero embeddings are not searchable")


class TransformerEmbedder:
    def __init__(self):
        from sentence_transformers import SentenceTransformer

        config = settings()
        self.key = config.embedding_key
        self.model = SentenceTransformer(
            config.embedding_model, revision=config.embedding_revision, device="cpu"
        )
        if self.model.get_sentence_embedding_dimension() != DIMENSIONS:
            raise ValueError(f"Model must produce {DIMENSIONS}-dimensional vectors")

    def encode(self, texts: list[str]) -> list[list[float]]:
        lengths = [
            len(ids)
            for ids in self.model.tokenizer(texts, truncation=False, padding=False)["input_ids"]
        ]
        if any(length > self.model.max_seq_length for length in lengths):
            raise ValueError("Text exceeds the model token limit; use a shorter query/chunk")
        vectors = self.model.encode(
            texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32
        ).tolist()
        validate_vectors(vectors, len(texts))
        return vectors


@lru_cache
def get_embedder() -> Embedder:
    return TransformerEmbedder()
