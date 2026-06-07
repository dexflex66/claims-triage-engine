import base64
import json
import os
import time

from fastapi.testclient import TestClient


def _jwt(payload):
    header = {"alg": "none", "typ": "JWT"}

    def enc(obj):
        raw = json.dumps(obj, separators=(",", ":")).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")

    return f"{enc(header)}.{enc(payload)}."


def test_ops_endpoints(tmp_path):
    db_path = tmp_path / "test_ops.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["OIDC_REQUIRE_SIGNATURE"] = "false"
    os.environ["KEY_ROTATION_ENFORCED"] = "false"
    os.environ["MTLS_REQUIRED"] = "false"
    os.environ["IP_ALLOWLIST_ENABLED"] = "false"

    from db.models import Base
    from db.session import engine
    from service.main import app

    Base.metadata.create_all(bind=engine)

    token = _jwt(
        {
            "sub": "tester",
            "roles": ["admin", "ops_submitter"],
            "aud": "payer-proof-claims",
            "exp": int(time.time()) + 3600,
        }
    )
    headers = {"Authorization": f"Bearer {token}"}

    with TestClient(app) as client:
        sla = client.get("/v1/ops/sla", headers=headers)
        assert sla.status_code == 200
        assert "success_rate" in sla.json()

        controls = client.get("/v1/ops/controls", headers=headers)
        assert controls.status_code == 200
        assert "key_rotation" in controls.json()

        metrics = client.get("/metrics")
        assert metrics.status_code == 200
        assert "payer_proof_http_requests_total" in metrics.text
