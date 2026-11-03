import uuid
from datetime import datetime, timezone
from typing import Any, List
from sqlalchemy import DateTime, String, ForeignKey, Text, Boolean, Index, ARRAY
from sqlalchemy.dialects.postgresql import UUID, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Content(Base):
    __tablename__ = "contents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # blog, social_post
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    long_text: Mapped[str] = mapped_column(Text, nullable=False)
    platform_contents: Mapped[List[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    image_variants: Mapped[List[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    primary_image_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    safety_check_passed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    safety_flags: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
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
    job: Mapped["Job"] = relationship(back_populates="content", foreign_keys=[job_id])
    company: Mapped["Company"] = relationship(back_populates="contents")
    images: Mapped[List["Image"]] = relationship(back_populates="content", foreign_keys="Image.content_id")

    def __repr__(self) -> str:
        return f"<Content(id={self.id}, type={self.type}, job_id={self.job_id})>"


Index("ix_contents_company_id", Content.company_id)