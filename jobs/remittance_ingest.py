"""Batch remittance ingestion job."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List

from db.session import session_scope
from local_claims_core import parse_era_json
from repositories import remittance as remittance_repo


def ingest_era_jsonl(path: str) -> Dict[str, int]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(path)

    ingested = 0
    failed = 0
    with session_scope() as session:
        with p.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                    parsed = parse_era_json(payload)
                    remittance_repo.upsert_remittance(session, parsed)
                    ingested += 1
                except Exception:
                    failed += 1
    return {"ingested": ingested, "failed": failed}
