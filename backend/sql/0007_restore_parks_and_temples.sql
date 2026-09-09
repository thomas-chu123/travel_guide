-- Restore parks and temples/shrines from the pre-rebuild backup made by 0004.
-- Safe to rerun: source_key is unique and existing rows are left untouched.
begin;
insert into travel.locations (
    id, source_key, name_ja, name_en, name_zh, category, area,
    latitude, longitude, location_text, address_ja, ward_city,
    official_url, access_url, exhibitions_url, price_min_jpy, price_max_jpy,
    price_note, exhibition_starts_on, exhibition_ends_on, exhibition_period_note,
    description_ja, description_en, source_name, source_url,
    created_at, updated_at, verified_at, status
)
select
    id, source_key, name_ja, name_en, name_zh, category, area,
    latitude, longitude, location_text, address_ja, ward_city,
    official_url, access_url, exhibitions_url, price_min_jpy, price_max_jpy,
    price_note, exhibition_starts_on, exhibition_ends_on, exhibition_period_note,
    description_ja, description_en, source_name, source_url,
    created_at, updated_at, verified_at, status
from travel.location_bak
where category in ('park', 'temple_shrine')
on conflict (source_key) do nothing;
notify pgrst, 'reload schema';
commit;
