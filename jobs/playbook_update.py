"""Playbook refresh from outcomes."""
from __future__ import annotations

from db.session import session_scope
from learning.playbook_updater import update_playbook_from_outcomes


def refresh_playbook(payer_id: str, procedure_code: str) -> dict:
    # Uses existing learning logic; this wrapper keeps an explicit job entrypoint.
    return update_playbook_from_outcomes(payer_id, procedure_code)
