from __future__ import annotations

import asyncio
import hashlib
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import httpx

from app.core.config import settings
from app.services.supabase import SupabaseRestClient
from worker.sources import go_tokyo, tokyo_art_beat
from worker.sources.common import Exhibition, normalized_name

TOKYO = ZoneInfo("Asia/Tokyo")
SYNC_PREFIX = "exhibition-sync:"


@dataclass(slots=True)
class SyncResult:
    fetched: dict[str, int]
    matched: int
    merged: int
    unmatched_venue_count: int
    unmatched_venues_sample: list[str]
    upserted: int = 0
    deleted: int = 0


def _venue_candidates(name: str) -> set[str]:
    normalized = normalized_name(name)
    candidates = {normalized}
    for suffix in ("美術館", "博物館", "ミュージアム", "ギャラリー"):
        normalized_suffix = normalized_name(suffix)
        if normalized.endswith(normalized_suffix):
            candidates.add(normalized[: -len(normalized_suffix)])
    return {candidate for candidate in candidates if candidate}


def match_venue(exhibition: Exhibition, venues: list[dict[str, Any]]) -> dict[str, Any] | None:
    target = _venue_candidates(exhibition.venue_name)
    exact = [
        venue
        for venue in venues
        if target & _venue_candidates(str(venue.get("name_ja") or ""))
    ]
    if len(exact) == 1:
        return exact[0]

    target_name = normalized_name(exhibition.venue_name)
    partial = []
    for venue in venues:
        venue_name = normalized_name(str(venue.get("name_ja") or ""))
        if min(len(target_name), len(venue_name)) >= 5 and (
            target_name in venue_name or venue_name in target_name
        ):
            partial.append(venue)
    return partial[0] if len(partial) == 1 else None


def _event_key(exhibition: Exhibition, venue: dict[str, Any]) -> str:
    identity = "|".join(
        (
            str(venue["id"]),
            normalized_name(exhibition.title),
            exhibition.starts_on.isoformat() if exhibition.starts_on else "",
            exhibition.ends_on.isoformat() if exhibition.ends_on else "",
        )
    )
    return SYNC_PREFIX + hashlib.sha256(identity.encode()).hexdigest()[:32]


def merge_exhibitions(items: list[tuple[Exhibition, dict[str, Any]]]) -> list[tuple[Exhibition, dict[str, Any]]]:
    merged: dict[str, tuple[Exhibition, dict[str, Any]]] = {}
    for exhibition, venue in items:
        key = _event_key(exhibition, venue)
        previous = merged.get(key)
        if not previous:
            merged[key] = (exhibition, venue)
            continue
        old = previous[0]
        sources = "+".join(sorted(set(old.source.split("+")) | {exhibition.source}))
        merged[key] = (
            Exhibition(
                source=sources,
                source_id=old.source_id,
                source_url=old.source_url,
                title=old.title,
                venue_name=old.venue_name,
                starts_on=old.starts_on or exhibition.starts_on,
                ends_on=old.ends_on or exhibition.ends_on,
                description=max(
                    (old.description, exhibition.description), key=lambda value: len(value or "")
                ),
                price_min_jpy=old.price_min_jpy if old.price_min_jpy is not None else exhibition.price_min_jpy,
                price_max_jpy=old.price_max_jpy if old.price_max_jpy is not None else exhibition.price_max_jpy,
                price_note=max((old.price_note, exhibition.price_note), key=lambda value: len(value or "")),
                official_url=old.official_url or exhibition.official_url,
            ),
            venue,
        )
    return list(merged.values())


