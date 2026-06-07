"""Import ERA-like JSONL remittance records."""
from __future__ import annotations

import argparse

from jobs.remittance_ingest import ingest_era_jsonl


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    args = parser.parse_args()
    print(ingest_era_jsonl(args.input))
