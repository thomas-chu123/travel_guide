from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.schemas import EventFeature, EventFeatureCollection, EventProperties, PointGeometry
from app.db.models import Event
from app.db.session import get_session
from app.repositories.events import TOKYO_BOUNDS, published_events_in_viewport

router = APIRouter()


def as_feature(event: Event) -> EventFeature:
    occurrence = min(event.occurrences, key=lambda item: item.starts_at, default=None)
    return EventFeature(
        id=event.id,
        geometry=PointGeometry(coordinates=(event.venue.longitude, event.venue.latitude)),
        properties=EventProperties(
            id=event.id,
            venue_id=event.venue.id,
            venue_name=event.venue.name,
            ward=event.venue.ward,
            category=event.category,  # type: ignore[arg-type]
            title=event.title,
            fee_kind=event.fee_kind,  # type: ignore[arg-type]
            price_min_jpy=event.price_min_jpy,
            price_max_jpy=event.price_max_jpy,
            starts_at=occurrence.starts_at if occurrence else None,
            ends_at=occurrence.ends_at if occurrence else None,
        ),
    )


@router.get("/events", response_model=EventFeatureCollection)
async def list_events(
    west: float = Query(TOKYO_BOUNDS[0], ge=-180, le=180),
    south: float = Query(TOKYO_BOUNDS[1], ge=-90, le=90),
    east: float = Query(TOKYO_BOUNDS[2], ge=-180, le=180),
    north: float = Query(TOKYO_BOUNDS[3], ge=-90, le=90),
    starts_before: datetime | None = None,
    ends_after: datetime | None = None,
    category: list[str] | None = Query(default=None),
    session: Session = Depends(get_session),
) -> EventFeatureCollection:
    if west >= east or south >= north:
        raise HTTPException(status_code=422, detail="viewport bounds are invalid")
    events = published_events_in_viewport(
        session,
        west=west,
        south=south,
        east=east,
        north=north,
        starts_before=starts_before,
        ends_after=ends_after,
        categories=category,
    )
    features = [as_feature(event) for event in events]
    return EventFeatureCollection(features=features, returned=len(features))
