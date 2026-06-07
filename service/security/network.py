"""Network access controls (IP allowlist)."""
from __future__ import annotations

import ipaddress
import os
from typing import List


def _cidrs() -> List[str]:
    raw = os.environ.get("IP_ALLOWLIST_CIDRS", "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def allowlist_enabled() -> bool:
    return os.environ.get("IP_ALLOWLIST_ENABLED", "false").lower() == "true"


def is_ip_allowed(ip: str) -> bool:
    cidrs = _cidrs()
    if not cidrs:
        return False
    try:
        addr = ipaddress.ip_address(ip)
    except Exception:
        return False

    for c in cidrs:
        try:
            if addr in ipaddress.ip_network(c, strict=False):
                return True
        except Exception:
            continue
    return False


def resolve_client_ip(forwarded_for: str, client_host: str) -> str:
    if forwarded_for:
        first = forwarded_for.split(",", 1)[0].strip()
        if first:
            return first
    return client_host or ""
