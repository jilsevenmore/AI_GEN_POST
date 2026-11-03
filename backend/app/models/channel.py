import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, String, ForeignKey, Boolean, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class ChannelConnection(Base):
    __tablename__ = "channel_connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    platform: Mapped[str] = mapped_column(String(20), nullable=False)  # instagram, facebook, linkedin
    external_account_id: Mapped[str] = mapped_column(String(255), nullable=False)
    account_name: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="channel_connections")
    publish_attempts: Mapped[list["PublishAttempt"]] = relationship(back_populates="channel", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ChannelConnection(id={self.id}, platform={self.platform}, company_id={self.company_id})>"


Index("ix_channel_connections_company_id", ChannelConnection.company_id)

# Unique constraint (also created in migration)
UniqueConstraint(
    "company_id", "platform", "external_account_id",
    name="uq_channel_company_platform_account",
    table="channel_connections"
)