from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal["exhibition", "attraction", "activity"]


class EventProperties(BaseModel):
    id: str
    venue_id: str
    venue_name: str
    ward: str | None
    category: Category
    title: str
    fee_kind: Literal["free", "paid", "unknown"]
    price_min_jpy: Decimal | None
    price_max_jpy: Decimal | None
    starts_at: datetime | None
    ends_at: datetime | None


class PointGeometry(BaseModel):
    type: Literal["Point"] = "Point"
    coordinates: tuple[float, float]


class EventFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: PointGeometry
    properties: EventProperties


class EventFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[EventFeature]
    returned: int


class ViewportQuery(BaseModel):
    west: float = Field(default=139.56, ge=-180, le=180)
    south: float = Field(default=35.52, ge=-90, le=90)
    east: float = Field(default=139.92, ge=-180, le=180)
    north: float = Field(default=35.82, ge=-90, le=90)


class LocationProperties(BaseModel):
    id: str
    venue_id: str | None = None
    name_zh: str | None = None
    address_ja: str | None = None
    address_en: str | None = None
    address_zh: str | None = None
    ward_city: str | None = None
    access_url: str | None = None
    exhibitions_url: str | None = None
    source_url: str | None = None
    verified_at: datetime | None = None
    status: str = "unverified"
    name_ja: str
    name_en: str | None
    category: str
    area: str | None
    location_text: str | None = None
    location_text_en: str | None = None
    location_text_zh: str | None = None
    official_url: str | None
    price_min_jpy: int | None
    price_max_jpy: int | None
    price_note: str | None
    price_note_en: str | None = None
    price_note_zh: str | None = None
    exhibition_starts_on: str | None
    exhibition_ends_on: str | None
    exhibition_period_note: str | None
    exhibition_period_note_en: str | None = None
    exhibition_period_note_zh: str | None = None
    opening_hours: str | None = None
    opening_hours_en: str | None = None
    opening_hours_zh: str | None = None
    description_ja: str | None
    description_en: str | None
    description_zh: str | None = None


class LocationFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    id: str
    geometry: PointGeometry
    properties: LocationProperties


class LocationFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[LocationFeature]
    returned: int
