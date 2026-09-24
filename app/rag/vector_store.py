"""Vector store abstraction using ChromaDB with an in-memory fallback.

The wrapper exposes a small API used by the ingestion and retrieval
components. Each chunk is stored with a stable id computed from source
and text to avoid duplicates on re-ingestion.
"""
from __future__ import annotations

import hashlib
from typing import Dict, Iterable, List, Optional, Tuple

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
except Exception:
    chromadb = None


def stable_chunk_id(source: str, text: str) -> str:
    h = hashlib.sha256(f"{source}:{text}".encode("utf-8")).hexdigest()
    return h


class VectorStore:
    """Small abstraction over ChromaDB (or in-memory fallback)."""

    def __init__(self, collection_name: str = "secure_ai_chunks"):
        self.collection_name = collection_name
        if chromadb is not None:
            # Create an in-memory chroma client
            self.client = chromadb.Client()
            # Create or get collection
            try:
                self.col = self.client.create_collection(name=collection_name)
            except Exception:
                self.col = self.client.get_collection(name=collection_name)
            self._use_chroma = True
        else:
            # Simple in-memory store: id -> (embedding, metadata)
            self._store: Dict[str, Tuple[List[float], Dict]] = {}
            self._use_chroma = False

    def upsert(self, items: Iterable[Tuple[str, List[float], Dict]]) -> None:
        """Upsert items. Each item is (id, embedding, metadata)."""
        if self._use_chroma:
            ids = []
            embeddings = []
            metadatas = []
            documents = []
            for id_, emb, meta in items:
                ids.append(id_)
                embeddings.append(emb)
                metadatas.append(meta)
                documents.append(meta.get("text", ""))
            self.col.upsert(ids=ids, embeddings=embeddings, metadatas=metadatas, documents=documents)
        else:
            for id_, emb, meta in items:
                # Overwrite existing entry (idempotent)
                self._store[id_] = (emb, meta.copy())

    def query(self, embedding: List[float], top_k: int = 3) -> List[Dict]:
        """Return top_k nearest items as list of metadata dicts with score."""
        if self._use_chroma:
            res = self.col.query(query_embeddings=[embedding], n_results=top_k)
            results = []
            # chroma returns dicts with 'ids','metadatas','distances','documents'
            for i in range(len(res["ids"][0])):
                results.append(
                    {
                        "id": res["ids"][0][i],
                        "metadata": res["metadatas"][0][i],
                        "document": res["documents"][0][i],
                        "score": res.get("distances", [[None]])[0][i] if res.get("distances") else None,
                    }
                )
            return results
        else:
            # Simple cosine-like similarity using dot product (not normalized)
            scores = []
            for id_, (emb, meta) in self._store.items():
                # compute dot product
                s = sum(a * b for a, b in zip(embedding, emb))
                scores.append((s, id_, emb, meta))
            scores.sort(reverse=True, key=lambda x: x[0])
            results = []
            for s, id_, emb, meta in scores[:top_k]:
                results.append({"id": id_, "metadata": meta, "document": meta.get("text"), "score": s})
            return results

    def exists(self, id_: str) -> bool:
        if self._use_chroma:
            # chroma has get with id
            try:
                res = self.col.get(ids=[id_])
                return len(res.get("ids", [])) > 0
            except Exception:
                return False
        else:
            return id_ in self._store
