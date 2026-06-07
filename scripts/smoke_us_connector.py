"""Smoke check for US278 connector transport."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from connectors.us_278_837 import US278837Connector


if __name__ == "__main__":
    c = US278837Connector()
    ack = c.submit({"case_id": "SMOKE-1"}, idempotency_key="smoke-idem-1")
    print({"mode": "live" if c.live_mode else "stub", "submission_id": ack.submission_id, "external_ref": ack.external_ref, "status": ack.status})
