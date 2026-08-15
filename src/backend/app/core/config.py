"""Application settings, loaded from environment variables / .env."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Pilahin API"
    app_version: str = "0.1.0"
    app_description: str = (
        "API for Pilahin (#PilahAjaDulu) — a waste-sorting app that rewards "
        "users with points for sorting their waste properly."
    )
    api_v1_prefix: str = "/api/v1"
    debug: bool = True

    # Swagger UI / ReDoc / OpenAPI schema. Disable in production by setting
    # ENABLE_DOCS=false if you don't want the API surface publicly browsable.
    enable_docs: bool = True

    # CORS
    cors_allow_origins: list[str] = ["*"]

    # PostgreSQL via SQLAlchemy Core (see app/db.py). The "postgresql+psycopg"
    # dialect selects the psycopg (v3) driver. `docker-compose.yml` runs a
    # matching postgres service for this default to work out of the box.
    database_url: str = "postgresql+psycopg://postgres:@localhost:5432/pilahin"

    # Waste classification pipeline (see pipeline/segment_classify.py)
    ml_device: str = "cpu"  # "cpu" | "mps" | "cuda"

    # Where /waste/submit saves the rendered segmentation overlay + results
    # grid for each submission (mirrors what segment_classify.py's CLI writes
    # for local runs). Relative to the process's working directory, which is
    # always src/backend (see main.py) — Docker, Vercel, and local dev all
    # run uvicorn from there.
    waste_output_dir: str = "pipeline/images/output"

    # LLM report generation (see app/services/llm/ and /report endpoint).
    # "openai" | "claude" | "ollama" — defaults to a local Ollama daemon so
    # /report works out of the box without any API key during development.
    llm_provider: str = "ollama"
    llm_model: str = "llama3.1"
    llm_max_tokens: int = 1024
    llm_temperature: float = 0.3

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"

    anthropic_api_key: str | None = None
    anthropic_base_url: str = "https://api.anthropic.com"

    ollama_base_url: str = "http://localhost:11434"

    # Auth (see app/core/security.py + app/api/deps.py). Override
    # JWT_SECRET_KEY via env/`.env` outside of local development —
    # this default is only safe for a throwaway dev DB.
    jwt_secret_key: str = "dev-only-insecure-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24


@lru_cache
def get_settings() -> Settings:
    return Settings()
