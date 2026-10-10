"""LLM provider factory / registry."""

from __future__ import annotations

from app.config import get_settings
from app.llm.base import LLMProvider
from app.llm.ollama import OllamaProvider
from app.llm.rules import RulesProvider


def get_provider(name: str | None = None) -> LLMProvider:
    """Return the configured provider. 'rules' is the safe default."""
    provider_name = (name or get_settings().llm_provider or "rules").strip().lower()
    if provider_name == "ollama":
        return OllamaProvider()
    return RulesProvider()
