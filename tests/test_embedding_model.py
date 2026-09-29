import os

import numpy as np
import pytest

from medlink.embeddings import get_embedder

pytestmark = pytest.mark.semantic


def test_real_multilingual_embedding_smoke():
    if os.getenv("RUN_SEMANTIC_TESTS") != "1":
        pytest.skip("Set RUN_SEMANTIC_TESTS=1 to download/test the real model")
    embedder = get_embedder()
    vectors = np.array(
        embedder.encode(
            [
                "무릎 수술 후 재활 및 보행 훈련",
                "Rehabilitation and walking exercise after knee surgery",
                "항생제 투여 후 감염과 발열을 관찰함",
            ]
        )
    )
    assert vectors.shape == (3, 384)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1, atol=1e-5)
    assert vectors[0] @ vectors[1] > vectors[0] @ vectors[2]
