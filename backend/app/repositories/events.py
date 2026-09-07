from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Event, EventOccurrence, Venue

TOKYO_BOUNDS = (139.56, 35.52, 139.92, 35.82)  # west, south, east, north


def published_events_in_viewport(
    session: Session,
    *,
    west: float,
    south: float,
    east: float,
    north: float,
    starts_before: datetime | None = None,
    ends_after: datetime | None = None,
    categories: list[str] | None = None,
    limit: int = 500,
) -> list[Event]:
    statement: Select[tuple[Event]] = (
        select(Event)
        .join(Event.venue)
        .join(Event.occurrences)
        .options(selectinload(Event.venue), selectinload(Event.occurrences))
        .where(
            Event.status == "published",
            Venue.longitude.between(west, east),
            Venue.latitude.between(south, north),
        )
        .order_by(EventOccurrence.starts_at)
        .limit(limit)
    )
    if categories:
        statement = statement.where(Event.category.in_(categories))
    if starts_before:
        statement = statement.where(EventOccurrence.starts_at < starts_before)
    if ends_after:
        statement = statement.where(EventOccurrence.ends_at > ends_after)
    return list(session.scalars(statement).unique())
