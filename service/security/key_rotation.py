"""Key rotation readiness checks for outbound signing keys."""
from __future__ import annotations

import os
from typing import Dict, List


class KeyRotationError(RuntimeError):
    pass


def validate_key_rotation() -> None:
    enforce = os.environ.get("KEY_ROTATION_ENFORCED", "false").lower() == "true"
    if not enforce:
        return

    active = os.environ.get("US278_ACTIVE_KEY_ID", "").strip()
    allowed_raw = os.environ.get("US278_ALLOWED_KEY_IDS", "")
    allowed = {x.strip() for x in allowed_raw.split(",") if x.strip()}
    configured = os.environ.get("US278_HMAC_KEY_ID", "").strip()

    errors: List[str] = []
    if not active:
        errors.append("missing_env:US278_ACTIVE_KEY_ID")
    if not allowed:
        errors.append("missing_env:US278_ALLOWED_KEY_IDS")
    if active and allowed and active not in allowed:
        errors.append("active_key_not_in_allowed")
    if configured and active and configured != active:
        errors.append("configured_key_mismatch_active")

    if errors:
        raise KeyRotationError("key_rotation_failed: " + ", ".join(errors))


def rotation_status() -> Dict[str, object]:
    active = os.environ.get("US278_ACTIVE_KEY_ID", "").strip()
    allowed_raw = os.environ.get("US278_ALLOWED_KEY_IDS", "")
    allowed = [x.strip() for x in allowed_raw.split(",") if x.strip()]
    configured = os.environ.get("US278_HMAC_KEY_ID", "").strip()
    return {
        "active_key_id": active,
        "configured_key_id": configured,
        "allowed_key_ids": allowed,
        "enforced": os.environ.get("KEY_ROTATION_ENFORCED", "false").lower() == "true",
    }
