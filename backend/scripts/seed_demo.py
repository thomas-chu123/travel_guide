"""Create idempotent local demo data for visual development tests."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.db.models import Event, EventOccurrence, Venue
from app.db.session import SessionLocal, create_local_schema

DEMO_EVENTS = [
    {
        "key": "ueno-autumn-art",
        "venue": {"name": "上野公園", "ward": "台東区", "latitude": 35.7148, "longitude": 139.7744},
        "category": "exhibition",
        "title": "東京藝術展（示範資料）",
        "fee_kind": "paid",
        "price_min_jpy": 1200,
    },
    {
        "key": "asakusa-walk",
        "venue": {"name": "浅草寺", "ward": "台東区", "latitude": 35.7148, "longitude": 139.7967},
        "category": "attraction",
        "title": "淺草文化散策（示範資料）",
        "fee_kind": "free",
        "price_min_jpy": None,
    },
    {
        "key": "shibuya-night-market",
        "venue": {"name": "渋谷スクランブルスクエア", "ward": "渋谷区", "latitude": 35.6580, "longitude": 139.7016},
        "category": "activity",
        "title": "澀谷夜間市集（示範資料）",
        "fee_kind": "free",
        "price_min_jpy": None,
    },
]


def seed() -> int:
    create_local_schema()
    now = datetime.now(UTC)
    created = 0

    with SessionLocal() as session:
        for item in DEMO_EVENTS:
            source_url = f"demo://{item['key']}"
            if session.scalar(select(Event).where(Event.source_url == source_url)):
                continue

            venue_data = item["venue"]
            venue = session.scalar(select(Venue).where(Venue.name == venue_data["name"]))
            if venue is None:
                venue = Venue(**venue_data)
                session.add(venue)
                session.flush()

            event = Event(
                venue_id=venue.id,
                category=item["category"],
                title=item["title"],
                source_language="ja",
                status="published",
                fee_kind=item["fee_kind"],
                price_min_jpy=item["price_min_jpy"],
                source_name="local-demo",
                source_url=source_url,
            )
            session.add(event)
            session.flush()
            session.add(
                EventOccurrence(
                    event_id=event.id,
                    starts_at=now - timedelta(days=1),
                    ends_at=now + timedelta(days=30),
                )
            )
            created += 1
        session.commit()

    return created


if __name__ == "__main__":
    print(f"Seeded {seed()} demo event(s).")
