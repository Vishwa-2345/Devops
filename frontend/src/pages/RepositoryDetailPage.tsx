import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ExternalLink, RefreshCw } from "lucide-react";
import { api, ApiError } from "@/api/client";
import { Button, Card, CardHeader, EmptyState, ErrorState, PageHeader, Spinner } from "@/components/ui";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { formatDateTime, shortSha } from "@/lib/format";

export function RepositoryDetailPage() {
  const { id } = useParams();
  const repoId = Number(id);
  const queryClient = useQueryClient();
  const { notify } = useToast();

  const repository = useQuery({
    queryKey: ["repository", repoId],
    queryFn: () => api.getRepository(repoId),
    enabled: Number.isFinite(repoId),
  });
  const workflows = useQuery({
    queryKey: ["repository-workflows", repoId],
    queryFn: () => api.repositoryWorkflows(repoId),
    enabled: Number.isFinite(repoId),
  });
  const incidents = useQuery({
    queryKey: ["repository-incidents", repoId],
    queryFn: () => api.listIncidents({ repository_id: repoId, limit: 10 }),
    enabled: Number.isFinite(repoId),
  });

  const sync = useMutation({
    mutationFn: () => api.syncRepository(repoId),
    onSuccess: (result) => {
      notify(`Synced ${result.runs_fetched} runs (${result.incidents_created} new incidents).`, "success");
      queryClient.invalidateQueries({ queryKey: ["repository", repoId] });
      queryClient.invalidateQueries({ queryKey: ["repository-workflows", repoId] });
      queryClient.invalidateQueries({ queryKey: ["repository-incidents", repoId] });
    },
    onError: (error) => notify((error as ApiError).message, "error"),
  });

  if (repository.isLoading) return <Spinner label="Loading repository…" />;
  if (repository.isError)
    return <ErrorState message={(repository.error as Error).message} onRetry={() => repository.refetch()} />;

  const repo = repository.data!;

  return (
    <div>
      <Link to="/repositories" className="mb-4 inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-700">
        <ArrowLeft className="h-4 w-4" /> Back to repositories
      </Link>

      <PageHeader
        title={repo.full_name}
        subtitle={repo.description || "No description provided."}
        action={
          <div className="flex gap-2">
            <a href={repo.html_url} target="_blank" rel="noreferrer">
              <Button variant="secondary">
                <ExternalLink className="h-4 w-4" /> Open on GitHub
              </Button>
            </a>
            <Button onClick={() => sync.mutate()} loading={sync.isPending}>
              <RefreshCw className="h-4 w-4" /> Sync now
            </Button>
          </div>
        }
      />

      {repo.last_sync_error && (
        <div className="mb-6 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-700">
          Last sync error: {repo.last_sync_error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Card className="p-5">
          <p className="text-xs uppercase tracking-wide text-slate-500">Default branch</p>
          <p className="mt-1 text-lg font-semibold text-slate-800">{repo.default_branch}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs uppercase tracking-wide text-slate-500">Visibility</p>
          <p className="mt-1 text-lg font-semibold text-slate-800">{repo.private ? "Private" : "Public"}</p>
        </Card>
        <Card className="p-5">
          <p className="text-xs uppercase tracking-wide text-slate-500">Last synced</p>
          <p className="mt-1 text-sm font-medium text-slate-800">{formatDateTime(repo.last_synced_at)}</p>
        </Card>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Recent workflow runs" subtitle={`${workflows.data?.total ?? 0} stored`} />
          {workflows.isLoading ? (
            <Spinner />
          ) : workflows.data && workflows.data.items.length > 0 ? (
            <div className="max-h-96 overflow-auto">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-white">
                  <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-5 py-2 font-medium">Workflow</th>
                    <th className="px-5 py-2 font-medium">Commit</th>
                    <th className="px-5 py-2 font-medium">Conclusion</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {workflows.data.items.map((run) => (
                    <tr key={run.id} className="hover:bg-slate-50">
                      <td className="px-5 py-3">
                        {run.html_url ? (
                          <a href={run.html_url} target="_blank" rel="noreferrer" className="font-medium text-brand-700 hover:underline">
                            {run.workflow_name}
                          </a>
                        ) : (
                          <span className="font-medium text-slate-700">{run.workflow_name}</span>
                        )}
                        <p className="text-xs text-slate-400">
                          #{run.run_number ?? "?"} · {run.head_branch ?? "—"}
                        </p>
                      </td>
                      <td className="px-5 py-3 font-mono text-xs text-slate-500">
                        {shortSha(run.head_sha)}
                      </td>
                      <td className="px-5 py-3">
                        <StatusBadge value={run.conclusion ?? run.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No workflow runs" description="Run a sync to retrieve workflow runs." />
          )}
        </Card>

        <Card>
          <CardHeader title="Incidents for this repository" subtitle={`${incidents.data?.total ?? 0} total`} />
          {incidents.isLoading ? (
            <Spinner />
          ) : incidents.data && incidents.data.items.length > 0 ? (
            <div className="divide-y divide-slate-100">
              {incidents.data.items.map((incident) => (
                <Link
                  key={incident.id}
                  to={`/incidents/${incident.id}`}
                  className="flex items-center justify-between gap-3 px-5 py-3 hover:bg-slate-50"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-800">{incident.title}</p>
                    <p className="text-xs text-slate-500">{incident.failure_category}</p>
                  </div>
                  <StatusBadge value={incident.status} kind="incident" />
                </Link>
              ))}
            </div>
          ) : (
            <EmptyState title="No incidents" description="No failures have been detected for this repository." />
          )}
        </Card>
      </div>
    </div>
  );
}
