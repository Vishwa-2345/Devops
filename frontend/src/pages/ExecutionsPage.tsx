import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { api } from "@/api/client";
import { Card, CardHeader, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDateTime } from "@/lib/format";

export function ExecutionsPage() {
  const [status, setStatus] = useState("");
  const executions = useQuery({
    queryKey: ["executions", status],
    queryFn: () => api.listExecutions({ status: status || undefined, limit: 100 }),
  });

  return (
    <div>
      <PageHeader
        title="Executions"
        subtitle="Audited remediation executions with verification outcomes."
        action={
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
            aria-label="Filter executions"
          >
            <option value="">All statuses</option>
            <option value="succeeded">Succeeded</option>
            <option value="failed">Failed</option>
            <option value="running">Running</option>
          </select>
        }
      />

      <Card>
        <CardHeader title="Execution history" subtitle={`${executions.data?.total ?? 0} total`} />
        {executions.isLoading ? (
          <Spinner />
        ) : executions.isError ? (
          <ErrorState message={(executions.error as Error).message} onRetry={() => executions.refetch()} />
        ) : executions.data!.items.length === 0 ? (
          <EmptyState
            title="No executions yet"
            description="Executions appear here after an approved remediation plan is run."
            action={<Activity className="h-5 w-5 text-slate-300" />}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[880px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-5 py-3 font-medium">Execution</th>
                  <th className="px-5 py-3 font-medium">Action</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Verification</th>
                  <th className="px-5 py-3 font-medium">Actor</th>
                  <th className="px-5 py-3 font-medium">Started</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {executions.data!.items.map((execution) => (
                  <tr key={execution.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3 font-mono text-xs text-slate-500">#{execution.id}</td>
                    <td className="px-5 py-3 text-slate-700">{execution.action_id}</td>
                    <td className="px-5 py-3">
                      <StatusBadge value={execution.status} kind="execution" />
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge value={execution.verification_status} kind="verification" />
                    </td>
                    <td className="px-5 py-3 text-slate-600">{execution.actor}</td>
                    <td className="px-5 py-3 text-slate-500">{formatDateTime(execution.started_at)}</td>
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
