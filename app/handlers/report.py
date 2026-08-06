"""Phase 3: /report — monthly category breakdown + AI-generated insights."""
from __future__ import annotations

from decimal import Decimal

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from app.models.user import User
from app.services.db import get_expenses_for_month
from app.services.gpt import generate_monthly_insights
from app.utils.decorators import check_subscription, log_errors
from app.utils.formatting import format_category_label, format_money

router = Router(name="report")


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def _totals_by_category(expenses) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for expense in expenses:
        totals[expense.category] = totals.get(expense.category, Decimal(0)) + expense.amount
    return totals


@router.message(Command("report"))
@log_errors
@check_subscription(min_tier="paid")
async def monthly_report(message: Message, user: User, session) -> None:
    now = message.date
    expenses = await get_expenses_for_month(session, user.id, now.year, now.month)

    if not expenses:
        await message.answer("📭 No expenses yet this month — nothing to report on!")
        return

    totals = _totals_by_category(expenses)
    grand_total = sum(totals.values(), Decimal(0))

    prev_year, prev_month = _previous_month(now.year, now.month)
    prev_expenses = await get_expenses_for_month(session, user.id, prev_year, prev_month)
    prev_totals = _totals_by_category(prev_expenses)

    lines = ["📊 Your Money This Month\n"]
    for category, total in sorted(totals.items(), key=lambda kv: kv[1], reverse=True):
        pct = (total / grand_total * 100) if grand_total else Decimal(0)
        trend = _trend_marker(total, prev_totals.get(category))
        lines.append(f"{format_category_label(category)}: {format_money(total)} ({pct:.0f}%){trend}")

    insights = await generate_monthly_insights(totals, language=user.language_code or "ru")
    if insights:
        lines.append("\n💡 Insights:")
        lines.extend(f"• {insight}" for insight in insights)

    lines.append(f"\n💰 Total: {format_money(grand_total)}")
    await message.answer("\n".join(lines))


def _trend_marker(current: Decimal, previous: Decimal | None) -> str:
    if previous is None or previous == 0:
        return ""
    change_pct = (current - previous) / previous * 100
    if change_pct >= 10:
        return f" 📈 +{change_pct:.0f}%"
    if change_pct <= -10:
        return f" 📉 {change_pct:.0f}%"
    return ""
