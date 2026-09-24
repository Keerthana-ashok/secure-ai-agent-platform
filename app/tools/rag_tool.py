"""RAG tool wrapper exposing the Retriever as a callable tool.

Provides a factory `make_search_tool(retriever)` which returns a function
`search_security_docs(query: str, top_k: int=3)` suitable for registration
in the `ToolRegistry`.
"""
from typing import Any, Dict, List, Callable


def make_search_tool(retriever) -> Callable:
    """Return a callable that wraps `retriever.retrieve(question, top_k)`.

    The returned function accepts keyword args `query` and optional `top_k`.
    """

    def search_security_docs(query: str, top_k: int = 3) -> Dict[str, Any]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        if top_k is None:
            top_k = 3
        try:
            top_k = int(top_k)
        except Exception:
            raise ValueError("top_k must be an integer")
        if top_k <= 0:
            raise ValueError("top_k must be > 0")

        # Call the retriever (may raise) and return structured results
        results = retriever.retrieve(query, top_k=top_k)
        return {"query": query, "top_k": top_k, "results": results}

    return search_security_docs


__all__ = ["make_search_tool"]
