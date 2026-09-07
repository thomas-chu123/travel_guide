import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_id() -> str:
    return str(uuid.uuid4())


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    address: Mapped[str | None] = mapped_column(String(500))
    ward: Mapped[str | None] = mapped_column(String(80), index=True)
    latitude: Mapped[float] = mapped_column(nullable=False)
    longitude: Mapped[float] = mapped_column(nullable=False)
    google_place_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, onupdate=datetime.now
    )

    events: Mapped[list["Event"]] = relationship(back_populates="venue")

    __table_args__ = (
        CheckConstraint("latitude >= -90 AND latitude <= 90", name="valid_venue_latitude"),
        CheckConstraint("longitude >= -180 AND longitude <= 180", name="valid_venue_longitude"),
    )


class Event(Base):
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    venue_id: Mapped[str] = mapped_column(ForeignKey("venues.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    source_language: Mapped[str] = mapped_column(String(16), nullable=False, default="ja")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="candidate", index=True)
    fee_kind: Mapped[str] = mapped_column(String(32), nullable=False, default="unknown")
    price_min_jpy: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    price_max_jpy: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    source_name: Mapped[str | None] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(String(2048))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.now, onupdate=datetime.now
    )

    venue: Mapped[Venue] = relationship(back_populates="events")
    occurrences: Mapped[list["EventOccurrence"]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "category IN ('exhibition', 'attraction', 'activity')", name="valid_event_category"
        ),
        CheckConstraint(
            "status IN ('candidate', 'published', 'rejected', 'stale')", name="valid_event_status"
        ),
        CheckConstraint(
            "fee_kind IN ('free', 'paid', 'unknown')", name="valid_fee_kind"
        ),
    )


class EventOccurrence(Base):
    __tablename__ = "event_occurrences"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(ForeignKey("events.id"), nullable=False, index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    event: Mapped[Event] = relationship(back_populates="occurrences")

    __table_args__ = (
        CheckConstraint("ends_at > starts_at", name="valid_occurrence_range"),
    )
