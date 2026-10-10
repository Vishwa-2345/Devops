import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IncidentDetailPage } from "@/pages/IncidentDetailPage";
import { mockFetch, renderWithProviders } from "./utils";
import { sampleIncidentDetail } from "./fixtures";
import type { IncidentDetail, RemediationPlan } from "@/types";

afterEach(() => {
  vi.unstubAllGlobals();
});

function detailWithPlan(status: RemediationPlan["status"]): IncidentDetail {
  const plan = { ...sampleIncidentDetail.remediation_plans[0], status };
  return { ...sampleIncidentDetail, status: sampleIncidentDetail.status, remediation_plans: [plan] };
}

describe("IncidentDetailPage", () => {
  it("renders the incident, diagnosis and remediation plan", async () => {
    mockFetch([
      { match: "/incidents/5", handler: () => ({ body: sampleIncidentDetail }) },
    ]);

    renderWithProviders(<IncidentDetailPage />, { route: "/incidents/5", path: "/incidents/:id" });

    expect(await screen.findByRole("heading", { name: "Build failed: npm install" })).toBeInTheDocument();
    expect(screen.getByText("Dependency installation failed.")).toBeInTheDocument();
    expect(screen.getByText("retry_workflow_run")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /approve/i })).toBeInTheDocument();
  });

  it("approves a plan through the API", async () => {
    const fetchMock = mockFetch([
      { match: "/incidents/5", handler: () => ({ body: sampleIncidentDetail }) },
      {
        match: "/remediations/10/approve",
        handler: () => ({
          body: {
            id: 1,
            remediation_plan_id: 10,
            decision: "approved",
            decided_by: "local-user",
            reason: null,
            plan_hash: "abc123",
            created_at: "2026-01-02T10:06:00Z",
          },
        }),
      },
    ]);
    const user = userEvent.setup();

    renderWithProviders(<IncidentDetailPage />, { route: "/incidents/5", path: "/incidents/:id" });
    await screen.findByRole("button", { name: /approve/i });

    await user.click(screen.getByRole("button", { name: /approve/i }));

    await waitFor(() => {
      const approveCall = fetchMock.mock.calls.find(([input]) =>
        input.toString().includes("/remediations/10/approve"),
      );
      expect(approveCall).toBeTruthy();
      expect((approveCall![1] as RequestInit).method).toBe("POST");
    });
  });

  it("confirms before executing an approved plan", async () => {
    const fetchMock = mockFetch([
      { match: "/incidents/5", handler: () => ({ body: detailWithPlan("approved") }) },
      {
        match: "/remediations/10/execute",
        handler: () => ({
          body: {
            id: 7,
            remediation_plan_id: 10,
            action_id: "retry_workflow_run",
            status: "succeeded",
            actor: "local-user",
            parameters: {},
            result: {},
            error: null,
            verification_status: "verified",
            verification_details: {},
            started_at: "2026-01-02T10:07:00Z",
            completed_at: "2026-01-02T10:08:00Z",
          },
        }),
      },
    ]);
    const user = userEvent.setup();

    renderWithProviders(<IncidentDetailPage />, { route: "/incidents/5", path: "/incidents/:id" });
    await user.click(await screen.findByRole("button", { name: /execute remediation/i }));

    expect(await screen.findByRole("dialog")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /^execute$/i }));

    await waitFor(() => {
      const execCall = fetchMock.mock.calls.find(([input]) =>
        input.toString().includes("/remediations/10/execute"),
      );
      expect(execCall).toBeTruthy();
    });
  });
});
