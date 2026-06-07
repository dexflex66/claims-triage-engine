"""Initialize DB schema for payer_proof_claims."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db.models import Base
from db.session import engine


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("schema_initialized")
