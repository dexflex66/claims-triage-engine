"""Fail-closed compliance gate for production go-live."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _is_true(name: str) -> bool:
    return os.environ.get(name, "false").strip().lower() == "true"


def main() -> None:
    errors: list[str] = []

    required_files = [
        ROOT / "compliance" / "retention_policy.yaml",
        ROOT / "compliance" / "incident_log_template.md",
        ROOT / "compliance" / "GO_LIVE_LEGAL_CHECKLIST.md",
        ROOT / "operations" / "UAT_ROLLBACK_RUNBOOK.md",
        ROOT / "db" / "PRODUCTION_RUNBOOK.md",
    ]
    for path in required_files:
        if not path.exists():
            errors.append(f"missing_file:{path}")

    for env_name in [
        "LEGAL_APPROVED",
        "SECURITY_APPROVED",
        "COMPLIANCE_APPROVED",
        "DPA_SIGNED",
        "BAA_SIGNED",
        "HIPAA_RISK_ASSESSMENT_COMPLETE",
    ]:
        if not _is_true(env_name):
            errors.append(f"missing_or_false:{env_name}")

    result = {"ok": len(errors) == 0, "errors": errors}
    print(json.dumps(result, indent=2))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
