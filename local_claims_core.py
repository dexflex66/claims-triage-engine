"""Explicit loader for local core modules to avoid namespace collision with QuEST core."""
from __future__ import annotations

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
import sys

_ROOT = Path(__file__).resolve().parent


def _load(rel_path: str, alias: str):
    path = _ROOT / rel_path
    spec = spec_from_file_location(alias, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {rel_path}")
    mod = module_from_spec(spec)
    sys.modules[alias] = mod
    spec.loader.exec_module(mod)
    return mod


_packet_builder = _load("core/packet_builder.py", "claims_packet_builder")
_outcome_capture = _load("core/outcome_capture.py", "claims_outcome_capture")
_remittance_parser = _load("core/remittance_parser.py", "claims_remittance_parser")

build_approval_packet = _packet_builder.build_approval_packet
validate_packet_citations = _packet_builder.validate_packet_citations

record_outcome = _outcome_capture.record_outcome
get_outcomes_by_payer_code = _outcome_capture.get_outcomes_by_payer_code

ParsedRemittance = _remittance_parser.ParsedRemittance
parse_era_json = _remittance_parser.parse_era_json
parse_835_text = _remittance_parser.parse_835_text
