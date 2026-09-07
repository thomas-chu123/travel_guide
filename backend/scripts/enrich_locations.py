"""Audit locations or apply reviewed, ID-targeted JSON patches (dry-run by default)."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from app.services.supabase import SupabaseRestClient

FIELDS = (
    "name_ja",
    "category",
    "address_ja",
    "ward_city",
    "latitude",
    "longitude",
    "official_url",
    "access_url",
    "exhibitions_url",
    "source_url",
    "verified_at",
    "status",
)
STATUSES = {"operating", "temporarily_closed", "relocated", "closed", "unverified"}


class VenuePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    venue_id: UUID
    name_ja: str | None = Field(default=None, min_length=1)
    name_zh: str | None = Field(default=None, min_length=1)
    category: str | None = Field(default=None, min_length=1)
    address_ja: str | None = Field(default=None, min_length=1)
    ward_city: str | None = Field(default=None, min_length=1)
    latitude: float | None = Field(default=None, ge=-90, le=90, allow_inf_nan=False)
    longitude: float | None = Field(default=None, ge=-180, le=180, allow_inf_nan=False)
    official_url: HttpUrl | None = None
    access_url: HttpUrl | None = None
    exhibitions_url: HttpUrl | None = None
    source_url: HttpUrl
    verified_at: datetime | None = None
    status: str | None = None

    @model_validator(mode="after")
    def validate_review(self) -> VenuePatch:
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Null patches are not allowed; omit unknown fields")
        if self.status is not None and self.status not in STATUSES:
            raise ValueError("Unknown status")
        if self.verified_at is not None and (
            self.verified_at.tzinfo is None or self.verified_at > datetime.now(UTC)
        ):
            raise ValueError("verified_at must include timezone and cannot be in the future")
        return self


async def read_all(client: SupabaseRestClient) -> list[dict]:
    rows = []
    while True:
        page = await client.request(
            "GET",
            "locations",
            profile="travel",
            params={
                "select": "*",
                "order": "id",
                "limit": "500",
                "offset": str(len(rows)),
            },
        )
        if not page:
            return rows
        rows.extend(page)


def audit(rows: list[dict]) -> dict:
    venues = [
        r
        for r in rows
        if r["category"]
        in {
            "museum",
            "art_museum",
            "gallery",
            "exhibition_space",
            "convention_center",
        }
        or any(word in r["name_ja"] for word in ("美術館", "ギャラリー", "展示館"))
    ]
    return {
        "total_locations": len(rows),
        "candidate_venues": len(venues),
        "missing_counts": {
            f: sum(r.get(f) in (None, "", "unverified") for r in venues) for f in FIELDS
        },
        "venues": [
            {
                "venue_id": r["id"],
                **r,
                "missing": [f for f in FIELDS if r.get(f) in (None, "", "unverified")],
            }
            for r in venues
        ],
    }


async def run(args: argparse.Namespace) -> None:
    import os

    config = {**dotenv_values(Path(__file__).resolve().parents[2] / ".env"), **os.environ}
    client = SupabaseRestClient(config["SUPABASE_PUBLIC_URL"], config["SUPABASE_SECRET_KEY"])
    rows = await read_all(client)
    if args.patches is None:
        report = audit(rows)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k: v for k, v in report.items() if k != "venues"}, ensure_ascii=False))
        return
    patches = [VenuePatch.model_validate(p) for p in json.loads(args.patches.read_text())]
    if len({p.venue_id for p in patches}) != len(patches):
        raise ValueError("Duplicate venue_id in patch file")
    existing = {r["id"]: r for r in rows}
    changes = []
    for patch in patches:
        row_id = str(patch.venue_id)
        if row_id not in existing:
            raise ValueError(f"Unknown venue_id: {row_id}")
        body = patch.model_dump(mode="json", exclude_unset=True, exclude={"venue_id"})
        if any(key not in existing[row_id] for key in body):
            raise ValueError("Apply SQL migration 0003 before updating venue fields")
        delta = {k: v for k, v in body.items() if existing[row_id].get(k) != v}
        if delta:
            changes.append({"id": row_id, "before": existing[row_id], "patch": delta})
    # A complete review/backup is written before any mutation.
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(changes, handle, ensure_ascii=False, indent=2)
    print(f"{len(changes)} changes; review/backup: {args.output}; apply={args.apply}")
    if args.apply:
        for change in changes:
            body = {**change["patch"], "updated_at": datetime.now(UTC).isoformat()}
            result = await client.request(
                "PATCH",
                "locations",
                profile="travel",
                params={
                    "id": "eq." + change["id"],
                    "updated_at": "eq." + change["before"]["updated_at"],
                },
                body=body,
                prefer="return=representation",
            )
            if not result or any(
                result[0].get(k) != v for k, v in change["patch"].items() if k != "verified_at"
            ):
                raise RuntimeError(f"Concurrent change or verification failed: {change['id']}")
            print(f"updated {change['id']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--patches", type=Path)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.apply and args.patches is None:
        parser.error("--apply requires --patches")
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
