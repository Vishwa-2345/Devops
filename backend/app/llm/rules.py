"""Deterministic rule-based LLM provider (always available)."""

from __future__ import annotations

from app.classifier import classify_failure
from app.llm.base import DiagnosisContext, DiagnosisResult, ProviderHealth


class RulesProvider:
    name = "rules"

    def diagnose(self, context: DiagnosisContext) -> DiagnosisResult:
        classification = classify_failure(
            context.logs,
            workflow_name=context.workflow_name,
            summary_hint=context.failure_hint,
        )
        summary = (
            f"{classification.label} detected in workflow '{context.workflow_name}' "
            f"for {context.repository_full_name}."
        )
        return DiagnosisResult(
            category=classification.category,
            summary=summary,
            probable_cause=classification.probable_cause,
            suggested_next_step=classification.suggested_next_step,
            confidence=classification.confidence,
            evidence=classification.evidence,
            automatable=classification.automatable,
            provider=self.name,
            model=None,
            raw={"log_excerpt": classification.log_excerpt},
        )

    def health(self) -> ProviderHealth:
        return ProviderHealth(
            name=self.name, available=True, detail="Deterministic rules always available."
        )
