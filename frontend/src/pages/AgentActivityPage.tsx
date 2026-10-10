import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { Cpu } from "lucide-react";
import { api } from "@/api/client";
import { Card, CardHeader, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { formatDateTime } from "@/lib/format";

const AGENTS = ["monitoring", "diagnosis", "planning", "risk_evaluation", "approval_gate", "remediation", "verification"];

export function AgentActivityPage() {
  const [agent, setAgent] = useState("");
  const activity = useQuery({
    queryKey: ["agent-activity", agent],
    queryFn: () => api.agentActivity({ agent: agent || undefined, limit: 100 }),
  });

  return (
    <div>
      <PageHeader
        title="Agent Activity"
        subtitle="Chronological event log emitted by each agent in the self-healing workflow."
        action={
          <select
            value={agent}
            onChange={(e) => setAgent(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
            aria-label="Filter by agent"
          >
            <option value="">All agents</option>
            {AGENTS.map((a) => (
              <option key={a} value={a}>
                {a.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        }
      />

      <Card>
        <CardHeader title="Event stream" subtitle={`${activity.data?.total ?? 0} events`} />
        {activity.isLoading ? (
          <Spinner />
        ) : activity.isError ? (
          <ErrorState message={(activity.error as Error).message} onRetry={() => activity.refetch()} />
        ) : activity.data!.items.length === 0 ? (
          <EmptyState
            title="No agent activity"
            description="Agent events are recorded when incidents are analyzed or remediated."
            action={<Cpu className="h-5 w-5 text-slate-300" />}
          />
        ) : (
          <ol className="divide-y divide-slate-100">
            {activity.data!.items.map((event) => (
              <li key={event.id} className="flex items-start gap-4 px-5 py-3">
                <span className="mt-1 inline-flex shrink-0 rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wide text-brand-700">
                  {event.agent}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-800">{event.message}</p>
                  <p className="mt-0.5 text-xs text-slate-400">
                    {event.event_type} · {formatDateTime(event.created_at)}
                    {event.incident_id && (
                      <>
                        {" · "}
                        <Link to={`/incidents/${event.incident_id}`} className="text-brand-600 hover:underline">
                          incident #{event.incident_id}
                        </Link>
                      </>
                    )}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  );
}
