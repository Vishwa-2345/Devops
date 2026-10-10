import { Badge } from "./ui";

type Tone = "slate" | "blue" | "green" | "red" | "amber" | "gray";

const CONCLUSION_TONES: Record<string, Tone> = {
  success: "green",
  failure: "red",
  cancelled: "gray",
  timed_out: "amber",
  startup_failure: "red",
  neutral: "slate",
  skipped: "gray",
  queued: "blue",
  in_progress: "blue",
  completed: "slate",
};

const INCIDENT_TONES: Record<string, Tone> = {
  open: "red",
  diagnosing: "amber",
  diagnosed: "amber",
  planned: "blue",
  awaiting_approval: "amber",
  approved: "blue",
  executing: "blue",
  verifying: "blue",
  resolved: "green",
  failed: "red",
};

const RISK_TONES: Record<string, Tone> = {
  low: "green",
  medium: "amber",
  high: "red",
  critical: "red",
};

const PLAN_TONES: Record<string, Tone> = {
  proposed: "blue",
  awaiting_approval: "amber",
  approved: "blue",
  rejected: "gray",
  executing: "blue",
  executed: "green",
  failed: "red",
  invalidated: "gray",
};

const EXECUTION_TONES: Record<string, Tone> = {
  running: "blue",
  succeeded: "green",
  failed: "red",
  skipped: "gray",
};

const VERIFICATION_TONES: Record<string, Tone> = {
  pending: "amber",
  verified: "green",
  unverified: "gray",
};

const INTEGRATION_TONES: Record<string, Tone> = {
  connected: "green",
  available: "green",
  healthy: "green",
  unconfigured: "amber",
  "rules-fallback": "blue",
  unreachable: "red",
};

function labelize(value: string | null | undefined): string {
  if (!value) return "unknown";
  return value.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function StatusBadge({ value, kind = "conclusion" }: { value: string | null; kind?: keyof typeof MAPS }) {
  const map = MAPS[kind];
  const tone = (value && map[value]) || "slate";
  return <Badge tone={tone}>{labelize(value)}</Badge>;
}

const MAPS = {
  conclusion: CONCLUSION_TONES,
  incident: INCIDENT_TONES,
  risk: RISK_TONES,
  plan: PLAN_TONES,
  execution: EXECUTION_TONES,
  verification: VERIFICATION_TONES,
  integration: INTEGRATION_TONES,
};
