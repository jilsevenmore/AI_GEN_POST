import uuid
from datetime import datetime, timezone
from typing import List
from sqlalchemy import DateTime, String, ForeignKey, Text, Integer, Boolean, Index, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Image(Base):
    __tablename__ = "images"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    content_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contents.id", ondelete="SET NULL"), nullable=True
    )
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    thumbnail_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(10), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    is_global: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    search_vector: Mapped[str | None] = mapped_column(Text, nullable=True)  # For pgvector
    approved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
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
    company: Mapped["Company"] = relationship(back_populates="images")
    content: Mapped["Content"] = relationship(back_populates="images", foreign_keys=[content_id])

    def __repr__(self) -> str:
        return f"<Image(id={self.id}, company_id={self.company_id}, is_global={self.is_global})>"


Index("ix_images_company_id", Image.company_id)
Index("ix_images_is_global", Image.is_global)
Index("ix_images_approved_at", Image.approved_at)