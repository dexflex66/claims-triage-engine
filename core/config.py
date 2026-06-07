"""Runtime configuration helpers."""
from __future__ import annotations

import os
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
_PAYER_PROOF_ROOT = _THIS_DIR.parent
_DOWNLOADS = _PAYER_PROOF_ROOT.parent
_QUEST_ROOT = Path(os.environ.get("QUEST_ROOT", str(_DOWNLOADS / "proof_first" / "clean_quest")))


def get_quest_root() -> Path:
    return _QUEST_ROOT


def get_database_url() -> str:
    return os.environ.get("DATABASE_URL", "sqlite:///./payer_proof_claims.db")


def get_oidc_settings() -> dict:
    return {
        "issuer": os.environ.get("OIDC_ISSUER", ""),
        "audience": os.environ.get("OIDC_AUDIENCE", "payer-proof-claims"),
        "jwks_url": os.environ.get("OIDC_JWKS_URL", ""),
        "require_signature": os.environ.get("OIDC_REQUIRE_SIGNATURE", "false").lower() == "true",
    }
