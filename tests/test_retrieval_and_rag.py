import pytest

from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import VectorStore, stable_chunk_id
from app.rag.retriever import Retriever
from app.rag.rag_service import RAGService
from app.llm.client import LLMClient


class DummyLLM(LLMClient):
    async def send_prompt(self, messages, **kwargs):
        # return a canned response that echoes user content
        for m in reversed(messages):
            if m.get("role") == "user":
                return "REPLY: " + m.get("content", "")
        return "REPLY"


def test_retrieval_returns_relevant_chunks():
    emb = EmbeddingService()
    vs = VectorStore(collection_name="test_retrieval")

    # insert two chunks
    t1 = "Passwords should never be stored in plaintext."
    id1 = stable_chunk_id("authentication.md", t1)
    e1 = emb.embed_text(t1)
    vs.upsert([(id1, e1, {"source": "authentication.md", "text": t1})])

    t2 = "Kubernetes pods should have resource limits."
    id2 = stable_chunk_id("k8s.md", t2)
    e2 = emb.embed_text(t2)
    vs.upsert([(id2, e2, {"source": "kubernetes-security.md", "text": t2})])

    retriever = Retriever(vs, emb)
    results = retriever.retrieve("What should I do with passwords?", top_k=1)
    assert results
    # top result should mention authentication.md
    assert results[0]["metadata"]["source"] in ("authentication.md", "auth.md")


@pytest.mark.asyncio
async def test_rag_service_calls_llm_and_returns_sources():
    emb = EmbeddingService()
    vs = VectorStore(collection_name="test_rag")

    t1 = "Passwords should never be stored in plaintext."
    id1 = stable_chunk_id("authentication.md", t1)
    e1 = emb.embed_text(t1)
    vs.upsert([(id1, e1, {"source": "authentication.md", "text": t1})])

    llm = DummyLLM()
    rag = RAGService(vector_store=vs, llm_client=llm)
    res = await rag.ask("How should passwords be protected?", top_k=1)
    assert "answer" in res
    assert res["sources"][0]["source"] == "authentication.md"
