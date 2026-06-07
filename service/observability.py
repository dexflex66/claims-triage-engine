"""Structured logging + lightweight Prometheus metrics helpers."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Dict

from fastapi import Response

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest

    _HAS_PROMETHEUS = True
except Exception:
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4"
    _HAS_PROMETHEUS = False


_logger = logging.getLogger("payer_proof_claims")

_fallback_counts: Dict[str, int] = {}
_fallback_latency_ms: Dict[str, float] = {}

if _HAS_PROMETHEUS:
    HTTP_REQUESTS = Counter(
        "payer_proof_http_requests_total",
        "Total HTTP requests",
        labelnames=("method", "path", "status"),
    )
    HTTP_LATENCY = Histogram(
        "payer_proof_http_request_duration_seconds",
        "HTTP request latency seconds",
        labelnames=("method", "path"),
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
    )


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("trace_id", "method", "path", "status", "duration_ms", "client_ip"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def configure_logging() -> None:
    if os.environ.get("LOG_JSON", "true").lower() != "true":
        logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
        return
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    root.addHandler(handler)
    root.setLevel(os.environ.get("LOG_LEVEL", "INFO"))


def _fallback_observe(method: str, path: str, status: int, duration_seconds: float) -> None:
    count_key = f'{method}|{path}|{status}'
    _fallback_counts[count_key] = _fallback_counts.get(count_key, 0) + 1
    lat_key = f"{method}|{path}"
    _fallback_latency_ms[lat_key] = _fallback_latency_ms.get(lat_key, 0.0) + (duration_seconds * 1000.0)


def observe_http(method: str, path: str, status: int, duration_seconds: float) -> None:
    if _HAS_PROMETHEUS:
        HTTP_REQUESTS.labels(method=method, path=path, status=str(status)).inc()
        HTTP_LATENCY.labels(method=method, path=path).observe(duration_seconds)
    else:
        _fallback_observe(method, path, status, duration_seconds)


def metrics_response() -> Response:
    if _HAS_PROMETHEUS:
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
    lines = [
        "# HELP payer_proof_http_requests_total Total HTTP requests",
        "# TYPE payer_proof_http_requests_total counter",
    ]
    for key, value in sorted(_fallback_counts.items()):
        method, path, status = key.split("|", 2)
        lines.append(
            f'payer_proof_http_requests_total{{method="{method}",path="{path}",status="{status}"}} {value}'
        )
    return Response(content="\n".join(lines) + "\n", media_type=CONTENT_TYPE_LATEST)


def request_logger() -> logging.Logger:
    return _logger
