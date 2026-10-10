"""LLM provider tests — rules and Ollama-unavailable fallback."""

from __future__ import annotations

from app.llm import DiagnosisContext, get_provider
from app.llm.ollama import OllamaProvider
from app.llm.rules import RulesProvider


def _context(logs: str = "npm ERR! code ERESOLVE\nCannot find module 'x'") -> DiagnosisContext:
    return DiagnosisContext(
        repository_full_name="octocat/demo-app",
        workflow_name="CI",
        conclusion="failure",
        logs=logs,
        run_url="https://github.com/octocat/demo-app/actions/runs/1",
    )


def test_rules_provider_always_available():
    provider = RulesProvider()
    result = provider.diagnose(_context())
    assert result.provider == "rules"
    assert result.category == "missing_npm_dependencies"
    assert provider.health().available is True


def test_factory_defaults_to_rules():
    provider = get_provider("rules")
    assert provider.name == "rules"


def test_ollama_without_model_falls_back_to_rules():
    provider = OllamaProvider(base_url="http://localhost:1", model="")
    assert provider.health().available is False
    result = provider.diagnose(_context())
    assert result.provider == "rules"
    assert result.category == "missing_npm_dependencies"


def test_ollama_unreachable_falls_back_to_rules():
    provider = OllamaProvider(base_url="http://localhost:1", model="llama3")
    health = provider.health()
    assert health.available is False
    result = provider.diagnose(_context())
    assert result.provider == "rules"
    assert result.category == "missing_npm_dependencies"
    assert result.automatable is True


def test_ollama_never_bypasses_security_flag():
    provider = OllamaProvider(base_url="http://localhost:1", model="llama3")
    result = provider.diagnose(_context("nothing known"))
    assert result.category == "unknown"
    assert result.automatable is False
