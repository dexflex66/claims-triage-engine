import pytest

from service.security.key_rotation import validate_key_rotation
from service.security.network import is_ip_allowed
from service.security.production_guard import validate_production_controls


def test_ip_allowlist_match(monkeypatch):
    monkeypatch.setenv("IP_ALLOWLIST_CIDRS", "10.0.0.0/8,192.168.1.0/24")
    assert is_ip_allowed("10.1.2.3")
    assert not is_ip_allowed("8.8.8.8")


def test_key_rotation_validation_fails(monkeypatch):
    monkeypatch.setenv("KEY_ROTATION_ENFORCED", "true")
    monkeypatch.setenv("US278_ACTIVE_KEY_ID", "kid-a")
    monkeypatch.setenv("US278_ALLOWED_KEY_IDS", "kid-b,kid-c")
    monkeypatch.setenv("US278_HMAC_KEY_ID", "kid-a")
    with pytest.raises(Exception):
        validate_key_rotation()


def test_key_rotation_validation_passes(monkeypatch):
    monkeypatch.setenv("KEY_ROTATION_ENFORCED", "true")
    monkeypatch.setenv("US278_ACTIVE_KEY_ID", "kid-a")
    monkeypatch.setenv("US278_ALLOWED_KEY_IDS", "kid-a,kid-b")
    monkeypatch.setenv("US278_HMAC_KEY_ID", "kid-a")
    validate_key_rotation()


def test_production_controls_fail_when_not_hardened(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OIDC_REQUIRE_SIGNATURE", "false")
    monkeypatch.setenv("MTLS_REQUIRED", "false")
    monkeypatch.setenv("IP_ALLOWLIST_ENABLED", "false")
    monkeypatch.setenv("KEY_ROTATION_ENFORCED", "false")
    monkeypatch.setenv("US278_ENFORCE_CONTRACT", "false")
    monkeypatch.setenv("IN_PREAUTH_ENFORCE_CONTRACT", "false")
    monkeypatch.setenv("ALLOW_STUB_CONNECTORS", "true")
    monkeypatch.setenv("DATABASE_URL", "sqlite:///./test.db")

    with pytest.raises(Exception):
        validate_production_controls()


def test_production_controls_pass_when_hardened(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OIDC_REQUIRE_SIGNATURE", "true")
    monkeypatch.setenv("OIDC_JWKS_URL", "https://idp.example/jwks.json")
    monkeypatch.setenv("MTLS_REQUIRED", "true")
    monkeypatch.setenv("TLS_CLIENT_CA_CERT_PATH", __file__)
    monkeypatch.setenv("TLS_SERVER_CERT_PATH", __file__)
    monkeypatch.setenv("TLS_SERVER_KEY_PATH", __file__)
    monkeypatch.setenv("IP_ALLOWLIST_ENABLED", "true")
    monkeypatch.setenv("IP_ALLOWLIST_CIDRS", "10.0.0.0/8")
    monkeypatch.setenv("KEY_ROTATION_ENFORCED", "true")
    monkeypatch.setenv("US278_ACTIVE_KEY_ID", "kid-a")
    monkeypatch.setenv("US278_ALLOWED_KEY_IDS", "kid-a")
    monkeypatch.setenv("US278_HMAC_KEY_ID", "kid-a")
    monkeypatch.setenv("US278_ENFORCE_CONTRACT", "true")
    monkeypatch.setenv("IN_PREAUTH_ENFORCE_CONTRACT", "true")
    monkeypatch.setenv("ALLOW_STUB_CONNECTORS", "false")
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@localhost:5432/db")

    validate_production_controls()
