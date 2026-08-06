"""User onboarding, language preference, and custom categories."""
from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

from app.models.category import DEFAULT_CATEGORIES, Category
from app.services.db import get_or_create_user, get_session
from app.utils.decorators import log_errors
from app.utils.formatting import format_category_label
from app.utils.validators import sanitize_text

router = Router(name="settings")

WELCOME_TEXT = (
    "👋 Welcome to <b>AI Bugalter</b> — your personal AI accountant!\n\n"
    "🎙️ Send a voice message to log an expense — I'll transcribe, categorize, "
    "and save it after you confirm.\n"
    "💬 No mic? Try: /add 50000 lunch at cafe\n"
    "💳 Track loans: /loan lend 50000 Khasan 1 month\n"
    "📊 See your spending: /expenses or /report\n\n"
    "Free tier: 5 transactions/month. /subscribe for unlimited."
)

HELP_TEXT = (
    "<b>Commands</b>\n"
    "🎙️ Send voice — log an expense\n"
    "/add &lt;amount&gt; &lt;description&gt; — log an expense by text\n"
    "/expenses — this month's spending summary\n"
    "/report — AI insights on this month's spending (paid)\n"
    "/loan &lt;lend|owe&gt; &lt;amount&gt; &lt;person&gt; [&lt;N&gt; &lt;day|week|month|year&gt;] — track a loan (paid)\n"
    "/loans — view active loans (paid)\n"
    "/categories — list your expense categories\n"
    "/language — change bot language\n"
    "/subscribe — see subscription plans\n"
)


class LanguageAction(CallbackData, prefix="lang"):
    code: str


@router.message(CommandStart())
@log_errors
async def start(message: Message) -> None:
    async with get_session() as session:
        await get_or_create_user(
            session,
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            language_code=message.from_user.language_code,
        )
    await message.answer(WELCOME_TEXT)


@router.message(Command("help"))
@log_errors
async def help_command(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("language"))
@log_errors
async def choose_language(message: Message) -> None:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data=LanguageAction(code="ru").pack()),
        InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data=LanguageAction(code="uz").pack()),
        InlineKeyboardButton(text="🇬🇧 English", callback_data=LanguageAction(code="en").pack()),
    )
    await message.answer("Choose your language:", reply_markup=builder.as_markup())


@router.callback_query(LanguageAction.filter())
@log_errors
async def set_language(callback: CallbackQuery, callback_data: LanguageAction) -> None:
    async with get_session() as session:
        user = await get_or_create_user(session, telegram_id=callback.from_user.id)
        user.language_code = callback_data.code
        await session.commit()

    await callback.message.edit_text(f"✅ Language set to {callback_data.code}.")
    await callback.answer()


@router.message(Command("categories"))
@log_errors
async def list_categories(message: Message) -> None:
    async with get_session() as session:
        user = await get_or_create_user(session, telegram_id=message.from_user.id)
        result = await session.execute(select(Category).where(Category.user_id == user.id))
        custom = list(result.scalars().all())

    lines = ["📂 <b>Default categories</b>"]
    lines.extend(format_category_label(name) for name in DEFAULT_CATEGORIES)

    if custom:
        lines.append("\n📂 <b>Your custom categories</b>")
        lines.extend(f"{cat.emoji or '📌'} {cat.name}" for cat in custom)

    lines.append("\nAdd one: /addcategory <name> <emoji>")
    await message.answer("\n".join(lines))


@router.message(Command("addcategory"))
@log_errors
async def add_category(message: Message) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 2:
        await message.answer("Usage: /addcategory <name> [emoji]\nExample: /addcategory gym 🏋️")
        return

    name = sanitize_text(parts[1], max_length=50).lower()
    emoji = parts[2].strip()[:10] if len(parts) > 2 else "📌"

    async with get_session() as session:
        user = await get_or_create_user(session, telegram_id=message.from_user.id)
        existing = await session.execute(
            select(Category).where(Category.user_id == user.id, Category.name == name)
        )
        if existing.scalar_one_or_none() is not None:
            await message.answer(f"You already have a '{name}' category.")
            return

        session.add(Category(user_id=user.id, name=name, emoji=emoji))
        await session.commit()

    await message.answer(f"✅ Added category {emoji} {name}")
