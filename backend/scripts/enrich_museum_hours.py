"""Discover official museum hours and optionally update travel.locations once.

The command is dry-run by default. SearXNG is used only to discover candidate
official pages; values are extracted from the pages themselves, never snippets.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import ClassVar
from urllib.parse import urljoin, urlparse

import httpx
from dotenv import dotenv_values

from app.services.supabase import SupabaseRestClient
from scripts.enrich_locations import read_all

ART_CATEGORIES = {
    "museum", "art_museum", "gallery", "exhibition_space", "convention_center"
}
HOURS_WORDS = ("開館時間", "開館時刻", "営業時間", "開館・休館", "利用時間")
CLOSED_WORDS = ("休館日", "休館", "休業日")
TIME_RE = re.compile(r"(?:[01]?\d|2[0-3])\s*[:：時]\s*[0-5]\d(?:\s*分)?")
SPACE_RE = re.compile(r"[ \t\u3000]+")
LINK_HINT_RE = re.compile(
    r"開館|休館|利用案内|来館|hours?|visit|guide|information", re.IGNORECASE
)


class PageParser(HTMLParser):
    BLOCKS: ClassVar = {"p", "div", "li", "dt", "dd", "tr", "h1", "h2", "h3", "br"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._anchor: list[str] = []
        self._ignored = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self._ignored += 1
        if self._ignored:
            return
        if tag in self.BLOCKS:
            self.parts.append("\n")
        if tag == "a":
            self._href = dict(attrs).get("href")
            self._anchor = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self._ignored:
            self._ignored -= 1
            return
        if self._ignored:
            return
        if tag == "a" and self._href:
            self.links.append((self._href, "".join(self._anchor).strip()))
            self._href = None
            self._anchor = []
        if tag in self.BLOCKS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored:
            return
        self.parts.append(data)
        if self._href is not None:
            self._anchor.append(data)

    def text_lines(self) -> list[str]:
        return [SPACE_RE.sub(" ", line).strip() for line in "".join(self.parts).splitlines()
                if SPACE_RE.sub(" ", line).strip()]


@dataclass(frozen=True)
class Discovery:
    opening_hours: str
    source_url: str


def extract_hours(html: str) -> str | None:
    parser = PageParser()
    parser.feed(html)
    lines = parser.text_lines()
    candidates: list[tuple[int, str]] = []
    for index, line in enumerate(lines):
        window = " ".join(lines[index:index + 3])
        has_hours_word = any(word in window for word in HOURS_WORDS)
        if not has_hours_word or not TIME_RE.search(window):
            continue
        score = 5 + sum(word in window for word in CLOSED_WORDS)
        candidates.append((score, window[:500]))
    if not candidates:
        return None
    hours = max(candidates, key=lambda item: (item[0], -len(item[1])))[1]
    hours = re.sub(r"\s+", " ", hours).strip(" |｜")
    return hours


def same_site(left: str, right: str) -> bool:
    a, b = urlparse(left).hostname or "", urlparse(right).hostname or ""
    return a == b or a.endswith("." + b) or b.endswith("." + a)


def useful_internal_links(base_url: str, html: str) -> list[str]:
    parser = PageParser()
    parser.feed(html)
    found: list[str] = []
    for href, label in parser.links:
        absolute = urljoin(base_url, href).split("#", 1)[0]
        if (
            absolute.startswith(("http://", "https://"))
            and same_site(base_url, absolute)
            and LINK_HINT_RE.search(label + " " + href)
            and absolute not in found
        ):
            found.append(absolute)
    return found


async def fetch_html(client: httpx.AsyncClient, url: str) -> tuple[str, str] | None:
    try:
        response = await client.get(url, follow_redirects=True)
        response.raise_for_status()
        if "html" not in response.headers.get("content-type", ""):
            return None
        return str(response.url), response.text
    except (httpx.HTTPError, ValueError):
        return None


async def search_candidates(
    client: httpx.AsyncClient, searxng_url: str, venue: dict
) -> list[str]:
    query = f'"{venue["name_ja"]}" 開館時間 休館日 公式'
    try:
        response = await client.get(
            searxng_url.rstrip("/") + "/search", params={"q": query, "format": "json"}
        )
        response.raise_for_status()
        results = response.json().get("results", [])
    except (httpx.HTTPError, ValueError, AttributeError):
        return []
    urls = [item.get("url") for item in results if isinstance(item, dict)]
    official = venue.get("official_url")
    if official:
        urls = [url for url in urls if isinstance(url, str) and same_site(official, url)]
    return [url for url in urls if isinstance(url, str) and url.startswith(("http://", "https://"))][:3]


async def discover(
    client: httpx.AsyncClient, venue: dict, searxng_url: str | None
) -> Discovery | None:
    official_url = venue.get("official_url")
    if not official_url:
        return None
    queue = [official_url]
    visited: set[str] = set()
    searched = False
    while len(visited) < 5:
        if not queue:
            if searched or not searxng_url:
                break
            queue.extend(await search_candidates(client, searxng_url, venue))
            searched = True
            if not queue:
                break
        url = queue.pop(0)
        if url in visited:
            continue
        visited.add(url)
        fetched = await fetch_html(client, url)
        if not fetched:
            continue
        final_url, html = fetched
        if not same_site(official_url, final_url):
            continue
        if hours := extract_hours(html):
            return Discovery(hours, final_url)
        queue.extend(link for link in useful_internal_links(final_url, html) if link not in visited)
    return None


async def run(args: argparse.Namespace) -> None:
    import os

    config = {**dotenv_values(Path(__file__).resolve().parents[2] / ".env"), **os.environ}
    supabase_url = config.get("SUPABASE_PUBLIC_URL")
    supabase_key = config.get("SUPABASE_SECRET_KEY")
    if not supabase_url or not supabase_key:
        raise RuntimeError("SUPABASE_PUBLIC_URL and SUPABASE_SECRET_KEY are required")
    database = SupabaseRestClient(supabase_url, supabase_key)
    rows = await read_all(database)
    venues = [
        row for row in rows
        if row.get("category") in ART_CATEGORIES
        and (args.overwrite or not row.get("opening_hours"))
    ]
    if args.limit is not None:
        venues = venues[:args.limit]

    headers = {"User-Agent": "TokyoWalkingMapHoursAudit/1.0 (+official-site verification)"}
    results: list[dict] = []
    async with httpx.AsyncClient(timeout=args.timeout, headers=headers) as web:
        for number, venue in enumerate(venues, 1):
            found = await discover(web, venue, config.get("SEARXNG_URL"))
            item = {
                "id": venue["id"], "name_ja": venue["name_ja"],
                "before": venue.get("opening_hours"),
                "opening_hours": found.opening_hours if found else None,
                "source_url": found.source_url if found else None,
            }
            results.append(item)
            print(f"[{number}/{len(venues)}] {venue['name_ja']}: " + ("found" if found else "skipped"))

    args.output.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "generated_at": datetime.now(UTC).isoformat(), "apply": args.apply,
        "candidates": len(venues), "found": sum(bool(r["opening_hours"]) for r in results),
        "results": results,
    }
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {args.output}")
    if not args.apply:
        print("dry-run only; rerun with --apply to update Supabase")
        return

    verified_at = datetime.now(UTC).isoformat()
    updated = 0
    for result in results:
        if not result["opening_hours"]:
            continue
        original = next(row for row in venues if row["id"] == result["id"])
        response = await database.request(
            "PATCH", "locations", profile="travel",
            params={"id": "eq." + result["id"], "updated_at": "eq." + original["updated_at"]},
            body={"opening_hours": result["opening_hours"], "verified_at": verified_at,
                  "updated_at": verified_at},
            prefer="return=representation",
        )
        if not response or response[0].get("opening_hours") != result["opening_hours"]:
            raise RuntimeError(f"Concurrent change or verification failed: {result['id']}")
        updated += 1
    print(f"updated {updated} locations")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write verified discoveries")
    parser.add_argument("--overwrite", action="store_true", help="replace existing hours")
    parser.add_argument("--limit", type=int, help="process only the first N candidates")
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--output", type=Path, default=Path("artifacts/museum-hours.json"))
    args = parser.parse_args()
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
