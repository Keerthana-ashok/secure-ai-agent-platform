"""Retriever: embed a question and return top-k chunks from the vector store."""
from typing import List, Dict

from .embeddings import EmbeddingService
from .vector_store import VectorStore


class Retriever:
    def __init__(self, vector_store: VectorStore, embedding_service: EmbeddingService):
        self.vs = vector_store
        self.emb = embedding_service

    def retrieve(self, question: str, top_k: int = 3) -> List[Dict]:
        if not question or not question.strip():
            raise ValueError("question is empty")
        q_emb = self.emb.embed_text(question)
        results = self.vs.query(q_emb, top_k=top_k)
        return results


__all__ = ["Retriever"]
