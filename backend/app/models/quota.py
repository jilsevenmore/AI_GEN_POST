import uuid
from datetime import datetime, date, timezone
from decimal import Decimal
from sqlalchemy import DateTime, Date, ForeignKey, Integer, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Quota(Base):
    __tablename__ = "quotas"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    daily_free_requests_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    daily_free_requests_limit: Mapped[int] = mapped_column(Integer, default=12, nullable=False)
    daily_spend_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("0.0"), nullable=False)
    daily_spend_cap_usd: Mapped[Decimal] = mapped_column(Numeric(10, 4), default=Decimal("10.0"), nullable=False)
    regenerations_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    regenerations_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    last_reset_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="quotas")

    def __repr__(self) -> str:
        return f"<Quota(id={self.id}, company_id={self.company_id})>"