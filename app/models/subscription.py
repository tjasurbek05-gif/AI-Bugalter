from datetime import date

from sqlalchemy import Date, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

SUBSCRIPTION_STATUS_ACTIVE = "active"
SUBSCRIPTION_STATUS_CANCELED = "canceled"
SUBSCRIPTION_STATUS_PAST_DUE = "past_due"


class Subscription(TimestampMixin, Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_price_id: Mapped[str | None] = mapped_column(String(255))
    tier: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=SUBSCRIPTION_STATUS_ACTIVE)
    current_period_start: Mapped[date | None] = mapped_column(Date)
    current_period_end: Mapped[date | None] = mapped_column(Date)

    user = relationship("User", back_populates="subscriptions")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Subscription id={self.id} tier={self.tier} status={self.status}>"
