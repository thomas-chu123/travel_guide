-- Run through a PostgreSQL connection that owns the travel schema.
-- PostgREST cannot execute DDL, so this migration deliberately lives outside
-- the REST importer.
create schema if not exists travel;

create table if not exists travel.locations (
    id uuid primary key default gen_random_uuid(),
    source_key text not null unique,
    name_ja text not null,
    name_en text,
    category text not null,
    area text,
    latitude double precision not null,
    longitude double precision not null,
    location_text text,
    official_url text,
    price_min_jpy integer,
    price_max_jpy integer,
    price_note text,
    exhibition_starts_on date,
    exhibition_ends_on date,
    exhibition_period_note text,
    description_ja text,
    description_en text,
    source_name text not null default 'code4fukui/tokyo-walking-map',
    source_url text not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (latitude between -90 and 90),
    check (longitude between -180 and 180),
    check (price_min_jpy is null or price_min_jpy >= 0),
    check (price_max_jpy is null or price_max_jpy >= 0)
);

create index if not exists locations_coordinates_idx
    on travel.locations (latitude, longitude);
create index if not exists locations_category_idx
    on travel.locations (category);
create index if not exists locations_area_idx
    on travel.locations (area);
