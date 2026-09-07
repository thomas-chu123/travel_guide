-- Apply as the owner of travel.locations, after 0002.
begin;
alter table travel.locations
    add column if not exists venue_id uuid generated always as (id) stored,
    add column if not exists name_zh text,
    add column if not exists address_ja text,
    add column if not exists ward_city text,
    add column if not exists access_url text,
    add column if not exists exhibitions_url text,
    add column if not exists verified_at timestamptz,
    add column if not exists status text not null default 'unverified';

create unique index if not exists locations_venue_id_idx on travel.locations (venue_id);
-- category remains open to existing parks, temples and other attractions.
comment on column travel.locations.category is
    'Art venues: art_museum, gallery, exhibition_space, convention_center. Legacy museum also includes history museums.';
comment on column travel.locations.venue_id is 'Stable alias of the existing location id.';
comment on column travel.locations.status is
    'operating, temporarily_closed, relocated, closed, unverified';

do $$ begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'travel.locations'::regclass and conname = 'locations_status_check'
    ) then
        alter table travel.locations add constraint locations_status_check
            check (status in ('operating', 'temporarily_closed', 'relocated', 'closed', 'unverified'));
    end if;
end $$;

-- Do not infer verified addresses or operating status from the legacy walking map.
notify pgrst, 'reload schema';
commit;
