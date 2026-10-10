import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Github, Plus, RefreshCw, Trash2 } from "lucide-react";
import { api, ApiError } from "@/api/client";
import {
  Button,
  Card,
  CardHeader,
  EmptyState,
  ErrorState,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { useToast } from "@/components/Toast";
import { formatRelative } from "@/lib/format";

const GITHUB_URL_RE = /^https:\/\/github\.com\/[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})\/[A-Za-z0-9_.-]{1,100}(?:\.git)?\/?$/;

export function RepositoriesPage() {
  const queryClient = useQueryClient();
  const { notify } = useToast();
  const [url, setUrl] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<{ id: number; name: string } | null>(null);

  const repositories = useQuery({ queryKey: ["repositories"], queryFn: () => api.listRepositories() });

  const createMutation = useMutation({
    mutationFn: (repoUrl: string) => api.createRepository(repoUrl),
    onSuccess: (repo) => {
      notify(`Repository ${repo.full_name} connected.`, "success");
      setUrl("");
      queryClient.invalidateQueries({ queryKey: ["repositories"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => notify((error as ApiError).message, "error"),
  });

  const syncMutation = useMutation({
    mutationFn: (id: number) => api.syncRepository(id),
    onSuccess: (result) => {
      notify(
        `Synced ${result.runs_fetched} runs (${result.incidents_created} new incidents).`,
        "success",
      );
      queryClient.invalidateQueries({ queryKey: ["repositories"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => notify((error as ApiError).message, "error"),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: number) => api.deleteRepository(id),
    onSuccess: () => {
      notify("Repository removed.", "success");
      setDeleteTarget(null);
      queryClient.invalidateQueries({ queryKey: ["repositories"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => notify((error as ApiError).message, "error"),
  });

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const trimmed = url.trim();
    if (!trimmed) {
      setValidationError("Repository URL is required.");
      return;
    }
    if (!GITHUB_URL_RE.test(trimmed)) {
      setValidationError("Enter a valid URL of the form https://github.com/OWNER/REPOSITORY");
      return;
    }
    setValidationError(null);
    createMutation.mutate(trimmed);
  }

  return (
    <div>
      <PageHeader
        title="Connected Repositories"
        subtitle="Track GitHub repositories, synchronize workflow runs and detect failures."
      />

      <Card className="mb-6">
        <CardHeader title="Connect a repository" subtitle="Only canonical GitHub HTTPS URLs are accepted." />
        <form onSubmit={handleSubmit} className="flex flex-col gap-3 p-5 sm:flex-row sm:items-start">
          <div className="flex-1">
            <label htmlFor="repo-url" className="sr-only">
              Repository URL
            </label>
            <input
              id="repo-url"
              type="text"
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                if (validationError) setValidationError(null);
              }}
              placeholder="https://github.com/owner/repository"
              aria-invalid={Boolean(validationError)}
              aria-describedby={validationError ? "repo-url-error" : undefined}
              className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-100"
            />
            {validationError && (
              <p id="repo-url-error" role="alert" className="mt-1.5 text-xs text-rose-600">
                {validationError}
              </p>
            )}
          </div>
          <Button type="submit" loading={createMutation.isPending}>
            <Plus className="h-4 w-4" /> Connect
          </Button>
        </form>
      </Card>

      <Card>
        <CardHeader title="Tracked repositories" subtitle={`${repositories.data?.total ?? 0} total`} />
        {repositories.isLoading ? (
          <Spinner />
        ) : repositories.isError ? (
          <ErrorState message={(repositories.error as Error).message} onRetry={() => repositories.refetch()} />
        ) : repositories.data!.items.length === 0 ? (
          <EmptyState
            title="No repositories yet"
            description="Connect your first repository using the form above."
            action={<Github className="h-5 w-5 text-slate-300" />}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="border-b border-slate-100 text-left text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-5 py-3 font-medium">Repository</th>
                  <th className="px-5 py-3 font-medium">Default branch</th>
                  <th className="px-5 py-3 font-medium">Last synced</th>
                  <th className="px-5 py-3 font-medium">Sync status</th>
                  <th className="px-5 py-3 text-right font-medium">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {repositories.data!.items.map((repo) => (
                  <tr key={repo.id} className="hover:bg-slate-50">
                    <td className="px-5 py-3">
                      <Link to={`/repositories/${repo.id}`} className="font-medium text-brand-700 hover:underline">
                        {repo.full_name}
                      </Link>
                      {repo.description && (
                        <p className="mt-0.5 max-w-md truncate text-xs text-slate-500">{repo.description}</p>
                      )}
                    </td>
                    <td className="px-5 py-3 text-slate-600">{repo.default_branch}</td>
                    <td className="px-5 py-3 text-slate-500">{formatRelative(repo.last_synced_at)}</td>
                    <td className="px-5 py-3">
                      {repo.last_sync_error ? (
                        <span className="text-xs text-rose-600" title={repo.last_sync_error}>
                          Error
                        </span>
                      ) : (
                        <span className="text-xs text-emerald-600">OK</span>
                      )}
                    </td>
                    <td className="px-5 py-3">
                      <div className="flex justify-end gap-2">
                        <Button
                          variant="secondary"
                          className="px-2.5 py-1.5"
                          onClick={() => syncMutation.mutate(repo.id)}
                          loading={syncMutation.isPending && syncMutation.variables === repo.id}
                        >
                          <RefreshCw className="h-3.5 w-3.5" /> Sync
                        </Button>
                        <Button
                          variant="ghost"
                          className="px-2.5 py-1.5 text-rose-600 hover:bg-rose-50"
                          onClick={() => setDeleteTarget({ id: repo.id, name: repo.full_name })}
                          aria-label={`Delete ${repo.full_name}`}
                        >
                          <Trash2 className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Remove repository"
        description={
          <>
            Remove <strong>{deleteTarget?.name}</strong> and all of its stored workflow runs and
            incidents? This does not affect GitHub itself.
          </>
        }
        confirmLabel="Remove"
        tone="danger"
        loading={deleteMutation.isPending}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
