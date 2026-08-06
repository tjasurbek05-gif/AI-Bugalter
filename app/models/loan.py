from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

LOAN_TYPE_LEND = "lend"  # they owe the user
LOAN_TYPE_OWE = "owe"  # user owes them

LOAN_STATUS_PENDING = "pending"
LOAN_STATUS_PAID = "paid"
LOAN_STATUS_OVERDUE = "overdue"


class Loan(TimestampMixin, Base):
    __tablename__ = "loans"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    person_name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="UZS")
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default=LOAN_STATUS_PENDING)
    description: Mapped[str | None] = mapped_column(Text)
    reminder_sent_at: Mapped[datetime | None] = mapped_column(DateTime)

    user = relationship("User", back_populates="loans")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Loan id={self.id} {self.type} {self.person_name} {self.amount}{self.currency} status={self.status}>"
