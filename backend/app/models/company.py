import uuid
from datetime import datetime, timezone
from sqlalchemy import DateTime, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.session import Base


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
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
    users: Mapped[list["User"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    brand_kit: Mapped["BrandKit"] = relationship(back_populates="company", uselist=False, cascade="all, delete-orphan")
    jobs: Mapped[list["Job"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    contents: Mapped[list["Content"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    images: Mapped[list["Image"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    channel_connections: Mapped[list["ChannelConnection"]] = relationship(back_populates="company", cascade="all, delete-orphan")
    quotas: Mapped[list["Quota"]] = relationship(back_populates="company", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Company(id={self.id}, name={self.name})>"