"""OpenAI-compatible chat-completions provider.

Targets the `/chat/completions` wire format shared by OpenAI itself and the
many self-hosted/gateway servers that mirror it (vLLM, LM Studio, Together,
Groq, Azure OpenAI with a matching `base_url`, ...). Swap `base_url` to
point this at any of those instead of api.openai.com.
"""

from __future__ import annotations

import httpx

from .base import ChatMessage, LLMProvider, LLMProviderError


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1") -> None:
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str:
        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "max_tokens": max_tokens,
                        "temperature": temperature,
                    },
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise LLMProviderError(f"OpenAI-compatible request failed: {exc}") from exc

        data = resp.json()
        try:
            return data["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMProviderError(f"Unexpected OpenAI-compatible response shape: {data}") from exc
