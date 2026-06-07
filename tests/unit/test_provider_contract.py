import pytest

from service.provider_contract import load_contract, validate_live_contract_env


def test_contract_loads():
    contract = load_contract("us_278_837")
    assert contract.get("contract_id") == "us_278_837"


def test_india_contract_loads():
    contract = load_contract("india_preauth")
    assert contract.get("contract_id") == "india_preauth"


def test_contract_validation_fails_when_missing_env(monkeypatch):
    monkeypatch.delenv("US278_BASE_URL", raising=False)
    monkeypatch.delenv("US278_API_TOKEN", raising=False)
    monkeypatch.delenv("US278_HMAC_SECRET", raising=False)
    monkeypatch.delenv("US278_HMAC_KEY_ID", raising=False)

    contract = load_contract("us_278_837")
    result = validate_live_contract_env(contract)
    assert not result.ok
    assert any(e.startswith("missing_env:US278_BASE_URL") for e in result.errors)


def test_contract_validation_passes_with_valid_env(monkeypatch):
    monkeypatch.setenv("US278_BASE_URL", "https://clearinghouse.example")
    monkeypatch.setenv("US278_AUTH_MODE", "bearer_hmac")
    monkeypatch.setenv("US278_API_TOKEN", "token")
    monkeypatch.setenv("US278_HMAC_SECRET", "secret")
    monkeypatch.setenv("US278_HMAC_KEY_ID", "kid")

    contract = load_contract("us_278_837")
    result = validate_live_contract_env(contract)
    assert result.ok


def test_india_contract_validation_passes_with_valid_env(monkeypatch):
    monkeypatch.setenv("IN_PREAUTH_BASE_URL", "https://insurer.example")
    monkeypatch.setenv("IN_PREAUTH_AUTH_MODE", "bearer_hmac")
    monkeypatch.setenv("IN_PREAUTH_API_TOKEN", "token")
    monkeypatch.setenv("IN_PREAUTH_HMAC_SECRET", "secret")
    monkeypatch.setenv("IN_PREAUTH_HMAC_KEY_ID", "kid")

    contract = load_contract("india_preauth")
    result = validate_live_contract_env(contract)
    assert result.ok
