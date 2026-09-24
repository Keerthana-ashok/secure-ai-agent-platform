"""Embedding service and provider abstraction.

This module provides a simple, deterministic embedding provider for
learning purposes and a small service wrapper used by the rest of the
RAG pipeline.
"""
from __future__ import annotations

import hashlib
from typing import List, Sequence

from ..config import get_settings


class EmbeddingError(Exception):
    pass


class EmbeddingProvider:
    """Abstract embedding provider."""

    def embed(self, text: str) -> List[float]:
        raise NotImplementedError()

    def embed_many(self, texts: Sequence[str]) -> List[List[float]]:
        return [self.embed(t) for t in texts]


class SimpleEmbeddingProvider(EmbeddingProvider):
    """Deterministic, simple embeddings based on SHA256.

    This is NOT a semantic embedding and only exists for learning and tests.
    It is deterministic, does not require API keys, and produces a fixed
    dimensional vector of floats.
    """

    def __init__(self, dim: int = 32):
        self.dim = dim

    def embed(self, text: str) -> List[float]:
        if not text or not text.strip():
            raise EmbeddingError("Empty text cannot be embedded")

        # Create a SHA256 digest and expand it to the requested dimension
        h = hashlib.sha256(text.encode("utf-8")).digest()
        # Repeat digest to have enough bytes
        needed = self.dim * 4
        buf = (h * ((needed // len(h)) + 1))[:needed]
        # Convert every 4 bytes to a signed int and normalize
        vals = []
        for i in range(0, needed, 4):
            chunk = buf[i : i + 4]
            ival = int.from_bytes(chunk, "big", signed=False)
            # Map into [-1, 1]
            vals.append((ival / 2 ** 32) * 2 - 1)
        return vals


class EmbeddingService:
    """Wrapper that exposes embedding functions using a configurable provider.

    For this learning project the provider defaults to `SimpleEmbeddingProvider`.
    In future this can be extended to call external embedding APIs.
    """

    def __init__(self):
        settings = get_settings()
        provider_name = getattr(settings, "embedding_provider", "simple")
        dim = getattr(settings, "embedding_dim", 32)
        if provider_name == "simple":
            self.provider = SimpleEmbeddingProvider(dim=dim)
        else:
            # Placeholder for external providers (not implemented)
            raise NotImplementedError(f"Embedding provider {provider_name} not implemented")

    def embed_text(self, text: str) -> List[float]:
        return self.provider.embed(text)

    def embed_texts(self, texts: Sequence[str]) -> List[List[float]]:
        return self.provider.embed_many(texts)


__all__ = ["EmbeddingService", "EmbeddingError"]
