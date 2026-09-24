"""Ingest docs -> chunks -> embeddings -> vector store.

This is a simple, idempotent ingestion script. Running it multiple times
will not create duplicate records thanks to stable chunk ids.
"""
import asyncio
from typing import Optional
from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import VectorStore, stable_chunk_id
from scripts.read_and_chunk import process_docs
import hashlib
import time


def ingest_docs(folder: str = "docs", vs: Optional[VectorStore] = None) -> VectorStore:
    """Process docs and upsert chunks into `vs`.

    If `vs` is None a new `VectorStore` is created and returned. Returns
    the VectorStore instance used so callers can reuse it.
    """
    print(f"Reading and chunking documents from '{folder}'...")
    chunks = process_docs(folder, max_chars=500)
    print(f"Found {len(chunks)} chunks after splitting.")
    emb_service = EmbeddingService()
    if vs is None:
        vs = VectorStore()

    to_upsert = []
    texts = [c for (_, c) in chunks]
    # Compute embeddings in batch
    print("Computing embeddings for chunks...")
    embeddings = emb_service.embed_texts(texts)
    print(f"Computed embeddings for {len(embeddings)} chunks.")

    for idx, ((meta, text), emb) in enumerate(zip(chunks, embeddings), start=1):
        source = meta.get("source")
        chunk_id = stable_chunk_id(source, text)
        # provenance metadata: infer source_type from filename prefix (trusted_ vs user_)
        source_type = "unknown"
        owner = None
        if isinstance(source, str):
            if source.startswith("trusted_") or source.startswith("official_"):
                source_type = "trusted"
            elif source.startswith("user_") or source.startswith("uploaded_"):
                source_type = "untrusted"
            else:
                source_type = "unknown"
            # owner inferred from filename (before first underscore) when present
            if "_" in source:
                owner = source.split("_")[0]

        doc_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        meta_out = {
            "source": source,
            "text": text,
            "doc_id": source,
            "owner": owner,
            "source_type": source_type,
            "version": 1,
            "ingested_at": time.time(),
            "hash": doc_hash,
        }
        to_upsert.append((chunk_id, emb, meta_out))
        print(f"Chunk {idx}: source={source}, len={len(text)} chars, id={chunk_id}")

    print(f"Upserting {len(to_upsert)} items into the vector store...")
    vs.upsert(to_upsert)
    print("Upsert complete.")
    return vs


if __name__ == "__main__":
    ingest_docs()
