import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Play, ShieldCheck, Sparkles, XCircle } from "lucide-react";
import { api, ApiError } from "@/api/client";
import { Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useToast } from "@/components/Toast";
import { formatDateTime } from "@/lib/format";

export function IncidentDetailPage() {
  const { id } = useParams();
  const incidentId = Number(id);
  const queryClient = useQueryClient();
  const { notify } = useToast();
  const [confirm, setConfirm] = useState<{ planId: number; action: "execute" } | null>(null);

  const incident = useQuery({
    queryKey: ["incident", incidentId],
    queryFn: () => api.getIncident(incidentId),
    enabled: Number.isFinite(incidentId),
  });

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["incident", incidentId] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["approvals"] });
  };

  const analyze = useMutation({
    mutationFn: () => api.analyzeIncident(incidentId),
    onSuccess: () => {
      notify("Agent analysis complete.", "success");
      invalidate();
    },
    onError: (error) => notify((error as ApiError).message, "error"),
  });

  const plan = useMutation({
    mutationFn: () => api.planRemediation(incidentId),
    onSuccess: () => {
      notify("Remediation plan generated.", "success");
      invalidate();
    },
    onError: (error) => notify((error as ApiError).message, "error"),
  });

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

  const execute = useMutation({
    mutationFn: (planId: number) => api.executeRemediation(planId, "local-user"),
    onSuccess: (execution) => {
      setConfirm(null);
      notify(
        execution.status === "succeeded"
          ? `Execution succeeded — verification: ${execution.verification_status}.`
          : `Execution ${execution.status}.`,
        execution.status === "succeeded" ? "success" : "error",
      );
      invalidate();
      queryClient.invalidateQueries({ queryKey: ["executions"] });
    },
    onError: (error) => {
      setConfirm(null);
      notify((error as ApiError).message, "error");
    },
  });

  if (incident.isLoading) return <Spinner label="Loading incident…" />;
  if (incident.isError)
    return <ErrorState message={(incident.error as Error).message} onRetry={() => incident.refetch()} />;

  const data = incident.data!;
  const diagnosis = data.diagnoses[data.diagnoses.length - 1];
  const latestPlan = data.remediation_plans[data.remediation_plans.length - 1];

  return (
    <div>
      <Link to="/incidents" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700">
        <ArrowLeft className="h-4 w-4" /> Back to incidents
      </Link>

      <PageHeader
        title={data.title}
        subtitle={`${data.repository?.full_name ?? "Unknown repository"} · detected ${formatDateTime(data.detected_at)}`}
        action={
          <div className="flex gap-2">
            <Button variant="secondary" onClick={() => analyze.mutate()} loading={analyze.isPending}>
              <Sparkles className="h-4 w-4" /> Run analysis
            </Button>
            <Button variant="secondary" onClick={() => plan.mutate()} loading={plan.isPending}>
              <ShieldCheck className="h-4 w-4" /> Plan remediation
            </Button>
          </div>
        }
      />

      <div className="mb-6 flex flex-wrap items-center gap-3">
        <StatusBadge value={data.status} kind="incident" />
        <StatusBadge value={data.severity} kind="risk" />
        <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-medium text-slate-600">
          {data.failure_category}
        </span>
      </div>

      {data.workflow_run && (
        <Card className="mb-6">
          <CardHeader title="Failed workflow run" />
          <div className="grid grid-cols-1 gap-4 p-5 sm:grid-cols-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Workflow</p>
              <p className="mt-1 text-sm font-medium text-slate-800">{data.workflow_run.workflow_name}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Branch</p>
              <p className="mt-1 text-sm font-medium text-slate-800">{data.workflow_run.head_branch ?? "—"}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Conclusion</p>
              <div className="mt-1">
                <StatusBadge value={data.workflow_run.conclusion} />
              </div>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Link</p>
              {data.workflow_run.html_url ? (
                <a
                  href={data.workflow_run.html_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 inline-block text-sm text-brand-600 hover:underline"
                >
                  View on GitHub
                </a>
              ) : (
                <p className="mt-1 text-sm text-slate-500">—</p>
              )}
            </div>
          </div>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Diagnosis" subtitle={diagnosis ? `${diagnosis.provider} provider` : undefined} />
          {!diagnosis ? (
            <EmptyState
              title="No diagnosis yet"
              description="Run analysis to classify the failure and produce a diagnosis."
            />
          ) : (
            <div className="space-y-4 p-5 text-sm">
              <div className="flex items-center justify-between">
                <span className="rounded-full bg-brand-50 px-2.5 py-0.5 text-xs font-medium text-brand-700">
                  {diagnosis.category}
                </span>
                <span className="text-xs text-slate-500">
                  confidence {Math.round(diagnosis.confidence * 100)}%
                </span>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Summary</p>
                <p className="mt-1 text-slate-700">{diagnosis.summary}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Probable cause</p>
                <p className="mt-1 text-slate-700">{diagnosis.probable_cause}</p>
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Suggested next step</p>
                <p className="mt-1 text-slate-700">{diagnosis.suggested_next_step}</p>
              </div>
              {diagnosis.evidence && diagnosis.evidence.length > 0 && (
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Evidence</p>
                  <pre className="mt-1 max-h-48 overflow-auto rounded-lg bg-slate-900 p-3 text-xs text-slate-100">
                    {diagnosis.evidence.join("\n")}
                  </pre>
                </div>
              )}
            </div>
          )}
        </Card>

        <Card>
          <CardHeader title="Remediation plan" subtitle={latestPlan ? `risk: ${latestPlan.risk_level}` : undefined} />
          {!latestPlan ? (
            <EmptyState
              title="No remediation plan"
              description="Generate a plan after analysis to see proposed, allowlisted actions."
            />
          ) : (
            <div className="space-y-4 p-5 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge value={latestPlan.status} kind="plan" />
                <StatusBadge value={latestPlan.risk_level} kind="risk" />
                {latestPlan.requires_approval && (
                  <span className="rounded-full bg-amber-50 px-2.5 py-0.5 text-xs font-medium text-amber-700 ring-1 ring-inset ring-amber-200">
                    approval required
                  </span>
                )}
              </div>
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Action</p>
                <p className="mt-1 font-medium text-slate-800">{latestPlan.action_id}</p>
                <p className="text-slate-600">{latestPlan.title}</p>
              </div>
              {latestPlan.description && (
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Description</p>
                  <p className="mt-1 text-slate-700">{latestPlan.description}</p>
                </div>
              )}
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Parameters</p>
                <pre className="mt-1 overflow-auto rounded-lg bg-slate-100 p-3 text-xs text-slate-700">
                  {JSON.stringify(latestPlan.parameters, null, 2)}
                </pre>
              </div>
              {latestPlan.verification_method && (
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Verification method</p>
                  <p className="mt-1 text-slate-700">{latestPlan.verification_method}</p>
                </div>
              )}

              <div className="flex flex-wrap gap-2 border-t border-slate-100 pt-4">
                {latestPlan.status === "awaiting_approval" && (
                  <>
                    <Button onClick={() => approve.mutate(latestPlan.id)} loading={approve.isPending}>
                      <ShieldCheck className="h-4 w-4" /> Approve
                    </Button>
                    <Button variant="secondary" onClick={() => reject.mutate(latestPlan.id)} loading={reject.isPending}>
                      <XCircle className="h-4 w-4" /> Reject
                    </Button>
                  </>
                )}
                {(latestPlan.status === "approved" || latestPlan.status === "proposed") && (
                  <Button onClick={() => setConfirm({ planId: latestPlan.id, action: "execute" })}>
                    <Play className="h-4 w-4" /> Execute remediation
                  </Button>
                )}
              </div>
            </div>
          )}
        </Card>
      </div>

      <ConfirmDialog
        open={Boolean(confirm)}
        title="Execute remediation"
        description="This will run the allowlisted remediation action. Success is only reported after verification."
        confirmLabel="Execute"
        loading={execute.isPending}
        onConfirm={() => confirm && execute.mutate(confirm.planId)}
        onCancel={() => setConfirm(null)}
      />
    </div>
  );
}
