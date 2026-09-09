from scripts.translate_supabase_content import translations_for_row


class FakeTranslator:
    def translate(self, text: str, target: str) -> str:
        return f"{target}:{text}"


def test_translates_missing_fields_and_preserves_existing_translation() -> None:
    row = {
        "name_ja": "東京都美術館",
        "name_en": "Tokyo Metropolitan Art Museum",
        "name_zh": None,
        "description_ja": "上野公園にある美術館",
        "description_en": None,
        "description_zh": None,
        "translation_meta": {},
    }

    result = translations_for_row("locations", row, FakeTranslator(), overwrite=False)

    assert "name_en" not in result
    assert result["name_zh"] == "zh:東京都美術館"
    assert result["description_en"] == "en:上野公園にある美術館"
    assert result["description_zh"] == "zh:上野公園にある美術館"
    assert result["translation_meta"]["name_zh"]["reviewed"] is False


def test_skips_rows_without_source_text() -> None:
    assert translations_for_row("exhibitions", {}, FakeTranslator(), False) == {}


def test_overwrite_replaces_existing_translation() -> None:
    row = {"title_ja": "展覧会", "title_en": "Official title", "title_zh": "官方標題"}

    result = translations_for_row("exhibitions", row, FakeTranslator(), overwrite=True)

    assert result["title_en"] == "en:展覧会"
    assert result["title_zh"] == "zh:展覧会"
