"""Helpers for provenance, trust, and conflict resolution for retrieved chunks."""
from typing import Dict, List, Any
import hashlib


def is_trusted(metadata: Dict[str, Any]) -> bool:
    st = metadata.get("source_type") if isinstance(metadata, dict) else None
    return st == "trusted"


def verify_integrity(metadata: Dict[str, Any]) -> bool:
    """Verify stored hash matches the chunk text"""
    if not metadata:
        return False
    text = metadata.get("text")
    stored = metadata.get("hash")
    if text is None or stored is None:
        return False
    h = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return h == stored


def prioritize_results(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return results ordered by trust then score.

    Trusted documents are preferred over untrusted ones even if score lower.
    """
    def key_fn(r: Dict[str, Any]):
        meta = r.get("metadata") or {}
        trusted = 1 if meta.get("source_type") == "trusted" else 0
        # higher trusted first, then higher score
        score = r.get("score") or 0
        return (trusted, score)

    return sorted(results, key=key_fn, reverse=True)
