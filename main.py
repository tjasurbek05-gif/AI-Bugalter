"""FastAPI entrypoint: Telegram webhook, Stripe webhook, health check."""
from __future__ import annotations

from contextlib import asynccontextmanager

import stripe as stripe_sdk
from aiogram.types import Update
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from sqlalchemy import text

from app.handlers.payment import handle_stripe_webhook
from app.services.cache import close_redis
from app.services.db import engine, init_models
from bot import create_bot, create_dispatcher, create_scheduler
from app.utils.logger import get_logger
from config import settings

logger = get_logger(__name__)
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not settings.is_production:
        await init_models()

    bot = create_bot()
    dp = create_dispatcher()
    scheduler = create_scheduler(bot)
    scheduler.start()

    if settings.is_production and settings.webhook_url:
        await bot.set_webhook(
            f"{settings.webhook_url.rstrip('/')}{settings.telegram_webhook_path}",
            drop_pending_updates=True,
        )

    app.state.bot = bot
    app.state.dp = dp
    app.state.scheduler = scheduler
    logger.info("app_started", extra={"env": settings.app_env})

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        if settings.is_production:
            await bot.delete_webhook()
        await bot.session.close()
        await close_redis()
        await engine.dispose()
        logger.info("app_stopped")


app = FastAPI(title="AI Bugalter", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health")
async def health() -> JSONResponse:
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        logger.exception("health_check_db_failed")
        db_ok = False

    status_code = 200 if db_ok else 503
    return JSONResponse(status_code=status_code, content={"status": "ok" if db_ok else "degraded", "db": db_ok})


@app.post(settings.telegram_webhook_path)
@limiter.limit("100/minute")
async def telegram_webhook(request: Request) -> dict:
    bot = request.app.state.bot
    dp = request.app.state.dp
    update = Update.model_validate(await request.json(), context={"bot": bot})
    await dp.feed_update(bot, update)
    return {"ok": True}


@app.post("/webhook/stripe")
@limiter.limit("60/minute")
async def stripe_webhook(request: Request, stripe_signature: str = Header(None)) -> dict:
    payload = await request.body()
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header")

    try:
        event = stripe_sdk.Webhook.construct_event(payload, stripe_signature, settings.stripe_webhook_secret)
    except (ValueError, stripe_sdk.error.SignatureVerificationError) as exc:
        logger.warning("stripe_webhook_signature_invalid", exc_info=exc)
        raise HTTPException(status_code=400, detail="Invalid signature") from exc

    await handle_stripe_webhook(event, request.app.state.bot)
    return {"ok": True}
