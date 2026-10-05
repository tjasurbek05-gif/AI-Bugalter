"""Phase 4: /subscribe checkout flow + Stripe webhook handling. Also the
Click (click.uz) Premium flow: a "Premium" button -> pick a duration -> pay.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData
from aiogram.types import CallbackQuery, InlineKeyboardButton, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select

import stripe
from app.models.click_transaction import CLICK_STATE_CANCELLED, CLICK_STATE_PAID, ClickTransaction
from app.models.subscription import Subscription
from app.models.user import User
from app.services import click as click_service
from app.services.db import get_or_create_user, get_session
from app.services.stripe import (
    StripeConfigError,
    TIER_DAYS,
    create_checkout_session,
    tier_for_price_id,
)
from app.utils.decorators import log_errors
from app.utils.logger import get_logger
from config import settings

router = Router(name="payment")
logger = get_logger(__name__)

TIER_DISPLAY: dict[str, str] = {
    "1_week": "1 Week — $1.49",
    "1_month": "1 Month — $4.99 ⭐",
    "3_months": "3 Months — $12.99",
    "6_months": "6 Months — $22.99",
    "1_year": "1 Year — $39.99",
}


class SubscribeAction(CallbackData, prefix="sub"):
    tier: str


@router.message(Command("subscribe"))
@log_errors
async def subscribe_command(message: Message) -> None:
    builder = InlineKeyboardBuilder()
    for tier, label in TIER_DISPLAY.items():
        builder.row(InlineKeyboardButton(text=label, callback_data=SubscribeAction(tier=tier).pack()))

    await message.answer(
        "💳 <b>Choose your plan</b>\n\n"
        "Unlimited transactions, AI categorization, monthly insights, and loan tracking.",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(SubscribeAction.filter())
@log_errors
async def select_tier(callback: CallbackQuery, callback_data: SubscribeAction) -> None:
    bot_username = settings.telegram_bot_username or "your_bot"
    try:
        session_obj = await create_checkout_session(
            telegram_id=callback.from_user.id,
            tier=callback_data.tier,
            success_url=f"https://t.me/{bot_username}?start=paid_success",
            cancel_url=f"https://t.me/{bot_username}?start=paid_cancelled",
        )
    except StripeConfigError:
        await callback.answer("This plan isn't available right now. Please try another.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Pay now", url=session_obj.url))
    await callback.message.answer(
        f"You selected: {TIER_DISPLAY[callback_data.tier]}\nTap below to complete payment securely via Stripe.",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


class PremiumMenuAction(CallbackData, prefix="premium_menu"):
    pass


class PremiumPlanAction(CallbackData, prefix="premium_plan"):
    tier: str


def _fmt_sum(amount: int) -> str:
    return f"{amount:,}".replace(",", " ")


@router.message(Command("premium"))
@log_errors
async def premium_command(message: Message) -> None:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="⭐ Premium", callback_data=PremiumMenuAction().pack()))
    await message.answer(
        "⭐ <b>Premium</b> — cheksiz tranzaksiyalar, AI tahlil va qarz kuzatuvi.",
        reply_markup=builder.as_markup(),
    )


@router.callback_query(PremiumMenuAction.filter())
@log_errors
async def open_premium_menu(callback: CallbackQuery) -> None:
    builder = InlineKeyboardBuilder()
    for plan in click_service.PREMIUM_PLANS.values():
        label = f"{plan.label} — {_fmt_sum(plan.amount)} so'm"
        builder.row(InlineKeyboardButton(text=label, callback_data=PremiumPlanAction(tier=plan.tier).pack()))

    await callback.message.answer("⭐ <b>Muddatni tanlang</b>", reply_markup=builder.as_markup())
    await callback.answer()


@router.callback_query(PremiumPlanAction.filter())
@log_errors
async def select_premium_plan(callback: CallbackQuery, callback_data: PremiumPlanAction) -> None:
    plan = click_service.PREMIUM_PLANS.get(callback_data.tier)
    if plan is None:
        await callback.answer("Bu reja topilmadi.", show_alert=True)
        return

    merchant_trans_id = click_service.new_merchant_trans_id(callback.from_user.id)

    async with get_session() as session:
        user = await get_or_create_user(session, telegram_id=callback.from_user.id)
        session.add(
            ClickTransaction(
                user_id=user.id,
                merchant_trans_id=merchant_trans_id,
                tier=plan.tier,
                amount=plan.amount,
            )
        )
        await session.commit()

    try:
        pay_url = click_service.build_pay_url(merchant_trans_id, plan.amount)
    except click_service.ClickConfigError:
        logger.warning("click_not_configured")
        await callback.answer("To'lov tizimi hali sozlanmagan. Birozdan so'ng urinib ko'ring.", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Click orqali to'lash", url=pay_url))
    await callback.message.answer(
        f"Siz tanladingiz: {plan.label} — {_fmt_sum(plan.amount)} so'm\n"
        "To'lovni yakunlash uchun quyidagi tugmani bosing.",
        reply_markup=builder.as_markup(),
    )
    await callback.answer()


def _click_response(data: dict, error: int, note: str, **extra: object) -> dict:
    return {
        "click_trans_id": data.get("click_trans_id"),
        "merchant_trans_id": data.get("merchant_trans_id"),
        "error": error,
        "error_note": note,
        **extra,
    }


async def handle_click_prepare(data: dict) -> dict:
    """Click's Prepare step: validate the transaction, don't activate anything yet."""
    if not click_service.verify_prepare_signature(data):
        return _click_response(data, click_service.ERROR_SIGN_FAILED, "SIGN CHECK FAILED!")

    merchant_trans_id = str(data.get("merchant_trans_id", ""))
    async with get_session() as session:
        result = await session.execute(
            select(ClickTransaction).where(ClickTransaction.merchant_trans_id == merchant_trans_id)
        )
        transaction = result.scalar_one_or_none()
        if transaction is None:
            return _click_response(data, click_service.ERROR_TRANSACTION_NOT_FOUND, "Transaction not found")
        if transaction.state == CLICK_STATE_PAID:
            return _click_response(data, click_service.ERROR_ALREADY_PAID, "Already paid")
        if Decimal(str(data.get("amount", "0"))) != transaction.amount:
            return _click_response(data, click_service.ERROR_AMOUNT_MISMATCH, "Incorrect amount")

        transaction.click_trans_id = str(data.get("click_trans_id", ""))
        await session.commit()

        return _click_response(
            data,
            click_service.ERROR_SUCCESS,
            "Success",
            merchant_prepare_id=transaction.id,
        )


async def handle_click_complete(data: dict, bot: Bot) -> dict:
    """Click's Complete step: payment is final, activate the premium plan."""
    if not click_service.verify_complete_signature(data):
        return _click_response(data, click_service.ERROR_SIGN_FAILED, "SIGN CHECK FAILED!")

    merchant_trans_id = str(data.get("merchant_trans_id", ""))
    async with get_session() as session:
        result = await session.execute(
            select(ClickTransaction).where(ClickTransaction.merchant_trans_id == merchant_trans_id)
        )
        transaction = result.scalar_one_or_none()
        if transaction is None:
            return _click_response(data, click_service.ERROR_TRANSACTION_NOT_FOUND, "Transaction not found")
        if transaction.state == CLICK_STATE_PAID:
            return _click_response(data, click_service.ERROR_ALREADY_PAID, "Already paid")

        if int(data.get("error", 0)) < 0:
            transaction.state = CLICK_STATE_CANCELLED
            await session.commit()
            return _click_response(data, click_service.ERROR_TRANSACTION_CANCELLED, "Transaction cancelled")

        plan = click_service.PREMIUM_PLANS.get(transaction.tier)
        days = plan.days if plan else 1

        user = await session.get(User, transaction.user_id)
        base = (
            user.subscription_expires_at
            if (user.subscription_expires_at and user.subscription_expires_at > datetime.utcnow())
            else datetime.utcnow()
        )
        user.subscription_tier = transaction.tier
        user.subscription_expires_at = base + timedelta(days=days)
        transaction.state = CLICK_STATE_PAID
        await session.commit()

        telegram_id = user.telegram_id
        prepare_id = transaction.id

    try:
        await bot.send_message(
            telegram_id,
            f"🎉 Premium faollashtirildi! ({plan.label if plan else transaction.tier})\n"
            "Cheksiz tranzaksiyalar, qarz kuzatuvi va AI tahlil endi ochiq.",
        )
    except Exception:  # noqa: BLE001 - webhook must still succeed even if the DM fails
        logger.exception("click_activation_notify_failed", extra={"telegram_id": telegram_id})

    return _click_response(
        data,
        click_service.ERROR_SUCCESS,
        "Success",
        merchant_confirm_id=prepare_id,
    )


