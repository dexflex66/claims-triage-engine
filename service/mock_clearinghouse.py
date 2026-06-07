"""Local mock clearinghouse for sandboxless integration testing.

Implements:
- POST /api/v1/prior-auth/submit
- GET  /api/v1/prior-auth/{external_ref}/status
- GET  /api/v1/prior-auth/{external_ref}/receipt

Provides two modes:
1) RunningMockServer: real local HTTP server (manual/local environments)
2) InProcessMockClearinghouse: urlopen-compatible in-process transport (CI/sandbox safe)
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse
from uuid import uuid4


_STATUS_PATH_RE = re.compile(r"^/api/v1/prior-auth/([^/]+)/status$")
_RECEIPT_PATH_RE = re.compile(r"^/api/v1/prior-auth/([^/]+)/receipt$")


@dataclass
class SubmissionRecord:
    submission_id: str
    external_ref: str
    idempotency_key: str
    packet: dict
    poll_count: int = 0
    state: str = "submitted"


@dataclass
class MockState:
    submissions_by_external: Dict[str, SubmissionRecord] = field(default_factory=dict)
    external_by_idempotency: Dict[str, str] = field(default_factory=dict)
    request_log: list = field(default_factory=list)


def _next_state(poll_count: int) -> str:
    if poll_count <= 0:
        return "submitted"
    if poll_count == 1:
        return "accepted"
    if poll_count == 2:
        return "processing"
    return "approved"


class MockClearinghouseEngine:
    """Pure request handler independent of network transport."""

    def __init__(self):
        self.state = MockState()

    def _record(self, method: str, path: str, headers: dict, payload: dict | None = None):
        self.state.request_log.append(
            {
                "method": method,
                "path": path,
                "headers": {str(k).lower(): str(v) for k, v in (headers or {}).items()},
                "payload": payload or {},
            }
        )

    def handle(self, method: str, path: str, headers: dict, payload: dict | None = None) -> Tuple[int, dict]:
        method = (method or "").upper()
        payload = payload or {}

        if method == "POST" and path == "/api/v1/prior-auth/submit":
            self._record(method, path, headers, payload)
            idem = str(headers.get("x-idempotency-key") or headers.get("X-Idempotency-Key") or "").strip()
            if not idem:
                return 400, {"error": "missing_idempotency_key"}

            case_id = str(payload.get("case_id") or "").strip()
            if not case_id:
                return 400, {"error": "missing_case_id"}

            existing_external = self.state.external_by_idempotency.get(idem)
            if existing_external:
                rec = self.state.submissions_by_external[existing_external]
                return (
                    200,
                    {
                        "submission_id": rec.submission_id,
                        "external_ref": rec.external_ref,
                        "status": rec.state,
                        "idempotent_replay": True,
                    },
                )

            submission_id = f"sub_{uuid4().hex[:16]}"
            external_ref = f"ext_{uuid4().hex[:12]}"
            rec = SubmissionRecord(
                submission_id=submission_id,
                external_ref=external_ref,
                idempotency_key=idem,
                packet=payload,
            )
            self.state.submissions_by_external[external_ref] = rec
            self.state.external_by_idempotency[idem] = external_ref
            return (
                200,
                {
                    "submission_id": submission_id,
                    "external_ref": external_ref,
                    "status": rec.state,
                },
            )

        m = _STATUS_PATH_RE.match(path)
        if method == "GET" and m:
            external_ref = m.group(1)
            self._record(method, path, headers, payload)
            rec = self.state.submissions_by_external.get(external_ref)
            if rec is None:
                return 404, {"error": "unknown_external_ref"}
            rec.poll_count += 1
            rec.state = _next_state(rec.poll_count)
            return (
                200,
                {
                    "external_ref": rec.external_ref,
                    "status": rec.state,
                    "poll_count": rec.poll_count,
                },
            )

        m = _RECEIPT_PATH_RE.match(path)
        if method == "GET" and m:
            external_ref = m.group(1)
            self._record(method, path, headers, payload)
            rec = self.state.submissions_by_external.get(external_ref)
            if rec is None:
                return 404, {"error": "unknown_external_ref"}
            if rec.state not in {"approved", "denied"}:
                return 409, {"error": "receipt_not_ready", "status": rec.state}
            return (
                200,
                {
                    "external_ref": rec.external_ref,
                    "artifact_ref": f"mock-receipt://{rec.external_ref}",
                    "status": rec.state,
                },
            )

        self._record(method, path, headers, payload)
        return 404, {"error": "not_found"}


class MockClearinghouseHandler(BaseHTTPRequestHandler):
    server_version = "MockClearinghouse/1.0"

    @property
    def engine(self) -> MockClearinghouseEngine:
        return self.server.engine  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args):
        return

    def _read_payload(self) -> dict:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length <= 0:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw) if raw else {}

    def _send(self, status: int, payload: dict):
        data = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):  # noqa: N802
        payload = self._read_payload()
        status, body = self.engine.handle(
            method="POST",
            path=self.path,
            headers={k: v for k, v in self.headers.items()},
            payload=payload,
        )
        self._send(status, body)

    def do_GET(self):  # noqa: N802
        status, body = self.engine.handle(
            method="GET",
            path=self.path,
            headers={k: v for k, v in self.headers.items()},
            payload={},
        )
        self._send(status, body)


class MockClearinghouseServer(ThreadingHTTPServer):
    def __init__(self, server_address):
        super().__init__(server_address, MockClearinghouseHandler)
        self.engine = MockClearinghouseEngine()


class RunningMockServer:
    """Context manager wrapper for the mock clearinghouse HTTP server."""

    def __init__(self, host: str = "127.0.0.1", port: int = 0):
        self.host = host
        self.port = port
        self.server: Optional[MockClearinghouseServer] = None
        self.thread: Optional[threading.Thread] = None

    @property
    def base_url(self) -> str:
        if self.server is None:
            raise RuntimeError("Mock server not started")
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    @property
    def state(self) -> MockState:
        if self.server is None:
            raise RuntimeError("Mock server not started")
        return self.server.engine.state

    def __enter__(self):
        self.server = MockClearinghouseServer((self.host, self.port))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
        if self.thread is not None:
            self.thread.join(timeout=2)


class _InProcessResponse:
    def __init__(self, payload: dict, status: int):
        self._payload = payload
        self.status = status

    def read(self):
        return json.dumps(self._payload, ensure_ascii=True).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class InProcessMockClearinghouse:
    """urlopen-compatible transport without binding sockets."""

    def __init__(self):
        self.engine = MockClearinghouseEngine()

    @property
    def state(self) -> MockState:
        return self.engine.state

    def urlopen(self, req, timeout=10):
        method = req.get_method()
        path = urlparse(req.full_url).path
        headers = {k.lower(): v for k, v in req.header_items()}
        payload = {}
        if getattr(req, "data", None):
            raw = req.data.decode("utf-8")
            payload = json.loads(raw) if raw else {}
        status, body = self.engine.handle(method=method, path=path, headers=headers, payload=payload)
        if status >= 400:
            # Mirror urllib behavior enough for connector retry/error handling.
            raise RuntimeError(f"Mock HTTP error status={status} body={body}")
        return _InProcessResponse(body, status)


def run_mock_server(host: str = "127.0.0.1", port: int = 8089):
    """Run mock clearinghouse in foreground for manual local use."""
    server = MockClearinghouseServer((host, port))
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
