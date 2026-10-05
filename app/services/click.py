"""Click (click.uz) integration: premium plan pricing + Merchant API signing.

Click's Merchant API has no SDK -- it calls our webhook twice per payment
(Prepare, then Complete) and authenticates each call with an MD5 signature.
See https://docs.click.uz/en/click-api-request-fields/ for the exact fields.
"""
from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from urllib.parse import urlencode

from app.utils.logger import get_logger
from config import settings

logger = get_logger(__name__)

CLICK_PAY_URL = "https://my.click.uz/services/pay"

# Click Merchant API action codes.
ACTION_PREPARE = 0
ACTION_COMPLETE = 1

# Click Merchant API error codes (subset we actually return).
ERROR_SUCCESS = 0
ERROR_SIGN_FAILED = -1
ERROR_AMOUNT_MISMATCH = -2
ERROR_TRANSACTION_NOT_FOUND = -5
ERROR_ALREADY_PAID = -4
ERROR_TRANSACTION_CANCELLED = -9


@dataclass(frozen=True)
class PremiumPlan:
    tier: str
    label: str
    days: int
    amount: int  # UZS, whole sums (Click works in sums, not tiyin)


PREMIUM_PLANS: dict[str, PremiumPlan] = {
    "premium_1_day": PremiumPlan(tier="premium_1_day", label="1 kun", days=1, amount=8_000),
    "premium_1_week": PremiumPlan(tier="premium_1_week", label="1 hafta", days=7, amount=20_000),
    "premium_1_month": PremiumPlan(tier="premium_1_month", label="1 oy", days=30, amount=37_000),
}


class ClickConfigError(RuntimeError):
    """Raised when Click credentials aren't configured yet."""


def new_merchant_trans_id(telegram_id: int) -> str:
    return f"{telegram_id}-{uuid.uuid4().hex[:10]}"


def build_pay_url(merchant_trans_id: str, amount: int) -> str:
    if not settings.click_service_id or not settings.click_merchant_id:
        raise ClickConfigError("CLICK_SERVICE_ID / CLICK_MERCHANT_ID are not configured")

    params = {
        "service_id": settings.click_service_id,
        "merchant_id": settings.click_merchant_id,
        "amount": amount,
        "transaction_param": merchant_trans_id,
    }
    return f"{CLICK_PAY_URL}?{urlencode(params)}"


def _sign(*parts: str) -> str:
    return hashlib.md5("".join(parts).encode("utf-8")).hexdigest()


def verify_prepare_signature(data: dict) -> bool:
    expected = _sign(
        str(data.get("click_trans_id", "")),
        str(data.get("service_id", "")),
        settings.click_secret_key,
        str(data.get("merchant_trans_id", "")),
        str(data.get("amount", "")),
        str(data.get("action", "")),
        str(data.get("sign_time", "")),
    )
    return expected == data.get("sign_string")


def verify_complete_signature(data: dict) -> bool:
    expected = _sign(
        str(data.get("click_trans_id", "")),
        str(data.get("service_id", "")),
        settings.click_secret_key,
        str(data.get("merchant_trans_id", "")),
        str(data.get("merchant_prepare_id", "")),
        str(data.get("amount", "")),
        str(data.get("action", "")),
        str(data.get("sign_time", "")),
    )
    return expected == data.get("sign_string")
