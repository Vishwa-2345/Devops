// Typed API client for the SelfHealOps backend.
import type {
  AgentEvent,
  Approval,
  DashboardSummary,
  Execution,
  Incident,
  IncidentDetail,
  Page,
  RemediationPlan,
  Repository,
  SettingsStatus,
  SyncResult,
  WorkflowRun,
} from "@/types";

const BASE_URL: string = (import.meta.env.VITE_API_BASE_URL as string) || "/api/v1";

export class ApiError extends Error {
  status: number;
  code?: string;
  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch (err) {
    throw new ApiError(
      "Unable to reach the SelfHealOps backend. Is it running?",
      0,
      "network_error",
    );
  }

  const text = await response.text();
  const data = text ? safeJson(text) : null;

  if (!response.ok) {
    const obj = data as { detail?: unknown; code?: unknown } | null;
    const detail =
      (obj && obj.detail != null ? String(obj.detail) : "") ||
      `Request failed with status ${response.status}`;
    const code = obj && obj.code != null ? String(obj.code) : undefined;
    throw new ApiError(detail, response.status, code);
  }
  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const str = search.toString();
  return str ? `?${str}` : "";
}

export const api = {
  health: () => request<{ status: string; version: string }>("/health"),

  dashboardSummary: () => request<DashboardSummary>("/dashboard/summary"),

  settingsStatus: () => request<SettingsStatus>("/settings/status"),

  // Repositories
  listRepositories: (limit = 50, offset = 0) =>
    request<Page<Repository>>(`/repositories${qs({ limit, offset })}`),
  createRepository: (url: string) =>
    request<Repository>("/repositories", { method: "POST", body: JSON.stringify({ url }) }),
  getRepository: (id: number) => request<Repository>(`/repositories/${id}`),
  deleteRepository: (id: number) =>
    request<{ message: string }>(`/repositories/${id}`, { method: "DELETE" }),
  syncRepository: (id: number) =>
    request<SyncResult>(`/repositories/${id}/sync`, { method: "POST" }),
  repositoryWorkflows: (id: number, onlyFailed = false, limit = 50, offset = 0) =>
    request<Page<WorkflowRun>>(
      `/repositories/${id}/workflows${qs({ only_failed: onlyFailed, limit, offset })}`,
    ),

  // Workflows
  listWorkflows: (repositoryId?: number, onlyFailed = false, limit = 50, offset = 0) =>
    request<Page<WorkflowRun>>(
      `/workflows${qs({ repository_id: repositoryId, only_failed: onlyFailed, limit, offset })}`,
    ),

  // Incidents
  listIncidents: (params: { limit?: number; offset?: number; status?: string; repository_id?: number } = {}) =>
    request<Page<Incident>>(`/incidents${qs(params)}`),
  getIncident: (id: number) => request<IncidentDetail>(`/incidents/${id}`),
  analyzeIncident: (id: number) =>
    request<IncidentDetail>(`/incidents/${id}/analyze`, { method: "POST" }),
  planRemediation: (id: number) =>
    request<IncidentDetail>(`/incidents/${id}/plan-remediation`, { method: "POST" }),

  // Remediations
  listRemediations: (params: { limit?: number; offset?: number; status?: string } = {}) =>
    request<Page<RemediationPlan>>(`/remediations${qs(params)}`),
  getRemediation: (id: number) => request<RemediationPlan>(`/remediations/${id}`),
  approveRemediation: (id: number, decidedBy: string, reason?: string) =>
    request<Approval>(`/remediations/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ decided_by: decidedBy, reason }),
    }),
  rejectRemediation: (id: number, decidedBy: string, reason?: string) =>
    request<Approval>(`/remediations/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ decided_by: decidedBy, reason }),
    }),
  executeRemediation: (id: number, actor: string) =>
    request<Execution>(`/remediations/${id}/execute`, {
      method: "POST",
      body: JSON.stringify({ actor }),
    }),

  // Agents / executions
  agentActivity: (params: { limit?: number; offset?: number; agent?: string; incident_id?: number } = {}) =>
    request<Page<AgentEvent>>(`/agents/activity${qs(params)}`),
  listExecutions: (params: { limit?: number; offset?: number; status?: string } = {}) =>
    request<Page<Execution>>(`/executions${qs(params)}`),
};
