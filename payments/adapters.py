"""Payment adapters for ACH, virtual card, and ERP posting."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from urllib.parse import urljoin
from urllib.request import Request, urlopen
from uuid import uuid4

from payments.base import PaymentPostResult


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class _HttpRailAdapter:
    rail = "http"

    def __init__(self, base_url_env: str, token_env: str, path_env: str, default_path: str):
        self.base_url = os.environ.get(base_url_env, "").rstrip("/")
        self.token = os.environ.get(token_env, "")
        self.path = os.environ.get(path_env, default_path)

    @property
    def live_mode(self) -> bool:
        return bool(self.base_url)

    def _post_http(self, payload: dict, idempotency_key: str) -> dict:
        url = urljoin(self.base_url + "/", self.path.lstrip("/"))
        body = json.dumps(payload, ensure_ascii=True).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Idempotency-Key": idempotency_key,
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        req = Request(url=url, data=body, method="POST", headers=headers)
        with urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}


class ACHAdapter(_HttpRailAdapter):
    rail = "ach"

    def __init__(self):
        super().__init__("ACH_POST_BASE_URL", "ACH_POST_API_TOKEN", "ACH_POST_PATH", "/api/v1/payments/ach")

    def post_payment(self, payload: dict, idempotency_key: str) -> PaymentPostResult:
        if not self.live_mode:
            pid = f"pay_{uuid4().hex[:16]}"
            return PaymentPostResult(
                payment_post_id=pid,
                rail=self.rail,
                status="posted",
                external_ref=f"ach_{uuid4().hex[:12]}",
                raw_payload={"mode": "stub", "posted_at": _now(), "payload": payload},
            )
        data = self._post_http(payload, idempotency_key)
        return PaymentPostResult(
            payment_post_id=str(data.get("payment_post_id") or f"pay_{uuid4().hex[:16]}"),
            rail=self.rail,
            status=str(data.get("status") or "posted"),
            external_ref=str(data.get("external_ref") or data.get("payment_id") or ""),
            raw_payload={"mode": "live", **data},
        )


class VirtualCardAdapter(_HttpRailAdapter):
    rail = "virtual_card"

    def __init__(self):
        super().__init__("VCARD_POST_BASE_URL", "VCARD_POST_API_TOKEN", "VCARD_POST_PATH", "/api/v1/payments/virtual-card")

    def post_payment(self, payload: dict, idempotency_key: str) -> PaymentPostResult:
        if not self.live_mode:
            pid = f"pay_{uuid4().hex[:16]}"
            return PaymentPostResult(
                payment_post_id=pid,
                rail=self.rail,
                status="posted",
                external_ref=f"vcard_{uuid4().hex[:12]}",
                raw_payload={"mode": "stub", "posted_at": _now(), "payload": payload},
            )
        data = self._post_http(payload, idempotency_key)
        return PaymentPostResult(
            payment_post_id=str(data.get("payment_post_id") or f"pay_{uuid4().hex[:16]}"),
            rail=self.rail,
            status=str(data.get("status") or "posted"),
            external_ref=str(data.get("external_ref") or data.get("payment_id") or ""),
            raw_payload={"mode": "live", **data},
        )


class ERPPostingAdapter(_HttpRailAdapter):
    rail = "erp"

    def __init__(self):
        super().__init__("ERP_POST_BASE_URL", "ERP_POST_API_TOKEN", "ERP_POST_PATH", "/api/v1/erp/payment-postings")

    def post_payment(self, payload: dict, idempotency_key: str) -> PaymentPostResult:
        if not self.live_mode:
            pid = f"pay_{uuid4().hex[:16]}"
            return PaymentPostResult(
                payment_post_id=pid,
                rail=self.rail,
                status="posted",
                external_ref=f"erp_{uuid4().hex[:12]}",
                raw_payload={"mode": "stub", "posted_at": _now(), "payload": payload},
            )
        data = self._post_http(payload, idempotency_key)
        return PaymentPostResult(
            payment_post_id=str(data.get("payment_post_id") or f"pay_{uuid4().hex[:16]}"),
            rail=self.rail,
            status=str(data.get("status") or "posted"),
            external_ref=str(data.get("external_ref") or data.get("entry_id") or ""),
            raw_payload={"mode": "live", **data},
        )


def get_payment_adapter(rail: str):
    r = (rail or "").strip().lower()
    if r == "ach":
        return ACHAdapter()
    if r == "virtual_card":
        return VirtualCardAdapter()
    if r == "erp":
        return ERPPostingAdapter()
    raise ValueError(f"unsupported_payment_rail:{rail}")
