from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.models.loan import LOAN_TYPE_LEND, LOAN_TYPE_OWE
from app.services.db import (
    create_loan,
    get_active_loans,
    get_loans_due_for_reminder,
    get_or_create_user,
    mark_loan_paid,
    mark_overdue_loans,
)
from app.utils.validators import ValidationError, parse_loan_command


class TestParseLoanCommand:
    def test_lend_with_duration(self):
        parsed = parse_loan_command("lend 50000 Khasan 1 month")
        assert parsed.type == LOAN_TYPE_LEND
        assert parsed.amount == Decimal("50000")
        assert parsed.person_name == "Khasan"
        assert parsed.due_date == date.today() + timedelta(days=30)

    def test_owe_with_weeks(self):
        parsed = parse_loan_command("owe 500000 Dad 2 weeks")
        assert parsed.type == LOAN_TYPE_OWE
        assert parsed.person_name == "Dad"
        assert parsed.due_date == date.today() + timedelta(days=14)

    def test_no_duration_means_no_due_date(self):
        parsed = parse_loan_command("lend 100000 Maria")
        assert parsed.person_name == "Maria"
        assert parsed.due_date is None

    def test_multi_word_person_name(self):
        parsed = parse_loan_command("lend 100000 John Smith 1 year")
        assert parsed.person_name == "John Smith"
        assert parsed.due_date == date.today() + timedelta(days=365)

    def test_empty_args_raises(self):
        with pytest.raises(ValidationError):
            parse_loan_command("")

    def test_invalid_type_raises(self):
        with pytest.raises(ValidationError):
            parse_loan_command("borrow 5000 Khasan")

    def test_missing_person_name_raises(self):
        with pytest.raises(ValidationError):
            parse_loan_command("lend 5000")

    def test_invalid_amount_raises(self):
        with pytest.raises(ValidationError):
            parse_loan_command("lend notanumber Khasan")


class TestLoanPersistence:
    async def test_create_and_list_active_loans(self, db_session):
        user = await get_or_create_user(db_session, telegram_id=7)
        await create_loan(db_session, user_id=user.id, loan_type=LOAN_TYPE_LEND, person_name="Khasan", amount=Decimal("50000"))
        await create_loan(db_session, user_id=user.id, loan_type=LOAN_TYPE_OWE, person_name="Dad", amount=Decimal("500000"))

        loans = await get_active_loans(db_session, user.id)
        assert len(loans) == 2

    async def test_mark_paid_removes_from_active(self, db_session):
        user = await get_or_create_user(db_session, telegram_id=8)
        loan = await create_loan(db_session, user_id=user.id, loan_type=LOAN_TYPE_LEND, person_name="Khasan", amount=Decimal("50000"))

        await mark_loan_paid(db_session, loan)
        active = await get_active_loans(db_session, user.id)
        assert active == []

    async def test_reminder_matches_loans_due_in_n_days(self, db_session):
        user = await get_or_create_user(db_session, telegram_id=9)
        due_soon = date.today() + timedelta(days=3)
        due_later = date.today() + timedelta(days=10)
        await create_loan(db_session, user_id=user.id, loan_type=LOAN_TYPE_LEND, person_name="Soon", amount=Decimal("1000"), due_date=due_soon)
        await create_loan(db_session, user_id=user.id, loan_type=LOAN_TYPE_LEND, person_name="Later", amount=Decimal("1000"), due_date=due_later)

        due = await get_loans_due_for_reminder(db_session, days_before=3)
        assert [loan.person_name for loan in due] == ["Soon"]

    async def test_mark_overdue_transitions_status(self, db_session):
        user = await get_or_create_user(db_session, telegram_id=10)
        past_due = date.today() - timedelta(days=1)
        await create_loan(db_session, user_id=user.id, loan_type=LOAN_TYPE_OWE, person_name="Bank", amount=Decimal("1000"), due_date=past_due)

        updated_count = await mark_overdue_loans(db_session)
        assert updated_count == 1

        loans = await get_active_loans(db_session, user.id)
        assert loans[0].status == "overdue"
