import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { api } from "@/api/client";
import { Card, CardHeader, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDateTime, shortSha } from "@/lib/format";

export function WorkflowsPage() {
  const [onlyFailed, setOnlyFailed] = useState(false);
  const workflows = useQuery({
    queryKey: ["workflows", onlyFailed],
    queryFn: () => api.listWorkflows(undefined, onlyFailed),
  });

  return (
    <div>
      <PageHeader
        title="Workflow Runs"
        subtitle="All synchronized GitHub Actions workflow runs across tracked repositories."
        action={
          <label className="inline-flex items-center gap-2 text-sm text-slate-600">
            <input
              type="checkbox"
              checked={onlyFailed}
              onChange={(e) => setOnlyFailed(e.target.checked)}
              className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
            />
            Show failed only
          </label>
        }
      />

      <Card>
        <CardHeader title="Workflow runs" subtitle={`${workflows.data?.total ?? 0} total`} />
        {workflows.isLoading ? (
          <Spinner />
        ) : workflows.isError ? (
          <ErrorState message={(workflows.error as Error).message} onRetry={() => workflows.refetch()} />
        ) : workflows.data!.items.length === 0 ? (
          <EmptyState
            title={onlyFailed ? "No failed runs" : "No workflow runs"}
            description="Synchronize a repository to retrieve workflow runs."
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[860px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-5 py-3 font-medium">Workflow</th>
                  <th className="px-5 py-3 font-medium">Branch</th>
                  <th className="px-5 py-3 font-medium">Commit</th>
                  <th className="px-5 py-3 font-medium">Event</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Started</th>
                  <th className="px-5 py-3 font-medium" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {workflows.data!.items.map((run) => (
                  <tr key={run.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3 font-medium text-slate-800">
                      {run.workflow_name}
                      <span className="ml-2 text-xs text-slate-400">#{run.run_number ?? "?"}</span>
                    </td>
                    <td className="px-5 py-3 text-slate-600">{run.head_branch ?? "—"}</td>
                    <td className="px-5 py-3 font-mono text-xs text-slate-500">{shortSha(run.head_sha)}</td>
                    <td className="px-5 py-3 text-slate-600">{run.event ?? "—"}</td>
                    <td className="px-5 py-3">
                      <StatusBadge value={run.conclusion ?? run.status} />
                    </td>
                    <td className="px-5 py-3 text-slate-500">{formatDateTime(run.started_at)}</td>
                    <td className="px-5 py-3 text-right">
                      {run.html_url && (
                        <a
                          href={run.html_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex items-center gap-1 text-xs text-brand-600 hover:underline"
                        >
                          GitHub <ExternalLink className="h-3 w-3" />
                        </a>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}
