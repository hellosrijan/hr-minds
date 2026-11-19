"""
The model seam. Everything else in the app talks to `LLM.chat()` in our own
message shape; only this file knows which provider is behind it.
"""

from dataclasses import dataclass, field
from typing import Literal

from hr_minds.settings.config import settings

Capability = Literal["default", "reasoning", "fast"]


class LLMNotConfigured(Exception):
    """LLM_BASE_URL, LLM_API_KEY or a model name is missing from the settings."""


@dataclass(frozen=True)
class LLMReply:
    """One model turn: either text, or tool calls."""

    content: str | None = None
    # [{"id": "...", "name": "...", "arguments": {...}}]
    tool_calls: list[dict] = field(default_factory=list)
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


def model_for(capability: Capability = "default") -> str:
    """The model name for a capability; reasoning/fast fall back to LLM_MODEL when empty."""
    specific = {"reasoning": settings.LLM_MODEL_REASONING, "fast": settings.LLM_MODEL_FAST}.get(capability)
    model = specific or settings.LLM_MODEL
    if not (model and settings.LLM_BASE_URL and settings.LLM_API_KEY):
        raise LLMNotConfigured()
    return model


class LLM:
    """The real model. The HTTP call is added in step 6; until then it only checks settings."""

    async def chat(
        self, messages: list[dict], tools: list[dict], capability: Capability = "default"
    ) -> LLMReply:
        """
        `messages` are plain dicts in our neutral shape:
          {"role": "user" | "assistant" | "tool", "content": str | None,
           "tool_calls": [...] | None, "tool_call_id": str | None, "tool_name": str | None}
        """
        model_for(capability)
        raise NotImplementedError("provider adapter comes in step 6")


def get_llm() -> LLM:
    """FastAPI dependency. Tests override it with a FakeLLM, the same way they override get_db."""
    return LLM()