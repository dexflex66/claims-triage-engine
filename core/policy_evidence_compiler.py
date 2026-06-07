"""
Policy evidence compiler. To avoid QuEST 'core' being shadowed by this package,
use the top-level compiler module::

  from compiler import compile_case, load_policy, Policy

Then pass compile_case(...) result to core.missing_evidence_engine and core.packet_builder.
"""
from __future__ import annotations
