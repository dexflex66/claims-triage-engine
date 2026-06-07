"""Connector interface for payer submissions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol


@dataclass
class SubmissionAck:
    submission_id: str
    external_ref: str
    status: str
    raw_payload: Dict[str, Any]


@dataclass
class StatusUpdate:
    external_ref: str
    status: str
    raw_payload: Dict[str, Any]


@dataclass
class ReceiptArtifact:
    external_ref: str
    artifact_ref: str
    raw_payload: Dict[str, Any]


class SubmissionConnector(Protocol):
    """Connector contract for all payer integrations."""

    def submit(self, packet: Dict[str, Any], idempotency_key: str) -> SubmissionAck:
        raise NotImplementedError

    def poll_status(self, external_ref: str) -> StatusUpdate:
        raise NotImplementedError

    def fetch_receipt(self, external_ref: str) -> ReceiptArtifact:
        raise NotImplementedError
