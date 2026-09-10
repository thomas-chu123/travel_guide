-- Provenance for one-time location description enrichment.
-- Apply as the owner of travel.locations before running the enrichment script.
alter table travel.locations
    add column if not exists enrichment_meta jsonb not null default '{}'::jsonb;

notify pgrst, 'reload schema';
commit;