async def handle_stripe_webhook(event: stripe.Event, bot: Bot) -> None:
    """Dispatch a verified Stripe event. Called from the FastAPI webhook route."""
    handler = _EVENT_HANDLERS.get(event["type"])
    if handler is None:
        logger.info("stripe_event_ignored", extra={"type": event["type"]})
        return
    await handler(event, bot)


async def _on_checkout_completed(event: stripe.Event, bot: Bot) -> None:
    obj = event["data"]["object"]
    telegram_id = obj.get("client_reference_id") or obj.get("metadata", {}).get("telegram_id")
    tier = obj.get("metadata", {}).get("tier")
    stripe_subscription_id = obj.get("subscription")
    stripe_customer_id = obj.get("customer")

    if not telegram_id or not tier:
        logger.warning("stripe_checkout_missing_metadata", extra={"event_id": event["id"]})
        return

    expires_at = datetime.utcnow() + timedelta(days=TIER_DAYS.get(tier, 30))

    async with get_session() as session:
        user = await get_or_create_user(session, telegram_id=int(telegram_id))
        user.subscription_tier = tier
        user.subscription_expires_at = expires_at
        user.stripe_customer_id = stripe_customer_id

        session.add(
            Subscription(
                user_id=user.id,
                stripe_subscription_id=stripe_subscription_id,
                tier=tier,
                status="active",
                current_period_start=datetime.utcnow().date(),
                current_period_end=expires_at.date(),
            )
        )
        await session.commit()

    try:
        await bot.send_message(
            int(telegram_id),
            f"🎉 Subscription activated! You're now on the {tier.replace('_', ' ')} plan.\n"
            "Unlimited transactions, loan tracking, and monthly insights are unlocked.",
        )
    except Exception:  # noqa: BLE001 - webhook must still succeed even if the DM fails
        logger.exception("stripe_activation_notify_failed", extra={"telegram_id": telegram_id})


