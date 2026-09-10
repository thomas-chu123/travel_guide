import importlib.util
import sys
from pathlib import Path

MODULE_PATH = Path(__file__).parents[1] / "scripts/enrich_location_descriptions.py"
SPEC = importlib.util.spec_from_file_location("enrich_location_descriptions", MODULE_PATH)
module = importlib.util.module_from_spec(SPEC)
assert SPEC.loader
sys.modules[SPEC.name] = module
SPEC.loader.exec_module(module)


def test_normalize_name_handles_width_spacing_and_punctuation():
    assert module.normalize_name(" 石浜・公園 ") == module.normalize_name("石浜公園")


def test_score_exact_nearby_category_match_is_high_confidence():
    row = {
        "name_ja": "石浜公園", "category": "park", "ward_city": "台東区",
        "latitude": 35.7247951, "longitude": 139.8040983,
    }
    match = module.Match(
        source="openstreetmap", source_id="way/588669896", name="石浜公園",
        latitude=35.7247951, longitude=139.8040983,
        raw={"leisure": "park", "description": "台東区の公園"},
    )
    score, evidence, distance = module.score_match(row, match)
    assert score == 100
    assert distance == 0
    assert "exact_normalized_name" in evidence


def test_score_rejects_far_away_same_name():
    row = {
        "name_ja": "中央公園", "category": "park", "ward_city": "新宿区",
        "latitude": 35.689, "longitude": 139.692,
    }
    match = module.Match(
        source="wikimedia", source_id="Q1", name="中央公園",
        latitude=35.0, longitude=139.0, description_ja="公園",
    )
    score, evidence, distance = module.score_match(row, match)
    assert score == 0
    assert distance > 1_000
    assert evidence == ["rejected_distance_over_1km"]


def test_candidate_does_not_overwrite_existing_description():
    row = {
        "name_ja": "例公園", "name_en": None, "description_ja": "既存説明",
        "description_zh": None, "category": "park", "ward_city": "台東区",
        "latitude": 35.0, "longitude": 139.0,
    }
    match = module.Match(
        source="wikimedia", source_id="Q2", name="例公園", latitude=35.0,
        longitude=139.0, description_ja="新説明", description_zh="中文說明",
        name_en="Example Park", raw={"description": "台東区の公園"},
    )
    record = module.candidate_record(row, match)
    assert "description_ja" not in record["patch"]
    assert record["patch"]["description_zh"] == "中文說明"
    assert record["patch"]["name_en"] == "Example Park"


def test_exact_typed_osm_park_gets_conservative_templates():
    row = {
        "name_ja": "石浜公園", "name_zh": "石濱公園", "name_en": "Ishihama Park",
        "description_ja": None, "description_zh": None, "category": "park",
        "ward_city": "台東区", "latitude": 35.7248, "longitude": 139.8041,
    }
    match = module.Match(
        source="openstreetmap", source_id="way/588669896", name="石浜公園",
        latitude=35.7248, longitude=139.8041, raw={"leisure": "park"},
    )
    record = module.candidate_record(row, match)
    assert record["score"] == 90
    assert record["patch"]["description_ja"] == "石浜公園は東京都台東区にある公園です。"
    assert record["patch"]["description_zh"] == "石濱公園是位於東京都台東區的公園。"


def test_non_park_poi_is_not_described_as_a_park():
    row = {
        "name_ja": "松の風公園への階段", "description_ja": None,
        "description_zh": None, "name_en": None, "category": "park",
        "ward_city": "練馬区", "latitude": 35.0, "longitude": 139.0,
    }
    match = module.Match(
        source="openstreetmap", source_id="way/1", name="松の風公園への階段",
        latitude=35.0, longitude=139.0, raw={"highway": "steps"},
    )
    assert module.candidate_record(row, match)["patch"] == {}
