"""Shared money/date formatting helpers for bot replies."""
from __future__ import annotations

from datetime import date
from decimal import Decimal

from app.models.category import DEFAULT_CATEGORIES

CATEGORY_EMOJI = {**DEFAULT_CATEGORIES}


def format_money(amount: Decimal, currency: str = "UZS") -> str:
    if amount == amount.to_integral_value():
        formatted = f"{int(amount):,}"
    else:
        formatted = f"{amount:,.2f}"
    return f"{formatted} {currency}"


def category_emoji(category: str) -> str:
    return CATEGORY_EMOJI.get(category, "📌")


def format_category_label(category: str) -> str:
    return f"{category_emoji(category)} {category.replace('_', ' ').title()}"


def format_date(value: date) -> str:
    return value.strftime("%b %d, %Y")
