import { useQuery } from "@tanstack/react-query";
import { Database, Github, Heart, ShieldCheck, Timer } from "lucide-react";
import { api } from "@/api/client";
import { Card, CardHeader, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";

export function SettingsPage() {
  const status = useQuery({ queryKey: ["settings"], queryFn: api.settingsStatus });
  const health = useQuery({ queryKey: ["backend-health"], queryFn: api.health });

  if (status.isLoading) return <Spinner label="Loading settings…" />;
  if (status.isError)
    return <ErrorState message={(status.error as Error).message} onRetry={() => status.refetch()} />;

  const data = status.data!;

  return (
    <div>
      <PageHeader
        title="Settings"
        subtitle="Runtime configuration and integration status. Secrets are read from environment variables only."
      />

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader title="GitHub integration" />
          <div className="space-y-3 p-5 text-sm">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 font-medium text-slate-700">
                <Github className="h-4 w-4 text-slate-500" /> Connection
              </span>
              <StatusBadge value={data.github.status} kind="integration" />
            </div>
            <p className="text-slate-600">{data.github.detail}</p>
          </div>
        </Card>

        <Card>
          <CardHeader title="LLM provider" />
          <div className="space-y-3 p-5 text-sm">
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-2 font-medium text-slate-700">
                <ShieldCheck className="h-4 w-4 text-slate-500" /> Provider
              </span>
              <StatusBadge value={data.llm.status} kind="integration" />
            </div>
            <p className="text-slate-600">{data.llm.detail}</p>
          </div>
        </Card>

        <Card>
          <CardHeader title="Runtime" />
          <dl className="divide-y divide-slate-100 text-sm">
            <div className="flex items-center justify-between px-5 py-3">
              <dt className="flex items-center gap-2 text-slate-500">
                <Heart className="h-4 w-4" /> Application version
              </dt>
              <dd className="font-medium text-slate-800">{data.app_version}</dd>
            </div>
            <div className="flex items-center justify-between px-5 py-3">
              <dt className="text-slate-500">Environment</dt>
              <dd className="font-medium text-slate-800">{data.environment}</dd>
            </div>
            <div className="flex items-center justify-between px-5 py-3">
              <dt className="flex items-center gap-2 text-slate-500">
                <Database className="h-4 w-4" /> Storage
              </dt>
              <dd className="font-medium text-slate-800">{data.database}</dd>
            </div>
            <div className="flex items-center justify-between px-5 py-3">
              <dt className="flex items-center gap-2 text-slate-500">
                <Timer className="h-4 w-4" /> Polling
              </dt>
              <dd className="font-medium text-slate-800">
                {data.polling_enabled ? `every ${data.poll_interval_seconds}s` : "disabled"}
              </dd>
            </div>
            <div className="flex items-center justify-between px-5 py-3">
              <dt className="text-slate-500">Backend health</dt>
              <dd>
                {health.isLoading ? (
                  <span className="text-slate-400">checking…</span>
                ) : health.isError ? (
                  <StatusBadge value="unreachable" kind="integration" />
                ) : (
                  <StatusBadge value="healthy" kind="integration" />
                )}
              </dd>
            </div>
          </dl>
        </Card>

        <Card>
          <CardHeader title="Security posture" subtitle="How SelfHealOps stays safe by default." />
          <ul className="space-y-3 p-5 text-sm text-slate-600">
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
              Remediation runs only through an allowlist of predefined actions — no arbitrary shell commands.
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
              High-risk plans require explicit human approval, enforced server-side with plan-hash invalidation.
            </li>
            <li className="flex gap-2">
              <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />
              Secrets are redacted from logs and API responses; tokens are never persisted or returned.
            </li>
          </ul>
        </Card>
      </div>
    </div>
  );
}
