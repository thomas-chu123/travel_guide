"""Export every travel.locations row to a timestamped JSON recovery file."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from dotenv import dotenv_values

from app.services.supabase import SupabaseRestClient
from scripts.enrich_locations import read_all


async def run(output: Path) -> None:
    config = {**dotenv_values(Path(__file__).resolve().parents[2] / ".env"), **os.environ}
    client = SupabaseRestClient(config["SUPABASE_PUBLIC_URL"], config["SUPABASE_SECRET_KEY"])
    rows = await read_all(client)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as handle:
        json.dump(rows, handle, ensure_ascii=False, indent=2)
    print(f"exported {len(rows)} rows to {output}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    asyncio.run(run(args.output))


if __name__ == "__main__":
    main()
