# Software Architecture & Tech Stack

## Overview

```mermaid
graph TD
    subgraph Clients["Client apps (planned — see src/frontend/)"]
        H[household app]
        WB[waste_bank app]
        WH[whole / program-admin app]
    end

    H -- "HTTPS + JWT" --> API
    WB -- "HTTPS + JWT" --> API
    WH -- "HTTPS + JWT" --> API

    subgraph Render["Render — Web Service (Docker)"]
        API["FastAPI app\nuvicorn, app/api/routes/*"]
        PIPE["In-process ML pipeline\nMask2Former (segmentation)\n+ ViT (waste classification)\nbaked into the image, CPU"]
        API --- PIPE
    end

    API -- "SQLAlchemy Core\npostgresql+psycopg, TLS" --> DB[(Supabase\nManaged PostgreSQL)]
    API -- "httpx, pluggable\nLLM_PROVIDER" --> LLM{{"OpenAI / Anthropic Claude\n/ local Ollama"}}
```

## Backend

| Layer | Choice | Notes |
|---|---|---|
| Language / runtime | Python 3.13 | `python:3.13-slim-bookworm` base image |
| Web framework | FastAPI + Starlette | pinned `starlette<1.0` (FastAPI 0.141.x still passes `on_startup`/`on_shutdown` into `Router.__init__`, which starlette ≥1.0 dropped) |
| ASGI server | uvicorn (`uvicorn[standard]`) | `uvicorn main:app`; honors `$PORT` for Render/Railway-style platforms |
| Data access | SQLAlchemy **Core** (no ORM) | `Table`/`select`/`insert`/`update` expressions directly against `app/db.py::metadata`; no session layer |
| DB driver | `psycopg[binary]>=3.1` | dialect string `postgresql+psycopg://` |
| Auth | PyJWT (HS256) + `pbkdf2_hmac("sha256", …, 600_000 iterations)` | see `app/core/security.py`; JWT bakes in `role` + `region_ids` so authorization checks are a single decode with no DB round-trip |
| Validation / schemas | Pydantic v2 (`pydantic-settings` for config) | `app/schemas/*.py` |
| ML pipeline | HuggingFace `transformers`, `torch`/`torchvision` (CPU wheels) | `facebook/mask2former-swin-tiny-coco-instance` for instance segmentation, `watersplash/waste-classification` (ViT) for category classification — see `src/backend/pipeline/segment_classify.py` |
| Image handling | Pillow, NumPy, Matplotlib, SciPy | overlay + results-grid rendering for each submission |
| LLM reports | Provider-agnostic `LLMProvider` ABC + `httpx` | OpenAI / Anthropic Claude / Ollama, selected at runtime via `LLM_PROVIDER` — see `app/services/llm/` |
| Container | Docker (single `Dockerfile`, non-root `appuser`, `HEALTHCHECK` on `/api/v1/health`) | ~3GB image: bakes in CPU torch + both HF model checkpoints so the running container needs no outbound calls to PyPI/huggingface.co |
| Local dev | `docker-compose.yml` | `postgres:16-alpine` + backend, wired via `DATABASE_URL` |

## Frontend

`src/frontend/` is scaffolded as three separate client apps (one per role) rather than one app with
role-based screens — see [user-journeys.md](user-journeys.md) for what each one needs to do. All three
are currently placeholders (empty `README.md`); framework and hosting are **not yet decided** and are
tracked in [`docs/todo.md`](todo.md) ("Frontend-backend wiring").

- **`household/`** — consumer app: submit waste photos, track points, browse/redeem rewards.
- **`waste_bank/`** — operator app: verify/collect pickups, confirm dropoffs, region-scoped.
- **`whole/`** — program-admin app: city-wide stats, region + waste_bank provisioning.

## Deployment target

| Component | Platform | Notes |
|---|---|---|
| Backend API | **Render** (Web Service, Docker runtime) | Builds the root `Dockerfile`; Render sets `$PORT` and the container's `CMD` already reads it (`uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}`). Health check path: `/api/v1/health`. |
| Database (DBMS) | **Supabase** (managed PostgreSQL) | Supabase's connection string is passed in as `DATABASE_URL` (`postgresql+psycopg://...`), same env var `app/core/config.py::Settings.database_url` already expects — no code change needed to point at Supabase instead of the docker-compose Postgres. |
| Frontend app(s) | TBD | Not yet implemented; a static/SPA host (e.g. Vercel/Netlify) is the likely fit once a framework is chosen. |

### Environment variables the backend needs in production

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Supabase Postgres connection string (`postgresql+psycopg://user:pass@host:port/db`) |
| `JWT_SECRET_KEY` | **Must** be overridden from the insecure dev default — see [no-secrets-in-config-defaults](../src/backend/app/core/config.py) |
| `CORS_ALLOW_ORIGINS` | Restrict from `["*"]` to the deployed frontend origin(s) once they exist |
| `LLM_PROVIDER`, `LLM_MODEL`, and one of `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `OLLAMA_BASE_URL` | Powers `GET /report/{user_id}` |
| `ML_DEVICE` | `cpu` on Render (no GPU tier assumed) |
| `ENABLE_DOCS` | Set `false` to hide Swagger/ReDoc/OpenAPI in production if the API surface shouldn't be publicly browsable |

### Known gaps to account for when deploying

- `waste_output_dir` (segmented image + results-grid outputs) is written to the container's writable
  layer — **ephemeral** on Render; needs an external store (e.g. Supabase Storage or S3-compatible
  bucket) if these need to persist across deploys/restarts.
