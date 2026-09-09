from dataclasses import replace
from datetime import date, datetime
from zoneinfo import ZoneInfo

from worker.main import next_run
from worker.sources.common import Exhibition, parse_jpy
from worker.sources.go_tokyo import parse as parse_go_tokyo
from worker.sources.tokyo_art_beat import parse as parse_tokyo_art_beat
from worker.sync_exhibitions import (
    _event_key,
    add_translations,
    build_row,
    match_venue,
    merge_exhibitions,
)


class FakeTranslator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def translate(self, text: str, target: str) -> str:
        self.calls.append((text, target))
        return f"{target}:{text}"


def test_go_tokyo_parser_extracts_period_description_and_price():
    html = """
    <div class="wrap_exhibition">
      <p class="ttl">展覧会 A</p>
      <div class="exhibition_cnt">
        <p class="facility">東京都美術館</p>
        <p>2026年4月21日～2026年9月13日</p>
        <p>展覧会の説明です。</p>
        <p>一般・当日料金：1,500円、学生500円</p>
      </div>
    </div>
    """
    item = parse_go_tokyo(html)[0]
    assert item.venue_name == "東京都美術館"
    assert item.starts_on == date(2026, 4, 21)
    assert item.price_min_jpy == 500
    assert item.price_max_jpy == 1500


def test_tokyo_art_beat_parser_resolves_linked_venue():
    localized = lambda value: {"ja-JP": value}
    payload = {
        "items": [{
            "sys": {"id": "event-1"},
            "fields": {
                "eventName": localized("企画展"),
                "venue": localized({"sys": {"id": "venue-1"}}),
                "scheduleStartsOn": localized("2026-09-01"),
                "scheduleEndsOn": localized("2026-10-01"),
                "admissionFee": localized("一般 1,200円"),
                "slug": localized("example"),
            },
        }],
        "includes": {"Entry": [{
            "sys": {"id": "venue-1", "contentType": {"sys": {"id": "venue"}}},
            "fields": {"fullName": localized("東京都美術館")},
        }]},
    }
    item = parse_tokyo_art_beat(payload)[0]
    assert item.title == "企画展"
    assert item.official_url == "https://www.tokyoartbeat.com/events/-/example"
    assert item.price_min_jpy == 1200

    payload["items"][0]["fields"]["admissionFee"] = localized(0)
    free_item = parse_tokyo_art_beat(payload)[0]
    assert free_item.price_note == "無料"
    assert free_item.price_min_jpy == 0

    payload["items"][0]["fields"]["admissionFee"] = localized("0")
    assert parse_tokyo_art_beat(payload)[0].price_note == "無料"


def test_match_merge_and_database_row_use_curated_venue_coordinates():
    venue = {
        "id": "venue-id",
        "name_ja": "東京都美術館",
        "area": "東京都",
        "latitude": 35.7,
        "longitude": 139.7,
        "address_ja": "東京都台東区",
        "ward_city": "台東区",
    }
    base = Exhibition(
        source="go-tokyo", source_id="1", source_url="https://example.jp/source",
        title="企画展", venue_name="東京都美術館", starts_on=date(2026, 9, 1),
        ends_on=date(2026, 10, 1), description="短い", price_min_jpy=1000,
    )
    richer = replace(base, source="tokyo-art-beat", description="より長い説明")
    assert match_venue(base, [venue]) == venue
    merged = merge_exhibitions([(base, venue), (richer, venue)])
    assert len(merged) == 1
    row = build_row(*merged[0], datetime(2026, 9, 8, tzinfo=ZoneInfo("Asia/Tokyo")))
    assert row["venue_id"] == "venue-id"
    assert row["title_ja"] == "企画展"
    assert row["description_ja"] == "より長い説明"
    assert set(row["source_refs"]) == {"go-tokyo", "tokyo-art-beat"}


def test_free_price_and_next_daily_run():
    assert parse_jpy("入場無料") == (0, 0)
    now = datetime(2026, 9, 8, 2, 1, tzinfo=ZoneInfo("Asia/Tokyo"))
    assert next_run(now) == datetime(2026, 9, 9, 2, 0, tzinfo=ZoneInfo("Asia/Tokyo"))


def test_event_identity_survives_corrected_end_date():
    venue = {"id": "venue-id"}
    item = Exhibition(
        source="source", source_id="1", source_url="https://example.jp/1",
        title="企画展", venue_name="美術館", starts_on=date(2026, 9, 1),
        ends_on=date(2026, 10, 1),
    )
    assert _event_key(item, venue) == _event_key(
        replace(item, ends_on=date(2026, 10, 15)), venue
    )


def test_translation_reuses_unchanged_values_and_translates_changed_source():
    now = datetime(2026, 9, 9, tzinfo=ZoneInfo("Asia/Tokyo"))
    row = {
        "title_ja": "企画展",
        "title_en": None,
        "title_zh": None,
        "description_ja": "新しい説明",
        "description_en": None,
        "description_zh": None,
        "price_note": None,
        "period_note": None,
        "translation_meta": {},
    }
    existing = {
        "title_ja": "企画展",
        "title_en": "Official exhibition",
        "title_zh": "官方展覽",
        "description_ja": "古い説明",
        "description_en": "Old description",
        "description_zh": "舊說明",
        "translation_meta": {"title_en": {"reviewed": True}},
    }
    translator = FakeTranslator()

    count = add_translations(row, existing, translator, now)

    assert count == 2
    assert row["title_en"] == "Official exhibition"
    assert row["title_zh"] == "官方展覽"
    assert row["description_en"] == "en:新しい説明"
    assert row["description_zh"] == "zh:新しい説明"
    assert translator.calls == [("新しい説明", "en"), ("新しい説明", "zh")]
