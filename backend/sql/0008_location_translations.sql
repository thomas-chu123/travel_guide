-- Add stored translations for the three supported UI languages.
-- Apply as the owner of the travel schema, after 0007.
begin;

alter table travel.locations
    add column if not exists description_zh text,
    add column if not exists address_en text,
    add column if not exists address_zh text,
    add column if not exists opening_hours_en text,
    add column if not exists opening_hours_zh text,
    add column if not exists translation_meta jsonb not null default '{}'::jsonb;

alter table travel.exhibitions
    add column if not exists title_zh text,
    add column if not exists description_zh text,
    add column if not exists price_note_en text,
    add column if not exists price_note_zh text,
    add column if not exists period_note_en text,
    add column if not exists period_note_zh text,
    add column if not exists translation_meta jsonb not null default '{}'::jsonb;

notify pgrst, 'reload schema';
commit;
