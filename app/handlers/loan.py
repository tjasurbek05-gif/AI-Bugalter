"""Phase 2: /loan create, /loans list, mark-as-paid, due-date reminders."""
from __future__ import annotations

from datetime import date as date_cls
from decimal import Decimal

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.models.loan import LOAN_TYPE_LEND, Loan
from app.models.user import User
from app.services.db import (
    create_loan,
    get_active_loans,
    get_loan_by_id,
    get_loans_due_for_reminder,
    get_or_create_user,
    get_session,
    mark_loan_paid,
    mark_overdue_loans,
)
from app.utils.decorators import check_subscription, log_errors
from app.utils.formatting import format_date, format_money
from app.utils.logger import get_logger
from app.utils.validators import ParsedLoan, ValidationError, parse_loan_command
from config import settings

router = Router(name="loan")
logger = get_logger(__name__)


class LoanStates(StatesGroup):
    confirming = State()


class LoanAction(CallbackData, prefix="loan"):
    action: str  # create | cancel


class LoanPaidAction(CallbackData, prefix="loanpaid"):
    loan_id: int


def _create_confirmation_text(loan: ParsedLoan) -> str:
    verb = "owes you" if loan.type == LOAN_TYPE_LEND else "you owe"
    due = f"Due: {format_date(loan.due_date)}" if loan.due_date else "Due: not set"
    return (
        "📋 Confirm loan:\n"
        f"{loan.person_name} {verb}: {format_money(loan.amount)}\n"
        f"{due}"
    )


@router.message(Command("loan"))
@log_errors
@check_subscription(min_tier="paid")
async def create_loan_command(
    message: Message, command: CommandObject, state: FSMContext, user: User, session
) -> None:
    try:
        parsed = parse_loan_command(command.args or "")
    except ValidationError as exc:
        await message.answer(str(exc))
        return

    await state.set_state(LoanStates.confirming)
    await state.update_data(
        type=parsed.type,
        amount=str(parsed.amount),
        person_name=parsed.person_name,
        due_date=parsed.due_date.isoformat() if parsed.due_date else None,
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Create", callback_data=LoanAction(action="create").pack()),
        InlineKeyboardButton(text="❌ Cancel", callback_data=LoanAction(action="cancel").pack()),
    )
    await message.answer(_create_confirmation_text(parsed), reply_markup=builder.as_markup())


@router.callback_query(LoanAction.filter(F.action == "create"), LoanStates.confirming)
@log_errors
async def confirm_create_loan(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    async with get_session() as session:
        user = await get_or_create_user(session, telegram_id=callback.from_user.id)
        due_date = date_cls.fromisoformat(data["due_date"]) if data.get("due_date") else None
        loan = await create_loan(
            session,
            user_id=user.id,
            loan_type=data["type"],
            person_name=data["person_name"],
            amount=Decimal(data["amount"]),
            due_date=due_date,
        )

    if loan.due_date:
        reminder_date = loan.due_date.strftime("%b %d")
        await callback.message.edit_text(f"✅ Loan created! I'll remind you around {reminder_date}.")
    else:
        await callback.message.edit_text("✅ Loan created!")
    await callback.answer()


@router.callback_query(LoanAction.filter(F.action == "cancel"), LoanStates.confirming)
@log_errors
async def cancel_create_loan(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("❌ Cancelled. Nothing was saved.")
    await callback.answer()


def _format_loan_line(loan: Loan) -> str:
    marker = " ⚠️ OVERDUE" if loan.status == "overdue" else (" ⏰" if loan.due_date else "")
    due = f" (Due: {format_date(loan.due_date)})" if loan.due_date else ""
    return f"├─ {loan.person_name}: {format_money(loan.amount, loan.currency)}{due}{marker}"


def _render_loans(loans: list[Loan]) -> str:
    owed_to_you = [loan for loan in loans if loan.type == LOAN_TYPE_LEND]
    you_owe = [loan for loan in loans if loan.type != LOAN_TYPE_LEND]

    lines = ["📋 Your Loans\n", "💰 You are owed:"]
    lines.extend([_format_loan_line(loan) for loan in owed_to_you] or ["├─ (none)"])

    lines.append("\n💳 You owe:")
    lines.extend([_format_loan_line(loan) for loan in you_owe] or ["├─ (none)"])

    return "\n".join(lines)


def _loans_keyboard(loans: list[Loan]) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    for loan in loans:
        label = f"✅ Paid: {loan.person_name} ({format_money(loan.amount, loan.currency)})"
        builder.row(InlineKeyboardButton(text=label, callback_data=LoanPaidAction(loan_id=loan.id).pack()))
    return builder


@router.message(Command("loans"))
@log_errors
@check_subscription(min_tier="paid")
async def list_loans(message: Message, user: User, session) -> None:
    await mark_overdue_loans(session)
    loans = await get_active_loans(session, user.id)

    if not loans:
        await message.answer("📭 No active loans. Create one with:\n/loan lend 50000 Khasan 1 month")
        return

    await message.answer(_render_loans(loans), reply_markup=_loans_keyboard(loans).as_markup())


@router.callback_query(LoanPaidAction.filter())
@log_errors
async def mark_paid(callback: CallbackQuery, callback_data: LoanPaidAction) -> None:
    async with get_session() as session:
        user = await get_or_create_user(session, telegram_id=callback.from_user.id)
        loan = await get_loan_by_id(session, callback_data.loan_id, user_id=user.id)
        if loan is None:
            await callback.answer("Loan not found (already settled?).", show_alert=True)
            return

        await mark_loan_paid(session, loan)
        remaining = await get_active_loans(session, user.id)

    await callback.answer("✅ Marked as paid!")
    if remaining:
        await callback.message.edit_text(_render_loans(remaining), reply_markup=_loans_keyboard(remaining).as_markup())
    else:
        await callback.message.edit_text("📭 No active loans left. Nicely done!")


async def send_due_reminders(bot: Bot) -> int:
    """Daily job: notify users about loans due in `loan_reminder_days_before` days."""
    sent = 0
    async with get_session() as session:
        await mark_overdue_loans(session)
        loans = await get_loans_due_for_reminder(session, settings.loan_reminder_days_before)

        for loan in loans:
            user = await session.get(User, loan.user_id)
            if user is None:
                continue
            verb = "owes you" if loan.type == LOAN_TYPE_LEND else "you owe"
            try:
                await bot.send_message(
                    user.telegram_id,
                    "🔔 Loan reminder!\n"
                    f"{loan.person_name} {verb} {format_money(loan.amount, loan.currency)}, "
                    f"due {format_date(loan.due_date)}.",
                )
                sent += 1
            except Exception:  # noqa: BLE001 - one user's failure shouldn't stop the batch
                logger.exception("loan_reminder_send_failed", extra={"telegram_id": user.telegram_id})
    return sent
