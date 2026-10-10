import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RepositoriesPage } from "@/pages/RepositoriesPage";
import { mockFetch, renderWithProviders } from "./utils";
import { sampleRepository } from "./fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

function listBody(items: unknown[]) {
  return { items, total: items.length, limit: 50, offset: 0 };
}

describe("RepositoriesPage", () => {
  it("lists connected repositories", async () => {
    mockFetch([{ match: "/repositories", handler: () => ({ body: listBody([sampleRepository]) }) }]);

    renderWithProviders(<RepositoriesPage />);

    expect(await screen.findByText("octocat/hello-world")).toBeInTheDocument();
    expect(screen.getByText("main")).toBeInTheDocument();
  });

  it("validates the repository URL before submitting", async () => {
    const fetchMock = mockFetch([
      { match: "/repositories", handler: () => ({ body: listBody([]) }) },
    ]);
    const user = userEvent.setup();

    renderWithProviders(<RepositoriesPage />);
    await screen.findByText(/no repositories yet/i);

    const input = screen.getByLabelText(/repository url/i);
    await user.type(input, "https://gitlab.com/foo/bar");
    await user.click(screen.getByRole("button", { name: /connect/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/valid url/i);
    const postCalls = fetchMock.mock.calls.filter(
      ([, init]) => (init as RequestInit | undefined)?.method === "POST",
    );
    expect(postCalls).toHaveLength(0);
  });

  it("submits a valid GitHub URL", async () => {
    const fetchMock = mockFetch([
      {
        match: "/repositories",
        handler: (init) => ({
          body: init?.method === "POST" ? sampleRepository : listBody([]),
        }),
      },
    ]);
    const user = userEvent.setup();

    renderWithProviders(<RepositoriesPage />);
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());

    await user.type(screen.getByLabelText(/repository url/i), "https://github.com/octocat/hello-world");
    await user.click(screen.getByRole("button", { name: /connect/i }));

    await waitFor(() => {
      const postCall = fetchMock.mock.calls.find(
        ([, init]) => (init as RequestInit | undefined)?.method === "POST",
      );
      expect(postCall).toBeTruthy();
      const body = JSON.parse((postCall![1] as RequestInit).body as string);
      expect(body.url).toBe("https://github.com/octocat/hello-world");
    });
  });
});
