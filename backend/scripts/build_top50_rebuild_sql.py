"""Geocode the reviewed Top 50 list and generate an atomic Supabase rebuild SQL file."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import httpx

ADDRESSES = [
    "東京都台東区上野公園13-9",
    "東京都台東区上野公園7-7",
    "東京都台東区上野公園8-36",
    "東京都港区六本木7-22-2",
    "東京都千代田区北の丸公園3-1",
    "東京都江東区三好4-1-1",
    "東京都港区六本木6-10-1 六本木ヒルズ森タワー53階",
    "東京都中央区京橋1-7-2",
    "東京都千代田区丸の内2-6-2",
    "東京都目黒区三田1-13-3 恵比寿ガーデンプレイス内",
    "東京都港区白金台5-21-9",
    "東京都墨田区亀沢2-7-2",
    "東京都台東区上野公園12-8",
    "東京都台東区上野公園1-2",
    "東京都渋谷区広尾3-12-36",
    "東京都港区南青山6-5-1",
    "東京都中央区日本橋室町2-1-1 三井本館7階",
    "東京都千代田区丸の内2-1-1 明治生命館1階",
    "東京都世田谷区上野毛3-9-25",
    "東京都港区六本木1-5-1",
    "東京都港区虎ノ門2-10-3",
    "東京都港区東新橋1-5-1 パナソニック東京汐留ビル4階",
    "東京都品川区東品川2-6-10 寺田倉庫G号",
    "東京都新宿区西新宿3-20-2 東京オペラシティタワー3階",
    "東京都新宿区西新宿3-20-2 東京オペラシティタワー4階",
    "東京都練馬区下石神井4-7-2",
    "東京都文京区目白台1-1-1",
    "東京都渋谷区松濤2-14-14",
    "東京都渋谷区松濤1-11-3",
    "東京都港区白金台5-12-6",
    "東京都目黒区目黒2-4-36",
    "東京都目黒区上目黒1-7-13",
    "東京都世田谷区砧公園1-2",
    "東京都世田谷区桜新町1-30-6",
    "東京都新宿区弁天町107",
    "東京都台東区谷中7-18-10",
    "東京都台東区根岸2-10-4",
    "東京都足立区千住橋戸町23",
    "東京都中央区日本橋蛎殻町1-35-7",
    "東京都府中市浅間町1-3",
    "東京都武蔵野市吉祥寺本町1-8-16 FFビル7階",
    "東京都三鷹市下連雀3-35-1 CORAL5階",
    "東京都小平市学園西町1-7-5",
    "東京都立川市緑町3-4 GREEN SPRINGS",
    "東京都八王子市八日町8-1 ビュータワー八王子2階",
    "東京都八王子市谷野町492-1",
    "東京都町田市原町田4-28-1",
    "東京都中央区京橋3-7-6",
    "東京都渋谷区代々木3-22-7 新宿文化クイントビル",
    "東京都千代田区一番町25 JCIIビル地下1階",
]

COORDINATE_OVERRIDES = {
    3: (35.717225, 139.772236),
    9: (35.678252, 139.763056),
    24: (35.683003, 139.686756),
    25: (35.683003, 139.686756),
    43: (35.7179693, 139.4755942),
    49: (35.686322, 139.69501),
}

STATUS_BY_RANK = {
    # Official 2026 brochure: facility maintenance closure Jun. 22-Oct. 2.
    46: "temporarily_closed",
}


def geocode(rank: int, name: str, address: str, client: httpx.Client) -> tuple[float, float]:
    if rank in COORDINATE_OVERRIDES:
        return COORDINATE_OVERRIDES[rank]
    ward_city = address.removeprefix("東京都").split("区", 1)[0] + "区"
    if "区" not in address.removeprefix("東京都").split("市", 1)[0]:
        ward_city = address.removeprefix("東京都").split("市", 1)[0] + "市"
    response = client.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": f"{name} {ward_city}",
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "jp",
            "accept-language": "ja",
        },
    )
    response.raise_for_status()
    matches = response.json()
    if not matches:
        raise RuntimeError(f"No geocoding result for {name} at {address}")
    latitude, longitude = float(matches[0]["lat"]), float(matches[0]["lon"])
    if not (35.45 <= latitude <= 35.90 and 139.20 <= longitude <= 140.00):
        raise RuntimeError(f"Geocoding result outside Tokyo for {address}: {latitude}, {longitude}")
    return latitude, longitude


def sql_for(rows: list[dict[str, object]]) -> str:
    payload = json.dumps(rows, ensure_ascii=False).replace("'", "''")
    return f"""-- Generated from backend/curation/top_50_tokyo_art_museums.json.
