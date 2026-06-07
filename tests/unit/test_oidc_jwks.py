import base64
import hmac
import json
import sys
import time
import types
import hashlib

import pytest
from fastapi import HTTPException

from service.security import oidc


def _unsigned_jwt(payload: dict) -> str:
    header = {"alg": "none", "typ": "JWT"}

    def _enc(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    return f"{_enc(header)}.{_enc(payload)}."


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")


def _b64url_decode(raw: str) -> bytes:
    pad = "=" * ((4 - len(raw) % 4) % 4)
    return base64.urlsafe_b64decode(raw + pad)


def _signed_hs256_jwt(payload: dict, secret: bytes, kid: str) -> str:
    header = {"alg": "HS256", "typ": "JWT", "kid": kid}

    def _enc(obj: dict) -> str:
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return _b64url(raw)

    h = _enc(header)
    p = _enc(payload)
    signing_input = f"{h}.{p}".encode("utf-8")
    sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
    return f"{h}.{p}.{_b64url(sig)}"


def _install_fake_jose_jwk(monkeypatch):
    jose_mod = types.ModuleType("jose")
    jwk_mod = types.ModuleType("jose.jwk")

    class _Verifier:
        def __init__(self, key_data):
            self._key_data = key_data

        def verify(self, message: bytes, signature: bytes) -> bool:
            key_bytes = _b64url_decode(str(self._key_data.get("k", "")))
            expect = hmac.new(key_bytes, message, hashlib.sha256).digest()
            return hmac.compare_digest(expect, signature)

    def _construct(key_data, algorithm):
        assert algorithm == "HS256"
        return _Verifier(key_data)

    jwk_mod.construct = _construct
    jose_mod.jwk = jwk_mod
    monkeypatch.setitem(sys.modules, "jose", jose_mod)
    monkeypatch.setitem(sys.modules, "jose.jwk", jwk_mod)


def _reset_jwks_cache() -> None:
    oidc._JWKS_CACHE["source"] = ""
    oidc._JWKS_CACHE["loaded_at"] = 0.0
    oidc._JWKS_CACHE["jwks"] = {"keys": []}


def test_signed_token_validates_against_jwks(monkeypatch):
    _reset_jwks_cache()
    _install_fake_jose_jwk(monkeypatch)
    secret = b"top-secret-key"
    jwks = {"keys": [{"kty": "oct", "kid": "kid-1", "alg": "HS256", "k": _b64url(secret)}]}
    token = _signed_hs256_jwt(
        {
            "sub": "signed-user",
            "roles": ["admin"],
            "aud": "payer-proof-claims",
            "exp": int(time.time()) + 3600,
        },
        secret=secret,
        kid="kid-1",
    )

    monkeypatch.setenv("OIDC_REQUIRE_SIGNATURE", "true")
    monkeypatch.setenv("OIDC_AUDIENCE", "payer-proof-claims")
    monkeypatch.setenv("OIDC_JWKS_JSON", json.dumps(jwks))
    monkeypatch.delenv("OIDC_JWKS_URL", raising=False)

    ctx = oidc.get_auth_context(f"Bearer {token}")
    assert ctx.subject == "signed-user"
    assert "admin" in ctx.roles


def test_signed_token_rejects_invalid_signature(monkeypatch):
    _reset_jwks_cache()
    _install_fake_jose_jwk(monkeypatch)
    right_secret = b"right-secret"
    wrong_secret = b"wrong-secret"
    jwks = {"keys": [{"kty": "oct", "kid": "kid-2", "alg": "HS256", "k": _b64url(right_secret)}]}
    token = _signed_hs256_jwt(
        {
            "sub": "signed-user",
            "roles": ["viewer"],
            "aud": "payer-proof-claims",
            "exp": int(time.time()) + 3600,
        },
        secret=wrong_secret,
        kid="kid-2",
    )

    monkeypatch.setenv("OIDC_REQUIRE_SIGNATURE", "true")
    monkeypatch.setenv("OIDC_AUDIENCE", "payer-proof-claims")
    monkeypatch.setenv("OIDC_JWKS_JSON", json.dumps(jwks))

    with pytest.raises(HTTPException) as exc:
        oidc.get_auth_context(f"Bearer {token}")
    assert exc.value.status_code == 401
    assert "signature" in exc.value.detail.lower()


def test_signature_mode_rejects_alg_none(monkeypatch):
    _reset_jwks_cache()
    _install_fake_jose_jwk(monkeypatch)
    token = _unsigned_jwt(
        {
            "sub": "unsigned-user",
            "roles": ["viewer"],
            "aud": "payer-proof-claims",
            "exp": int(time.time()) + 3600,
        }
    )
    monkeypatch.setenv("OIDC_REQUIRE_SIGNATURE", "true")
    monkeypatch.setenv("OIDC_JWKS_JSON", json.dumps({"keys": []}))

    with pytest.raises(HTTPException) as exc:
        oidc.get_auth_context(f"Bearer {token}")
    assert exc.value.status_code == 401
    assert "algorithm" in exc.value.detail.lower()


def test_unsigned_mode_still_allows_local_tokens(monkeypatch):
    token = _unsigned_jwt(
        {
            "sub": "local-user",
            "roles": ["viewer"],
            "aud": "payer-proof-claims",
            "exp": int(time.time()) + 3600,
        }
    )
    monkeypatch.setenv("OIDC_REQUIRE_SIGNATURE", "false")
    monkeypatch.setenv("OIDC_AUDIENCE", "payer-proof-claims")
    ctx = oidc.get_auth_context(f"Bearer {token}")
    assert ctx.subject == "local-user"
    assert "viewer" in ctx.roles
