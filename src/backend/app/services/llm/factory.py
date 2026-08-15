"""Picks the configured LLM backend. Add a new provider by implementing
`LLMProvider` and registering it in `_PROVIDERS` below.
"""

from __future__ import annotations

from app.core.config import Settings

from .base import LLMProvider, LLMProviderError
from .claude_provider import ClaudeProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    name = settings.llm_provider.lower()

    if name == "openai":
        if not settings.openai_api_key:
            raise LLMProviderError("LLM_PROVIDER=openai requires OPENAI_API_KEY to be set")
        return OpenAIProvider(
            api_key=settings.openai_api_key,
            model=settings.llm_model,
            base_url=settings.openai_base_url,
        )

    if name == "claude":
        if not settings.anthropic_api_key:
            raise LLMProviderError("LLM_PROVIDER=claude requires ANTHROPIC_API_KEY to be set")
        return ClaudeProvider(
            api_key=settings.anthropic_api_key,
            model=settings.llm_model,
            base_url=settings.anthropic_base_url,
        )

    if name == "ollama":
        return OllamaProvider(model=settings.llm_model, base_url=settings.ollama_base_url)

    raise LLMProviderError(f"Unknown LLM_PROVIDER {settings.llm_provider!r} (expected openai/claude/ollama)")
