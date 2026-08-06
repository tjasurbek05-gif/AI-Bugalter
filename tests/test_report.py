from decimal import Decimal

from app.handlers.report import _previous_month, _totals_by_category, _trend_marker
from app.services.db import create_expense, get_expenses_for_month, get_or_create_user


class FakeExpense:
    def __init__(self, category: str, amount: Decimal) -> None:
        self.category = category
        self.amount = amount


class TestTotalsByCategory:
    def test_sums_per_category(self):
        expenses = [
            FakeExpense("food", Decimal("100")),
            FakeExpense("food", Decimal("50")),
            FakeExpense("transport", Decimal("20")),
        ]
        totals = _totals_by_category(expenses)
        assert totals == {"food": Decimal("150"), "transport": Decimal("20")}

    def test_empty_list(self):
        assert _totals_by_category([]) == {}


class TestPreviousMonth:
    def test_regular_month(self):
        assert _previous_month(2026, 8) == (2026, 7)

    def test_january_wraps_to_previous_year_december(self):
        assert _previous_month(2026, 1) == (2025, 12)


class TestTrendMarker:
    def test_no_previous_data(self):
        assert _trend_marker(Decimal("100"), None) == ""

    def test_previous_zero(self):
        assert _trend_marker(Decimal("100"), Decimal("0")) == ""

    def test_significant_increase(self):
        marker = _trend_marker(Decimal("150"), Decimal("100"))
        assert "📈" in marker
        assert "+50%" in marker

    def test_significant_decrease(self):
        marker = _trend_marker(Decimal("50"), Decimal("100"))
        assert "📉" in marker
        assert "-50%" in marker

    def test_small_change_no_marker(self):
        assert _trend_marker(Decimal("103"), Decimal("100")) == ""


class TestMonthlyAggregationAcrossMonths:
    async def test_expenses_isolated_by_month(self, db_session):
        user = await get_or_create_user(db_session, telegram_id=99)
        await create_expense(db_session, user_id=user.id, amount=Decimal("1000"), category="food")

        from datetime import datetime

        now = datetime.utcnow()
        this_month = await get_expenses_for_month(db_session, user.id, now.year, now.month)
        prev_year, prev_month = _previous_month(now.year, now.month)
        last_month = await get_expenses_for_month(db_session, user.id, prev_year, prev_month)

        assert len(this_month) == 1
        assert len(last_month) == 0
