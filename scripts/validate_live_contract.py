"""Validate live connector environment against provider contract."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from service.provider_contract import load_contract, validate_live_contract_env


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract", default="us_278_837")
    args = parser.parse_args()

    contract = load_contract(args.contract)
    result = validate_live_contract_env(contract)
    print({"ok": result.ok, "errors": result.errors, "warnings": result.warnings})
    if not result.ok:
        raise SystemExit(2)
