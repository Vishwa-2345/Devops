"""Strict allowlist of supported remediation actions.

Security model
--------------
* Only actions declared here can ever be planned or executed.
* No action executes arbitrary shell commands or arbitrary URLs.
* The only action that mutates external state is ``RERUN_WORKFLOW``, which calls
  a single, fixed GitHub REST endpoint for an existing run.
* Parameters are validated against a per-action schema; unknown params are
  rejected.
* Risk level drives approval requirements (medium/high/critical require approval).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.models import RiskLevel

APPROVAL_REQUIRED_RISKS = {
    RiskLevel.MEDIUM.value,
    RiskLevel.HIGH.value,
    RiskLevel.CRITICAL.value,
}


class UnsupportedActionError(ValueError):
    """Raised when an action is unknown or its parameters are invalid."""


@dataclass(frozen=True)
class ParamSpec:
    name: str
    type: str  # "int" | "str"
    required: bool = True
    max_length: int | None = None


@dataclass(frozen=True)
class RemediationAction:
    action_id: str
    title: str
    description: str
    risk_level: str
    required_permissions: list[str]
    params: list[ParamSpec]
    preconditions: list[str]
    expected_effect: str
    verification_method: str
    executable: bool = True
    mutates_external_state: bool = False

    @property
    def requires_approval(self) -> bool:
        return self.risk_level in APPROVAL_REQUIRED_RISKS


ACTIONS: dict[str, RemediationAction] = {
    "RERUN_WORKFLOW": RemediationAction(
        action_id="RERUN_WORKFLOW",
        title="Re-run the failed GitHub Actions workflow",
        description=(
            "Request GitHub to re-run the existing workflow run. Useful for transient "
            "failures (flaky tests, network errors, rate limits)."
        ),
        risk_level=RiskLevel.MEDIUM.value,
        required_permissions=["github_token", "actions:write"],
        params=[ParamSpec(name="run_id", type="int", required=True)],
        preconditions=[
            "A Github token with actions:write is configured.",
            "The workflow run exists and is in a completed state.",
        ],
        expected_effect="GitHub schedules a new attempt of the same workflow run.",
        verification_method=(
            "Re-fetch the run and confirm its status becomes queued/in_progress "
            "and that a new attempt is registered."
        ),
        executable=True,
        mutates_external_state=True,
    ),
    "RECOMMEND_DEPENDENCY_FIX": RemediationAction(
        action_id="RECOMMEND_DEPENDENCY_FIX",
        title="Recommend a dependency correction",
        description=(
            "Produce a reviewable recommendation to add/update an npm dependency "
            "(for example via a pull request). Does not modify code automatically."
        ),
        risk_level=RiskLevel.LOW.value,
        required_permissions=[],
        params=[
            ParamSpec(name="package", type="str", required=True, max_length=200),
            ParamSpec(name="manifest", type="str", required=False, max_length=200),
            ParamSpec(name="reason", type="str", required=False, max_length=500),
        ],
        preconditions=["The failure was classified as a missing/invalid dependency."],
        expected_effect="A human-reviewable dependency change recommendation is recorded.",
        verification_method="A subsequent workflow run succeeds after the change is applied.",
        executable=True,
        mutates_external_state=False,
    ),
    "RECOMMEND_CONFIG_FIX": RemediationAction(
        action_id="RECOMMEND_CONFIG_FIX",
        title="Recommend a configuration correction",
        description="Produce a reviewable recommendation to correct a configuration value.",
        risk_level=RiskLevel.LOW.value,
        required_permissions=[],
        params=[
            ParamSpec(name="config_file", type="str", required=True, max_length=300),
            ParamSpec(name="detail", type="str", required=True, max_length=1000),
        ],
        preconditions=["The failure was classified as a configuration error."],
        expected_effect="A human-reviewable configuration change recommendation is recorded.",
        verification_method="A subsequent workflow run succeeds after the change is applied.",
        executable=True,
        mutates_external_state=False,
    ),
    "RECOMMEND_ENV_VAR_FIX": RemediationAction(
        action_id="RECOMMEND_ENV_VAR_FIX",
        title="Recommend an environment variable / secret fix",
        description=(
            "Produce a recommendation to define a missing environment variable or "
            "repository secret."
        ),
        risk_level=RiskLevel.LOW.value,
        required_permissions=[],
        params=[
            ParamSpec(name="variable_name", type="str", required=True, max_length=200),
            ParamSpec(name="scope", type="str", required=False, max_length=200),
        ],
        preconditions=["The failure was classified as a missing environment variable."],
        expected_effect="A human-reviewable environment/secret recommendation is recorded.",
        verification_method="A subsequent workflow run succeeds after the variable is defined.",
        executable=True,
        mutates_external_state=False,
    ),
}


def get_action(action_id: str) -> RemediationAction:
    action = ACTIONS.get(action_id)
    if action is None:
        raise UnsupportedActionError(
            f"Unknown remediation action '{action_id}'. Supported actions: {sorted(ACTIONS)}"
        )
    return action


def validate_parameters(action: RemediationAction, parameters: dict[str, Any]) -> dict[str, Any]:
    """Validate parameters against the action schema and return a cleaned copy.

    Rejects unknown keys, missing required keys, wrong types and over-long values.
    """
    if parameters is None:
        parameters = {}
    if not isinstance(parameters, dict):
        raise UnsupportedActionError("Parameters must be an object.")

    allowed = {p.name: p for p in action.params}
    unknown = set(parameters) - set(allowed)
    if unknown:
        raise UnsupportedActionError(f"Unsupported parameter(s): {sorted(unknown)}")

    cleaned: dict[str, Any] = {}
    for spec in action.params:
        if spec.name not in parameters or parameters[spec.name] in (None, ""):
            if spec.required:
                raise UnsupportedActionError(f"Missing required parameter '{spec.name}'.")
            continue
        value = parameters[spec.name]
        if spec.type == "int":
            try:
                value = int(value)
            except (TypeError, ValueError) as exc:
                raise UnsupportedActionError(
                    f"Parameter '{spec.name}' must be an integer."
                ) from exc
        else:
            value = str(value)
            if spec.max_length and len(value) > spec.max_length:
                raise UnsupportedActionError(f"Parameter '{spec.name}' is too long.")
        cleaned[spec.name] = value
    return cleaned


def build_plan_for_category(category: str, *, run_id: int | None = None) -> dict[str, Any] | None:
    """Deterministically map a failure category to a default remediation plan.

    Returns a dict with action_id/parameters/title, or None when no automated or
    recommendation action is available.
    """
    if category in {"k8s_oomkilled", "k8s_crashloopbackoff", "container_failure"}:
        # These require human infrastructure changes; recommend a config correction.
        return {
            "action_id": "RECOMMEND_CONFIG_FIX",
            "title": "Recommend infrastructure/container configuration review",
            "parameters": {
                "config_file": "deployment manifest / Dockerfile",
                "detail": "Increase memory limits or fix container startup configuration.",
            },
        }
    if category == "missing_npm_dependencies":
        return {
            "action_id": "RECOMMEND_DEPENDENCY_FIX",
            "title": "Recommend adding the missing npm dependency",
            "parameters": {
                "package": "missing-package",
                "manifest": "package.json",
                "reason": "npm could not resolve a required module.",
            },
        }
    if category == "missing_env_var":
        return {
            "action_id": "RECOMMEND_ENV_VAR_FIX",
            "title": "Recommend defining a missing environment variable/secret",
            "parameters": {"variable_name": "UNKNOWN", "scope": "workflow or repository secret"},
        }
    if category in {"configuration_error", "build_failure", "typescript_error"}:
        return {
            "action_id": "RECOMMEND_CONFIG_FIX",
            "title": "Recommend correcting the failing configuration/build step",
            "parameters": {
                "config_file": "build configuration",
                "detail": "Review the failing build/configuration step and correct it.",
            },
        }
    if category in {"test_failure", "authentication_failure", "docker_build_failure"} and (
        run_id is not None
    ):
        if category == "test_failure":
            return {
                "action_id": "RERUN_WORKFLOW",
                "title": "Re-run the workflow (possible transient/flaky failure)",
                "parameters": {"run_id": run_id},
            }
    return None


def compute_plan_hash(action_id: str, parameters: dict[str, Any], risk_level: str) -> str:
    payload = json.dumps(
        {"action_id": action_id, "parameters": parameters, "risk_level": risk_level},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
