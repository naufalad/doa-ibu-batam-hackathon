# TODO

_Last updated: 2026-08-16_

## Now

1. Frontend-backend wiring for the household mobile app
2. Frontend-backend wiring for the waste bank mobile app
3. Frontend-backend wiring for the municipal (admin) app — `src/frontend/municipal/` replaces the old `whole/` placeholder
4. Fix `GET /rewards`: the route now selects/returns a `name` column, but both the `rewards` table (`app/db.py`) and `RewardOut` (`app/schemas/reward.py`) still define this field as `title` — 500s at runtime until one side is renamed to match (see [api-endpoints.md](api-endpoints.md))
5. Deploy the backend (Render + Supabase Postgres) and fill in the README's Application link / pitch video / slide deck placeholders

## Backend hardening (before going live)

6. Persist segmented-image / results-grid outputs externally (Supabase Storage or S3-compatible bucket) — currently written to the container's ephemeral writable layer and lost on redeploy/restart
7. Restrict `CORS_ALLOW_ORIGINS` from `["*"]` to the real frontend origin(s) once they're deployed
8. Replace `rewards_policy.py`'s placeholder per-kg point ranges with real market rates once product defines them (purity multiplier from `waste_confidence` is in place, but the base rates are still made up)

## Frontend

9. Pick a framework + hosting for `household/`, `waste_bank/`, and `municipal/` — all three are still empty placeholders (`README.md` only)

## Docs / submission

10. Fill in [disclaimer.md](disclaimer.md)'s AI-tools list and team members table (currently placeholders)
11. Fill in the README's Application link, pitch video, and slide deck placeholders once available
