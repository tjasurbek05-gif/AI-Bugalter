import json
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.db import (
    count_expenses_this_month,
    create_expense,
    get_or_create_user,
    sum_expenses_this_month,
)
from app.services.gpt import ParsingError, _to_parsed_expense, parse_expense
from app.utils.validators import ValidationError, validate_amount


def _fake_openai_response(payload: dict) -> SimpleNamespace:
    message = SimpleNamespace(content=json.dumps(payload))
    return SimpleNamespace(choices=[SimpleNamespace(message=message)])


class TestValidateAmount:
    def test_accepts_plain_number(self):
        assert validate_amount("50000") == Decimal("50000")

    def test_strips_thousands_separators(self):
        assert validate_amount("50,000") == Decimal("50000")

    def test_rejects_zero(self):
        with pytest.raises(ValidationError):
            validate_amount("0")

    def test_rejects_negative(self):
        with pytest.raises(ValidationError):
            validate_amount("-100")

    def test_rejects_garbage(self):
        with pytest.raises(ValidationError):
            validate_amount("lots of money")

    def test_rejects_absurdly_large(self):
        with pytest.raises(ValidationError):
            validate_amount("99999999999999")


class TestParsedExpenseFromGPT:
    def test_valid_response(self):
        expense = _to_parsed_expense(
            {"amount": 100000, "category": "food", "description": "Lunch", "currency": "uzs"}
        )
        assert expense.amount == Decimal("100000")
        assert expense.category == "food"
        assert expense.description == "Lunch"
        assert expense.currency == "UZS"

    def test_missing_amount_raises(self):
        with pytest.raises(ParsingError):
            _to_parsed_expense({"category": "food"})

    def test_zero_amount_raises(self):
        with pytest.raises(ParsingError):
            _to_parsed_expense({"amount": 0, "category": "food"})

    def test_unknown_category_falls_back_to_other(self):
        expense = _to_parsed_expense({"amount": 5000, "category": "spaceships"})
        assert expense.category == "other"

    def test_defaults_currency_to_uzs(self):
        expense = _to_parsed_expense({"amount": 5000, "category": "food"})
        assert expense.currency == "UZS"


class TestExpensePersistence:
    async def test_create_and_sum_expenses(self, db_session):
        user = await get_or_create_user(db_session, telegram_id=111)
        await create_expense(db_session, user_id=user.id, amount=Decimal("50000"), category="food")
        await create_expense(db_session, user_id=user.id, amount=Decimal("25000"), category="transport")

        total = await sum_expenses_this_month(db_session, user.id)
        assert total == Decimal("75000")

        count = await count_expenses_this_month(db_session, user.id)
        assert count == 2

    async def test_expenses_scoped_per_user(self, db_session):
        user_a = await get_or_create_user(db_session, telegram_id=1)
        user_b = await get_or_create_user(db_session, telegram_id=2)
        await create_expense(db_session, user_id=user_a.id, amount=Decimal("1000"), category="food")

        assert await count_expenses_this_month(db_session, user_a.id) == 1
        assert await count_expenses_this_month(db_session, user_b.id) == 0

    async def test_free_tier_limit_boundary(self, db_session):
        from config import settings

        user = await get_or_create_user(db_session, telegram_id=42)
        for _ in range(settings.free_tier_monthly_limit):
            await create_expense(db_session, user_id=user.id, amount=Decimal("1000"), category="other")

        used = await count_expenses_this_month(db_session, user.id)
        assert used >= settings.free_tier_monthly_limit


class TestParseExpenseWithMockedGPT:
    async def test_parses_well_formed_response(self, monkeypatch):
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=AsyncMock(
                        return_value=_fake_openai_response(
                            {"amount": 25000, "category": "food", "description": "Coffee", "currency": "UZS"}
                        )
                    )
                )
            )
        )
        monkeypatch.setattr("app.services.gpt.get_openai_client", lambda: client)

        expense = await parse_expense("25000 for coffee")
        assert expense.amount == Decimal("25000")
        assert expense.category == "food"
        assert expense.description == "Coffee"

    async def test_gpt_hallucination_raises_parsing_error(self, monkeypatch):
        client = SimpleNamespace(
            chat=SimpleNamespace(
                completions=SimpleNamespace(
                    create=AsyncMock(return_value=_fake_openai_response({"not_amount": "???"}))
                )
            )
        )
        monkeypatch.setattr("app.services.gpt.get_openai_client", lambda: client)

        with pytest.raises(ParsingError):
            await parse_expense("gibberish")
