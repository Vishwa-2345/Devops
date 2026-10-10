import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckSquare, ShieldCheck, XCircle } from "lucide-react";
import { api, ApiError } from "@/api/client";
import { Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { formatDateTime } from "@/lib/format";

const STATUS_FILTER: Record<string, string | undefined> = {
  awaiting_approval: "awaiting_approval",
  approved: "approved",
  rejected: "rejected",
  "": undefined,
};

export function ApprovalsPage() {
  const [status, setStatus] = useState("awaiting_approval");
  const queryClient = useQueryClient();
  const { notify } = useToast();

  const plans = useQuery({
    queryKey: ["approvals", status],
    queryFn: () => api.listRemediations({ status: STATUS_FILTER[status], limit: 100 }),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["approvals"] });
    queryClient.invalidateQueries({ queryKey: ["remediations"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };

  const approve = useMutation({
    mutationFn: (planId: number) => api.approveRemediation(planId, "local-user"),
    onSuccess: () => {
      notify("Plan approved.", "success");
      invalidate();
    },
    onError: (error) => notify((error as ApiError).message, "error"),
  });

  const reject = useMutation({
    mutationFn: (planId: number) => api.rejectRemediation(planId, "local-user"),
    onSuccess: () => {
      notify("Plan rejected.", "info");
      invalidate();
    },
    onError: (error) => notify((error as ApiError).message, "error"),
  });

  const items = plans.data?.items ?? [];

  return (
    <div>
      <PageHeader
        title="Approvals"
        subtitle="Human-in-the-loop gate. High-risk remediations require an explicit decision."
        action={
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700"
            aria-label="Filter approvals"
          >
            <option value="awaiting_approval">Awaiting approval</option>
            <option value="approved">Approved</option>
            <option value="rejected">Rejected</option>
            <option value="">All</option>
          </select>
        }
      />

      <Card>
        <CardHeader title="Approval requests" subtitle={`${plans.data?.total ?? 0} total`} />
        {plans.isLoading ? (
          <Spinner />
        ) : plans.isError ? (
          <ErrorState message={(plans.error as Error).message} onRetry={() => plans.refetch()} />
        ) : items.length === 0 ? (
          <EmptyState
            title="Nothing awaiting approval"
            description="When the planning agent proposes a high-risk action, it will appear here."
            action={<CheckSquare className="h-5 w-5 text-slate-300" />}
          />
        ) : (
          <div className="divide-y divide-slate-100">
            {items.map((plan) => (
              <div key={plan.id} className="p-5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <Link
                        to={`/incidents/${plan.incident_id}`}
                        className="font-medium text-brand-700 hover:underline"
                      >
                        {plan.title}
                      </Link>
                      <StatusBadge value={plan.status} kind="plan" />
                      <StatusBadge value={plan.risk_level} kind="risk" />
                    </div>
                    <p className="mt-1 text-sm text-slate-600">{plan.description}</p>
                    <p className="mt-0.5 text-xs text-slate-400">
                      {plan.action_id} · incident #{plan.incident_id} · created {formatDateTime(plan.created_at)}
                    </p>
                  </div>
                  {plan.status === "awaiting_approval" && (
                    <div className="flex gap-2">
                      <Button
                        onClick={() => approve.mutate(plan.id)}
                        loading={approve.isPending && approve.variables === plan.id}
                      >
                        <ShieldCheck className="h-4 w-4" /> Approve
                      </Button>
                      <Button
                        variant="secondary"
                        onClick={() => reject.mutate(plan.id)}
                        loading={reject.isPending && reject.variables === plan.id}
                      >
                        <XCircle className="h-4 w-4" /> Reject
                      </Button>
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
