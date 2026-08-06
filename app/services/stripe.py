"""Stripe integration: checkout sessions + webhook signature verification."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass

import stripe

from app.utils.logger import get_logger
from config import settings

logger = get_logger(__name__)

stripe.api_key = settings.stripe_secret_key

# Tier -> (display duration in days, Stripe Price ID)
TIER_PRICE_MAP: dict[str, str] = {
    "1_week": settings.stripe_price_1_week,
    "1_month": settings.stripe_price_1_month,
    "3_months": settings.stripe_price_3_months,
    "6_months": settings.stripe_price_6_months,
    "1_year": settings.stripe_price_1_year,
}

TIER_DAYS: dict[str, int] = {
    "1_week": 7,
    "1_month": 30,
    "3_months": 90,
    "6_months": 180,
    "1_year": 365,
}

PRICE_TO_TIER: dict[str, str] = {v: k for k, v in TIER_PRICE_MAP.items() if v}


class StripeConfigError(RuntimeError):
    """Raised when a requested tier has no configured Stripe Price ID."""


@dataclass
class CheckoutSession:
    id: str
    url: str


async def create_checkout_session(
    telegram_id: int,
    tier: str,
    success_url: str,
    cancel_url: str,
    customer_email: str | None = None,
) -> CheckoutSession:
    price_id = TIER_PRICE_MAP.get(tier)
    if not price_id:
        raise StripeConfigError(f"No Stripe price configured for tier={tier!r}")

    def _create() -> stripe.checkout.Session:
        return stripe.checkout.Session.create(
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=success_url,
            cancel_url=cancel_url,
            client_reference_id=str(telegram_id),
            customer_email=customer_email,
            metadata={"telegram_id": str(telegram_id), "tier": tier},
        )

    session = await asyncio.to_thread(_create)
    return CheckoutSession(id=session.id, url=session.url)


def construct_webhook_event(payload: bytes, sig_header: str) -> stripe.Event:
    return stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)


def tier_for_price_id(price_id: str) -> str | None:
    return PRICE_TO_TIER.get(price_id)
