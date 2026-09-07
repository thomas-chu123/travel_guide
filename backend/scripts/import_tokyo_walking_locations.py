"""Import curated Tokyo Walking Map points into travel.locations via PostgREST."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import re
import ssl
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import certifi

SOURCE_REPOSITORY = "https://github.com/code4fukui/tokyo-walking-map"
SOURCE_CSV_URL = SOURCE_REPOSITORY + "/blob/main/tokyo-walking-map_placemark_ja.csv"
CSV_NAMES = ("tokyo-walking-map_placemark_ja.csv", "tokyo-walking-map_placemark_en.csv")
URL_ONLY = re.compile(r"^https?://[^\s<]+$", re.IGNORECASE)
ROUTE_POINT_NAMES_JA = {
    "スタート", "ゴール", "AED設置箇所", "ウォーキングポイント", "説明板", "ウォーキングサイン",
    "トイレ", "だれでもトイレ", "コンビニ", "バス停（路線バス）",
}
ROUTE_POINT_NAMES_EN = {
    "Start", "Goal", "AED location", "Recommended spots", "Explanation board", "Walking signs",
    "Restroom", "Accessible restroom", "Convenience store", "Bus stop",
}


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def clean_description(value: str) -> str | None:
    parser = TextExtractor()
    parser.feed(value)
    cleaned = " ".join(" ".join(parser.parts).split())
    return html.unescape(cleaned) or None


def is_route_or_transport_point(name_ja: str, name_en: str) -> bool:
    normalized_ja = name_ja.strip()
    normalized_en = name_en.strip()
    if normalized_ja in ROUTE_POINT_NAMES_JA or normalized_en in ROUTE_POINT_NAMES_EN:
        return True
    if normalized_ja.endswith("駅") or normalized_en.lower().endswith((" station", " sta.", " sta")):
        return True
    if normalized_ja.isdecimal() or normalized_en.isdecimal():
        return True
    return any(token in normalized_ja for token in ("AED", "トイレ", "コンビニ", "ウォーキング", "バス停"))


def category_for(name_ja: str, name_en: str) -> str:
    name = f"{name_ja} {name_en}".lower()
    if any(token in name for token in ("公園", "緑地", "庭園", "park", "garden")):
        return "park"
    if any(token in name for token in ("神社", "寺", "shrine", "temple")):
        return "temple_shrine"
    if any(token in name for token in ("美術館", "博物館", "資料館", "museum", "gallery")):
        return "museum"
    if any(token in name for token in ("動物園", "zoo", "水族館", "aquarium")):
        return "zoo_aquarium"
    if any(token in name for token in ("商店", "カフェ", "食堂", "restaurant", "cafe")):
        return "food_shopping"
    return "point_of_interest"


def price_note_for(description_ja: str | None, description_en: str | None) -> str | None:
    text = f"{description_ja or ''} {description_en or ''}".lower()
    if "入園料" in text or "admission fee" in text or "entrance fee" in text:
        return "Admission fee required; amount is not provided by the source."
    return None


def source_key(name_ja: str, latitude: str, longitude: str) -> str:
    value = f"{name_ja}|{latitude}|{longitude}".encode()
    return hashlib.sha256(value).hexdigest()


def load_rows(data_dir: Path) -> list[dict[str, object]]:
    ja_path, en_path = (data_dir / name for name in CSV_NAMES)
    with ja_path.open(encoding="utf-8-sig", newline="") as handle:
        ja_rows = list(csv.DictReader(handle))
    with en_path.open(encoding="utf-8-sig", newline="") as handle:
        en_rows = list(csv.DictReader(handle))
    if len(ja_rows) != len(en_rows):
        raise ValueError("Japanese and English CSVs do not have the same number of rows")

    locations: list[dict[str, object]] = []
    for ja, en in zip(ja_rows, en_rows, strict=True):
        if ja["lat"] != en["lat"] or ja["lng"] != en["lng"]:
            raise ValueError("Japanese and English CSV coordinates do not align")
        if is_route_or_transport_point(ja["name"], en["name"]):
            continue
        description_ja = clean_description(ja["description"])
        description_en = clean_description(en["description"])
        official_url = description_ja if description_ja and URL_ONLY.fullmatch(description_ja) else None
        locations.append(
            {
                "source_key": source_key(ja["name"], ja["lat"], ja["lng"]),
                "name_ja": ja["name"],
                "name_en": en["name"] or None,
                "category": category_for(ja["name"], en["name"]),
                "area": "Tokyo Metropolis",
                "latitude": float(ja["lat"]),
                "longitude": float(ja["lng"]),
                "location_text": None,
                "official_url": official_url,
                "price_min_jpy": None,
                "price_max_jpy": None,
                "price_note": price_note_for(description_ja, description_en),
                "exhibition_starts_on": None,
                "exhibition_ends_on": None,
                "exhibition_period_note": None,
                "description_ja": description_ja,
                "description_en": description_en,
                "source_url": SOURCE_CSV_URL,
            }
        )
    return locations


def post_rows(base_url: str, key: str, rows: list[dict[str, object]], dry_run: bool) -> None:
    if dry_run:
        print(json.dumps({"would_import": len(rows)}, ensure_ascii=False))
        return
    endpoint = base_url.rstrip("/") + "/rest/v1/locations?on_conflict=source_key"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept-Profile": "travel",
        "Content-Profile": "travel",
        "Prefer": "resolution=merge-duplicates,return=minimal",
        "User-Agent": "TokyoEventMapImporter/1.0",
    }
    for start in range(0, len(rows), 200):
        request = Request(
            endpoint,
            data=json.dumps(rows[start : start + 200], ensure_ascii=False).encode(),
            headers=headers,
            method="POST",
        )
        try:
            with urlopen(
                request,
                timeout=30,
                context=ssl.create_default_context(cafile=certifi.where()),
            ) as response:
                if response.status not in (200, 201, 204):
                    raise RuntimeError(f"Unexpected response status: {response.status}")
        except HTTPError as error:
            raise RuntimeError(error.read().decode("utf-8", "replace")) from error
        print(f"imported {min(start + 200, len(rows))}/{len(rows)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rows = load_rows(args.data_dir)
    base_url = os.environ.get("SUPABASE_PUBLIC_URL")
    key = os.environ.get("SUPABASE_SECRET_KEY")
    if not base_url or not key:
        sys.exit("SUPABASE_PUBLIC_URL and SUPABASE_SECRET_KEY must be configured")
    post_rows(base_url, key, rows, args.dry_run)


if __name__ == "__main__":
    main()
