"""Production security guardrails."""
from __future__ import annotations

import ipaddress
import os
from typing import Dict, List


class ProductionControlError(RuntimeError):
    pass


def _is_true(name: str) -> bool:
    return os.environ.get(name, "false").strip().lower() == "true"


def _app_env() -> str:
    return os.environ.get("APP_ENV", "dev").strip().lower()


def _validate_cidrs(raw: str) -> bool:
    cidrs = [x.strip() for x in raw.split(",") if x.strip()]
    if not cidrs:
        return False
    for c in cidrs:
        ipaddress.ip_network(c, strict=False)
    return True


def validate_production_controls() -> None:
    if _app_env() != "production":
        return

    errors: List[str] = []
    if not _is_true("OIDC_REQUIRE_SIGNATURE"):
        errors.append("OIDC_REQUIRE_SIGNATURE must be true")
    if not os.environ.get("OIDC_JWKS_URL", "").strip() and not os.environ.get("OIDC_JWKS_JSON", "").strip():
        errors.append("OIDC_JWKS_URL or OIDC_JWKS_JSON must be set")
    if not _is_true("KEY_ROTATION_ENFORCED"):
        errors.append("KEY_ROTATION_ENFORCED must be true")
    if not _is_true("MTLS_REQUIRED"):
        errors.append("MTLS_REQUIRED must be true")
    if not _is_true("IP_ALLOWLIST_ENABLED"):
        errors.append("IP_ALLOWLIST_ENABLED must be true")
    cidrs_raw = os.environ.get("IP_ALLOWLIST_CIDRS", "")
    if _is_true("IP_ALLOWLIST_ENABLED"):
        try:
            if not _validate_cidrs(cidrs_raw):
                errors.append("IP_ALLOWLIST_CIDRS must be non-empty valid CIDR list")
        except Exception:
            errors.append("IP_ALLOWLIST_CIDRS contains invalid CIDR")

    if not _is_true("US278_ENFORCE_CONTRACT"):
        errors.append("US278_ENFORCE_CONTRACT must be true")
    if not _is_true("IN_PREAUTH_ENFORCE_CONTRACT"):
        errors.append("IN_PREAUTH_ENFORCE_CONTRACT must be true")
    if _is_true("ALLOW_STUB_CONNECTORS"):
        errors.append("ALLOW_STUB_CONNECTORS must be false")

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url.startswith("postgresql"):
        errors.append("DATABASE_URL must use PostgreSQL in production")

    if errors:
        raise ProductionControlError("production_controls_failed: " + "; ".join(errors))


def production_control_status() -> Dict[str, object]:
    return {
        "app_env": _app_env(),
        "oidc_signature_required": _is_true("OIDC_REQUIRE_SIGNATURE"),
        "has_jwks_source": bool(os.environ.get("OIDC_JWKS_URL", "").strip() or os.environ.get("OIDC_JWKS_JSON", "").strip()),
        "key_rotation_enforced": _is_true("KEY_ROTATION_ENFORCED"),
        "mtls_required": _is_true("MTLS_REQUIRED"),
        "ip_allowlist_enabled": _is_true("IP_ALLOWLIST_ENABLED"),
        "us_contract_enforced": _is_true("US278_ENFORCE_CONTRACT"),
        "in_contract_enforced": _is_true("IN_PREAUTH_ENFORCE_CONTRACT"),
        "allow_stub_connectors": _is_true("ALLOW_STUB_CONNECTORS"),
        "database_url": os.environ.get("DATABASE_URL", ""),
    }
