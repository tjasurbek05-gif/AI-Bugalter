"""Cross-cutting handler decorators: subscription gating + error logging.

Designed for aiogram handlers whose first positional argument is a
`types.Message` (or anything with a `.from_user` and `.answer()`).
"""
from __future__ import annotations

import functools
from collections.abc import Awaitable, Callable
from typing import ParamSpec, TypeVar

from app.services.db import get_or_create_user, get_session
from app.utils.logger import get_logger

logger = get_logger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def check_subscription(min_tier: str = "free"):
    """Require an active subscription before running the handler.

    Fetches/creates the DB user and injects it as `user=` kwarg. On the free
    tier this is a no-op gate (everyone qualifies); for paid tiers it checks
    `user.has_active_subscription` and, if expired/absent, replies with an
    upgrade prompt instead of running the handler.
    """

    def decorator(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R | None]]:
        @functools.wraps(func)
        async def wrapper(message, *args: P.args, **kwargs: P.kwargs) -> R | None:
            async with get_session() as session:
                user = await get_or_create_user(
                    session,
                    telegram_id=message.from_user.id,
                    username=message.from_user.username,
                    first_name=message.from_user.first_name,
                    language_code=getattr(message.from_user, "language_code", None),
                )

                if min_tier != "free" and not user.has_active_subscription:
                    await message.answer(
                        "⭐ This feature needs an active subscription.\n"
                        "Use /subscribe to see plans starting at $1.49."
                    )
                    return None

                kwargs["user"] = user
                kwargs["session"] = session
                return await func(message, *args, **kwargs)

        return wrapper

    return decorator


def log_errors(func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R | None]]:
    """Catch, log, and gracefully degrade any unhandled exception in a handler."""

    @functools.wraps(func)
    async def wrapper(message, *args: P.args, **kwargs: P.kwargs) -> R | None:
        try:
            return await func(message, *args, **kwargs)
        except Exception:  # noqa: BLE001 - top-level handler boundary
            logger.exception("handler_error", extra={"handler": func.__name__})
            try:
                await message.answer("😕 Something went wrong on my end. Please try again in a moment.")
            except Exception:  # noqa: BLE001 - best effort notification
                logger.exception("handler_error_notify_failed")
            return None

    return wrapper
