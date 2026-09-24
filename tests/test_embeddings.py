import pytest

from app.rag.embeddings import EmbeddingService, EmbeddingError


def test_embed_text_creates_vector():
    s = EmbeddingService()
    v = s.embed_text("Passwords should never be stored in plaintext.")
    assert isinstance(v, list)
    assert len(v) == 32


def test_embed_many_texts():
    s = EmbeddingService()
    texts = ["a", "b", "c"]
    vs = s.embed_texts(texts)
    assert len(vs) == 3


def test_empty_text_rejected():
    s = EmbeddingService()
    with pytest.raises(EmbeddingError):
        s.embed_text("")
