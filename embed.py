"""Local embeddings: turn text into numbers that represent its meaning.
Runs on the machine itself, so it uses no API tokens.

Memory matters here: embedding 75 long search summaries in one go used 1.3 GB, which is more
than a small hosted server has. So texts are shortened, sent in small batches, and only one
thread embeds at a time.
"""
import os
import threading
from pathlib import Path

os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")

import numpy as np  # noqa: E402
from fastembed import TextEmbedding  # noqa: E402

MAX_CHARS = 600   # enough to tell what a text is about
BATCH = 8         # texts embedded at once

_model = None
_lock = threading.Lock()


def model():
    global _model
    if _model is None:
        _model = TextEmbedding("BAAI/bge-small-en-v1.5",
                               cache_dir=str(Path(__file__).parent / ".models"), threads=2)
    return _model


def _unit(vectors):
    v = np.array(list(vectors), dtype=np.float32)
    return v / np.linalg.norm(v, axis=1, keepdims=True)


def embed(texts):
    """One vector per text. `a @ b` is their similarity (1.0 = same meaning)."""
    texts = [t[:MAX_CHARS] for t in texts]
    with _lock:
        return _unit(model().embed(texts, batch_size=BATCH))


def similarity_to(query, passages):
    """How close each passage is to the query."""
    passages = [p[:MAX_CHARS] for p in passages]
    with _lock:
        q = _unit(model().query_embed([query[:MAX_CHARS]]))[0]
        return _unit(model().passage_embed(passages, batch_size=BATCH)) @ q
