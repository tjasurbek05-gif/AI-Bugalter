"""Phase 1: voice -> Whisper -> GPT -> confirm -> save. Plus /expenses summary."""
from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.services import cache
from app.services.db import (
    count_expenses_this_month,
    create_expense,
    get_expenses_for_month,
    get_or_create_user,
    get_session,
    sum_expenses_this_month,
)
from app.services.gpt import CATEGORY_NAMES, ParsedExpense, ParsingError, parse_expense
from app.services.whisper import TranscriptionError, transcribe_voice
from app.utils.decorators import log_errors
from app.utils.formatting import format_category_label, format_date, format_money
from app.utils.logger import get_logger
from app.utils.validators import ValidationError, sanitize_text, validate_amount
from config import settings

router = Router(name="expense")
logger = get_logger(__name__)


class ExpenseStates(StatesGroup):
    confirming = State()
    editing = State()


class ExpenseAction(CallbackData, prefix="exp"):
    action: str  # confirm | edit | cancel


def _confirmation_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Confirm", callback_data=ExpenseAction(action="confirm").pack()),
        InlineKeyboardButton(text="✏️ Edit", callback_data=ExpenseAction(action="edit").pack()),
        InlineKeyboardButton(text="🗑 Cancel", callback_data=ExpenseAction(action="cancel").pack()),
    )
    return builder


def _confirmation_text(expense: ParsedExpense) -> str:
    return (
        "✅ Got it!\n"
        f"💵 {format_money(expense.amount, expense.currency)}\n"
        f"🏪 Category: {format_category_label(expense.category)}\n"
        f"📝 {expense.description or '—'}"
    )


async def _reject_free_tier_limit(message: Message, telegram_id: int) -> bool:
    """Returns True (and replies) if the user has hit the free tier cap."""
    async with get_session() as session:
        user = await get_or_create_user(
            session,
            telegram_id=telegram_id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            language_code=message.from_user.language_code,
        )
        if user.has_active_subscription:
            return False

        used = await count_expenses_this_month(session, user.id)
        if used >= settings.free_tier_monthly_limit:
            await message.answer(
                f"🚫 You've used all {settings.free_tier_monthly_limit} free transactions this month.\n"
                "Upgrade for unlimited tracking — from $1.49. Use /subscribe to see plans."
            )
            return True
        return False


@router.message(F.voice)
@log_errors
async def handle_voice_expense(message: Message, state: FSMContext) -> None:
    if await _reject_free_tier_limit(message, message.from_user.id):
        return

    status = await message.answer("🎙️ Transcribing...")

    voice = message.voice
    transcription = await cache.get_cached_transcription(voice.file_unique_id)
    if transcription is None:
        buffer = BytesIO()
        await message.bot.download(voice, destination=buffer)
        try:
            transcription = await transcribe_voice(buffer.getvalue(), filename=f"{voice.file_unique_id}.ogg")
        except TranscriptionError:
            await status.edit_text(
                "😕 I couldn't transcribe that voice message (network hiccup or unclear audio).\n"
                "Try again, or type it manually: /add 50000 food lunch"
            )
            return
        await cache.cache_transcription(voice.file_unique_id, transcription)

    await _parse_and_confirm(message, state, transcription, status, voice_message_id=voice.file_id)


@router.message(Command("add"))
@log_errors
async def handle_manual_add(message: Message, state: FSMContext) -> None:
    """Typed fallback for when voice transcription is unavailable: /add 50000 food lunch."""
    if await _reject_free_tier_limit(message, message.from_user.id):
        return

    text = (message.text or "").split(maxsplit=1)
    if len(text) < 2 or not text[1].strip():
        await message.answer("Usage: /add <amount> <description>\nExample: /add 50000 lunch at cheburek place")
        return

    status = await message.answer("🤖 Parsing...")
    await _parse_and_confirm(message, state, text[1].strip(), status, voice_message_id=None)


