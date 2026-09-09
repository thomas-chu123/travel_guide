-- Separate frequently changing exhibitions from stable venue/location records.
-- Apply as the owner of the travel schema, after 0005.
begin;

create table if not exists travel.exhibitions (
    id uuid primary key default gen_random_uuid(),
    source_key text not null unique,
    venue_id uuid not null references travel.locations(id) on delete cascade,
    title_ja text not null,
    title_en text,
    starts_on date,
    ends_on date,
    period_note text,
    official_url text,
    price_min_jpy integer,
    price_max_jpy integer,
    price_note text,
    description_ja text,
    description_en text,
    sources text[] not null default '{}',
    source_refs jsonb not null default '{}'::jsonb,
    verified_at timestamptz,
    status text not null default 'operating',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (price_min_jpy is null or price_min_jpy >= 0),
    check (price_max_jpy is null or price_max_jpy >= 0),
    check (ends_on is null or starts_on is null or ends_on >= starts_on)
);

create index if not exists exhibitions_venue_id_idx on travel.exhibitions (venue_id);
create index if not exists exhibitions_period_idx on travel.exhibitions (starts_on, ends_on);
create index if not exists exhibitions_source_refs_idx
    on travel.exhibitions using gin (source_refs);

-- Migrate legacy exhibition-shaped location rows. The stable key intentionally
-- excludes ends_on, since publishers commonly correct an end date later.
insert into travel.exhibitions (
    source_key, venue_id, title_ja, title_en, starts_on, ends_on, period_note,
    official_url, price_min_jpy, price_max_jpy, price_note,
    description_ja, description_en, sources, source_refs,
    verified_at, status, created_at, updated_at
)
select
    e.source_key,
    venue.id, e.name_ja, e.name_en, e.exhibition_starts_on, e.exhibition_ends_on,
    e.exhibition_period_note, e.official_url, e.price_min_jpy, e.price_max_jpy,
    e.price_note, e.description_ja, e.description_en,
    regexp_split_to_array(e.source_name, '\+'),
    jsonb_build_object(e.source_name, jsonb_build_object('url', e.source_url)),
    e.verified_at, e.status, e.created_at, e.updated_at
from travel.locations e
join lateral (
    select v.id
    from travel.locations v
    where v.category <> 'exhibition'
      and v.name_ja = e.location_text
      and v.latitude = e.latitude
      and v.longitude = e.longitude
    order by v.id
    limit 1
) venue on true
where e.category = 'exhibition'
on conflict (source_key) do update set
    ends_on = excluded.ends_on,
    period_note = excluded.period_note,
    official_url = excluded.official_url,
    price_min_jpy = excluded.price_min_jpy,
    price_max_jpy = excluded.price_max_jpy,
    price_note = excluded.price_note,
    description_ja = excluded.description_ja,
    sources = excluded.sources,
    source_refs = excluded.source_refs,
    verified_at = excluded.verified_at,
    updated_at = excluded.updated_at;

-- Abort instead of silently losing an exhibition whose venue could not be linked.
do $$
begin
    if exists (
        select 1 from travel.locations e
        where e.category = 'exhibition'
          and not exists (
              select 1 from travel.locations v
              where v.category <> 'exhibition'
                and v.name_ja = e.location_text
                and v.latitude = e.latitude
                and v.longitude = e.longitude
          )
    ) then
        raise exception 'some legacy exhibitions could not be linked to a venue';
    end if;
end $$;

delete from travel.locations where category = 'exhibition';
notify pgrst, 'reload schema';
commit;
