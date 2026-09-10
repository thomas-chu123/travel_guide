"""Discover reusable location descriptions and optionally update Supabase once.

The command is dry-run by default. It searches Wikimedia by the existing Japanese
name, verifies candidates against the existing coordinates/ward, and optionally
uses OpenStreetMap only as corroborating structured data. No arbitrary websites
or search-result snippets are scraped.

Apply ``sql/0009_location_enrichment_meta.sql`` before using ``--apply``.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from dotenv import dotenv_values

from app.services.supabase import SupabaseRestClient
from scripts.enrich_locations import read_all

WIKIDATA_REST = "https://www.wikidata.org/w/rest.php/wikibase/v1"
OVERPASS_APIS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
USER_AGENT = (
    "TokyoTravelGuideLocationEnricher/1.0 "
    "(https://github.com/thomas-chu123/travel_guide; one-time data audit)"
)
SPACE_RE = re.compile(r"[\s\u3000]+")
PUNCT_RE = re.compile(r"[・･·\-‐‑‒–—―,，.。()（）「」『』\[\]]")
CATEGORY_WORDS = {
    "park": ("公園", "庭園", "park", "garden"),
    "temple_shrine": ("神社", "神宮", "寺", "寺院", "宮", "shrine", "temple"),
    "museum": ("博物館", "資料館", "museum"),
    "art_museum": ("美術館", "museum", "gallery"),
    "gallery": ("画廊", "ギャラリー", "gallery"),
    "exhibition_space": ("展示", "展覧", "gallery", "exhibition"),
    "convention_center": ("会議", "コンベンション", "convention"),
}
TOKYO_LOCALITY_RE = re.compile(r"東京都([^0-9０-９,， ]+?[区市町村])")


@dataclass(frozen=True)
class Match:
    source: str
    source_id: str
    name: str
    latitude: float | None
    longitude: float | None
    description_ja: str | None = None
    description_zh: str | None = None
    name_en: str | None = None
    source_url: str | None = None
    license: str | None = None
    raw: dict[str, Any] | None = None


def normalize_name(value: str | None) -> str:
    text = unicodedata.normalize("NFKC", value or "").casefold()
    return PUNCT_RE.sub("", SPACE_RE.sub("", text))


def distance_m(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    radius = 6_371_000
    lat1, lat2 = math.radians(a_lat), math.radians(b_lat)
    d_lat = lat2 - lat1
    d_lon = math.radians(b_lon - a_lon)
    value = math.sin(d_lat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(d_lon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(value), math.sqrt(1 - value))


def category_compatible(category: str, text: str) -> bool:
    words = CATEGORY_WORDS.get(category)
    return not words or any(word.casefold() in text.casefold() for word in words)


def osm_category_compatible(category: str, tags: dict[str, Any]) -> bool:
    """Require an explicit OSM feature tag before generating prose from a match."""
    if category == "park":
        return tags.get("leisure") in {"park", "garden", "nature_reserve"}
    if category == "temple_shrine":
        return tags.get("amenity") == "place_of_worship" or tags.get("historic") in {
            "shrine", "temple"
        }
    if category in {"museum", "art_museum"}:
        return tags.get("tourism") == "museum"
    if category in {"gallery", "exhibition_space"}:
        return tags.get("tourism") in {"gallery", "museum"}
    if category == "convention_center":
        return tags.get("amenity") in {"conference_centre", "events_venue"}
    return False


def locality_labels(row: dict[str, Any]) -> tuple[str, str]:
    ward = row.get("ward_city")
    if ward and any(suffix in ward for suffix in "区市町村"):
        zh_ward = ward.replace("区", "區")
        return f"東京都{ward}", f"東京都{zh_ward}"
    address = row.get("address_ja") or ""
    found = TOKYO_LOCALITY_RE.search(address)
    if found:
        locality = found.group(1)
        return f"東京都{locality}", f"東京都{locality.replace('区', '區')}"
    return "東京都内", "東京都內"


def structured_template(
    row: dict[str, Any], match: Match
) -> tuple[str | None, str | None]:
    """Create deliberately modest prose only from an exact, typed OSM object."""
    if match.source != "openstreetmap" or not match.raw:
        return None, None
    if normalize_name(row.get("name_ja")) != normalize_name(match.name):
        return None, None
    category = str(row.get("category", ""))
    if not osm_category_compatible(category, match.raw):
        return None, None
    names = {
        "park": ("公園", "公園"),
        "temple_shrine": ("寺社", "寺廟或神社"),
        "museum": ("博物館", "博物館"),
        "art_museum": ("美術館", "美術館"),
        "gallery": ("ギャラリー", "藝廊"),
        "exhibition_space": ("展示施設", "展覽設施"),
        "convention_center": ("会議・イベント施設", "會議及活動設施"),
    }
    kind_ja, kind_zh = names[category]
    locality_ja, locality_zh = locality_labels(row)
    name_zh = row.get("name_zh") or row["name_ja"]
    return (
        f'{row["name_ja"]}は{locality_ja}にある{kind_ja}です。',
        f"{name_zh}是位於{locality_zh}的{kind_zh}。",
    )


def score_match(row: dict[str, Any], match: Match) -> tuple[int, list[str], float | None]:
    score, evidence = 0, []
    row_name = normalize_name(row.get("name_ja"))
    candidate_name = normalize_name(match.name)
    if row_name and row_name == candidate_name:
        score += 50
        evidence.append("exact_normalized_name")
    elif row_name and (row_name in candidate_name or candidate_name in row_name):
        score += 25
        evidence.append("partial_name")

    distance = None
    if all(value is not None for value in (
        row.get("latitude"), row.get("longitude"), match.latitude, match.longitude
    )):
        distance = distance_m(
            float(row["latitude"]), float(row["longitude"]),
            float(match.latitude), float(match.longitude),
        )
        if distance <= 100:
            score += 30
            evidence.append("within_100m")
        elif distance <= 300:
            score += 15
            evidence.append("within_300m")
        elif distance > 1_000:
            return 0, ["rejected_distance_over_1km"], distance

    raw_context = " ".join(str(value) for value in (match.raw or {}).values() if value)
    context = " ".join(filter(None, (match.description_ja, raw_context)))
    if (
        osm_category_compatible(str(row.get("category", "")), match.raw or {})
        or category_compatible(str(row.get("category", "")), context)
    ):
        score += 10
        evidence.append("compatible_category")
    ward = row.get("ward_city")
    if ward and ward in context:
        score += 10
        evidence.append("ward_in_description")
    return score, evidence, distance


def claim_coordinate(entity: dict[str, Any]) -> tuple[float | None, float | None]:
    try:
        if "statements" in entity:
            value = entity["statements"]["P625"][0]["value"]["content"]
        else:
            value = entity["claims"]["P625"][0]["mainsnak"]["datavalue"]["value"]
        return float(value["latitude"]), float(value["longitude"])
    except (KeyError, IndexError, TypeError, ValueError):
        return None, None


async def wikipedia_extract(
    client: httpx.AsyncClient, site: str, title: str
) -> tuple[str | None, str | None]:
    language = {"jawiki": "ja", "zhwiki": "zh"}.get(site)
    if not language:
        return None, None
    encoded = quote(title.replace(" ", "_"), safe="")
    response = await client.get(
        f"https://{language}.wikipedia.org/api/rest_v1/page/summary/{encoded}",
        params={"redirect": "true"},
    )
    response.raise_for_status()
    extract = response.json().get("extract")
    if not extract:
        return None, None
    paragraph = next((p.strip() for p in extract.split("\n") if p.strip()), None)
    if paragraph and len(paragraph) > 800:
        paragraph = paragraph[:797].rstrip() + "…"
    return paragraph, f"https://{language}.wikipedia.org/wiki/{encoded}"


async def wikidata_matches(client: httpx.AsyncClient, row: dict[str, Any]) -> list[Match]:
    response = await client.get(f"{WIKIDATA_REST}/search/items", params={
        "q": row["name_ja"], "language": "ja", "limit": "5",
    })
    response.raise_for_status()
    ids = [item["id"] for item in response.json().get("results", [])]
    if not ids:
        return []
    matches: list[Match] = []
    for item_id in ids:
        response = await client.get(f"{WIKIDATA_REST}/entities/items/{item_id}")
        response.raise_for_status()
        entity = response.json()
        labels = entity.get("labels", {})
        descriptions = entity.get("descriptions", {})
        sitelinks = entity.get("sitelinks", {})
        lat, lon = claim_coordinate(entity)
        ja_extract = zh_extract = ja_url = zh_url = None
        if "jawiki" in sitelinks:
            ja_extract, ja_url = await wikipedia_extract(
                client, "jawiki", sitelinks["jawiki"]["title"]
            )
        if "zhwiki" in sitelinks:
            zh_extract, zh_url = await wikipedia_extract(
                client, "zhwiki", sitelinks["zhwiki"]["title"]
            )
        matches.append(Match(
            source="wikimedia", source_id=item_id,
            name=labels.get("ja", row["name_ja"]),
            latitude=lat, longitude=lon,
            description_ja=ja_extract or descriptions.get("ja"),
            description_zh=zh_extract or descriptions.get("zh"),
            name_en=labels.get("en"),
            source_url=ja_url or zh_url or f"https://www.wikidata.org/wiki/{item_id}",
            license="CC BY-SA (Wikipedia extract); CC0 (Wikidata fields)",
            raw={
                "description": " ".join(descriptions.values()),
                "wikipedia_ja_url": ja_url,
                "wikipedia_zh_url": zh_url,
            },
        ))
    return matches


def overpass_query(rows: list[dict[str, Any]], radius: int) -> str:
    clauses = []
    for row in rows:
        if row.get("latitude") is not None and row.get("longitude") is not None:
            category = row.get("category")
            selector = {
                "park": '["leisure"~"^(park|garden|nature_reserve)$"]',
                "temple_shrine": '["amenity"="place_of_worship"]',
                "museum": '["tourism"="museum"]',
                "art_museum": '["tourism"="museum"]',
                "gallery": '["tourism"~"^(gallery|museum)$"]',
                "exhibition_space": '["tourism"~"^(gallery|museum)$"]',
                "convention_center": '["amenity"~"^(conference_centre|events_venue)$"]',
            }.get(category, "")
            clauses.append(
                f'nwr(around:{radius},{float(row["latitude"]):.7f},'
                f'{float(row["longitude"]):.7f}){selector}["name"];'
            )
    return "[out:json][timeout:60];(" + "".join(clauses) + ");out center tags;"


async def osm_matches(
    client: httpx.AsyncClient, rows: list[dict[str, Any]], radius: int
) -> dict[str, list[Match]]:
    if not rows:
        return {}
    response = None
    last_error: httpx.HTTPError | None = None
    query = overpass_query(rows, radius)
    for attempt in range(3):
        endpoint = OVERPASS_APIS[attempt % len(OVERPASS_APIS)]
        try:
            response = await client.post(endpoint, content=query)
            response.raise_for_status()
            break
        except httpx.HTTPError as exc:
            last_error = exc
            await asyncio.sleep(1 + attempt * 2)
    if response is None or response.is_error:
        assert last_error is not None
        raise last_error
    elements = response.json().get("elements", [])
    result: dict[str, list[Match]] = {row["id"]: [] for row in rows}
    for element in elements:
        tags = element.get("tags", {})
        name = tags.get("name") or tags.get("name:ja")
        point = element.get("center", element)
        if not name or point.get("lat") is None or point.get("lon") is None:
            continue
        match = Match(
            source="openstreetmap", source_id=f'{element["type"]}/{element["id"]}',
            name=name, latitude=float(point["lat"]), longitude=float(point["lon"]),
            name_en=tags.get("name:en"),
            source_url=f'https://www.openstreetmap.org/{element["type"]}/{element["id"]}',
            license="ODbL 1.0", raw=tags,
        )
        for row in rows:
            if normalize_name(row.get("name_ja")) == normalize_name(name):
                distance = distance_m(
                    float(row["latitude"]), float(row["longitude"]),
                    float(match.latitude), float(match.longitude),
                )
                if distance <= radius:
                    result[row["id"]].append(match)
    return result


def candidate_record(
    row: dict[str, Any], match: Match, *, overwrite: bool = False
) -> dict[str, Any]:
    score, evidence, distance = score_match(row, match)
    patch = {}
    template_ja, template_zh = structured_template(row, match)
    description_ja = match.description_ja or template_ja
    description_zh = match.description_zh or template_zh
    if (overwrite or not row.get("description_ja")) and description_ja:
        patch["description_ja"] = description_ja
    if (overwrite or not row.get("description_zh")) and description_zh:
        patch["description_zh"] = description_zh
    if (overwrite or not row.get("name_en")) and match.name_en:
        patch["name_en"] = match.name_en
    return {
        "source": match.source, "source_id": match.source_id, "source_url": match.source_url,
        "attribution_urls": {
            key: value for key, value in (match.raw or {}).items()
            if key.endswith("_url") and value
        },
        "license": match.license, "score": score,
        "distance_m": round(distance, 1) if distance is not None else None,
        "evidence": evidence, "patch": patch,
    }


async def run(args: argparse.Namespace) -> None:
    import os

    config = {**dotenv_values(Path(__file__).resolve().parents[2] / ".env"), **os.environ}
    url, key = config.get("SUPABASE_PUBLIC_URL"), config.get("SUPABASE_SECRET_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_PUBLIC_URL and SUPABASE_SECRET_KEY are required")
    database = SupabaseRestClient(url, key)
    rows = [row for row in await read_all(database) if row.get("category") != "exhibition"]
    if args.category:
        rows = [row for row in rows if row.get("category") == args.category]
    if not args.overwrite:
        rows = [row for row in rows if not row.get("description_ja") or not row.get("description_zh")]
    if args.limit:
        rows = rows[:args.limit]

    headers = {"User-Agent": USER_AGENT, "Api-User-Agent": USER_AGENT}
    osm_by_id: dict[str, list[Match]] = {}
    async with httpx.AsyncClient(timeout=args.timeout, headers=headers) as web:
        if "osm" in args.sources:
            for start in range(0, len(rows), args.batch_size):
                osm_by_id.update(await osm_matches(web, rows[start:start + args.batch_size], args.radius))
                if start + args.batch_size < len(rows):
                    await asyncio.sleep(args.delay)
        results = []
        for number, row in enumerate(rows, 1):
            matches = []
            if "wikimedia" in args.sources:
                try:
                    matches.extend(await wikidata_matches(web, row))
                except httpx.HTTPError as exc:
                    print(f"warning: Wikimedia failed for {row['name_ja']}: {exc}")
            matches.extend(osm_by_id.get(row["id"], []))
            candidates = sorted(
                (candidate_record(row, match, overwrite=args.overwrite) for match in matches),
                key=lambda item: item["score"], reverse=True,
            )
            best = candidates[0] if candidates else None
            ambiguous = len(candidates) > 1 and best["score"] - candidates[1]["score"] < 10
            if ambiguous and best["source"] != candidates[1]["source"]:
                # Independent Wikimedia and OSM records with the same name and nearby
                # coordinates corroborate one place; they are not competing matches.
                ambiguous = not (
                    "exact_normalized_name" in best["evidence"]
                    and "exact_normalized_name" in candidates[1]["evidence"]
                    and best["distance_m"] is not None
                    and candidates[1]["distance_m"] is not None
                    and best["distance_m"] <= args.radius
                    and candidates[1]["distance_m"] <= args.radius
                )
            status = "unmatched"
            if best and best["patch"]:
                status = "high_confidence" if best["score"] >= args.min_score and not ambiguous else "needs_review"
            results.append({
                "id": row["id"], "name_ja": row["name_ja"], "category": row.get("category"),
                "before": {key: row.get(key) for key in (
                    "name_en", "description_ja", "description_zh", "enrichment_meta", "updated_at"
                )},
                "status": status, "best": best, "candidates": candidates,
            })
            print(f"[{number}/{len(rows)}] {row['name_ja']}: {status}")
            if number < len(rows):
                await asyncio.sleep(args.delay)

    report = {
        "generated_at": datetime.now(UTC).isoformat(), "apply": args.apply,
        "sources": sorted(args.sources), "minimum_score": args.min_score,
        "counts": {status: sum(item["status"] == status for item in results)
                   for status in ("high_confidence", "needs_review", "unmatched")},
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report and pre-write backup: {args.output}")
    if not args.apply:
        print("dry-run only; review the report and rerun with --apply")
        return

    now = datetime.now(UTC).isoformat()
    updated = []
    for item in results:
        if item["status"] != "high_confidence":
            continue
        source = item["best"]
        body = dict(source["patch"])
        enrichment_meta = dict(item["before"].get("enrichment_meta") or {})
        enrichment_meta["description"] = {
                "source": source["source"], "source_id": source["source_id"],
                "source_url": source["source_url"], "license": source["license"],
                "attribution_urls": source["attribution_urls"],
                "retrieved_at": now, "match_score": source["score"],
                "distance_m": source["distance_m"], "evidence": source["evidence"],
        }
        body["enrichment_meta"] = enrichment_meta
        body["updated_at"] = now
        response = await database.request(
            "PATCH", "locations", profile="travel",
            params={"id": "eq." + item["id"], "updated_at": "eq." + item["before"]["updated_at"]},
            body=body, prefer="return=representation",
        )
        if not response:
            raise RuntimeError(f"Concurrent update or missing migration for {item['id']}")
        updated.append(item["id"])
    print(f"updated {len(updated)} locations")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write high-confidence matches")
    parser.add_argument("--overwrite", action="store_true", help="include rows with descriptions")
    parser.add_argument("--category")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--sources", default="wikimedia,osm")
    parser.add_argument("--min-score", type=int, default=80)
    parser.add_argument("--radius", type=int, default=300)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--output", type=Path, default=Path("artifacts/location-descriptions.json"))
    args = parser.parse_args()
    args.sources = {source.strip() for source in args.sources.split(",") if source.strip()}
    unknown = args.sources - {"wikimedia", "osm"}
    if unknown:
        parser.error("unknown sources: " + ", ".join(sorted(unknown)))
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be at least 1")
    if args.radius < 25 or args.radius > 1_000:
        parser.error("--radius must be between 25 and 1000 metres")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
