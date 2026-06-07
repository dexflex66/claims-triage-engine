"""Payment posting adapter interfaces."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Protocol


@dataclass
class PaymentPostResult:
    payment_post_id: str
    rail: str
    status: str
    external_ref: str
    raw_payload: Dict[str, Any]


class PaymentPostingAdapter(Protocol):
    def post_payment(self, payload: Dict[str, Any], idempotency_key: str) -> PaymentPostResult:
        raise NotImplementedError
