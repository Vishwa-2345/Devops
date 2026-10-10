// Shared TypeScript types mirroring the backend API schemas.

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface Repository {
  id: number;
  owner: string;
  name: string;
  full_name: string;
  html_url: string;
  default_branch: string;
  description: string | null;
  private: boolean;
  github_repo_id: number | null;
  source: string;
  last_synced_at: string | null;
  last_sync_error: string | null;
  created_at: string;
}

export interface SyncResult {
  repository_id: number;
  runs_fetched: number;
  runs_created: number;
  runs_updated: number;
  incidents_created: number;
  incidents_updated: number;
  message: string;
}

export interface WorkflowRun {
  id: number;
  repository_id: number;
  github_run_id: number;
  workflow_name: string;
  run_number: number | null;
  event: string | null;
  head_branch: string | null;
  head_sha: string | null;
  status: string;
  conclusion: string | null;
  html_url: string | null;
  actor: string | null;
  started_at: string | null;
  completed_at: string | null;
}

export interface Diagnosis {
  id: number;
  incident_id: number;
  provider: string;
  model: string | null;
  category: string;
  summary: string;
  probable_cause: string | null;
  suggested_next_step: string | null;
  confidence: number;
  evidence: string[] | null;
  automatable: boolean;
  created_at: string;
}

export interface RemediationPlan {
  id: number;
  incident_id: number;
  action_id: string;
  title: string;
  description: string | null;
  parameters: Record<string, unknown>;
  risk_level: string;
  status: string;
  requires_approval: boolean;
  expected_effect: string | null;
  verification_method: string | null;
  plan_hash: string;
  created_at: string;
  updated_at: string;
}

export interface Approval {
  id: number;
  remediation_plan_id: number;
  decision: string;
  decided_by: string;
  reason: string | null;
  plan_hash: string;
  created_at: string;
}

export interface Execution {
  id: number;
  remediation_plan_id: number;
  action_id: string;
  status: string;
  actor: string;
  parameters: Record<string, unknown> | null;
  result: Record<string, unknown> | null;
  error: string | null;
  verification_status: string;
  verification_details: Record<string, unknown> | null;
  started_at: string;
  completed_at: string | null;
}

export interface AgentEvent {
  id: number;
  incident_id: number | null;
  run_id: string | null;
  agent: string;
  event_type: string;
  message: string;
  data: Record<string, unknown> | null;
  created_at: string;
}

export interface Incident {
  id: number;
  repository_id: number;
  workflow_run_id: number;
  title: string;
  failure_category: string;
  severity: string;
  status: string;
  summary: string | null;
  detected_at: string;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface IncidentDetail extends Incident {
  repository: Repository | null;
  workflow_run: WorkflowRun | null;
  diagnoses: Diagnosis[];
  remediation_plans: RemediationPlan[];
}

export interface DashboardCounts {
  repositories: number;
  workflow_runs: number;
  failed_runs: number;
  open_incidents: number;
  pending_approvals: number;
  successful_remediations: number;
}

export interface RecentIncident {
  id: number;
  title: string;
  failure_category: string;
  severity: string;
  status: string;
  repository: string;
  detected_at: string;
}

export interface SuccessStat {
  label: string;
  total: number;
}

export interface DashboardSummary {
  counts: DashboardCounts;
  recent_incidents: RecentIncident[];
  recent_events: AgentEvent[];
  workflow_stats: SuccessStat[];
  github_connected: boolean;
  llm_provider: string;
  llm_available: boolean;
}

export interface IntegrationStatus {
  name: string;
  configured: boolean;
  status: string;
  detail: string;
}

export interface SettingsStatus {
  app_version: string;
  environment: string;
  github: IntegrationStatus;
  llm: IntegrationStatus;
  polling_enabled: boolean;
  poll_interval_seconds: number;
  database: string;
  cors_origins: string[];
}
