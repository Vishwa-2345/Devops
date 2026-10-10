import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import { OverviewPage } from "@/pages/OverviewPage";
import { mockFetch, renderWithProviders } from "./utils";
import { sampleDashboard } from "./fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("OverviewPage", () => {
  it("renders dashboard statistics from the API", async () => {
    mockFetch([{ match: "/dashboard/summary", handler: () => ({ body: sampleDashboard }) }]);

    renderWithProviders(<OverviewPage />);

    expect(await screen.findByText("Overview")).toBeInTheDocument();
    expect(await screen.findByText("Connected Repositories")).toBeInTheDocument();
    expect(screen.getByText("Successful Remediations")).toBeInTheDocument();
    expect(screen.getByText("Build failed: npm install")).toBeInTheDocument();
    expect(screen.getByText("Diagnosis produced with 72% confidence.")).toBeInTheDocument();
  });

  it("shows a spinner while the dashboard loads", () => {
    mockFetch([
      {
        match: "/dashboard/summary",
        handler: () => ({ body: sampleDashboard }),
      },
    ]);

    renderWithProviders(<OverviewPage />);
    expect(screen.getByText(/loading dashboard/i)).toBeInTheDocument();
  });

  it("renders an error state when the request fails", async () => {
    mockFetch([
      {
        match: "/dashboard/summary",
        handler: () => ({ status: 500, body: { detail: "Internal error" } }),
      },
    ]);

    renderWithProviders(<OverviewPage />);

    expect(await screen.findByRole("alert")).toHaveTextContent("Internal error");
    expect(screen.getByRole("button", { name: /retry/i })).toBeInTheDocument();
  });

  it("shows the GitHub call-to-action when not connected", async () => {
    mockFetch([{ match: "/dashboard/summary", handler: () => ({ body: sampleDashboard }) }]);

    renderWithProviders(<OverviewPage />);

    await waitFor(() =>
      expect(screen.getByText(/configure github/i)).toBeInTheDocument(),
    );
  });
});
