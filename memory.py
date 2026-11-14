"""Evidence memory: a local vector database (Qdrant) of every passage the tool has read.

When a new assumption is tested, passages from earlier tests that are close in meaning are
recalled and screened alongside the fresh search results. A passage that is recalled and chosen
is reused as it is, so the page is never fetched or read a second time.
"""
import atexit
import threading
import uuid
from datetime import date
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from embed import embed

FOLDER = Path(__file__).parent / "evidence_db"
COLLECTION = "evidence"
MIN_SIMILARITY = 0.60   # recalled passages are screened by Haiku afterwards, so this can be loose
_lock = threading.Lock()  # one writer or reader at a time: the local database is a single file
_client = None


def _db():
    global _client
    if _client is None:
        _client = QdrantClient(path=str(FOLDER))
        if not _client.collection_exists(COLLECTION):
            _client.create_collection(
                COLLECTION, vectors_config=VectorParams(size=384, distance=Distance.COSINE))
    return _client


@atexit.register
def _close():
    if _client is not None:
        _client.close()


def remember(claim, assumption, items):
    """Store the passages read for one assumption. items: evidence dicts with url, title, text..."""
    items = [e for e in items if not e.get("memory")]  # don't re-store what was recalled
    if not items:
        return 0
    vectors = embed(e["text"][:2000] for e in items)
    points = [PointStruct(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, e["url"] + "|" + assumption)),
        vector=v.tolist(),
        payload={"url": e["url"], "title": e["title"], "source_type": e["source_type"],
                 "text": e["text"], "claim": claim, "assumption": assumption,
                 "date": date.today().isoformat()})
        for e, v in zip(items, vectors)]
    with _lock:
        _db().upsert(COLLECTION, points=points)
    return len(points)


def recall(assumption, limit=4):
    """Passages from earlier tests that are close in meaning to this assumption, best first.
    One per page. Returns payload dicts with an added 'similarity'."""
    vector = embed([assumption])[0].tolist()
    with _lock:
        hits = _db().query_points(COLLECTION, query=vector, limit=limit * 3, with_payload=True,
                                  score_threshold=MIN_SIMILARITY).points
    seen, out = set(), []
    for h in hits:
        if h.payload["url"] not in seen:
            seen.add(h.payload["url"])
            out.append({**h.payload, "similarity": round(h.score, 2)})
    return out[:limit]


def size():
    with _lock:
        return _db().count(COLLECTION).count
