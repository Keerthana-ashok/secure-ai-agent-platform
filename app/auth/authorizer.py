import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("authorizer")


class Authorizer:
    """Simple application-level authorizer and audit logger for tools.

    - Maps tools to required permissions.
    - Decides whether a given user is allowed to execute a tool.
    - Records audit entries for sensitive tool attempts.
    """

    DEFAULT_TOOL_PERMISSIONS = {
        "search_security_docs": "DOCUMENT_READ",
        "delete_document": "DOCUMENT_DELETE",
    }

    def __init__(self, tool_permissions: Optional[Dict[str, str]] = None):
        self.tool_permissions = dict(self.DEFAULT_TOOL_PERMISSIONS)
        if tool_permissions:
            self.tool_permissions.update(tool_permissions)
        # in-memory audit log for tests; each entry is a dict
        self._audit_logs: List[Dict[str, Any]] = []

    def authorize(self, user: Optional[Dict[str, Any]], tool_name: str) -> Tuple[bool, Optional[str]]:
        """Return (allowed, reason). If no permission required, allow.

        `user` is expected to be a dict with at least `id` and `permissions` list.
        """
        required = self.tool_permissions.get(tool_name)
        if not required:
            return True, None

        user_perms = []
        if user and isinstance(user, dict):
            user_perms = user.get("permissions", []) or []

        if required in user_perms:
            return True, None

        return False, f"requires {required}"

    def authorize_resource(self, user: Optional[Dict[str, Any]], tool_name: str, args: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Perform resource-scoped authorization checks for tools that require it.

        For example, `delete_document` requires the user be the owner of the document
        or have a broader permission like DOCUMENT_DELETE_ANY.
        """
        # Example: delete_document ownership check
        if tool_name == "delete_document":
            doc_id = args.get("document_id") if isinstance(args, dict) else None
            if not doc_id:
                return False, "missing document_id"
            try:
                # avoid importing heavy modules at top-level in case of circulars
                from ..tools.sensitive_tools import get_document_store_snapshot

                store = get_document_store_snapshot()
                doc = store.get(doc_id)
                if not doc:
                    return False, "not_found"
                owner = doc.get("owner")
                user_id = (user.get("id") if user and isinstance(user, dict) else None)
                # allow if user is owner
                if owner and user_id and owner == user_id:
                    return True, None
                # allow if user has global delete-any permission
                user_perms = user.get("permissions", []) if user and isinstance(user, dict) else []
                if "DOCUMENT_DELETE_ANY" in user_perms:
                    return True, None
                return False, "user not owner"
            except Exception:
                return False, "resource check failed"

        return True, None

    def _redact_args(self, args: Any) -> Any:
        # Basic redaction: redact values for keys that look sensitive
        if isinstance(args, dict):
            out = {}
            for k, v in args.items():
                if any(s in k.lower() for s in ("secret", "password", "token")):
                    out[k] = "[REDACTED]"
                else:
                    out[k] = v
            return out
        return args

    def record_audit(
        self,
        user: Optional[Dict[str, Any]],
        tool_name: str,
        args: Any,
        decision: str,
        success: Optional[bool] = None,
    ) -> None:
        entry = {
            "timestamp": time.time(),
            "user_id": (user.get("id") if user and isinstance(user, dict) else None),
            "tool": tool_name,
            "args": self._redact_args(args),
            "decision": decision,
            "success": success,
        }
        self._audit_logs.append(entry)
        logger.info("AUDIT %s %s %s", entry["user_id"], tool_name, decision)

    def get_audit_logs(self) -> List[Dict[str, Any]]:
        return list(self._audit_logs)
