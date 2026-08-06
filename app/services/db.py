"""Database engine, session management, and query helpers."""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.models.base import Base
from app.models.expense import Expense
from app.models.loan import LOAN_STATUS_PENDING, Loan
from app.models.user import FREE_TIER, User
from config import settings

engine = create_async_engine(settings.database_url, pool_pre_ping=True, future=True)
async_session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with async_session_factory() as session:
        yield session


async def init_models() -> None:
    """Create tables if they don't exist yet (dev/test convenience; prod uses schema.sql)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Users ────────────────────────────────────────────────
async def get_or_create_user(
    session: AsyncSession,
    telegram_id: int,
    username: str | None = None,
    first_name: str | None = None,
    language_code: str | None = None,
) -> User:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()
    if user is not None:
        return user

    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        language_code=language_code or "en",
        subscription_tier=FREE_TIER,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> User | None:
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    return result.scalar_one_or_none()


# ── Expenses ─────────────────────────────────────────────
async def count_expenses_this_month(session: AsyncSession, user_id: int) -> int:
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.count(Expense.id)).where(
            Expense.user_id == user_id,
            Expense.created_at >= start_of_month,
        )
    )
    return result.scalar_one()


async def create_expense(
    session: AsyncSession,
    user_id: int,
    amount: Decimal,
    category: str,
    description: str | None = None,
    currency: str = "UZS",
    voice_message_id: str | None = None,
) -> Expense:
    expense = Expense(
        user_id=user_id,
        amount=amount,
        category=category,
        description=description,
        currency=currency,
        voice_message_id=voice_message_id,
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return expense


async def get_expenses_for_month(
    session: AsyncSession, user_id: int, year: int, month: int
) -> list[Expense]:
    start = datetime(year, month, 1)
    end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
    result = await session.execute(
        select(Expense)
        .where(Expense.user_id == user_id, Expense.created_at >= start, Expense.created_at < end)
        .order_by(Expense.created_at.desc())
    )
    return list(result.scalars().all())


async def sum_expenses_this_month(session: AsyncSession, user_id: int) -> Decimal:
    start_of_month = datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    result = await session.execute(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.user_id == user_id,
            Expense.created_at >= start_of_month,
        )
    )
    return Decimal(result.scalar_one())


# ── Loans ────────────────────────────────────────────────
async def create_loan(
    session: AsyncSession,
    user_id: int,
    loan_type: str,
    person_name: str,
    amount: Decimal,
    due_date: date | None = None,
    currency: str = "UZS",
    description: str | None = None,
) -> Loan:
    loan = Loan(
        user_id=user_id,
        type=loan_type,
        person_name=person_name,
        amount=amount,
        due_date=due_date,
        currency=currency,
        description=description,
        status=LOAN_STATUS_PENDING,
    )
    session.add(loan)
    await session.commit()
    await session.refresh(loan)
    return loan


async def get_active_loans(session: AsyncSession, user_id: int) -> list[Loan]:
    result = await session.execute(
        select(Loan)
        .where(Loan.user_id == user_id, Loan.status != "paid")
        .order_by(Loan.due_date.asc().nulls_last())
    )
    return list(result.scalars().all())


async def get_loan_by_id(session: AsyncSession, loan_id: int, user_id: int) -> Loan | None:
    result = await session.execute(
        select(Loan).where(Loan.id == loan_id, Loan.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def mark_loan_paid(session: AsyncSession, loan: Loan) -> Loan:
    loan.status = "paid"
    await session.commit()
    await session.refresh(loan)
    return loan


async def get_loans_due_for_reminder(session: AsyncSession, days_before: int) -> list[Loan]:
    """Loans due in exactly `days_before` days that haven't had a reminder sent today."""
    target_date = date.today() + timedelta(days=days_before)
    result = await session.execute(
        select(Loan).where(
            Loan.status == LOAN_STATUS_PENDING,
            Loan.due_date == target_date,
        )
    )
    return list(result.scalars().all())


async def mark_overdue_loans(session: AsyncSession) -> int:
    result = await session.execute(
        select(Loan).where(Loan.status == LOAN_STATUS_PENDING, Loan.due_date < date.today())
    )
    loans = list(result.scalars().all())
    for loan in loans:
        loan.status = "overdue"
    if loans:
        await session.commit()
    return len(loans)
