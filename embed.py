"""Local embeddings: turn text into numbers that represent its meaning.
Runs on the laptop, so it uses no API tokens."""
import os
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import numpy as np  # noqa: E402
from fastembed import TextEmbedding  # noqa: E402

_model = None


def model():
    global _model
    if _model is None:
        _model = TextEmbedding("BAAI/bge-small-en-v1.5",
                               cache_dir=str(Path(__file__).parent / ".models"))
    return _model


def _unit(vectors):
    v = np.array(list(vectors), dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def embed(texts):
    """One vector per text. `a @ b` is their similarity (1.0 = same meaning)."""
    return _unit(model().embed(list(texts)))


def similarity_to(query, passages):
    """How close each passage is to the query."""
    q = _unit(model().query_embed([query]))[0]
    return _unit(model().passage_embed(list(passages))) @ q
