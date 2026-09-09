"""Restore selected location categories from travel.location_bak via PostgREST."""

import argparse
import asyncio
import os
from typing import Any

from dotenv import load_dotenv

from app.services.supabase import SupabaseRestClient

CATEGORIES = ("park", "temple_shrine")
GENERATED_COLUMNS = {"venue_id"}


async def read_category(client: SupabaseRestClient, category: str, table: str = "location_bak") -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    while True:
        page = await client.request(
            "GET",
            table,
            params={"select": "*", "category": f"eq.{category}", "limit": "500", "offset": str(len(rows)), "order": "id"},
            profile="travel",
        )
        if not page:
            return rows
        rows.extend(page)


async def run(apply: bool) -> None:
    load_dotenv()
    client = SupabaseRestClient(os.environ["SUPABASE_PUBLIC_URL"], os.environ["SUPABASE_SECRET_KEY"])
    for category in CATEGORIES:
        rows = await read_category(client, category)
        print(f"{category}: {len(rows)} rows found")
        if not apply:
            continue
        for start in range(0, len(rows), 200):
            body = [{key: value for key, value in row.items() if key not in GENERATED_COLUMNS} for row in rows[start:start + 200]]
            await client.request(
                "POST", "locations", body=body,
                prefer="resolution=ignore-duplicates,return=minimal", profile="travel",
            )
        print(f"{category}: restore complete")
        restored = await read_category(client, category, "locations")
        print(f"{category}: {len(restored)} rows now in locations")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="write rows; otherwise only report counts")
    asyncio.run(run(parser.parse_args().apply))
