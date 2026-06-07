"""Transport and mTLS readiness checks."""
from __future__ import annotations

import os
from pathlib import Path
from typing import List


class TransportControlError(RuntimeError):
    pass


def validate_transport_controls() -> None:
    mtls_required = os.environ.get("MTLS_REQUIRED", "false").lower() == "true"
    if not mtls_required:
        return

    ca = os.environ.get("TLS_CLIENT_CA_CERT_PATH", "")
    cert = os.environ.get("TLS_SERVER_CERT_PATH", "")
    key = os.environ.get("TLS_SERVER_KEY_PATH", "")

    missing = []
    for env_name, value in [
        ("TLS_CLIENT_CA_CERT_PATH", ca),
        ("TLS_SERVER_CERT_PATH", cert),
        ("TLS_SERVER_KEY_PATH", key),
    ]:
        if not value:
            missing.append(f"missing_env:{env_name}")
        elif not Path(value).exists():
            missing.append(f"missing_file:{env_name}:{value}")

    if missing:
        raise TransportControlError("transport_control_failed: " + ", ".join(missing))
