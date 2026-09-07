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
    rows: list[dict[str, Any]] = []
    try:
        while True:
            page = await client.request(
                "GET",
                "locations",
                # Selecting * also works before the additive venue migration is applied.
                params={"select": "*", "order": "id", "limit": "500", "offset": str(len(rows))},
                profile="travel",
            )
            if not page:
                break
            rows.extend(page)
    except SupabaseRestError as error:
        raise HTTPException(status_code=502, detail="Unable to load travel locations") from error

    features = [
        LocationFeature(
            id=str(row["id"]),
            geometry=PointGeometry(coordinates=(row["longitude"], row["latitude"])),
            properties=LocationProperties(
                **{**row, "venue_id": row.get("venue_id") or str(row["id"])}
            ),
        )
        for row in rows
    ]
    return LocationFeatureCollection(features=features, returned=len(features))