-- Run once in Supabase SQL Editor. The transaction rolls back on any failure.
begin;

do $$ begin
    if to_regclass('travel.location_bak') is not null then
        raise exception 'travel.location_bak already exists; preserve or rename it before rebuilding';
    end if;
end $$;

create table travel.location_bak as table travel.locations with no data;
insert into travel.location_bak select * from travel.locations;
revoke all on travel.location_bak from anon, authenticated;
grant select on travel.location_bak to service_role;

do $$ declare source_count bigint; backup_count bigint; begin
    select count(*) into source_count from travel.locations;
    select count(*) into backup_count from travel.location_bak;
    if source_count <> backup_count then
        raise exception 'backup count mismatch: source %, backup %', source_count, backup_count;
    end if;
end $$;

truncate table travel.locations;

insert into travel.locations (
    id, source_key, name_ja, name_en, name_zh, category, area,
    latitude, longitude, location_text, address_ja, ward_city,
    official_url, access_url, exhibitions_url, source_name, source_url,
    description_ja, verified_at, status
)
select
    x.id::uuid, x.source_key, x.name_ja, x.name_en, x.name_zh, x.category, x.area,
    x.latitude, x.longitude, x.address_ja, x.address_ja, x.ward_city,
    x.official_url, x.access_url, x.exhibitions_url, x.source_name, x.source_url,
    x.description_ja, x.verified_at::timestamptz, x.status
from jsonb_to_recordset('{payload}'::jsonb) as x(
    id text, source_key text, name_ja text, name_en text, name_zh text,
    category text, area text, latitude double precision, longitude double precision,
    address_ja text, ward_city text, official_url text, access_url text,
    exhibitions_url text, source_name text, source_url text,
    description_ja text, verified_at text, status text
);

do $$ declare inserted_count bigint; begin
    select count(*) into inserted_count from travel.locations;
    if inserted_count <> 50 then
        raise exception 'expected 50 rebuilt locations, got %', inserted_count;
    end if;
end $$;

notify pgrst, 'reload schema';
commit;
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    selected = json.loads(args.input.read_text(encoding="utf-8"))
    if len(selected) != 50 or [row["rank"] for row in selected] != list(range(1, 51)):
        raise ValueError("Input must contain unique ranks 1 through 50")
    if len({row["name_ja"] for row in selected}) != 50:
        raise ValueError("Museum names must be unique")
    rows = []
    with httpx.Client(
        timeout=30,
        headers={"User-Agent": "TokyoTravelGuideDataCuration/1.0"},
    ) as client:
        for selected_row, address in zip(selected, ADDRESSES, strict=True):
            latitude, longitude = geocode(
                selected_row["rank"], selected_row["name_ja"], address, client
            )
            official_url = selected_row["official_url"]
            rank = selected_row["rank"]
            rows.append(
                {
                    "id": str(uuid5(NAMESPACE_URL, f"tokyo-art-top50:{rank}")),
                    "source_key": f"tokyo-art-top50:{rank:02d}",
                    "name_ja": selected_row["name_ja"],
                    "name_en": None,
                    "name_zh": None,
                    "category": "art_museum",
                    "area": "東京都",
                    "latitude": latitude,
                    "longitude": longitude,
                    "address_ja": address,
                    "ward_city": address.removeprefix("東京都").split("区", 1)[0] + "区"
                    if "区" in address.removeprefix("東京都").split("市", 1)[0]
                    else address.removeprefix("東京都").split("市", 1)[0] + "市",
                    "official_url": official_url,
                    "access_url": official_url,
                    "exhibitions_url": official_url,
                    "source_name": "Tokyo Museum Grutto Pass 2026 / official website / OpenStreetMap Nominatim",
                    "source_url": selected_row["source_url"],
                    "description_ja": f"東京美術館 Top 50 編集順位: {rank}",
                    "verified_at": "2026-09-08T00:00:00+09:00",
                    "status": STATUS_BY_RANK.get(rank, "operating"),
                }
            )
            print(f"geocoded {rank}/50 {selected_row['name_ja']}")
            time.sleep(1.05)
    args.output.write_text(sql_for(rows), encoding="utf-8")
    print(f"generated {args.output}")


if __name__ == "__main__":
    main()
