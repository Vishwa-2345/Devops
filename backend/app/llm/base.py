"""LLM provider abstraction and shared diagnosis types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from pydantic import BaseModel, Field


@dataclass
class DiagnosisContext:
    repository_full_name: str
    workflow_name: str
    conclusion: str | None
    logs: str = ""
    run_url: str | None = None
    failure_hint: str = ""


class DiagnosisResult(BaseModel):
    """Validated, bounded diagnosis output. Extra/unknown fields are ignored."""

    category: str = Field(default="unknown", max_length=100)
    summary: str = Field(default="", max_length=2000)
    probable_cause: str = Field(default="", max_length=2000)
    suggested_next_step: str = Field(default="", max_length=2000)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)
    automatable: bool = False
    provider: str = "rules"
    model: str | None = None
    raw: dict | None = None


@dataclass
class ProviderHealth:
    name: str
    available: bool
    detail: str = ""


class LLMProvider(Protocol):
    name: str

    def diagnose(self, context: DiagnosisContext) -> DiagnosisResult:  # pragma: no cover - protocol
        ...

    def health(self) -> ProviderHealth:  # pragma: no cover - protocol
        ...


__all__ = [
    "DiagnosisContext",
    "DiagnosisResult",
    "ProviderHealth",
    "LLMProvider",
]
