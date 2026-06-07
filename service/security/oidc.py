"""OIDC/JWT validation and RBAC helpers.

Default mode requires a bearer token. Signature validation can be enforced via
OIDC_REQUIRE_SIGNATURE=true when python-jose is installed.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass
from typing import Dict, List
from urllib.error import URLError
from urllib.request import Request, urlopen

from fastapi import Depends, Header, HTTPException, status


_JWKS_CACHE: Dict[str, object] = {"source": "", "loaded_at": 0.0, "jwks": {"keys": []}}


@dataclass
class AuthContext:
    subject: str
    roles: List[str]
    claims: Dict[str, object]


def _decode_segment(segment: str) -> Dict[str, object]:
    pad = "=" * ((4 - len(segment) % 4) % 4)
    raw = base64.urlsafe_b64decode(segment + pad)
    return json.loads(raw.decode("utf-8"))


def _decode_segment_bytes(segment: str) -> bytes:
    pad = "=" * ((4 - len(segment) % 4) % 4)
    return base64.urlsafe_b64decode(segment + pad)


def _decode_token_without_signature(token: str) -> Dict[str, object]:
    parts = token.split(".")
    if len(parts) < 2:
        raise ValueError("Invalid JWT format")
    return _decode_segment(parts[1])


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() == "true"


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except Exception:
        return default


def _get_expected_issuer() -> str:
    return os.environ.get("OIDC_ISSUER", "").strip()


def _get_expected_audience() -> str:
    return os.environ.get("OIDC_AUDIENCE", "payer-proof-claims").strip()


def _jwks_source() -> str:
    jwks_json = os.environ.get("OIDC_JWKS_JSON", "").strip()
    if jwks_json:
        digest = hashlib.sha256(jwks_json.encode("utf-8")).hexdigest()
        return f"json:{digest}"
    url = os.environ.get("OIDC_JWKS_URL", "").strip()
    return f"url:{url}"


def _load_jwks() -> Dict[str, object]:
    source = _jwks_source()
    ttl_seconds = max(_int_env("OIDC_JWKS_CACHE_SECONDS", 300), 0)
    now = time.time()

    if (
        _JWKS_CACHE.get("source") == source
        and isinstance(_JWKS_CACHE.get("loaded_at"), float)
        and (now - float(_JWKS_CACHE.get("loaded_at", 0.0)) <= ttl_seconds)
    ):
        cached = _JWKS_CACHE.get("jwks")
        if isinstance(cached, dict):
            return cached

    jwks_json = os.environ.get("OIDC_JWKS_JSON", "").strip()
    if jwks_json:
        try:
            jwks = json.loads(jwks_json)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OIDC_JWKS_JSON is not valid JSON",
            ) from exc
    else:
        jwks_url = os.environ.get("OIDC_JWKS_URL", "").strip()
        if not jwks_url:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="OIDC_JWKS_URL not set")
        if (not jwks_url.startswith("https://")) and (not _bool_env("OIDC_ALLOW_INSECURE_JWKS", False)):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OIDC_JWKS_URL must use https unless OIDC_ALLOW_INSECURE_JWKS=true",
            )
        timeout = max(float(os.environ.get("OIDC_JWKS_TIMEOUT_SECONDS", "5")), 1.0)
        req = Request(jwks_url, headers={"Accept": "application/json"})
        try:
            with urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
        except URLError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Unable to fetch OIDC JWKS",
            ) from exc
        try:
            jwks = json.loads(raw)
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OIDC JWKS response is not valid JSON",
            ) from exc

    if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="OIDC JWKS missing keys array")

    _JWKS_CACHE["source"] = source
    _JWKS_CACHE["loaded_at"] = now
    _JWKS_CACHE["jwks"] = jwks
    return jwks


def _verify_signature_with_jwks(token: str) -> Dict[str, object]:
    try:
        from jose import jwk
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="OIDC signature validation requested but python-jose unavailable",
        ) from exc

    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT format")

    try:
        header = _decode_segment(parts[0])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT header") from exc

    alg = str(header.get("alg") or "").strip()
    if not alg or alg.lower() == "none":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT algorithm")

    kid = str(header.get("kid") or "").strip()
    jwks = _load_jwks()
    keys = [k for k in jwks["keys"] if isinstance(k, dict)]
    if kid:
        keys = [k for k in keys if str(k.get("kid") or "") == kid]
    if not keys:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No matching JWKS key")

    signing_input = f"{parts[0]}.{parts[1]}".encode("utf-8")
    try:
        signature = _decode_segment_bytes(parts[2])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT signature encoding") from exc

    verified = False
    for key_data in keys:
        key_alg = str(key_data.get("alg") or "").strip()
        if key_alg and key_alg != alg:
            continue
        try:
            key = jwk.construct(key_data, algorithm=alg)
            if key.verify(signing_input, signature):
                verified = True
                break
        except Exception:
            continue
    if not verified:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT signature")

    try:
        payload = _decode_segment(parts[1])
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid JWT payload") from exc
    return payload


def _validate_claims(payload: Dict[str, object]) -> None:
    now = int(time.time())
    exp = int(payload.get("exp", now + 1))
    if exp < now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")

    nbf = payload.get("nbf")
    if nbf is not None and int(nbf) > now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token not active")

    expected_issuer = _get_expected_issuer()
    iss = str(payload.get("iss", ""))
    if expected_issuer and iss != expected_issuer:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token issuer")

    expected_audience = _get_expected_audience()
    aud = payload.get("aud")
    if expected_audience:
        if isinstance(aud, str) and aud != expected_audience:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token audience")
        if isinstance(aud, list) and expected_audience not in aud:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token audience")


def _extract_roles(payload: Dict[str, object]) -> List[str]:
    roles = payload.get("roles")
    if isinstance(roles, list):
        return [str(r) for r in roles]
    realm = payload.get("realm_access")
    if isinstance(realm, dict) and isinstance(realm.get("roles"), list):
        return [str(r) for r in realm["roles"]]
    scope = payload.get("scope")
    if isinstance(scope, str):
        return [s.strip() for s in scope.split() if s.strip()]
    return []


def get_auth_context(authorization: str = Header(default="")) -> AuthContext:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1].strip()

    if _bool_env("OIDC_REQUIRE_SIGNATURE", False):
        payload = _verify_signature_with_jwks(token)
    else:
        payload = _decode_token_without_signature(token)

    _validate_claims(payload)
    sub = str(payload.get("sub") or payload.get("client_id") or "unknown")
    roles = _extract_roles(payload)
    return AuthContext(subject=sub, roles=roles, claims=payload)


def require_roles(*allowed: str):
    allowed_set = set(allowed)

    def _dep(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not allowed_set.intersection(set(ctx.roles)):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient role")
        return ctx

    return _dep
