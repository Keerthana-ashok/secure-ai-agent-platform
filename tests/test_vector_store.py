import pytest

from app.rag.vector_store import VectorStore, stable_chunk_id


def test_upsert_and_query_in_memory():
    vs = VectorStore(collection_name="test_chunks")
    # Force in-memory if chroma not installed
    id1 = stable_chunk_id("auth.md", "Passwords should never be stored in plaintext.")
    emb1 = [0.1] * 32
    meta1 = {"source": "auth.md", "text": "Passwords should never be stored in plaintext."}

    vs.upsert([(id1, emb1, meta1)])
    assert vs.exists(id1)

    res = vs.query(emb1, top_k=1)
    assert len(res) == 1
    assert res[0]["id"] == id1


def test_idempotent_upsert():
    vs = VectorStore(collection_name="test_chunks2")
    id1 = stable_chunk_id("a.md", "hello")
    emb = [0.0] * 32
    meta = {"source": "a.md", "text": "hello"}
    vs.upsert([(id1, emb, meta)])
    vs.upsert([(id1, emb, meta)])
    assert vs.exists(id1)
