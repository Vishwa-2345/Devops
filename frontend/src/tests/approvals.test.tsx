import { afterEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ApprovalsPage } from "@/pages/ApprovalsPage";
import { mockFetch, renderWithProviders } from "./utils";
import { samplePlan } from "./fixtures";

afterEach(() => {
  vi.unstubAllGlobals();
});

function page(items: unknown[]) {
  return { items, total: items.length, limit: 100, offset: 0 };
}

describe("ApprovalsPage", () => {
  it("lists remediation plans awaiting approval", async () => {
    mockFetch([{ match: "/remediations", handler: () => ({ body: page([samplePlan]) }) }]);

    renderWithProviders(<ApprovalsPage />);

    expect(await screen.findByText("Retry the failed workflow run")).toBeInTheDocument();
    expect(screen.getByText("Awaiting Approval")).toBeInTheDocument();
  });

  it("shows an empty state when nothing awaits approval", async () => {
    mockFetch([{ match: "/remediations", handler: () => ({ body: page([]) }) }]);

    renderWithProviders(<ApprovalsPage />);

    expect(await screen.findByText(/nothing awaiting approval/i)).toBeInTheDocument();
  });

  it("approves a plan and posts the decision", async () => {
    const fetchMock = mockFetch([
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
      { match: "/remediations", handler: () => ({ body: page([samplePlan]) }) },
    ]);
    const user = userEvent.setup();

    renderWithProviders(<ApprovalsPage />);
    await user.click(await screen.findByRole("button", { name: /^approve$/i }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([input]) =>
        input.toString().includes("/remediations/10/approve"),
      );
      expect(call).toBeTruthy();
      const body = JSON.parse((call![1] as RequestInit).body as string);
      expect(body.decided_by).toBe("local-user");
    });
  });

  it("rejects a plan and posts the decision", async () => {
    const fetchMock = mockFetch([
      {
        match: "/remediations/10/reject",
        handler: () => ({
          body: {
            id: 2,
            remediation_plan_id: 10,
            decision: "rejected",
            decided_by: "local-user",
            reason: null,
            plan_hash: "abc123",
            created_at: "2026-01-02T10:06:00Z",
          },
        }),
      },
      { match: "/remediations", handler: () => ({ body: page([samplePlan]) }) },
    ]);
    const user = userEvent.setup();

    renderWithProviders(<ApprovalsPage />);
    await user.click(await screen.findByRole("button", { name: /^reject$/i }));

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([input]) =>
        input.toString().includes("/remediations/10/reject"),
      );
      expect(call).toBeTruthy();
    });
  });
});
