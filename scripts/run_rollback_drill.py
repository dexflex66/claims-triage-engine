"""Run rollback drill: backup primary DB and optional restore validation DB."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def _run(cmd: list[str], env: dict[str, str] | None = None) -> None:
    subprocess.run(cmd, check=True, env=env)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--primary-db-url", required=True, help="Primary database URL")
    parser.add_argument("--backup-out", required=True, help="Backup output file path")
    parser.add_argument("--restore-db-url", default="", help="Optional restore target database URL")
    parser.add_argument("--clean-restore", action="store_true", help="Use clean restore mode")
    parser.add_argument("--report-out", default="artifacts/rollback_drill_report.json")
    args = parser.parse_args()

    report: dict[str, object] = {"ok": False, "backup_out": args.backup_out, "steps": []}
    backup_path = Path(args.backup_out)
    backup_path.parent.mkdir(parents=True, exist_ok=True)

    _run(
        [
            "python",
            "scripts/db_backup.py",
            "--database-url",
            args.primary_db_url,
            "--out",
            args.backup_out,
        ]
    )
    report["steps"].append({"name": "backup", "ok": True})

    if args.restore_db_url:
        cmd = [
            "python",
            "scripts/db_restore.py",
            "--database-url",
            args.restore_db_url,
            "--in",
            args.backup_out,
        ]
        if args.clean_restore:
            cmd.append("--clean")
        _run(cmd)
        report["steps"].append({"name": "restore", "ok": True})

    report["ok"] = True
    report_path = Path(args.report_out)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
