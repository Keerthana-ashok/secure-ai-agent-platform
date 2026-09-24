import os
import tempfile
import shutil
import time
import json

from app.rag.vector_store import VectorStore
from scripts.ingest import ingest_docs
from app.rag.retriever import Retriever
from app.rag.embeddings import EmbeddingService
from app.rag.provenance import prioritize_results, is_trusted, verify_integrity


def write_docs(folder: str, docs: dict):
    os.makedirs(folder, exist_ok=True)
    for name, text in docs.items():
        path = os.path.join(folder, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def test_rag_poisoning_and_provenance():
    tmp = tempfile.mkdtemp(prefix="rag_test_")
    try:
        # Step 1: create trusted authoritative docs
        docs = {
            "trusted_password_policy.md": "Password minimum length: 14 characters\nMFA: required for privileged accounts\nSession timeout: 30 minutes\n",
            "trusted_authentication_policy.md": "Authentication: MFA required for admin roles\n",
        }
        write_docs(tmp, docs)

        # ingest
        vs = VectorStore(collection_name="test_poisoning")
        ingest_docs(folder=tmp, vs=vs)

        # baseline retrieval
        emb = EmbeddingService()
        retriever = Retriever(vs, emb)
        res = retriever.retrieve("minimum password length", top_k=3)
        assert len(res) > 0
        # ensure at least one trusted doc is in results
        assert any(is_trusted(r.get("metadata", {})) for r in res)

        # Step 3: simulate poisoning by adding an untrusted doc with conflicting claim
        poisoned = {
            "user_poisoned_password_policy.md": "Password minimum length: 4 characters\nMFA: optional\nSession timeout: 5 minutes\n",
        }
        write_docs(tmp, poisoned)
        # re-ingest (idempotent; new doc will be added)
        ingest_docs(folder=tmp, vs=vs)

        # retrieve again and inspect which docs are returned
        res2 = retriever.retrieve("minimum password length", top_k=5)
        assert len(res2) > 0

        # Check that poisoned doc is present among results
        poisoned_present = any((r.get("metadata", {}).get("source") or "").startswith("user_") for r in res2)
        assert poisoned_present

        # Now apply provenance prioritization: trusted docs should be preferred
        prio = prioritize_results(res2)
        top = prio[0]
        assert is_trusted(top.get("metadata", {})), "Trusted document should take precedence"

        # Step: integrity verification - tamper with an ingested chunk's text and ensure hash mismatch
        # For in-memory VS we can inspect store internals (not ideal but fine for test)
        # Find a trusted result and tamper its metadata text
        trusted_chunk = next((r for r in res2 if is_trusted(r.get("metadata", {}))), None)
        assert trusted_chunk is not None
        meta = trusted_chunk.get("metadata")
        # tamper: change text
        original_text = meta.get("text")
        meta["text"] = original_text + "\nmalicious appendix"
        # verify_integrity should now fail
        assert not verify_integrity(meta)

    finally:
        shutil.rmtree(tmp)
