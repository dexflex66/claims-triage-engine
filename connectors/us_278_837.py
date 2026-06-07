"""US 278/837 connector with live HTTP transport + safe fallback.

Live mode is enabled when US278_BASE_URL is configured. Otherwise, the connector
returns deterministic stub responses so non-prod flows keep working.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

from connectors.base import ReceiptArtifact, StatusUpdate, SubmissionAck
from connectors.us_278_837_mapper import (
    build_submit_payload,
    parse_receipt_response,
    parse_status_response,
    parse_submit_response,
)
from service.provider_contract import enforce_live_contract, load_contract


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_int(v: str, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _safe_float(v: str, default: float) -> float:
    try:
        return float(v)
    except Exception:
        return default


class US278837Connector:
    """Connector for US clearinghouse-style prior auth transport."""

    channel = "us_278_837"

    _status_map = {
        "queued": "queued",
        "submitted": "submitted",
        "accepted": "acknowledged",
        "ack": "acknowledged",
        "acknowledged": "acknowledged",
        "processing": "processing",
        "approved": "approved",
        "denied": "denied",
        "failed": "failed",
        "error": "failed",
        "timeout": "timeout",
    }

    def __init__(self) -> None:
        self.contract = load_contract("us_278_837")
        self.base_url = os.environ.get("US278_BASE_URL", "").rstrip("/")
        self.submit_path = os.environ.get("US278_SUBMIT_PATH", "/api/v1/prior-auth/submit")
        self.status_path_template = os.environ.get("US278_STATUS_PATH_TEMPLATE", "/api/v1/prior-auth/{external_ref}/status")
        self.receipt_path_template = os.environ.get("US278_RECEIPT_PATH_TEMPLATE", "/api/v1/prior-auth/{external_ref}/receipt")
        self.api_token = os.environ.get("US278_API_TOKEN", "")
        self.hmac_secret = os.environ.get("US278_HMAC_SECRET", "")
        self.hmac_key_id = os.environ.get("US278_HMAC_KEY_ID", "")
        self.timeout_seconds = _safe_float(os.environ.get("US278_TIMEOUT_SECONDS", "10"), 10.0)
        self.max_retries = _safe_int(os.environ.get("US278_MAX_RETRIES", "3"), 3)
        self.backoff_seconds = _safe_float(os.environ.get("US278_BACKOFF_SECONDS", "0.5"), 0.5)
        self.enforce_contract = os.environ.get("US278_ENFORCE_CONTRACT", "true").lower() == "true"
        contract_status = self.contract.get("status_mapping")
        if isinstance(contract_status, dict) and contract_status:
            self._status_map = {str(k).lower(): str(v) for k, v in contract_status.items()}
        if self.live_mode and self.enforce_contract:
            enforce_live_contract("us_278_837")

    @property
    def live_mode(self) -> bool:
        return bool(self.base_url)

    def _normalize_status(self, status: str) -> str:
        s = str(status or "").strip().lower()
        return self._status_map.get(s, "processing")

    def _sign_headers(self, method: str, path: str, body: bytes, idempotency_key: str, timestamp: str) -> Dict[str, str]:
        if not self.hmac_secret:
            return {}
        body_hash = hashlib.sha256(body).hexdigest()
        canonical = "\n".join([method.upper(), path, timestamp, idempotency_key or "", body_hash])
        signature = hmac.new(self.hmac_secret.encode("utf-8"), canonical.encode("utf-8"), hashlib.sha256).hexdigest()
        headers = {
            "X-Quest-Signature": signature,
            "X-Quest-Timestamp": timestamp,
        }
        if self.hmac_key_id:
            headers["X-Quest-Key-Id"] = self.hmac_key_id
        return headers

    def _request_json(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        idempotency_key: str = "",
    ) -> Dict[str, Any]:
        if not self.base_url:
            raise RuntimeError("Live transport is not configured")

        url = urljoin(self.base_url + "/", path.lstrip("/"))
        body = json.dumps(payload or {}, ensure_ascii=True).encode("utf-8") if payload is not None else b""
        ts = _now()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Idempotency-Key": idempotency_key,
            "X-Request-Timestamp": ts,
            "X-Connector-Channel": self.channel,
        }
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        headers.update(self._sign_headers(method, path, body, idempotency_key, ts))

        last_err = None
        for attempt in range(1, self.max_retries + 1):
            req = Request(url=url, data=body if body else None, method=method.upper(), headers=headers)
            try:
                with urlopen(req, timeout=self.timeout_seconds) as resp:
                    raw = resp.read().decode("utf-8")
                    data = json.loads(raw) if raw else {}
                    data.setdefault("_http_status", getattr(resp, "status", 200))
                    data.setdefault("_attempt", attempt)
                    return data
            except HTTPError as exc:
                last_err = exc
                if exc.code in {429, 500, 502, 503, 504} and attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * attempt)
                    continue
                detail = exc.read().decode("utf-8") if hasattr(exc, "read") else str(exc)
                raise RuntimeError(f"US278 HTTPError code={exc.code} detail={detail}") from exc
            except URLError as exc:
                last_err = exc
                if attempt < self.max_retries:
                    time.sleep(self.backoff_seconds * attempt)
                    continue
                raise RuntimeError(f"US278 URLError: {exc}") from exc

        raise RuntimeError(f"US278 request failed after retries: {last_err}")

    def submit(self, packet, idempotency_key: str) -> SubmissionAck:
        submit_payload = build_submit_payload(packet, self.contract)
        if not self.live_mode:
            sid = f"sub_{uuid4().hex[:16]}"
            ext = f"us278_{uuid4().hex[:12]}"
            return SubmissionAck(
                submission_id=sid,
                external_ref=ext,
                status="submitted",
                raw_payload={
                    "channel": self.channel,
                    "mode": "stub",
                    "idempotency_key": idempotency_key,
                    "accepted_at": _now(),
                    "packet_case_id": submit_payload.get("case_id"),
                    "submit_payload": submit_payload,
                },
            )

        response = self._request_json("POST", self.submit_path, payload=submit_payload, idempotency_key=idempotency_key)
        parsed = parse_submit_response(response, self.contract)
        submission_id = str(parsed.get("submission_id") or f"sub_{uuid4().hex[:16]}")
        external_ref = str(parsed.get("external_ref") or "")
        if not external_ref:
            external_ref = f"us278_{uuid4().hex[:12]}"
        status = self._normalize_status(str(parsed.get("status") or "submitted"))
        return SubmissionAck(
            submission_id=submission_id,
            external_ref=external_ref,
            status=status,
            raw_payload={"channel": self.channel, "mode": "live", "submit_payload": submit_payload, **response},
        )

    def poll_status(self, external_ref: str) -> StatusUpdate:
        if not self.live_mode:
            return StatusUpdate(
                external_ref=external_ref,
                status="acknowledged",
                raw_payload={"channel": self.channel, "mode": "stub", "status_checked_at": _now()},
            )

        path = self.status_path_template.format(external_ref=external_ref)
        response = self._request_json("GET", path, payload=None, idempotency_key=f"status:{external_ref}")
        parsed = parse_status_response(response, self.contract)
        status = self._normalize_status(str(parsed.get("status") or "processing"))
        return StatusUpdate(
            external_ref=external_ref,
            status=status,
            raw_payload={"channel": self.channel, "mode": "live", **response},
        )

    def fetch_receipt(self, external_ref: str) -> ReceiptArtifact:
        if not self.live_mode:
            return ReceiptArtifact(
                external_ref=external_ref,
                artifact_ref=f"receipt://{self.channel}/{external_ref}",
                raw_payload={"channel": self.channel, "mode": "stub", "receipt_fetched_at": _now()},
            )

        path = self.receipt_path_template.format(external_ref=external_ref)
        response = self._request_json("GET", path, payload=None, idempotency_key=f"receipt:{external_ref}")
        parsed = parse_receipt_response(response, self.contract)
        artifact_ref = str(parsed.get("artifact_ref") or "")
        if not artifact_ref:
            artifact_ref = f"receipt://{self.channel}/{external_ref}"
        return ReceiptArtifact(
            external_ref=external_ref,
            artifact_ref=artifact_ref,
            raw_payload={"channel": self.channel, "mode": "live", **response},
        )
