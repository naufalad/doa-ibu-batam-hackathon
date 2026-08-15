"""Local Ollama provider, talking to its native `/api/chat` endpoint.

No API key needed — this assumes an `ollama serve` daemon reachable at
`base_url` (default `http://localhost:11434`) with `model` already pulled
(`ollama pull llama3.1`, etc). Good default for offline/no-budget dev.
"""

from __future__ import annotations

import httpx

from .base import ChatMessage, LLMProvider, LLMProviderError


class OllamaProvider(LLMProvider):
    def __init__(self, model: str, base_url: str = "http://localhost:11434") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str:
        async with httpx.AsyncClient(timeout=120) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                        "options": {"temperature": temperature, "num_predict": max_tokens},
                    },
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise LLMProviderError(
                    f"Ollama request failed ({exc}). Is `ollama serve` running "
                    f"and has `{self.model}` been pulled?"
                ) from exc

        data = resp.json()
        try:
            return data["message"]["content"]
        except KeyError as exc:
            raise LLMProviderError(f"Unexpected Ollama response shape: {data}") from exc
