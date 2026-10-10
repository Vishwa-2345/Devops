import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { AlertOctagon } from "lucide-react";
import { api } from "@/api/client";
import { Card, CardHeader, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";
import { formatRelative } from "@/lib/format";

const STATUS_OPTIONS = [
  "open",
  "diagnosed",
  "awaiting_approval",
  "resolved",
  "failed",
];

export function IncidentsPage() {
  const [status, setStatus] = useState("");
  const incidents = useQuery({
    queryKey: ["incidents", status],
    queryFn: () => api.listIncidents({ status: status || undefined }),
  });

  return (
    <div>
      <PageHeader
        title="Incidents"
        subtitle="Failures detected from failed workflow runs, ready for diagnosis and remediation."
        action={
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
            aria-label="Filter by status"
          >
            <option value="">All statuses</option>
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        }
      />

      <Card>
        <CardHeader title="Detected incidents" subtitle={`${incidents.data?.total ?? 0} total`} />
        {incidents.isLoading ? (
          <Spinner />
        ) : incidents.isError ? (
          <ErrorState message={(incidents.error as Error).message} onRetry={() => incidents.refetch()} />
        ) : incidents.data!.items.length === 0 ? (
          <EmptyState
            title="No incidents"
            description="When a workflow run fails, an incident is created automatically after synchronization."
            action={<AlertOctagon className="h-5 w-5 text-slate-300" />}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-5 py-3 font-medium">Incident</th>
                  <th className="px-5 py-3 font-medium">Category</th>
                  <th className="px-5 py-3 font-medium">Severity</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Detected</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {incidents.data!.items.map((incident) => (
                  <tr key={incident.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <Link to={`/incidents/${incident.id}`} className="font-medium text-brand-700 hover:underline">
                        {incident.title}
                      </Link>
                    </td>
                    <td className="px-5 py-3 text-slate-600">{incident.failure_category}</td>
                    <td className="px-5 py-3">
                      <StatusBadge value={incident.severity} kind="risk" />
                    </td>
                    <td className="px-5 py-3">
                      <StatusBadge value={incident.status} kind="incident" />
                    </td>
                    <td className="px-5 py-3 text-slate-500">{formatRelative(incident.detected_at)}</td>
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
