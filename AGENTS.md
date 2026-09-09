# AGENTS.md

## Project overview

This repository is a Tokyo attraction and exhibition map. The current implementation is:

- `frontend/`: React 19, TypeScript, Vite, MapLibre GL JS and PMTiles.
- `backend/`: FastAPI API plus a standalone exhibition synchronization worker.
- Supabase schema `travel`: production venue/exhibition data accessed through PostgREST.
- Local SQLite/Alembic: development scaffolding and tests; it is not the source of the current
  public map data.

The frontend must only read public location data through FastAPI. Never expose Supabase secret
keys in frontend code or Vite variables.

## Current product behavior

The map drawer has two filter levels:

1. Attraction category, displayed above the exhibition date filter:
   - `art`: `美術館/展覽館`
   - `park`: `公園`
   - `temple_shrine`: `寺廟/神社`
   - `all`: `全部景點` (default)
2. Exhibition date: current, future, or all. Date filtering applies only to records whose
   category is `exhibition`; ordinary venues remain visible.

The art group includes `museum`, `art_museum`, `gallery`, `exhibition_space`,
`convention_center`, and `exhibition`.

Category changes must update both the drawer list and the MapLibre layers. The drawer list is
limited to features inside the current map viewport.

## Map marker rules

- Museum, park, and temple/shrine markers are PNG symbol layers, not colored circle layers.
- Their source files are in `frontend/src/assets/`:
  - `museum-icon.png`
  - `park-icon.png`
  - `temple-shrine-icon.png`
- All three marker assets use the same presentation: a centered subject inside a white
  water-drop pin, subtle cool-gray border/shadow, and genuine transparency outside the pin.
- Keep the assets square, currently 320 x 320 RGBA, and use the same MapLibre `icon-size` so the
  categories appear at a consistent visual scale.
- The generic `location-points` circle layer must explicitly exclude `museum`, `art_museum`,
  `park`, and `temple_shrine`; otherwise duplicate colored dots appear beneath image markers.
- Do not nest or combine MapLibre legacy filters with expression filters and then silence the
  TypeScript error with a cast. Category selection uses layer `visibility`; filters on a layer
  must remain a single valid filter syntax.
- Do not mistake icons rendered by the GSI basemap for application marker layers. Validate the
  `museum-points`, `park-points`, and `temple-shrine-points` layers themselves.

When generating or editing raster marker assets, use the image generation workflow. Inspect the
saved file afterward: a checkerboard drawn into an RGB image is not transparency. Final assets
must report an alpha channel and must be copied into `frontend/src/assets/` before code refers to
them.

## Supabase location data

- Active table: `travel.locations`.
- Exhibition table: `travel.exhibitions`.
- Pre-rebuild backup table: `travel.location_bak` (singular). Do not use `locations_bak`.
- `backend/sql/0004_backup_and_rebuild_top50_museums.sql` created the backup and rebuilt the
  active museum set.
- `backend/sql/0007_restore_parks_and_temples.sql` restores `park` and `temple_shrine` rows from
  the backup. It is idempotent through the unique `source_key`.
- `backend/scripts/restore_location_categories.py` performs the equivalent restore through
  PostgREST. It is dry-run by default; `--apply` performs writes.
- The current backup contains 718 parks and 382 temples/shrines. Preserve original UUIDs,
  `source_key`, provenance, timestamps, and unverified status when restoring them.
- `venue_id` is generated from `id`; never include it in PostgREST insert payloads.
- Never print `.env` values or Supabase credentials. Use the backend REST client and the
  `travel` profile.

The locations API joins exhibitions to their venue coordinates and emits one GeoJSON feature
collection. Venue categories and `exhibition` features coexist in this response.

## Development commands

Run commands from the correct directory:

```bash
# Frontend
cd frontend
npm run build
npm run dev

# Backend
cd backend
.venv/bin/pytest -q
.venv/bin/uvicorn app.main:app --reload

# Full local development environment
./scripts/dev-deploy.sh
```

`./scripts/pm2-deploy.sh` is a broad production operation: it installs dependencies, runs
database migrations, rebuilds the frontend, and restarts API, worker, and web services. Do not
run it merely to validate a UI change. For an existing PM2 deployment, inspect the process list
and restart only the required service when possible.

## Required verification

A successful TypeScript/Vite build is necessary but is not UI acceptance. For changes affecting
the map or drawer, completion requires all of the following:

1. Run `npm run build` and the relevant backend tests.
2. Start or update the frontend actually being tested; confirm which hashed JS bundle the server
   returns. Do not assume that writing `dist/` updates a running or remote deployment.
3. Open the served app in a browser and inspect the rendered UI.
4. Open the drawer and confirm all four category buttons are visible and `全部景點` is selected
   initially.
5. Select each category and verify both list contents and map visibility.
6. At a viewport containing known records, confirm museums, parks, and temples/shrines use their
   water-drop PNG marker rather than colored circles.
7. Check the console/network panel for image-load, MapLibre layer, API, or stale-bundle errors.

If browser control is unavailable, report that limitation explicitly. Verifying bundle strings
or asset filenames is useful evidence but must not be described as visual browser verification.

## Change and safety rules

- Keep changes scoped; preserve unrelated work in a dirty worktree.
- Prefer idempotent data migrations and dry runs before Supabase writes.
- Do not truncate or rebuild `travel.locations` unless the user explicitly requests it and a
  verified backup exists.
- Do not run broad deployment scripts when a frontend-only restart is sufficient.
- Never claim deployment success based only on source changes or build output.
- Keep Tokyo date comparisons in `Asia/Tokyo`.
- Preserve source attribution for map data and imported location/exhibition records.
