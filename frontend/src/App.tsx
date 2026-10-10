import { Navigate, Route, Routes } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { OverviewPage } from "@/pages/OverviewPage";
import { RepositoriesPage } from "@/pages/RepositoriesPage";
import { RepositoryDetailPage } from "@/pages/RepositoryDetailPage";
import { WorkflowsPage } from "@/pages/WorkflowsPage";
import { IncidentsPage } from "@/pages/IncidentsPage";
import { IncidentDetailPage } from "@/pages/IncidentDetailPage";
import { AgentActivityPage } from "@/pages/AgentActivityPage";
import { RemediationsPage } from "@/pages/RemediationsPage";
import { ApprovalsPage } from "@/pages/ApprovalsPage";
import { ExecutionsPage } from "@/pages/ExecutionsPage";
import { SettingsPage } from "@/pages/SettingsPage";

export default function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route path="/" element={<OverviewPage />} />
        <Route path="/repositories" element={<RepositoriesPage />} />
        <Route path="/repositories/:id" element={<RepositoryDetailPage />} />
        <Route path="/workflows" element={<WorkflowsPage />} />
        <Route path="/incidents" element={<IncidentsPage />} />
        <Route path="/incidents/:id" element={<IncidentDetailPage />} />
        <Route path="/remediations" element={<RemediationsPage />} />
        <Route path="/approvals" element={<ApprovalsPage />} />
        <Route path="/executions" element={<ExecutionsPage />} />
        <Route path="/agents" element={<AgentActivityPage />} />
        <Route path="/settings" element={<SettingsPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
