"""Claude-compatible provider, talking to the Anthropic Messages API wire
format (`POST /v1/messages` with `x-api-key` + `anthropic-version` headers).

Unlike the OpenAI shape, Anthropic takes the system prompt as its own
top-level `system` field rather than as a `"system"`-role message, so this
provider splits it out of `messages` before sending.
"""

from __future__ import annotations

import httpx

from .base import ChatMessage, LLMProvider, LLMProviderError

ANTHROPIC_VERSION = "2023-06-01"


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str, base_url: str = "https://api.anthropic.com") -> None:
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
        system_prompt, turns = _split_system(messages)

        payload: dict = {
            "model": self.model,
            "messages": turns,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=60) as client:
            try:
                resp = await client.post(
                    f"{self.base_url}/v1/messages",
                    headers={
                        "x-api-key": self.api_key,
                        "anthropic-version": ANTHROPIC_VERSION,
                        "content-type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise LLMProviderError(f"Claude request failed: {exc}") from exc

        data = resp.json()
        try:
            return "".join(block["text"] for block in data["content"] if block.get("type") == "text")
        except (KeyError, TypeError) as exc:
            raise LLMProviderError(f"Unexpected Claude response shape: {data}") from exc


def _split_system(messages: list[ChatMessage]) -> tuple[str | None, list[dict]]:
    """Pull leading `"system"`-role messages out into Anthropic's separate field."""
    system_parts = [m["content"] for m in messages if m["role"] == "system"]
    turns = [{"role": m["role"], "content": m["content"]} for m in messages if m["role"] != "system"]
    return ("\n\n".join(system_parts) or None), turns
