import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  CheckSquare,
  CircleCheck,
  Github,
  Plug,
  ShieldCheck,
  Workflow,
} from "lucide-react";
import {
  Bar,
  BarChart,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api } from "@/api/client";
import { Card, CardHeader, EmptyState, ErrorState, PageHeader, Spinner, StatCard } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";
import { formatRelative } from "@/lib/format";

const BAR_COLORS = ["#16a34a", "#e11d48", "#64748b", "#2563eb"];

export function OverviewPage() {
  const summary = useQuery({ queryKey: ["dashboard"], queryFn: api.dashboardSummary });

  if (summary.isLoading) return <Spinner label="Loading dashboard…" />;
  if (summary.isError)
    return (
      <ErrorState
        message={(summary.error as Error).message}
        onRetry={() => summary.refetch()}
      />
    );

  const data = summary.data!;
  const counts = data.counts;
  const hasData = counts.repositories > 0;

  return (
    <div>
      <PageHeader
        title="Overview"
        subtitle="Self-healing status across connected repositories and CI/CD workflows."
        action={
          !data.github_connected ? (
            <Link
              to="/settings"
              className="inline-flex items-center gap-2 rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-medium text-amber-800"
            >
              <Plug className="h-4 w-4" /> Configure GitHub
            </Link>
          ) : undefined
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <StatCard label="Connected Repositories" value={counts.repositories} icon={<Github className="h-5 w-5" />} tone="blue" />
        <StatCard label="Workflow Runs" value={counts.workflow_runs} icon={<Workflow className="h-5 w-5" />} tone="slate" />
        <StatCard label="Failed Runs" value={counts.failed_runs} icon={<AlertOctagon className="h-5 w-5" />} tone="red" />
        <StatCard label="Open Incidents" value={counts.open_incidents} icon={<AlertOctagon className="h-5 w-5" />} tone="amber" />
        <StatCard label="Pending Approvals" value={counts.pending_approvals} icon={<CheckSquare className="h-5 w-5" />} tone="amber" />
        <StatCard
          label="Successful Remediations"
          value={counts.successful_remediations}
          icon={<CircleCheck className="h-5 w-5" />}
          tone="green"
        />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader
            title="Workflow run outcomes"
            subtitle="Computed from synchronized GitHub Actions runs."
          />
          <div className="p-5">
            {data.workflow_stats.every((s) => s.total === 0) ? (
              <EmptyState
                title="No workflow runs yet"
                description="Connect a repository and synchronize it to populate statistics."
              />
            ) : (
              <div className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={data.workflow_stats}>
                    <XAxis dataKey="label" tick={{ fontSize: 12 }} stroke="#94a3b8" />
                    <YAxis allowDecimals={false} tick={{ fontSize: 12 }} stroke="#94a3b8" />
                    <Tooltip
                      contentStyle={{ borderRadius: 8, borderColor: "#e2e8f0", fontSize: 12 }}
                    />
                    <Bar dataKey="total" radius={[4, 4, 0, 0]}>
                      {data.workflow_stats.map((_entry, index) => (
                        <Cell key={index} fill={BAR_COLORS[index % BAR_COLORS.length]} />
                      ))}
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
        </Card>

        <Card>
          <CardHeader title="Integration status" subtitle="Live capability report." />
          <div className="space-y-4 p-5 text-sm">
            <div className="flex items-start gap-3">
              <Github className="mt-0.5 h-4 w-4 text-slate-500" />
              <div>
                <p className="font-medium text-slate-800">GitHub</p>
                <p className="text-slate-500">
                  {data.github_connected
                    ? "Token configured — private repos, logs and re-runs available."
                    : "No token — public repos only, logs/re-runs unavailable."}
                </p>
              </div>
            </div>
            <div className="flex items-start gap-3">
              <ShieldCheck className="mt-0.5 h-4 w-4 text-slate-500" />
              <div>
                <p className="font-medium text-slate-800">LLM provider</p>
                <p className="text-slate-500">
                  {data.llm_provider}
                  {data.llm_available ? " (available)" : " (deterministic rules fallback)"}
                </p>
              </div>
            </div>
          </div>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader
            title="Recent incidents"
            action={
              <Link to="/incidents" className="text-xs font-medium text-brand-600 hover:underline">
                View all
              </Link>
            }
          />
          {data.recent_incidents.length === 0 ? (
            <EmptyState title="No incidents detected" description="Failures will appear here after synchronization." />
          ) : (
            <div className="divide-y divide-slate-100">
              {data.recent_incidents.map((incident) => (
                <Link
                  key={incident.id}
                  to={`/incidents/${incident.id}`}
                  className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-slate-50"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-800">{incident.title}</p>
                    <p className="text-xs text-slate-500">
                      {incident.repository} · {formatRelative(incident.detected_at)}
                    </p>
                  </div>
                  <StatusBadge value={incident.status} kind="incident" />
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card>
          <CardHeader
            title="Recent agent activity"
            action={
              <Link to="/agents" className="text-xs font-medium text-brand-600 hover:underline">
                View all
              </Link>
            }
          />
          {data.recent_events.length === 0 ? (
            <EmptyState title="No agent activity yet" description="Analysis and remediation events will appear here." />
          ) : (
            <div className="max-h-80 divide-y divide-slate-100 overflow-auto">
              {data.recent_events.map((event) => (
                <div key={event.id} className="px-5 py-3">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs font-semibold uppercase tracking-wide text-brand-600">
                      {event.agent}
                    </span>
                    <span className="text-xs text-slate-400">{formatRelative(event.created_at)}</span>
                  </div>
                  <p className="mt-1 text-sm text-slate-700">{event.message}</p>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {!hasData && (
        <Card className="mt-6">
          <EmptyState
            title="No repositories connected yet"
            description="Add a GitHub repository to start monitoring workflow runs and detecting failures."
            action={
              <Link
                to="/repositories"
                className="inline-flex items-center gap-2 rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
              >
                <Github className="h-4 w-4" /> Connect a repository
              </Link>
            }
          />
        </Card>
      )}
    </div>
  );
}
