"""Common interface every LLM backend implements.

Keeping this as a plain ABC (rather than importing any one vendor's SDK
here) is what lets `app/services/report_generator.py` stay provider-agnostic
— it only ever talks to `LLMProvider.chat(...)`, never to OpenAI/Anthropic/
Ollama specifics directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Literal, TypedDict


class ChatMessage(TypedDict):
    role: Literal["system", "user", "assistant"]
    content: str


class LLMProvider(ABC):
    """A chat-completion backend, addressed by its OpenAI/Claude/Ollama API."""

    @abstractmethod
    async def chat(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> str:
        """Send a chat-style conversation, return the assistant's reply text.

        `messages` may include a leading `"system"` message; providers whose
        wire format pulls the system prompt out of the message list (e.g.
        Claude) are responsible for that translation internally.
        """
        raise NotImplementedError


class LLMProviderError(RuntimeError):
    """Raised when a provider is misconfigured or the backend call fails."""
