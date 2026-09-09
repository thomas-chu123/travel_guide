"""Remove spatially close, same-name park duplicates through PostgREST.

The command is a dry run unless ``--apply`` is supplied. Same-name parks farther
apart than the configured distance are preserved as separate locations.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from collections import defaultdict
from pathlib import Path

from dotenv import dotenv_values

from app.services.supabase import SupabaseRestClient
from scripts.enrich_locations import read_all


def distance_km(left: dict, right: dict) -> float:
    left_lat, right_lat = map(math.radians, (left["latitude"], right["latitude"]))
    delta_lat = math.radians(right["latitude"] - left["latitude"])
    delta_lon = math.radians(right["longitude"] - left["longitude"])
    haversine = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(left_lat) * math.cos(right_lat) * math.sin(delta_lon / 2) ** 2
    )
    return 12_742 * math.asin(math.sqrt(haversine))


def duplicate_clusters(rows: list[dict], max_distance_km: float) -> list[list[dict]]:
    by_name: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["category"] == "park":
            by_name[row["name_ja"].strip()].append(row)

    result = []
    for same_name_rows in by_name.values():
        parent = list(range(len(same_name_rows)))

        def find(index: int) -> int:
            while parent[index] != index:
                parent[index] = parent[parent[index]]
                index = parent[index]
            return index

        def union(left: int, right: int) -> None:
            left_root, right_root = find(left), find(right)
            if left_root != right_root:
                parent[right_root] = left_root

        for left in range(len(same_name_rows)):
            for right in range(left):
                if distance_km(same_name_rows[left], same_name_rows[right]) <= max_distance_km:
                    union(left, right)

        components: dict[int, list[dict]] = defaultdict(list)
        for index, row in enumerate(same_name_rows):
            components[find(index)].append(row)
        result.extend(component for component in components.values() if len(component) > 1)
    return result


def choose_keeper(cluster: list[dict]) -> dict:
    # Keep the point nearest to the other same-name points. Stable ID ordering
    # makes the decision deterministic when coordinates are identical.
    return min(
        cluster,
        key=lambda candidate: (
            sum(distance_km(candidate, other) for other in cluster),
            candidate["id"],
        ),
    )


async def run(args: argparse.Namespace) -> None:
    config = {**dotenv_values(Path(__file__).resolve().parents[2] / ".env"), **os.environ}
    client = SupabaseRestClient(config["SUPABASE_PUBLIC_URL"], config["SUPABASE_SECRET_KEY"])
    rows = await read_all(client)
    clusters = duplicate_clusters(rows, args.max_distance_km)
    plan = []
    for cluster in clusters:
        keeper = choose_keeper(cluster)
        for row in cluster:
            if row["id"] != keeper["id"]:
                plan.append({"keeper": keeper, "delete": row})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(plan, handle, ensure_ascii=False, indent=2)
    print(
        f"{len(clusters)} duplicate clusters; {len(plan)} deletions; "
        f"plan: {args.output}; apply={args.apply}"
    )

    if not args.apply:
        return
    delete_ids = {item["delete"]["id"] for item in plan}
    exhibitions = await client.request(
        "GET",
        "exhibitions",
        profile="travel",
        params={"select": "venue_id", "limit": "5000"},
    )
    referenced_ids = delete_ids & {row["venue_id"] for row in exhibitions}
    if referenced_ids:
        raise RuntimeError(
            "Refusing to cascade-delete exhibitions referenced by: "
            + ", ".join(sorted(referenced_ids))
        )
    deleted = 0
    for item in plan:
        row = item["delete"]
        result = await client.request(
            "DELETE",
            "locations",
            profile="travel",
            params={"id": "eq." + row["id"], "category": "eq.park"},
            prefer="return=representation",
        )
        if not result or len(result) != 1 or result[0]["id"] != row["id"]:
            raise RuntimeError(f"Deletion verification failed: {row['id']}")
        deleted += 1
    remaining = await client.request(
        "GET",
        "locations",
        profile="travel",
        params={"select": "id,name_ja,category,latitude,longitude", "category": "eq.park", "limit": "2000"},
    )
    remaining_clusters = duplicate_clusters(remaining, args.max_distance_km)
    if remaining_clusters:
        raise RuntimeError(f"Post-delete verification found {len(remaining_clusters)} duplicate clusters")
    print(f"deleted and verified {deleted} park rows; {len(remaining)} parks remain")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--max-distance-km", type=float, default=2.0)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.max_distance_km <= 0:
        parser.error("--max-distance-km must be positive")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
