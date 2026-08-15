# API Endpoints

Base path: `{API_V1_PREFIX}` = `/api/v1` (see `app/core/config.py::Settings.api_v1_prefix`).
Interactive docs (when `ENABLE_DOCS=true`, the default): `/docs` (Swagger UI), `/redoc`, `/openapi.json`.

Auth: `Authorization: Bearer <JWT>`, obtained from `POST /auth/login`. The `Auth` column below lists
which role(s) may call each route; **none** means no `Authorization` header is required at all.

## Health

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | none | Liveness/readiness check. Used by the Docker `HEALTHCHECK`. |

## Auth

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/auth/login` | none | OAuth2 password grant (`username`=email, `password`). Returns a JWT (`Token`) encoding `sub`, `email`, `role`, and (for `waste_bank`) `region_ids`. |

## Users

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/users` | none | Public self-signup. Always creates `role=user`. |
| POST | `/users/waste-bank-admins` | `authorized` | Provisions a `waste_bank` admin scoped to one or more `region_ids`. |
| GET | `/users/me` | any authenticated | Caller's own profile. |
| GET | `/users/{user_id}` | self or `authorized` | Look up a user's profile; 403 if neither self nor `authorized`. |

## Regions

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/regions` | none | List all regions (backs signup / admin-provisioning dropdowns). |
| POST | `/regions` | `authorized` | Create a region. 409 if the name already exists. |

## Waste

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/waste/submit` | `user` | Upload a waste photo (`multipart/form-data`: `file`, optional `weight_kg`). Runs Mask2Former segmentation + ViT classification, persists a `waste_submissions` row plus one `wastes` + `waste_tokens` row per detected object. |
| POST | `/waste/submissions/{submission_id}/delivery-method` | `user` (owner) | One-shot: body `{"method": "pickup" \| "self_dropoff"}`. `pickup` returns a scheduled collection slot; `self_dropoff` returns the nearest `waste_bank` covering the user's region. |
| POST | `/waste/tokens/{token_id}/draw` | `user` (owner) | Draws a random point value from the token's `[start_range, end_range]` and credits it to the caller's `points_balance`. One-shot per token. |
| GET | `/waste/pickups` | `waste_bank`, `authorized` | Submissions still at `pending_pickup`. Region-scoped automatically for `waste_bank`; `authorized` sees everything, optionally filtered via `?region_id=`. |
| GET | `/waste/history` | any authenticated | All submissions regardless of status, role-scoped: `user` → own only; `waste_bank` → their region(s); `authorized` → everything, filterable via `?status=`, `?region_id=`, `?user_id=`. |
| POST | `/waste/pickups/{submission_id}/collect` | `waste_bank`, `authorized` | Marks a `pending_pickup` submission `collected`. |
| POST | `/waste/dropoffs/{submission_id}/confirm` | `waste_bank`, `authorized` | Marks a `pending_dropoff` submission `dropped_off`. Intended to be called by the destination waste bank's automated intake system. |

## Rewards

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/rewards` | none | List the reward catalog from the `rewards` table. ⚠️ Currently under active edit and broken as written: it selects/returns a `name` column, but both the `rewards` table (`app/db.py`) and `RewardOut` (`app/schemas/reward.py`) still define this field as `title` — will raise at runtime until one side is renamed to match. |
| POST | `/rewards/redeem` | `user` | Body `{"reward_id": int}`. Atomically checks stock + balance, deducts points, decrements stock, and records a `redemptions` row (`status="pending"`). |

## Report

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/report/me` | any authenticated | `?days=30`. Caller's own report — id comes from the JWT, nothing to pass in. Same behavior as `/report/{user_id}` below otherwise. |
| GET | `/report/{user_id}` | self or `authorized` | `?days=30`. Summarizes the user's last N days of waste submissions and asks the configured LLM provider (`LLM_PROVIDER`: openai/claude/ollama) for a short narrative. 403 if neither self nor `authorized`; 404 if there's no history in the window; 502 if the LLM call fails. All numeric fields are computed locally — the LLM only ever writes the free-text `narrative`. |
