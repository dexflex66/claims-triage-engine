"""Check DB readiness for production (engine connectivity + migrations applied)."""
from __future__ import annotations

import os
from pathlib import Path
import sys

from sqlalchemy import inspect, text

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.session import engine

MIGRATIONS_DIR = ROOT / "db" / "migrations"


def main() -> None:
    db_url = os.environ.get("DATABASE_URL", "")
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    expected = [p.stem for p in migration_files]

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
        inspector = inspect(conn)
        table_exists = inspector.has_table("schema_migrations")

        applied = set()
        if table_exists:
            rows = conn.execute(text("SELECT version FROM schema_migrations")).fetchall()
            applied = {str(r[0]) for r in rows}

    pending = [v for v in expected if v not in applied]
    ok = len(pending) == 0
    print({"ok": ok, "database_url": db_url, "pending_migrations": pending, "applied_count": len(applied)})
    if not ok:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
