"""Role-based access and minimum-necessary checks (HIPAA baseline)."""
from __future__ import annotations

from typing import Dict, Iterable, Set

_DEFAULT_ROLES: Dict[str, Set[str]] = {
    "viewer": {"case:read", "packet:read", "queue:read", "audit:read"},
    "reviewer": {"case:read", "packet:read", "queue:read", "approve_to_send", "queue:write", "outcome:write"},
    "ops_submitter": {"case:read", "packet:read", "submit", "status:read", "reconciliation:read", "outcome:write"},
    "admin": {
        "case:read",
        "case:write",
        "packet:read",
        "queue:read",
        "queue:write",
        "approve_to_send",
        "config:read",
        "config:write",
        "audit:read",
        "submit",
        "status:read",
        "reconciliation:read",
        "outcome:write",
    },
}

_user_roles: Dict[str, str] = {}


def assign_role(user_id: str, role: str) -> None:
    _user_roles[user_id] = role


def get_role(user_id: str) -> str:
    return _user_roles.get(user_id, "viewer")


def has_permission(user_id: str, permission: str) -> bool:
    role = get_role(user_id)
    perms = _DEFAULT_ROLES.get(role, set())
    return permission in perms


def has_permission_for_roles(roles: Iterable[str], permission: str) -> bool:
    """RBAC check for token-derived roles."""
    for role in roles:
        if permission in _DEFAULT_ROLES.get(role, set()):
            return True
    return False


def check_minimum_necessary(user_id: str, resource_type: str, action: str) -> bool:
    role = get_role(user_id)
    perms = _DEFAULT_ROLES.get(role, set())
    key = f"{resource_type}:{action}"
    return key in perms or role == "admin"
