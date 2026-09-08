from __future__ import annotations

import re
from datetime import UTC, date, datetime

import httpx

from worker.sources.common import Exhibition, clean_text, parse_jpy

SOURCE_URL = "https://www.tokyoartbeat.com/events/top"
CONTENTFUL_BASE = "https://cdn.prod.tabdev.net/api/cda/published"
SPACE = "j05yk38inose"
TOKEN_PATTERN = re.compile(r'accessToken:"([^"]+)"')
SCRIPT_PATTERN = re.compile(r'<script[^>]+src="([^"]+\.js)"')


def localized(value: object, locale: str = "ja-JP") -> object | None:
    if not isinstance(value, dict):
        return value
    return value.get(locale) or value.get("en-US") or next(iter(value.values()), None)


def content_date(value: object) -> date | None:
    return date.fromisoformat(str(value)[:10]) if value else None


def parse(payload: dict) -> list[Exhibition]:
    entries = payload.get("includes", {}).get("Entry", [])
    venues = {
        entry["sys"]["id"]: entry
        for entry in entries
        if entry.get("sys", {}).get("contentType", {}).get("sys", {}).get("id") == "venue"
    }
    exhibitions = []
    for item in payload.get("items", []):
        fields = item.get("fields", {})
        venue_link = localized(fields.get("venue")) or {}
        venue = venues.get(venue_link.get("sys", {}).get("id"))
        if not venue:
            continue
        venue_fields = venue.get("fields", {})
        title = clean_text(str(localized(fields.get("eventName")) or ""))
        venue_name = clean_text(str(localized(venue_fields.get("fullName")) or ""))
        if not title or not venue_name:
            continue
        starts_raw = localized(fields.get("scheduleStartsOn"))
        ends_raw = localized(fields.get("scheduleEndsOn"))
        starts_on = content_date(starts_raw)
        ends_on = content_date(ends_raw)
        fee_value = localized(fields.get("admissionFee"))
        if fee_value is None:
            fee_value = localized(fields.get("fee"))
        if isinstance(fee_value, (int, float)) or (
            isinstance(fee_value, str) and fee_value.isdigit()
        ):
            numeric_fee = int(fee_value)
            fee = "無料" if numeric_fee == 0 else f"{numeric_fee:,}円"
        else:
            fee = clean_text(str(fee_value or ""))
        price_min, price_max = parse_jpy(fee)
        slug = localized(fields.get("slug"))
        official_url = localized(fields.get("showsWebpage"))
        if not official_url and slug:
            official_url = f"https://www.tokyoartbeat.com/events/-/{slug}"
        exhibitions.append(
            Exhibition(
                source="tokyo-art-beat",
                source_id=item["sys"]["id"],
                source_url=SOURCE_URL,
                title=title,
                venue_name=venue_name,
                starts_on=starts_on,
                ends_on=ends_on,
                description=clean_text(str(localized(fields.get("description")) or "")),
                price_min_jpy=price_min,
                price_max_jpy=price_max,
                price_note=fee,
                official_url=str(official_url) if official_url else None,
            )
        )
    return exhibitions


async def discover_access_token(client: httpx.AsyncClient) -> str:
    page = await client.get(SOURCE_URL)
    page.raise_for_status()
    scripts = SCRIPT_PATTERN.findall(page.text)
    for script in reversed(scripts):
        response = await client.get(httpx.URL(SOURCE_URL).join(script))
        if response.is_success and CONTENTFUL_BASE in response.text:
            match = TOKEN_PATTERN.search(response.text)
            if match:
                return match.group(1)
    raise RuntimeError("Tokyo Art Beat public feed token was not found")


async def fetch(client: httpx.AsyncClient, today: date | None = None) -> list[Exhibition]:
    today = today or datetime.now(UTC).date()
    token = await discover_access_token(client)
    endpoint = f"{CONTENTFUL_BASE}/spaces/{SPACE}/environments/master/entries"
    results = []
    offset = 0
    while True:
        response = await client.get(
            endpoint,
            params={
                "access_token": token,
                "content_type": "event",
                "locale": "*",
                "include": 2,
                "limit": 500,
                "skip": offset,
                "fields.scheduleEndsOn[gte]": today.isoformat(),
            },
        )
        response.raise_for_status()
        payload = response.json()
        results.extend(parse(payload))
        offset += len(payload.get("items", []))
        if offset >= payload.get("total", 0) or not payload.get("items"):
            break
    return results
