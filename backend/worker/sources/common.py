from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True, slots=True)
class Exhibition:
    source: str
    source_id: str
    source_url: str
    title: str
    venue_name: str
    starts_on: date | None
    ends_on: date | None
    description: str | None = None
    price_min_jpy: int | None = None
    price_max_jpy: int | None = None
    price_note: str | None = None
    official_url: str | None = None


def clean_text(value: str | None) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.split())
    return cleaned or None


def normalized_name(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).casefold()
    return re.sub(r"[\s・･\-‐–—―_\[\]【】「」『』（）()]", "", value)


def parse_jpy(text: str | None) -> tuple[int | None, int | None]:
    if not text:
        return None, None
    if "無料" in text or re.search(r"(?:^|\D)0\s*円", text):
        return 0, 0
    values = [int(value.replace(",", "")) for value in re.findall(r"([0-9][0-9,]*)\s*円", text)]
    return (min(values), max(values)) if values else (None, None)
