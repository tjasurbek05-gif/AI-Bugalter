from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

DEFAULT_CATEGORIES = {
    "food": "🍔",
    "transport": "🚕",
    "utilities": "🏠",
    "shopping": "🛍️",
    "health": "💊",
    "entertainment": "🎬",
    "education": "📚",
    "other": "📌",
}


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_category_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(10))
    color: Mapped[str | None] = mapped_column(String(10))

    user = relationship("User", back_populates="categories")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Category id={self.id} name={self.name}>"
