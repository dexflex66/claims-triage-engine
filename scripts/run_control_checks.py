"""Run transport + key rotation control checks."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.security.key_rotation import validate_key_rotation
from service.security.production_guard import validate_production_controls
from service.security.transport_controls import validate_transport_controls


if __name__ == "__main__":
    validate_transport_controls()
    validate_key_rotation()
    validate_production_controls()
    print({"ok": True})
