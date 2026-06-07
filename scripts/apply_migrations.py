"""Apply SQL migrations in db/migrations in lexical order."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from sqlalchemy import text

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import engine

MIGRATIONS_DIR = ROOT / "db" / "migrations"


def _split_sql(sql: str) -> list[str]:
    return [stmt.strip() for stmt in sql.split(";") if stmt.strip()]


def main() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    if not migration_files:
        print({"ok": True, "applied": []})
        return

    applied: list[str] = []
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  version VARCHAR(128) PRIMARY KEY,
                  applied_at VARCHAR(64) NOT NULL
                )
                """
            )
        )
        rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
        existing = {str(r[0]) for r in rows}

        for path in migration_files:
            version = path.stem
            if version in existing:
                continue

            sql = path.read_text(encoding="utf-8")
            for stmt in _split_sql(sql):
                conn.exec_driver_sql(stmt)
            conn.execute(
                text("INSERT INTO schema_migrations(version, applied_at) VALUES (:v, :ts)"),
                {"v": version, "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")},
            )
            applied.append(version)

    print({"ok": True, "applied": applied})


if __name__ == "__main__":
    main()
