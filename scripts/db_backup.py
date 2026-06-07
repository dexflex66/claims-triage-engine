"""Create a PostgreSQL backup using pg_dump custom format."""
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
        raise SystemExit("DATABASE_URL must be postgresql:// or postgresql+psycopg:// for backup")
    return url


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True, help="Backup path, e.g. backups/payer_proof_claims.dump")
    parser.add_argument("--database-url", default="", help="Overrides DATABASE_URL")
    args = parser.parse_args()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    url = _database_url(args.database_url)
    url = url.replace("postgresql+psycopg://", "postgresql://", 1)

    cmd = ["pg_dump", "--format=custom", "--no-owner", "--no-privileges", "--file", str(out), url]
    subprocess.run(cmd, check=True)
    print({"ok": True, "backup_file": str(out)})


if __name__ == "__main__":
    main()
