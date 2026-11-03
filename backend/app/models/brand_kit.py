import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, String, ForeignKey, Text, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class BrandKit(Base):
    __tablename__ = "brand_kits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    tagline: Mapped[str | None] = mapped_column(String(500), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    primary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)  # #RRGGBB
    secondary_color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    use_openai_only: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
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
    company: Mapped["Company"] = relationship(back_populates="brand_kit")

    def __repr__(self) -> str:
        return f"<BrandKit(id={self.id}, company_id={self.company_id}, company_name={self.company_name})>"