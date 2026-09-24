"""RAG service: retrieve context and ask the LLM using the existing client.

This module avoids printing document contents to stdout; logs are limited to counts
and safe metadata to avoid leaking confidential text into logs.
"""
from typing import List, Dict
import logging

from ..llm.client import LLMClient, LLMError
from .embeddings import EmbeddingService
from .vector_store import VectorStore
from .retriever import Retriever

logger = logging.getLogger("rag")


INSTRUCTION = (
    "Answer the question using the provided context. "
    "If the context does not contain enough information to answer the question, "
    "say that the information is not available in the provided knowledge base. "
    "Do not invent facts."
)


class RAGService:
    def __init__(self, vector_store: VectorStore, llm_client: LLMClient):
        self.vs = vector_store
        self.llm = llm_client
        self.emb = EmbeddingService()
        self.retriever = Retriever(self.vs, self.emb)

    def _build_context(self, retrieved: List[Dict]) -> str:
        parts = []
        for r in retrieved:
            meta = r.get("metadata", {})
            source = meta.get("source") or meta.get("file") or "unknown"
            chunk_id = r.get("id")
            text = meta.get("text") or r.get("document") or ""
            parts.append(f"Source: {source}  Chunk: {chunk_id}\n{text}")
        return "\n\n".join(parts)

    async def ask(self, question: str, top_k: int = 3) -> Dict:
        logger.info("Retrieving top %s chunks for question (redacted): %s", top_k, "<redacted>")
        retrieved = self.retriever.retrieve(question, top_k=top_k)
        logger.info("Retrieved %d chunks", len(retrieved))

        # Log safe metadata about sources (do not log document text/snippets)
        safe_sources = [
            {"source": (r.get("metadata") or {}).get("source"), "chunk_id": r.get("id")} for r in retrieved
        ]
        logger.debug("Retrieved sources: %s", safe_sources)

        context = self._build_context(retrieved)

        # Build a concise user prompt: context + question. Instruction is
        # provided as the system message only. We do not log the prompt contents
        # because it may include retrieved text.
        user_prompt = f"Context:\n{context}\n\nQuestion: {question}\nAnswer:"

        try:
            messages = [
                {"role": "system", "content": INSTRUCTION},
                {"role": "user", "content": user_prompt},
            ]
            answer = await self.llm.send_prompt(messages)
        except LLMError:
            # LLM errors are propagated to the caller for handling
            raise

        # Build sources list for return
        sources = safe_sources

        return {"answer": answer, "sources": sources, "retrieved": retrieved}


__all__ = ["RAGService"]
