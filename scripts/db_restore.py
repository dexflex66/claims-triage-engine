"""Restore PostgreSQL backup created by scripts/db_backup.py."""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


def _database_url(arg_url: str) -> str:
    url = (arg_url or "").strip() or os.environ.get("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL is required")
    if not url.startswith("postgresql"):
        raise SystemExit("DATABASE_URL must be postgresql:// or postgresql+psycopg:// for restore")
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--in", dest="in_file", required=True, help="Backup file path")
    parser.add_argument("--database-url", default="", help="Overrides DATABASE_URL")
    parser.add_argument("--clean", action="store_true", help="Drop existing DB objects before restore")
    args = parser.parse_args()

    backup_file = Path(args.in_file)
    if not backup_file.exists():
        raise SystemExit(f"Backup file not found: {backup_file}")
    url = _database_url(args.database_url)

    cmd = ["pg_restore", "--no-owner", "--no-privileges"]
    if args.clean:
        cmd.append("--clean")
    cmd.extend(["--dbname", url, str(backup_file)])
    subprocess.run(cmd, check=True)
    print({"ok": True, "restored_from": str(backup_file), "clean": args.clean})


if __name__ == "__main__":
    main()
