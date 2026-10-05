from decimal import Decimal

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

CLICK_STATE_CREATED = 0
CLICK_STATE_PAID = 2
CLICK_STATE_CANCELLED = -2


class ClickTransaction(TimestampMixin, Base):
    """One Click (click.uz) payment attempt for a premium plan purchase."""

    __tablename__ = "click_transactions"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    merchant_trans_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    click_trans_id: Mapped[str | None] = mapped_column(String(64), index=True)
    tier: Mapped[str] = mapped_column(String(50), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    state: Mapped[int] = mapped_column(Integer, default=CLICK_STATE_CREATED)

    user = relationship("User")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ClickTransaction id={self.id} tier={self.tier} state={self.state}>"