def build_row(exhibition: Exhibition, venue: dict[str, Any], verified_at: datetime) -> dict[str, Any]:
    start = exhibition.starts_on.isoformat() if exhibition.starts_on else None
    end = exhibition.ends_on.isoformat() if exhibition.ends_on else None
    period = " ～ ".join(value for value in (start, end) if value) or None
    return {
        "source_key": _event_key(exhibition, venue),
        "name_ja": exhibition.title,
        "name_en": None,
        "name_zh": None,
        "category": "exhibition",
        "area": venue.get("area"),
        "latitude": venue["latitude"],
        "longitude": venue["longitude"],
        "location_text": venue["name_ja"],
        "address_ja": venue.get("address_ja") or venue.get("location_text"),
        "ward_city": venue.get("ward_city"),
        "official_url": exhibition.official_url,
        "access_url": venue.get("access_url"),
        "exhibitions_url": exhibition.official_url,
        "price_min_jpy": exhibition.price_min_jpy,
        "price_max_jpy": exhibition.price_max_jpy,
        "price_note": exhibition.price_note,
        "exhibition_starts_on": start,
        "exhibition_ends_on": end,
        "exhibition_period_note": period,
        "description_ja": exhibition.description,
        "description_en": None,
        "source_name": exhibition.source,
        "source_url": exhibition.source_url,
        "verified_at": verified_at.isoformat(),
        "status": "operating",
        "updated_at": verified_at.isoformat(),
    }


async def _read_all(client: SupabaseRestClient, *, filter_params: dict[str, str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    while True:
        params = {**filter_params, "select": "*", "limit": "500", "offset": str(len(rows))}
        page = await client.request("GET", "locations", params=params, profile="travel")
        if not page:
            return rows
        rows.extend(page)


async def sync_exhibitions(*, dry_run: bool = False) -> SyncResult:
    if not settings.supabase_public_url or not settings.supabase_secret_key:
        raise RuntimeError("SUPABASE_PUBLIC_URL and SUPABASE_SECRET_KEY are required")
    database = SupabaseRestClient(settings.supabase_public_url, settings.supabase_secret_key)
    venues = await _read_all(database, filter_params={"source_key": "like.tokyo-art-top50:*"})
    if not venues:
        raise RuntimeError("No tokyo-art-top50 venues found in travel.locations")

    today = datetime.now(TOKYO).date()
    headers = {"User-Agent": "TokyoEventMapExhibitionWorker/1.0"}
    async with httpx.AsyncClient(headers=headers, follow_redirects=True, timeout=45) as web:
        go_items, tab_items = await asyncio.gather(
            go_tokyo.fetch(web), tokyo_art_beat.fetch(web, today=today)
        )
    fetched = {"go-tokyo": len(go_items), "tokyo-art-beat": len(tab_items)}
    matched: list[tuple[Exhibition, dict[str, Any]]] = []
    unmatched = set()
    for exhibition in [*go_items, *tab_items]:
        if exhibition.ends_on and exhibition.ends_on < today:
            continue
        venue = match_venue(exhibition, venues)
        if venue:
            matched.append((exhibition, venue))
        else:
            unmatched.add(exhibition.venue_name)
    merged = merge_exhibitions(matched)
    result = SyncResult(fetched, len(matched), len(merged), len(unmatched), sorted(unmatched)[:20])
    if dry_run:
        return result

    now = datetime.now(TOKYO)
    rows = [build_row(exhibition, venue, now) for exhibition, venue in merged]
    for offset in range(0, len(rows), 100):
        batch = rows[offset : offset + 100]
        await database.request(
            "POST",
            "locations",
            params={"on_conflict": "source_key"},
            body=batch,
            prefer="resolution=merge-duplicates,return=minimal",
            profile="travel",
        )
        result.upserted += len(batch)

    existing = await _read_all(database, filter_params={"source_key": f"like.{SYNC_PREFIX}*"})
    current_keys = {row["source_key"] for row in rows}
    stale_ids = [row["id"] for row in existing if row["source_key"] not in current_keys]
    for offset in range(0, len(stale_ids), 100):
        ids = stale_ids[offset : offset + 100]
        await database.request(
            "DELETE",
            "locations",
            params={"id": f"in.({','.join(ids)})"},
            prefer="return=minimal",
            profile="travel",
        )
        result.deleted += len(ids)
    return result


def result_dict(result: SyncResult) -> dict[str, Any]:
    return asdict(result)
