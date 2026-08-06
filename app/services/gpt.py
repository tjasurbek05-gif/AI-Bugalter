"""GPT wrapper: expense parsing (GPT-4 Mini) + monthly insights (GPT-4)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from app.models.category import DEFAULT_CATEGORIES
from app.services.whisper import get_openai_client
from app.utils.logger import get_logger
from config import settings

logger = get_logger(__name__)

CATEGORY_NAMES = list(DEFAULT_CATEGORIES.keys())


class ParsingError(RuntimeError):
    """Raised when GPT fails to return a usable, well-formed expense."""


@dataclass
class ParsedExpense:
    amount: Decimal
    category: str
    description: str
    currency: str = "UZS"


_EXPENSE_SYSTEM_PROMPT = (
    "You extract a single expense from a short, informal message (often a voice "
    "transcript, possibly in Russian, Uzbek, or English). "
    f"Pick `category` from exactly this list: {', '.join(CATEGORY_NAMES)}. "
    "If nothing fits well, use 'other'. "
    "Respond with ONLY a JSON object: "
    '{"amount": <number>, "currency": "<3-letter code, default UZS>", '
    '"category": "<one of the allowed categories>", "description": "<short description>"}. '
    "Amount must be a plain positive number (no thousands separators, no currency symbol)."
)

_INSIGHTS_SYSTEM_PROMPT = (
    "You are a friendly personal finance assistant. Given a user's spending by "
    "category for the current month, write 2-3 short, actionable, encouraging "
    "insights. Reply in {language}. Keep each insight to one sentence. "
    "Respond with ONLY a JSON object: {\"insights\": [\"...\", \"...\"]}."
)


async def parse_expense(transcription: str) -> ParsedExpense:
    """Parse a freeform transcription into a structured expense via GPT-4 Mini."""
    client = get_openai_client()
    try:
        response = await client.chat.completions.create(
            model=settings.gpt_parse_model,
            messages=[
                {"role": "system", "content": _EXPENSE_SYSTEM_PROMPT},
                {"role": "user", "content": transcription},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        logger.warning("gpt_parse_failed", exc_info=exc)
        raise ParsingError(f"Could not parse expense: {exc}") from exc

    return _to_parsed_expense(data)


def _to_parsed_expense(data: dict) -> ParsedExpense:
    try:
        amount = Decimal(str(data["amount"]))
    except (KeyError, InvalidOperation, TypeError) as exc:
        raise ParsingError(f"Invalid or missing amount in GPT response: {data!r}") from exc

    if amount <= 0:
        raise ParsingError(f"Amount must be positive, got {amount}")

    category = str(data.get("category", "other")).lower().strip()
    if category not in CATEGORY_NAMES:
        category = "other"

    description = str(data.get("description", "")).strip()
    currency = str(data.get("currency", "UZS")).upper().strip()[:3] or "UZS"

    return ParsedExpense(amount=amount, category=category, description=description, currency=currency)


async def generate_monthly_insights(
    category_totals: dict[str, Decimal], language: str = "ru"
) -> list[str]:
    """Generate 2-3 short AI insights about the month's spending."""
    if not category_totals:
        return []

    client = get_openai_client()
    summary_lines = "\n".join(f"{cat}: {total}" for cat, total in category_totals.items())

    try:
        response = await client.chat.completions.create(
            model=settings.gpt_insights_model,
            messages=[
                {
                    "role": "system",
                    "content": _INSIGHTS_SYSTEM_PROMPT.format(language=language),
                },
                {"role": "user", "content": summary_lines},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        insights = data.get("insights", [])
        return [str(i) for i in insights][:3]
    except Exception as exc:  # noqa: BLE001
        logger.warning("gpt_insights_failed", exc_info=exc)
        return []