async def _parse_and_confirm(
    message: Message,
    state: FSMContext,
    transcription: str,
    status: Message,
    voice_message_id: str | None,
) -> None:
    try:
        expense = await parse_expense(transcription)
    except ParsingError:
        await status.edit_text(
            "😕 I couldn't figure out an amount/category from that.\n"
            "Try: /add 50000 food lunch at cheburek place"
        )
        return

    await state.set_state(ExpenseStates.confirming)
    await state.update_data(
        amount=str(expense.amount),
        currency=expense.currency,
        category=expense.category,
        description=expense.description,
        voice_message_id=voice_message_id,
    )
    await status.edit_text(_confirmation_text(expense), reply_markup=_confirmation_keyboard().as_markup())


@router.callback_query(ExpenseAction.filter(F.action == "confirm"), ExpenseStates.confirming)
@log_errors
async def confirm_expense(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()

    async with get_session() as session:
        user = await get_or_create_user(session, telegram_id=callback.from_user.id)
        await create_expense(
            session,
            user_id=user.id,
            amount=Decimal(data["amount"]),
            category=data["category"],
            description=data.get("description"),
            currency=data.get("currency", "UZS"),
            voice_message_id=data.get("voice_message_id"),
        )
        month_total = await sum_expenses_this_month(session, user.id)

    await callback.message.edit_text(
        f"💾 Saved! You've spent {format_money(month_total)} this month."
    )
    await callback.answer()


@router.callback_query(ExpenseAction.filter(F.action == "cancel"), ExpenseStates.confirming)
@log_errors
async def cancel_expense(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("🗑 Cancelled. Nothing was saved.")
    await callback.answer()


@router.callback_query(ExpenseAction.filter(F.action == "edit"), ExpenseStates.confirming)
@log_errors
async def start_edit_expense(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(ExpenseStates.editing)
    await callback.message.edit_text(
        "✏️ Reply with the corrected info:\n"
        f"<amount> <category> <description>\n\n"
        f"Categories: {', '.join(CATEGORY_NAMES)}\n"
        "Example: 150000 food lunch at cafe"
    )
    await callback.answer()


@router.message(ExpenseStates.editing)
@log_errors
async def apply_edit_expense(message: Message, state: FSMContext) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Usage: <amount> <category> <description>\nExample: 150000 food lunch at cafe")
        return

    try:
        amount = validate_amount(parts[0])
    except ValidationError as exc:
        await message.answer(f"😕 {exc}")
        return

    category = parts[1].lower().strip()
    if category not in CATEGORY_NAMES:
        category = "other"
    description = sanitize_text(parts[2]) if len(parts) > 2 else ""

    expense = ParsedExpense(amount=amount, category=category, description=description)
    await state.set_state(ExpenseStates.confirming)
    await state.update_data(
        amount=str(expense.amount), currency=expense.currency,
        category=expense.category, description=expense.description,
    )
    await message.answer(_confirmation_text(expense), reply_markup=_confirmation_keyboard().as_markup())


@router.message(Command("expenses"))
@log_errors
async def show_monthly_expenses(message: Message) -> None:
    now = message.date
    async with get_session() as session:
        user = await get_or_create_user(session, telegram_id=message.from_user.id)
        expenses = await get_expenses_for_month(session, user.id, now.year, now.month)

    if not expenses:
        await message.answer("📭 No expenses recorded yet this month. Send a voice message to add one!")
        return

    totals: dict[str, Decimal] = {}
    for expense in expenses:
        totals[expense.category] = totals.get(expense.category, Decimal(0)) + expense.amount
    grand_total = sum(totals.values(), Decimal(0))

    lines = [f"📊 This Month ({len(expenses)} transactions)\n"]
    for category, total in sorted(totals.items(), key=lambda kv: kv[1], reverse=True):
        pct = (total / grand_total * 100) if grand_total else Decimal(0)
        lines.append(f"{format_category_label(category)}: {format_money(total)} ({pct:.0f}%)")
    lines.append(f"\n💰 Total: {format_money(grand_total)}")
    lines.append(f"🗓 Last entry: {format_date(expenses[0].created_at.date())}")

    await message.answer("\n".join(lines))
