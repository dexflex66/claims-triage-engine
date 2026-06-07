"""Run local mock clearinghouse for sandboxless connector testing."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.mock_clearinghouse import run_mock_server


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8089)
    args = parser.parse_args()
    print(f"mock_clearinghouse_listening http://{args.host}:{args.port}")
    run_mock_server(host=args.host, port=args.port)
