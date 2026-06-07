"""Smoke check for India preauth connector transport."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from connectors.india_preauth import IndiaPreauthConnector


if __name__ == "__main__":
    c = IndiaPreauthConnector()
    ack = c.submit({"case_id": "SMOKE-IN-1", "payer_id": "STAR"}, idempotency_key="smoke-in-idem-1")
    print(
        {
            "mode": "live" if c.live_mode else "stub",
            "submission_id": ack.submission_id,
            "external_ref": ack.external_ref,
            "status": ack.status,
        }
    )
