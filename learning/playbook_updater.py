"""Closed-loop learning playbook updater."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import sys

_here = Path(__file__).resolve().parent
_root = _here.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from local_claims_core import get_outcomes_by_payer_code  # noqa: E402

_PLAYBOOKS_DIR = Path(__file__).resolve().parent.parent / "data" / "playbooks"


def _ensure_playbooks_dir() -> None:
    _PLAYBOOKS_DIR.mkdir(parents=True, exist_ok=True)


def load_playbook(payer_id: str, procedure_code: str) -> Dict[str, Any]:
    _ensure_playbooks_dir()
    path = _PLAYBOOKS_DIR / f"{payer_id}_{procedure_code}.json"
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "payer_id": payer_id,
        "procedure_code": procedure_code,
        "approval_count": 0,
        "denial_count": 0,
        "denial_reason_counts": {},
        "requested_addenda_counts": {},
        "suggested_evidence_hints": [],
    }


def _upsert_db_playbook(playbook: Dict[str, Any]) -> None:
    try:
        from sqlalchemy import select

        from db.models import Playbook
        from db.session import session_scope

        with session_scope() as session:
            row = session.execute(
                select(Playbook).where(
                    Playbook.payer_id == playbook["payer_id"],
                    Playbook.procedure_code == playbook["procedure_code"],
                )
            ).scalar_one_or_none()
            if row is None:
                row = Playbook(
                    payer_id=playbook["payer_id"],
                    procedure_code=playbook["procedure_code"],
                    payload=playbook,
                )
                session.add(row)
            else:
                row.payload = playbook
    except Exception:
        # Keep file persistence as fallback.
        pass


def update_playbook_from_outcomes(payer_id: str, procedure_code: str) -> Dict[str, Any]:
    outcomes = get_outcomes_by_payer_code(payer_id, procedure_code)
    playbook = load_playbook(payer_id, procedure_code)

    playbook["approval_count"] = sum(1 for o in outcomes if o.get("outcome") == "approved")
    playbook["denial_count"] = sum(1 for o in outcomes if o.get("outcome") == "denied")

    denial_reason_counts: Dict[str, int] = {}
    addenda_counts: Dict[str, int] = {}
    for o in outcomes:
        for r in o.get("reason_codes") or []:
            denial_reason_counts[r] = denial_reason_counts.get(r, 0) + 1
        for a in o.get("requested_addenda") or []:
            addenda_counts[a] = addenda_counts.get(a, 0) + 1

    playbook["denial_reason_counts"] = denial_reason_counts
    playbook["requested_addenda_counts"] = addenda_counts

    _ensure_playbooks_dir()
    path = _PLAYBOOKS_DIR / f"{payer_id}_{procedure_code}.json"
    with path.open("w", encoding="utf-8") as f:
        json.dump(playbook, f, indent=2)

    _upsert_db_playbook(playbook)
    return playbook
