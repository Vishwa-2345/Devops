"""GitHub REST API client.

Thin, testable wrapper around httpx. Tests inject an ``httpx.Client`` backed by
``httpx.MockTransport`` so no real network or credentials are required.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from app.config import get_settings
from app.security import sanitize_log

logger = logging.getLogger(__name__)


class GitHubError(Exception):
    """Base error for GitHub integration failures."""

    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        rate_limited: bool = False,
        reset_at: int | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.rate_limited = rate_limited
        self.reset_at = reset_at


@dataclass
class FailureLogs:
    text: str
    available: bool
    note: str = ""


class GitHubClient:
    def __init__(
        self,
        token: str | None = None,
        base_url: str | None = None,
        timeout: float | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        settings = get_settings()
        self.token = token if token is not None else settings.github_token
        self.base_url = (base_url or settings.github_api_base_url).rstrip("/")
        self.timeout = timeout or settings.github_request_timeout
        self._owns_client = client is None
        self._client = client or httpx.Client(
            base_url=self.base_url,
            timeout=self.timeout,
            follow_redirects=True,
        )

    # -- internals --------------------------------------------------------- #
    @property
    def configured(self) -> bool:
        return bool(self.token and self.token.strip())

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "SelfHealOps/0.1",
        }
        if self.configured:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(
        self, method: str, path: str, params: dict | None = None, **kwargs
    ) -> httpx.Response:
        url = path if path.startswith("http") else f"{self.base_url}{path}"
        try:
            response = self._client.request(
                method, url, headers=self._headers(), params=params, **kwargs
            )
        except httpx.TimeoutException as exc:
            raise GitHubError(f"GitHub request timed out: {exc}") from exc
        except httpx.HTTPError as exc:
            raise GitHubError(f"GitHub request failed: {exc}") from exc

        if response.status_code == 404:
            raise GitHubError(
                "Repository, workflow run or resource not found, or not accessible "
                "with the current credentials.",
                status_code=404,
            )
        if response.status_code in (403, 429):
            remaining = response.headers.get("x-ratelimit-remaining")
            reset = response.headers.get("x-ratelimit-reset")
            if remaining == "0" or response.status_code == 429:
                raise GitHubError(
                    "GitHub API rate limit exceeded. Configure GITHUB_TOKEN to raise limits.",
                    status_code=response.status_code,
                    rate_limited=True,
                    reset_at=int(reset) if reset and reset.isdigit() else None,
                )
            raise GitHubError(
                "GitHub denied the request (insufficient permissions).",
                status_code=response.status_code,
            )
        if response.status_code == 401:
            raise GitHubError("GitHub authentication failed (invalid token).", status_code=401)
        if response.status_code >= 500:
            raise GitHubError(
                f"GitHub server error ({response.status_code}).", status_code=response.status_code
            )
        if response.status_code >= 400:
            raise GitHubError(
                f"GitHub request failed with status {response.status_code}.",
                status_code=response.status_code,
            )
        return response

    def _get_json(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params).json()

    # -- public API -------------------------------------------------------- #
    def get_repository(self, owner: str, repo: str) -> dict:
        return self._get_json(f"/repos/{owner}/{repo}")

    def list_workflow_runs(
        self, owner: str, repo: str, per_page: int | None = None, max_pages: int | None = None
    ) -> list[dict]:
        settings = get_settings()
        per_page = per_page or settings.github_per_page
        max_pages = max_pages or settings.github_max_pages
        runs: list[dict] = []
        for page in range(1, max_pages + 1):
            payload = self._get_json(
                f"/repos/{owner}/{repo}/actions/runs",
                params={"per_page": per_page, "page": page},
            )
            batch = payload.get("workflow_runs", [])
            runs.extend(batch)
            if len(batch) < per_page:
                break
        return runs

    def get_workflow_run(self, owner: str, repo: str, run_id: int) -> dict:
        return self._get_json(f"/repos/{owner}/{repo}/actions/runs/{run_id}")

    def list_run_jobs(self, owner: str, repo: str, run_id: int) -> list[dict]:
        payload = self._get_json(f"/repos/{owner}/{repo}/actions/runs/{run_id}/jobs")
        return payload.get("jobs", [])

    def get_job_logs(self, owner: str, repo: str, job_id: int) -> str:
        response = self._request("GET", f"/repos/{owner}/{repo}/actions/jobs/{job_id}/logs")
        # Large logs may redirect to a zip/text blob; response text is best-effort.
        return response.text or ""

    def collect_failure_logs(self, owner: str, repo: str, run_id: int) -> FailureLogs:
        """Best-effort retrieval of failure logs for a workflow run."""
        try:
            jobs = self.list_run_jobs(owner, repo, run_id)
        except GitHubError as exc:
            return FailureLogs(text="", available=False, note=f"Could not list jobs: {exc.message}")

        failed_jobs = [
            j for j in jobs if j.get("conclusion") in {"failure", "timed_out", "cancelled"}
        ]
        if not failed_jobs:
            return FailureLogs(
                text="", available=False, note="No failed jobs found to retrieve logs for."
            )

        chunks: list[str] = []
        got_any = False
        for job in failed_jobs[:5]:
            job_id = job.get("id")
            if not job_id:
                continue
            try:
                text = self.get_job_logs(owner, repo, int(job_id))
            except GitHubError as exc:
                chunks.append(f"[job {job.get('name')}] log unavailable: {exc.message}")
                continue
            if text:
                got_any = True
                chunks.append(f"===== job: {job.get('name')} =====\n{text}")

        note = "" if got_any else "Logs require a token with actions:read for this repository."
        combined = sanitize_log("\n".join(chunks))
        return FailureLogs(text=combined, available=got_any, note=note)

    def rerun_workflow(self, owner: str, repo: str, run_id: int) -> dict:
        response = self._request("POST", f"/repos/{owner}/{repo}/actions/runs/{run_id}/rerun")
        # 201 Created; empty body.
        return {"status_code": response.status_code}

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> GitHubClient:
        return self

    def __exit__(self, *exc) -> None:
        self.close()
