from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from app.api.routes.supabase import get_client
from app.api.schemas import (
    LocationFeature,
    LocationFeatureCollection,
    LocationProperties,
    PointGeometry,
)
from app.services.supabase import SupabaseRestClient, SupabaseRestError

router = APIRouter()


@router.get("/locations", response_model=LocationFeatureCollection)
async def list_locations(
    client: SupabaseRestClient = Depends(get_client),
) -> LocationFeatureCollection:
    async def read_all(table: str, params: dict[str, str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        while True:
            page = await client.request(
                "GET",
                table,
                params={**params, "limit": "500", "offset": str(len(rows))},
                profile="travel",
            )
            if not page:
                return rows
            rows.extend(page)

    try:
        rows = await read_all(
            "locations", {"select": "*", "category": "neq.exhibition", "order": "id"}
        )
        exhibitions = await read_all("exhibitions", {"select": "*", "order": "id"})
    except SupabaseRestError as error:
        raise HTTPException(status_code=502, detail="Unable to load travel locations") from error

    venues = {str(row["id"]): row for row in rows}
    features: list[LocationFeature] = [
        LocationFeature(
            id=str(row["id"]),
            geometry=PointGeometry(coordinates=(row["longitude"], row["latitude"])),
            properties=LocationProperties(
                **{**row, "venue_id": row.get("venue_id") or str(row["id"])}
            ),
        )
        for row in rows
    ]
    for exhibition in exhibitions:
        venue = venues.get(str(exhibition["venue_id"]))
        if not venue:
            continue
        refs = exhibition.get("source_refs") or {}
        source_url = next(
            (ref.get("url") for ref in refs.values() if isinstance(ref, dict) and ref.get("url")),
            None,
        )
        properties = {
            **venue,
            "id": str(exhibition["id"]),
            "venue_id": str(venue["id"]),
            "name_ja": exhibition["title_ja"],
            "name_en": exhibition.get("title_en"),
            "category": "exhibition",
            "location_text": venue["name_ja"],
            "official_url": exhibition.get("official_url"),
            "price_min_jpy": exhibition.get("price_min_jpy"),
            "price_max_jpy": exhibition.get("price_max_jpy"),
            "price_note": exhibition.get("price_note"),
            "exhibition_starts_on": exhibition.get("starts_on"),
            "exhibition_ends_on": exhibition.get("ends_on"),
            "exhibition_period_note": exhibition.get("period_note"),
            "description_ja": exhibition.get("description_ja"),
            "description_en": exhibition.get("description_en"),
            "source_url": source_url,
            "verified_at": exhibition.get("verified_at"),
            "status": exhibition.get("status", "operating"),
        }
        features.append(
            LocationFeature(
                id=str(exhibition["id"]),
                geometry=PointGeometry(coordinates=(venue["longitude"], venue["latitude"])),
                properties=LocationProperties(**properties),
            )
        )
    return LocationFeatureCollection(features=features, returned=len(features))
