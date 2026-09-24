"""Simulated sensitive tools for testing authorization (no real destructive ops)."""
from typing import Dict, Any

# Simple in-memory 'documents' store for tests/demos
_DOCUMENT_STORE: Dict[str, Dict[str, Any]] = {
    "doc1": {"id": "doc1", "content": "important auth info", "owner": "alice"},
    "doc2": {"id": "doc2", "content": "old log", "owner": "bob"},
}


def delete_document(document_id: str) -> Dict[str, Any]:
    """Simulate deletion of a document. Returns a structured result.

    This function MUST NOT perform any real destructive operation in tests.
    """
    if document_id not in _DOCUMENT_STORE:
        return {"error": "not_found", "document_id": document_id}

    # simulate deletion
    _DOCUMENT_STORE.pop(document_id, None)
    return {"deleted": document_id}


def get_document_store_snapshot() -> Dict[str, Dict[str, Any]]:
    return dict(_DOCUMENT_STORE)
