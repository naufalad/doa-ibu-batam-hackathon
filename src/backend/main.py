"""FastAPI application factory + entrypoint for Pilahin.

Lives at the `src/backend` root (next to `requirements.txt`, sibling to the
`app` package) rather than inside `app/`, so this directory is self-contained
for both `uvicorn main:app` (Docker/Vercel, cwd = src/backend) and local dev
(`python main.py`, also from src/backend). Importing it as a script or as
`main:app` — never as `app.main`, and never by running a file inside `app/`
directly — is what keeps these as absolute imports instead of relative ones.

Prod: uvicorn main:app --host 0.0.0.0 --port 8000
Dev:  python main.py   # auto-reload
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, health, regions, report, rewards, waste
from app.api.routes import users
from app.core.config import get_settings
from app.db import init_db

TAGS_METADATA = [
    {"name": "health", "description": "Liveness/readiness check."},
    {"name": "auth", "description": "Login / JWT issuance."},
    {
        "name": "users",
        "description": "User accounts, roles (user/waste_bank/authorized), and points balance.",
    },
    {"name": "regions", "description": "Region catalog used for user addresses and waste_bank scoping."},
    {
        "name": "waste",
        "description": "Waste-sorting photo submissions, run through the "
        "segmentation + classification pipeline, the pickup-vs-dropoff "
        "delivery choice, and the region-scoped pickup/dropoff workflow "
        "for waste_bank/authorized accounts.",
    },
    {"name": "rewards", "description": "Rewards catalog and point redemptions."},
    {
        "name": "report",
        "description": "LLM-generated summaries of a user's waste-sorting history.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Must use `lifespan=` rather than the deprecated `@app.on_event`
    # startup hook — see the starlette<1.0 pin note in requirements.txt.
    init_db()
    yield


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=settings.app_description,
        debug=settings.debug,
        openapi_tags=TAGS_METADATA,
        docs_url="/docs" if settings.enable_docs else None,
        redoc_url="/redoc" if settings.enable_docs else None,
        openapi_url="/openapi.json" if settings.enable_docs else None,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(auth.router, prefix=settings.api_v1_prefix)
    app.include_router(users.router, prefix=settings.api_v1_prefix)
    app.include_router(regions.router, prefix=settings.api_v1_prefix)
    app.include_router(waste.router, prefix=settings.api_v1_prefix)
    app.include_router(rewards.router, prefix=settings.api_v1_prefix)
    app.include_router(report.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)