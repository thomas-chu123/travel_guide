from __future__ import annotations

import hashlib
import re
from datetime import date
from html.parser import HTMLParser

import httpx

from worker.sources.common import Exhibition, clean_text, parse_jpy

SOURCE_URL = (
    "https://www.gotokyo.org/jp/see-and-do/arts-and-design/"
    "art-and-exhibitions/index.html"
)
DATE_PATTERN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日[～〜](\d{4})年(\d{1,2})月(\d{1,2})日")


class GoTokyoParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.depth = 0
        self.event_depth: int | None = None
        self.capture: str | None = None
        self.capture_link: str | None = None
        self.parts: list[str] = []
        self.current: dict[str, object] = {}
        self.items: list[dict[str, object]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag == "div":
            self.depth += 1
            if "wrap_exhibition" in (attrs_dict.get("class") or "").split():
                self.event_depth = self.depth
                self.current = {"paragraphs": []}
        if self.event_depth is not None and tag == "p":
            classes = (attrs_dict.get("class") or "").split()
            self.capture = "title" if "ttl" in classes else "venue" if "facility" in classes else "p"
            self.capture_link = attrs_dict.get("data-link")
            self.parts = []

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag == "p" and self.capture:
            value = clean_text("".join(self.parts))
            if value:
                if self.capture == "title":
                    self.current["title"] = value
                elif self.capture == "venue":
                    self.current["venue"] = value
                else:
                    self.current["paragraphs"].append(value)
            self.capture = None
            self.capture_link = None
        if tag == "div":
            if self.event_depth == self.depth:
                if self.current.get("title") and self.current.get("venue"):
                    self.items.append(self.current)
                self.event_depth = None
                self.current = {}
            self.depth -= 1


def parse(html: str) -> list[Exhibition]:
    parser = GoTokyoParser()
    parser.feed(html)
    exhibitions = []
    for item in parser.items:
        paragraphs = item["paragraphs"]
        date_index = next((i for i, text in enumerate(paragraphs) if DATE_PATTERN.fullmatch(text)), None)
        if date_index is None:
            continue
        match = DATE_PATTERN.fullmatch(paragraphs[date_index])
        values = [int(value) for value in match.groups()]
        starts_on = date(*values[:3])
        ends_on = date(*values[3:])
        description = paragraphs[date_index + 1] if len(paragraphs) > date_index + 1 else None
        price_parts = [text for text in paragraphs[date_index + 2 :] if "円" in text or "無料" in text]
        price_note = clean_text(" ".join(price_parts))
        price_min, price_max = parse_jpy(price_note)
        identity = "|".join((item["title"], item["venue"], starts_on.isoformat()))
        exhibitions.append(
            Exhibition(
                source="go-tokyo",
                source_id=hashlib.sha256(identity.encode()).hexdigest()[:24],
                source_url=SOURCE_URL,
                title=item["title"],
                venue_name=item["venue"],
                starts_on=starts_on,
                ends_on=ends_on,
                description=description,
                price_min_jpy=price_min,
                price_max_jpy=price_max,
                price_note=price_note,
                official_url=item.get("official_url"),
            )
        )
    return exhibitions


async def fetch(client: httpx.AsyncClient) -> list[Exhibition]:
    response = await client.get(SOURCE_URL)
    response.raise_for_status()
    return parse(response.text)
