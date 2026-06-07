"""Provider contract loading and live credential validation."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import yaml


_CONTRACT_DIR = Path(__file__).resolve().parent.parent / "config" / "contracts"


@dataclass
class ContractValidationResult:
    ok: bool
    errors: List[str]
    warnings: List[str]


class ProviderContractError(RuntimeError):
    """Raised when live connector contract requirements are not met."""


def load_contract(contract_id: str) -> Dict[str, object]:
    path = _CONTRACT_DIR / f"{contract_id}_contract.yaml"
    if not path.exists():
        raise ProviderContractError(f"Missing contract file: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def validate_live_contract_env(contract: Dict[str, object]) -> ContractValidationResult:
    errors: List[str] = []
    warnings: List[str] = []

    transport = contract.get("transport", {}) if isinstance(contract.get("transport"), dict) else {}
    auth = contract.get("auth", {}) if isinstance(contract.get("auth"), dict) else {}

    base_url_env = str(transport.get("base_url_env", "US278_BASE_URL"))
    base_url = os.environ.get(base_url_env, "").strip()
    if not base_url:
        errors.append(f"missing_env:{base_url_env}")
    else:
        require_https = bool(transport.get("require_https_in_live", True))
        if require_https and not base_url.startswith("https://"):
            errors.append(f"insecure_base_url:{base_url}")

    mode_env = str(auth.get("mode_env", "US278_AUTH_MODE"))
    mode = os.environ.get(mode_env, "bearer_hmac").strip().lower()
    supported = set(str(x).lower() for x in (auth.get("supported_modes") or []))
    if supported and mode not in supported:
        errors.append(f"unsupported_auth_mode:{mode}")

    bearer_env = str(auth.get("bearer_token_env", "US278_API_TOKEN"))
    hmac_secret_env = str(auth.get("hmac_secret_env", "US278_HMAC_SECRET"))
    hmac_key_env = str(auth.get("hmac_key_id_env", "US278_HMAC_KEY_ID"))

    if mode in {"bearer", "bearer_hmac"} and not os.environ.get(bearer_env, "").strip():
        errors.append(f"missing_env:{bearer_env}")

    if mode in {"hmac", "bearer_hmac"}:
        if not os.environ.get(hmac_secret_env, "").strip():
            errors.append(f"missing_env:{hmac_secret_env}")
        if not os.environ.get(hmac_key_env, "").strip():
            errors.append(f"missing_env:{hmac_key_env}")

    timeout_env = str(transport.get("timeout_env", "US278_TIMEOUT_SECONDS"))
    retries_env = str(transport.get("retries_env", "US278_MAX_RETRIES"))
    if timeout_env in os.environ:
        try:
            if float(os.environ[timeout_env]) <= 0:
                errors.append(f"invalid_timeout:{timeout_env}")
        except Exception:
            errors.append(f"invalid_timeout:{timeout_env}")
    if retries_env in os.environ:
        try:
            if int(os.environ[retries_env]) < 1:
                errors.append(f"invalid_retries:{retries_env}")
        except Exception:
            errors.append(f"invalid_retries:{retries_env}")

    return ContractValidationResult(ok=not errors, errors=errors, warnings=warnings)


def enforce_live_contract(contract_id: str) -> None:
    contract = load_contract(contract_id)
    result = validate_live_contract_env(contract)
    if not result.ok:
        raise ProviderContractError(
            "Live connector contract validation failed: " + ", ".join(result.errors)
        )


def is_live_requested(base_url_env: str = "US278_BASE_URL") -> bool:
    return bool(os.environ.get(base_url_env, "").strip())
