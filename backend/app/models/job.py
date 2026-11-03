import uuid
from datetime import datetime, timezone
from typing import List
from sqlalchemy import DateTime, String, ForeignKey, Text, Integer, Index, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # blog, post
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    topic: Mapped[str] = mapped_column(Text, nullable=False)
    tone: Mapped[str | None] = mapped_column(String(100), nullable=True)
    audience: Mapped[str | None] = mapped_column(String(200), nullable=True)
    keywords: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    image_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    platforms: Mapped[List[str]] = mapped_column(ARRAY(String), default=list, nullable=False)
    use_references: Mapped[bool] = mapped_column(default=True, nullable=False)
    reference_image_ids: Mapped[List[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    current_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    regeneration_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
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
    company: Mapped["Company"] = relationship(back_populates="jobs")
    user: Mapped["User"] = relationship(back_populates="jobs", foreign_keys=[user_id])
    content: Mapped["Content"] = relationship(back_populates="job", uselist=False, cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Job(id={self.id}, type={self.type}, status={self.status}, company_id={self.company_id})>"


# Explicit indexes
Index("ix_jobs_company_id", Job.company_id)
Index("ix_jobs_user_id", Job.user_id)
Index("ix_jobs_status", Job.status)