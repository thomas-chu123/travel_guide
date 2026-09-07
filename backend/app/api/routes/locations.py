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

LOCATION_COLUMNS = (
    "id,name_ja,name_en,category,area,latitude,longitude,official_url,price_min_jpy,"
    "price_max_jpy,price_note,exhibition_starts_on,exhibition_ends_on,"
    "exhibition_period_note,description_ja,description_en"
)


@router.get("/locations", response_model=LocationFeatureCollection)
async def list_locations(client: SupabaseRestClient = Depends(get_client)) -> LocationFeatureCollection:
    try:
        rows: list[dict[str, Any]] = await client.request(
            "GET",
            "locations",
            params={"select": LOCATION_COLUMNS, "order": "name_ja", "limit": "3000"},
            profile="travel",
        )
    except SupabaseRestError as error:
        raise HTTPException(status_code=502, detail="Unable to load travel locations") from error

    features = [
        LocationFeature(
            id=str(row["id"]),
            geometry=PointGeometry(coordinates=(row["longitude"], row["latitude"])),
            properties=LocationProperties(**row),
        )
        for row in rows
    ]
    return LocationFeatureCollection(features=features, returned=len(features))
