"""Policy helpers for service runtime."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, List, Sequence, Tuple

import yaml

_ALLOWED_PAYERS_BY_COUNTRY = {
    "US": {"BCBS", "AETNA"},
    "IN": {"STAR_HEALTH", "HDFC_ERGO"},
}

_POLICY_PATH_BY_COUNTRY = {
    "US": "policy/claims_policy_us.yaml",
    "IN": "policy/claims_policy_india.yaml",
}


def _policy_path_for_country(country: str) -> str:
    c = (country or "").upper()
    path = _POLICY_PATH_BY_COUNTRY.get(c)
    if not path:
        raise ValueError(f"Unsupported country: {country}")
    return path


@lru_cache(maxsize=8)
def _load_policy_yaml(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


@lru_cache(maxsize=8)
def _provenance_alias_config(path: str) -> Tuple[Dict[str, str], Tuple[Tuple[str, str], ...]]:
    data = _load_policy_yaml(path)
    aliases_raw = data.get("provenance_aliases") or {}
    prefixes_raw = data.get("provenance_prefix_aliases") or {}

    aliases: Dict[str, str] = {}
    if isinstance(aliases_raw, dict):
        for k, v in aliases_raw.items():
            src = str(k or "").strip()
            dst = str(v or "").strip()
            if src and dst:
                aliases[src.upper()] = dst

    prefixes: List[Tuple[str, str]] = []
    if isinstance(prefixes_raw, dict):
        for k, v in prefixes_raw.items():
            prefix = str(k or "").strip()
            dst = str(v or "").strip()
            if prefix and dst:
                prefixes.append((prefix.upper(), dst))

    prefixes.sort(key=lambda x: len(x[0]), reverse=True)
    return aliases, tuple(prefixes)


def _normalize_provenance_id(
    provenance: str,
    aliases: Dict[str, str],
    prefixes: Sequence[Tuple[str, str]],
) -> str:
    raw = str(provenance or "").strip()
    if not raw:
        return raw
    upper = raw.upper()
    if upper in aliases:
        return aliases[upper]
    for prefix, target in prefixes:
        if upper.startswith(prefix):
            return target
    return raw


def validate_policy_runtime(policy: Any, country: str, payer_id: str) -> List[str]:
    """Boot/runtime checks for policy compatibility and minimum fields."""
    errors: List[str] = []

    req_fields = [f.name for f in getattr(policy, "required_fields", [])]
    if not req_fields:
        errors.append("policy.required_fields_missing")

    prov = getattr(policy, "provenance_sources", [])
    if not prov:
        errors.append("policy.provenance_sources_missing")
    else:
        for src in prov:
            rho = getattr(src, "rho", None)
            if rho is None:
                errors.append("policy.provenance_source_missing_rho")
                break

    # Country allowlist validation
    codes = set((getattr(policy, "country_codes", None) or []) or [])
    if country and codes and country not in codes:
        errors.append(f"policy.country_not_allowed:{country}")

    c = (country or "").upper()
    allowed_payers = _ALLOWED_PAYERS_BY_COUNTRY.get(c, set())
    p = (payer_id or "").upper()
    if allowed_payers and p and p not in allowed_payers:
        errors.append(f"policy.payer_not_allowed:{payer_id}")

    alias_errors = validate_provenance_alias_config(policy, country)
    if alias_errors:
        errors.extend(alias_errors)

    return errors


def load_policy_for_country(country: str):
    from compiler import load_policy  # lazy: requires QUEST_ROOT at runtime only
    return load_policy(_policy_path_for_country(country))


def validate_provenance_alias_config(policy: Any, country: str) -> List[str]:
    path = _policy_path_for_country(country)
    aliases, prefixes = _provenance_alias_config(path)
    if not aliases and not prefixes:
        return []
    known = {getattr(src, "id", "") for src in getattr(policy, "provenance_sources", [])}
    errors: List[str] = []
    for alias, target in aliases.items():
        if target not in known:
            errors.append(f"policy.provenance_alias_target_unknown:{alias}->{target}")
    for prefix, target in prefixes:
        if target not in known:
            errors.append(f"policy.provenance_prefix_alias_target_unknown:{prefix}->{target}")
    return sorted(set(errors))


def normalize_evidence_provenance(country: str, evidence: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Map dataset/source provenance IDs to canonical policy provenance IDs."""
    path = _policy_path_for_country(country)
    aliases, prefixes = _provenance_alias_config(path)
    if not aliases and not prefixes:
        return evidence, 0

    remapped = 0
    out: List[Dict[str, Any]] = []
    for ev in evidence:
        item = dict(ev or {})
        raw = str(item.get("provenance", "") or "").strip()
        normalized = _normalize_provenance_id(raw, aliases, prefixes)
        if raw and normalized and normalized != raw:
            item["provenance_original"] = raw
            item["provenance"] = normalized
            remapped += 1
        out.append(item)
    return out, remapped