async def _on_subscription_updated(event: stripe.Event, bot: Bot) -> None:
    obj = event["data"]["object"]
    stripe_subscription_id = obj.get("id")
    status = obj.get("status")
    current_period_end = obj.get("current_period_end")
    line_items = obj.get("items", {}).get("data") or []
    price_id = line_items[0].get("price", {}).get("id") if line_items else None
    tier = tier_for_price_id(price_id) if price_id else None

    async with get_session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if subscription is None:
            return

        subscription.status = status
        if current_period_end:
            subscription.current_period_end = datetime.utcfromtimestamp(current_period_end).date()

        user = await session.get(User, subscription.user_id)
        if user is not None and status == "active":
            if tier:
                user.subscription_tier = tier
            if current_period_end:
                user.subscription_expires_at = datetime.utcfromtimestamp(current_period_end)
        await session.commit()


async def _on_subscription_deleted(event: stripe.Event, bot: Bot) -> None:
    obj = event["data"]["object"]
    stripe_subscription_id = obj.get("id")

    async with get_session() as session:
        result = await session.execute(
            select(Subscription).where(Subscription.stripe_subscription_id == stripe_subscription_id)
        )
        subscription = result.scalar_one_or_none()
        if subscription is None:
            return

        subscription.status = "canceled"
        user = await session.get(User, subscription.user_id)
        if user is not None:
            user.subscription_tier = "free"
            user.subscription_expires_at = None
        await session.commit()

        if user is not None:
            try:
                await bot.send_message(
                    user.telegram_id,
                    "Your subscription has ended. You're back on the free tier (5 transactions/month).\n"
                    "Use /subscribe to renew anytime.",
                )
            except Exception:  # noqa: BLE001
                logger.exception("stripe_cancellation_notify_failed", extra={"user_id": user.id})


_EVENT_HANDLERS = {
    "checkout.session.completed": _on_checkout_completed,
    "customer.subscription.updated": _on_subscription_updated,
    "customer.subscription.deleted": _on_subscription_deleted,
}
