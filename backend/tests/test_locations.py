import asyncio
import importlib.util
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.api.routes.locations import list_locations

spec = importlib.util.spec_from_file_location(
    "enrich_locations", Path(__file__).parents[1] / "scripts/enrich_locations.py"
)
enrich = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = enrich
spec.loader.exec_module(enrich)


def test_patch_rejects_null_and_unknown_fields():
    base = {"venue_id": str(uuid4()), "source_url": "https://example.org/"}
    for extra in (
        {"official_url": None},
        {"latitude": 91},
        {"status": "open"},
        {"official_url": "javascript:alert(1)"},
        {"id": str(uuid4())},
    ):
        with pytest.raises(ValidationError):
            enrich.VenuePatch.model_validate({**base, **extra})


def test_audit_does_not_count_zero_coordinates_as_missing():
    report = enrich.audit(
        [{"id": "a", "name_ja": "美術館", "category": "museum", "latitude": 0, "longitude": 0}]
    )
    assert report["missing_counts"]["latitude"] == 0
    assert report["missing_counts"]["official_url"] == 1


def test_locations_paginates_even_when_server_caps_page_and_supports_legacy_schema():
    row = {
        "id": str(uuid4()),
        "name_ja": "美術館",
        "name_en": None,
        "category": "museum",
        "area": None,
        "latitude": 35,
        "longitude": 139,
        "official_url": None,
        "price_min_jpy": None,
        "price_max_jpy": None,
        "price_note": None,
        "exhibition_starts_on": None,
        "exhibition_ends_on": None,
        "exhibition_period_note": None,
        "description_ja": None,
        "description_en": None,
    }

    class Client:
        async def request(self, method, table, **kwargs):
            offset = int(kwargs["params"]["offset"])
            return [row] if offset < 2 else []

    result = asyncio.run(list_locations(Client()))
    assert result.returned == 2
    assert result.features[0].properties.venue_id == row["id"]
    assert result.features[0].properties.status == "unverified"
