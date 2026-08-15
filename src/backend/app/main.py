"""FastAPI application factory for Pilahin."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import health, report, rewards, waste
from .api.routes import users
from .core.config import get_settings

TAGS_METADATA = [
    {"name": "health", "description": "Liveness/readiness check."},
    {"name": "users", "description": "User accounts and points balance."},
    {
        "name": "waste",
        "description": "Waste-sorting photo submissions, run through the "
        "segmentation + classification pipeline.",
    },
    {"name": "rewards", "description": "Rewards catalog and point redemptions."},
    {
        "name": "report",
        "description": "LLM-generated summaries of a user's waste-sorting history.",
    },
]


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
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router, prefix=settings.api_v1_prefix)
    app.include_router(users.router, prefix=settings.api_v1_prefix)
    app.include_router(waste.router, prefix=settings.api_v1_prefix)
    app.include_router(rewards.router, prefix=settings.api_v1_prefix)
    app.include_router(report.router, prefix=settings.api_v1_prefix)

    return app


app = create_app()
