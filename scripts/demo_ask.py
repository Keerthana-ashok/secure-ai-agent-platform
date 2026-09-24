"""Demo: ingest docs and ask a question using a dummy LLM.

This demo uses the local embedding service and vector store and a
dummy LLM that echoes the user prompt to demonstrate the RAG flow
without requiring external API keys.
"""
import asyncio
import sys
from pathlib import Path

# Ensure repository root is on sys.path so local imports work when running
# this script directly: `python scripts/demo_ask.py`
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.ingest import ingest_docs
from app.rag.embeddings import EmbeddingService
from app.rag.vector_store import VectorStore
from app.rag.rag_service import RAGService


class DummyLLM:
    async def send_prompt(self, messages, **kwargs):
        # Return a simple answer indicating which user message was received.
        # Find the user message content.
        user_content = None
        for m in reversed(messages):
            if m.get("role") == "user":
                user_content = m.get("content")
                break
        return "(dummy answer) Received user prompt:\n" + (user_content or "")


async def main():
    print("Ingesting documents into vector store...")
    vs = ingest_docs()
    print("Ingestion complete.")

    llm = DummyLLM()
    rag = RAGService(vector_store=vs, llm_client=llm)

    # You can change this question or accept input from the user.
    question = "How should passwords be protected?"
    print(f"\nUser question: {question}\n")
    print("Running retrieval and asking the LLM...\n")
    res = await rag.ask(question, top_k=3)

    print("\nFinal answer:\n")
    print(res.get("answer"))

    print("\nSources returned:")
    for s in res.get("sources", []):
        print(s)


if __name__ == "__main__":
    asyncio.run(main())
