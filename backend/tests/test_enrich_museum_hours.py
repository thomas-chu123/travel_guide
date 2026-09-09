import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "enrich_museum_hours", Path(__file__).parents[1] / "scripts/enrich_museum_hours.py"
)
hours = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hours
spec.loader.exec_module(hours)


def test_extracts_hours_and_closure_from_visible_official_text():
    html = """
      <html><script>営業時間 00:00</script><body>
      <h2>開館時間</h2><p>10:00～18:00（入館は17:30まで）</p>
      <p>休館日 月曜日、年末年始</p></body></html>
    """
    assert hours.extract_hours(html) == (
        "開館時間 10:00～18:00（入館は17:30まで） 休館日 月曜日、年末年始"
    )


def test_rejects_page_without_explicit_hours_heading():
    assert hours.extract_hours("<p>イベント開始 10:00、終了 17:00</p>") is None


def test_keeps_only_useful_same_site_links():
    html = """
      <a href='/visit/hours'>利用案内</a>
      <a href='https://evil.example/hours'>開館時間</a>
      <a href='/news'>ニュース</a>
    """
    assert hours.useful_internal_links("https://museum.example/", html) == [
        "https://museum.example/visit/hours"
    ]
