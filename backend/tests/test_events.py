from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from app.db.models import Event, EventOccurrence, Venue
from app.db.session import configure_database, create_local_schema, get_session_factory
from app.main import app


def test_events_returns_only_published_events_in_viewport(tmp_path) -> None:
    configure_database(f"sqlite:///{tmp_path / 'event-map.db'}")
    create_local_schema()
    with get_session_factory()() as session:
        venue = Venue(name="上野公園", ward="台東区", latitude=35.7148, longitude=139.7744)
        session.add(venue)
        session.flush()
        published = Event(venue_id=venue.id, category="exhibition", title="公開中", status="published")
        candidate = Event(venue_id=venue.id, category="activity", title="未公開", status="candidate")
        session.add_all([published, candidate])
        session.flush()
        now = datetime.now(UTC)
        session.add_all(
            [
                EventOccurrence(event_id=published.id, starts_at=now, ends_at=now + timedelta(days=1)),
                EventOccurrence(event_id=candidate.id, starts_at=now, ends_at=now + timedelta(days=1)),
            ]
        )
        session.commit()

    with TestClient(app) as client:
        response = client.get("/api/v1/events?west=139.7&south=35.6&east=139.8&north=35.8")

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["returned"] == 1
    assert payload["features"][0]["properties"]["title"] == "公開中"
