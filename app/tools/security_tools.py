"""Simple security-related tools for demonstration."""
from typing import Dict


def get_security_policy(topic: str) -> Dict[str, str]:
    """Return a small predefined policy for a few topics.

    Args:
        topic: short topic key such as 'authentication', 'password_storage', 'secrets'

    Returns:
        A dict with 'topic' and 'policy' keys.
    """
    topic = (topic or "").strip().lower()
    if topic in ("authentication", "auth"):
        return {
            "topic": "authentication",
            "policy": (
                "Verify identities using strong methods (MFA where appropriate). "
                "Do not store passwords in plaintext; use secure hashing like Argon2id."
            ),
        }
    if topic in ("password_storage", "passwords", "password"):
        return {
            "topic": "password_storage",
            "policy": (
                "Never store passwords in plaintext. Use a vetted password hashing algorithm "
                "(Argon2id, bcrypt) with appropriate parameters and salt. Rotate and revoke "
                "credentials when needed."
            ),
        }
    if topic in ("secrets", "secrets_management", "secret"):
        return {
            "topic": "secrets",
            "policy": (
                "Store secrets in a dedicated secrets manager (Vault, AWS Secrets Manager). "
                "Avoid hardcoding secrets or logging them. Grant least privilege and rotate." 
            ),
        }

    return {"topic": topic, "policy": "No policy found for this topic."}


__all__ = ["get_security_policy"]
 
def lookup_security_control(control_name: str) -> dict:
    control = (control_name or "").strip().lower()
    mapping = {
        "rbac": "Role-Based Access Control: define roles and bind least-privilege permissions.",
        "networkpolicy": "Kubernetes NetworkPolicy: restrict pod-to-pod traffic by labels and ports.",
        "csp": "Content Security Policy: limit allowed sources for scripts and resources.",
        "secrets": "Secrets should be stored in a secrets manager and not in images or code.",
    }
    # normalize keys
    for k in list(mapping.keys()):
        if control == k or control == k.lower():
            return {"control": k, "description": mapping[k]}

    return {"control": control_name, "description": "No information available for this control."}


def check_password_policy(password: str) -> dict:
    pwd = password or ""
    issues = []
    if len(pwd) < 8:
        issues.append("too_short")
    if pwd.lower() == pwd:
        issues.append("no_uppercase")
    if pwd.upper() == pwd:
        issues.append("no_lowercase")
    if not any(c.isdigit() for c in pwd):
        issues.append("no_digit")
    if not any(c in "!@#$%^&*()-_+=" for c in pwd):
        issues.append("no_symbol")

    return {"password_ok": len(issues) == 0, "issues": issues}


__all__ = ["get_security_policy", "lookup_security_control", "check_password_policy"]
