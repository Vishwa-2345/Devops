"""Deterministic, rule-based CI/CD failure classification.

Rules are evaluated in priority order. Logs are treated as untrusted: we only
*scan* text for signals and never execute or interpret instructions in it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.security import sanitize_log

UNKNOWN = "unknown"


@dataclass(frozen=True)
class CategoryRule:
    category: str
    label: str
    patterns: list[re.Pattern]
    probable_cause: str
    suggested_next_step: str
    base_confidence: float
    automatable: bool
    severity: str = "medium"


def _p(*patterns: str) -> list[re.Pattern]:
    return [re.compile(p, re.IGNORECASE) for p in patterns]


RULES: list[CategoryRule] = [
    CategoryRule(
        category="k8s_oomkilled",
        label="Kubernetes OOMKilled",
        patterns=_p(r"OOMKilled", r"out of memory", r"memory cgroup out of memory", r"Error: OOM"),
        probable_cause="The container exceeded its memory limit and was killed by the kernel.",
        suggested_next_step="Raise the container memory limit/request and investigate memory usage.",
        base_confidence=0.9,
        automatable=False,
        severity="high",
    ),
    CategoryRule(
        category="k8s_crashloopbackoff",
        label="Kubernetes CrashLoopBackOff",
        patterns=_p(r"CrashLoopBackOff", r"back-off restarting failed container"),
        probable_cause="A pod keeps crashing and Kubernetes is backing off restarts.",
        suggested_next_step="Inspect pod logs and the container exit code; fix the crash.",
        base_confidence=0.88,
        automatable=False,
        severity="high",
    ),
    CategoryRule(
        category="missing_npm_dependencies",
        label="Missing npm dependencies",
        patterns=_p(
            r"Cannot find module",
            r"npm ERR! code ERESOLVE",
            r"npm error code ERESOLVE",
            r"npm ERR! 404",
            r"Could not resolve dependency",
            r"ERR_MODULE_NOT_FOUND",
            r"missing script",
            r"npx: command not found",
        ),
        probable_cause="A required npm package is missing from the manifest or lockfile.",
        suggested_next_step="Install/add the missing dependency and commit the updated lockfile.",
        base_confidence=0.85,
        automatable=True,
        severity="medium",
    ),
    CategoryRule(
        category="typescript_error",
        label="TypeScript compilation error",
        patterns=_p(r"error TS\d{3,5}", r"tsc\b.*error", r"Type '.*?' is not assignable"),
        probable_cause="The TypeScript compiler reported type errors.",
        suggested_next_step="Fix the reported type errors, then re-run the type check.",
        base_confidence=0.9,
        automatable=True,
        severity="medium",
    ),
    CategoryRule(
        category="test_failure",
        label="Test failure",
        patterns=_p(
            r"^\s*FAILED\s",
            r"^\s*FAIL\s+\S+",
            r"Tests? failed",
            r"\d+ (?:tests? )?(?:failed|failing|passed)",
            r"AssertionError",
            r"Assertion failed",
            r"^\s*[✕×]\s",
            r"pytest.*(?:failed|error)",
        ),
        probable_cause="One or more automated tests failed.",
        suggested_next_step="Reproduce the failing test locally and fix the root cause.",
        base_confidence=0.8,
        automatable=True,
        severity="medium",
    ),
    CategoryRule(
        category="docker_build_failure",
        label="Docker build failure",
        patterns=_p(
            r"docker build",
            r"failed to solve",
            r"ERROR: failed to build",
            r"Dockerfile.*error",
            r"failed to compute cache key",
            r"buildkit",
        ),
        probable_cause="The Docker image build failed (Dockerfile or build context issue).",
        suggested_next_step="Review the Dockerfile and build context; fix the failing step.",
        base_confidence=0.8,
        automatable=False,
        severity="medium",
    ),
    CategoryRule(
        category="container_failure",
        label="Container failure",
        patterns=_p(
            r"container exited with (?:code|status)",
            r"OCI runtime error",
            r"Error response from daemon",
            r"container.*unhealthy",
        ),
        probable_cause="A container failed to run correctly.",
        suggested_next_step="Inspect container logs and exit code; fix the runtime error.",
        base_confidence=0.75,
        automatable=False,
        severity="medium",
    ),
    CategoryRule(
        category="missing_env_var",
        label="Missing environment variable",
        patterns=_p(
            r"environment variable .* (?:is )?not set",
            r"Missing required env",
            r"process\.env\.[A-Z0-9_]+",
            r"KeyError: ['\"][A-Z0-9_]+['\"]",
            r"required variable .* is missing",
        ),
        probable_cause="A required environment variable/secret is not configured.",
        suggested_next_step="Define the missing environment variable or repository secret.",
        base_confidence=0.8,
        automatable=True,
        severity="high",
    ),
    CategoryRule(
        category="authentication_failure",
        label="Authentication / authorization failure",
        patterns=_p(
            r"\b401\b",
            r"\b403\b",
            r"Bad credentials",
            r"Authentication failed",
            r"Permission denied",
            r"unauthorized",
            r"could not read Username",
            r"invalid token",
        ),
        probable_cause="Credentials are missing, invalid or lack required permissions.",
        suggested_next_step="Verify the token/secret and that required scopes/permissions are granted.",
        base_confidence=0.75,
        automatable=False,
        severity="high",
    ),
    CategoryRule(
        category="configuration_error",
        label="Configuration error",
        patterns=_p(
            r"Invalid configuration",
            r"configuration error",
            r"invalid value",
            r"yaml: (?:line|unmarshal)",
            r"JSONDecodeError",
            r"failed to parse",
            r"unexpected token",
        ),
        probable_cause="A configuration file or value is malformed or invalid.",
        suggested_next_step="Validate and correct the configuration, then re-run the workflow.",
        base_confidence=0.75,
        automatable=True,
        severity="medium",
    ),
    CategoryRule(
        category="build_failure",
        label="Build failure",
        patterns=_p(
            r"Build failed",
            r"compilation (?:failed|error)",
            r"ERROR in ",
            r"error during build",
            r"make: \*\*\*",
            r"gcc: error",
        ),
        probable_cause="The build step failed.",
        suggested_next_step="Review build output and resolve the compilation/build error.",
        base_confidence=0.7,
        automatable=True,
        severity="medium",
    ),
]


@dataclass
class Classification:
    category: str
    label: str
    probable_cause: str
    suggested_next_step: str
    confidence: float
    automatable: bool
    severity: str
    evidence: list[str] = field(default_factory=list)
    log_excerpt: str = ""

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "label": self.label,
            "probable_cause": self.probable_cause,
            "suggested_next_step": self.suggested_next_step,
            "confidence": self.confidence,
            "automatable": self.automatable,
            "severity": self.severity,
            "evidence": self.evidence,
        }


def _collect_evidence(text: str, patterns: list[re.Pattern], limit: int = 5) -> list[str]:
    evidence: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(p.search(stripped) for p in patterns):
            evidence.append(stripped[:300])
            if len(evidence) >= limit:
                break
    return evidence


def classify_failure(
    logs: str,
    *,
    workflow_name: str = "",
    summary_hint: str = "",
) -> Classification:
    """Classify a failure from log text. Deterministic and LLM-independent."""
    clean = sanitize_log(logs or "")
    haystack = "\n".join(filter(None, [clean, summary_hint, workflow_name]))

    for rule in RULES:
        hits = _collect_evidence(haystack, rule.patterns)
        if not hits:
            continue
        # Confidence scales with number of distinct matching signals.
        confidence = min(0.98, rule.base_confidence + 0.03 * (len(hits) - 1))
        excerpt_lines = [ln for ln in clean.splitlines() if ln.strip()][:40]
        return Classification(
            category=rule.category,
            label=rule.label,
            probable_cause=rule.probable_cause,
            suggested_next_step=rule.suggested_next_step,
            confidence=round(confidence, 2),
            automatable=rule.automatable,
            severity=rule.severity,
            evidence=hits,
            log_excerpt="\n".join(excerpt_lines)[:4000],
        )

    excerpt_lines = [ln for ln in clean.splitlines() if ln.strip()][:40]
    return Classification(
        category=UNKNOWN,
        label="Unknown failure",
        probable_cause="The failure could not be matched to a known pattern.",
        suggested_next_step="Review the full workflow logs manually to identify the root cause.",
        confidence=0.25,
        automatable=False,
        severity="medium",
        evidence=["No known failure signature detected in the available logs."],
        log_excerpt="\n".join(excerpt_lines)[:4000],
    )
