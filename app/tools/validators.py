"""Tool argument validators and generic schema checks."""
from typing import Any, Dict, Tuple
import logging

logger = logging.getLogger("validators")


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "boolean":
        return isinstance(value, bool)
    return True


def validate_against_schema(args: Dict[str, Any], schema: Dict[str, Any]) -> Tuple[bool, str]:
    """Perform lightweight JSON-schema-like validation.

    Returns (allowed, reason).
    """
    props = schema.get("properties", {}) if isinstance(schema, dict) else {}

    # reject unexpected args
    for k in args:
        if k not in props:
            return False, f"unexpected argument: {k}"

    # types and basic constraints
    for name, spec in props.items():
        if name not in args:
            continue
        val = args[name]
        expected_type = spec.get("type")
        if expected_type and not _type_matches(val, expected_type):
            return False, f"invalid type for {name}: expected {expected_type}"

        if expected_type == "string":
            maxlen = spec.get("maxLength")
            if maxlen and isinstance(val, str) and len(val) > maxlen:
                return False, f"{name} too long"

        if expected_type in ("integer", "number"):
            minimum = spec.get("minimum")
            maximum = spec.get("maximum")
            if minimum is not None and val < minimum:
                return False, f"{name} below minimum {minimum}"
            if maximum is not None and val > maximum:
                return False, f"{name} above maximum {maximum}"

    return True, "ok"


# Per-tool validators
def validate_search_security_docs(args: Dict[str, Any], user: Dict[str, Any]) -> Tuple[bool, str]:
    # schema: query (string), top_k (integer, 1-10)
    schema = {
        "properties": {
            "query": {"type": "string", "maxLength": 2000},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 10},
        }
    }
    return validate_against_schema(args, schema)


def validate_delete_document(args: Dict[str, Any], user: Dict[str, Any]) -> Tuple[bool, str]:
    # Ensure document_id is a string and the user is owner or has explicit delete permission
    if "document_id" not in args:
        return False, "missing document_id"
    if not isinstance(args["document_id"], str):
        return False, "invalid type for document_id"
    # ownership/resource checks will be performed elsewhere (Authorizer or higher-level),
    # here we just validate type and length
    if len(args["document_id"]) > 200:
        return False, "document_id too long"
    return True, "ok"


TOOL_VALIDATORS = {
    "search_security_docs": validate_search_security_docs,
    "delete_document": validate_delete_document,
}


def validate_tool_args(tool_name: str, args: Dict[str, Any], user: Dict[str, Any]) -> Tuple[bool, str]:
    fn = TOOL_VALIDATORS.get(tool_name)
    if fn:
        try:
            return fn(args, user)
        except Exception as e:
            logger.exception("validator error for %s", tool_name)
            return False, f"validator error: {e}"

    # default: accept (no validator)
    return True, "ok"
