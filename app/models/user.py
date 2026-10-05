from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

FREE_TIER = "free"
SUBSCRIPTION_TIERS = (
    "free",
    "1_week",
    "1_month",
    "3_months",
    "6_months",
    "1_year",
    "premium_1_day",
    "premium_1_week",
    "premium_1_month",
)


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(255))
    first_name: Mapped[str | None] = mapped_column(String(255))
    language_code: Mapped[str] = mapped_column(String(10), default="en")
    subscription_tier: Mapped[str] = mapped_column(String(50), default=FREE_TIER)
    subscription_expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    expenses = relationship("Expense", back_populates="user", cascade="all, delete-orphan")
    loans = relationship("Loan", back_populates="user", cascade="all, delete-orphan")
    categories = relationship("Category", back_populates="user", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")

    @property
    def has_active_subscription(self) -> bool:
        if self.subscription_tier == FREE_TIER:
            return False
        if self.subscription_expires_at is None:
            return False
        return self.subscription_expires_at > datetime.utcnow()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} telegram_id={self.telegram_id} tier={self.subscription_tier}>"
