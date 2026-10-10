import { useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertOctagon,
  AppWindow,
  BarChart3,
  CheckSquare,
  Cpu,
  Github,
  History,
  LayoutDashboard,
  Menu,
  Plug,
  Server,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";
import { api } from "@/api/client";

interface NavItem {
  to: string;
  label: string;
  icon: typeof LayoutDashboard;
}

const NAV: { section: string; items: NavItem[] }[] = [
  {
    section: "Overview",
    items: [
      { to: "/", label: "Dashboard", icon: LayoutDashboard },
      { to: "/repositories", label: "Repositories", icon: Github },
      { to: "/workflows", label: "Workflow Runs", icon: Workflow },
    ],
  },
  {
    section: "Self-Healing",
    items: [
      { to: "/incidents", label: "Incidents", icon: AlertOctagon },
      { to: "/remediations", label: "Remediation Proposals", icon: ShieldCheck },
      { to: "/approvals", label: "Approval Queue", icon: CheckSquare },
      { to: "/executions", label: "Execution History", icon: History },
    ],
  },
  {
    section: "Observability",
    items: [
      { to: "/agents", label: "Agent Activity", icon: Cpu },
      { to: "/settings", label: "Settings & Status", icon: Plug },
    ],
  },
];

function ConnectionPill() {
  const { data } = useQuery({
    queryKey: ["settings-status"],
    queryFn: api.settingsStatus,
    refetchInterval: 30000,
  });

  if (!data) {
    return <span className="text-xs text-slate-400">Checking backend…</span>;
  }

  const githubOk = data.github.configured;
  const llmOk = data.llm.configured;

  return (
    <div className="flex flex-wrap items-center gap-2 text-xs">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 ring-1 ring-inset ${
          githubOk
            ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
            : "bg-amber-50 text-amber-700 ring-amber-200"
        }`}
        title={data.github.detail}
      >
        <Github className="h-3.5 w-3.5" />
        {githubOk ? "GitHub connected" : "GitHub unconfigured"}
      </span>
      <span
        className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 ring-1 ring-inset ${
          llmOk
            ? "bg-emerald-50 text-emerald-700 ring-emerald-200"
            : "bg-slate-100 text-slate-600 ring-slate-200"
        }`}
        title={data.llm.detail}
      >
        <Cpu className="h-3.5 w-3.5" />
        LLM: {data.llm.configured ? data.llm.name : `${data.llm.name} (rules fallback)`}
      </span>
    </div>
  );
}

export function Layout() {
  const [open, setOpen] = useState(false);
  const location = useLocation();

  return (
    <div className="flex min-h-screen bg-slate-100">
      {/* Sidebar */}
      <aside
        className={`fixed inset-y-0 left-0 z-30 w-64 transform border-r border-slate-800 bg-slate-900 text-slate-300 transition-transform lg:static lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="flex h-16 items-center justify-between px-5">
          <div className="flex items-center gap-2">
            <div className="rounded-lg bg-brand-600 p-1.5">
              <Activity className="h-5 w-5 text-white" />
            </div>
            <div>
              <p className="text-sm font-semibold text-white">SelfHealOps</p>
              <p className="text-[11px] text-slate-400">Agentic DevOps</p>
            </div>
          </div>
          <button
            className="text-slate-400 hover:text-white lg:hidden"
            onClick={() => setOpen(false)}
            aria-label="Close navigation"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="mt-2 space-y-6 px-3 pb-6">
          {NAV.map((group) => (
            <div key={group.section}>
              <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                {group.section}
              </p>
              <ul className="mt-2 space-y-1">
                {group.items.map((item) => {
                  const Icon = item.icon;
                  const active =
                    item.to === "/"
                      ? location.pathname === "/"
                      : location.pathname.startsWith(item.to);
                  return (
                    <li key={item.to}>
                      <NavLink
                        to={item.to}
                        onClick={() => setOpen(false)}
                        className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                          active
                            ? "bg-brand-600 text-white"
                            : "text-slate-300 hover:bg-slate-800 hover:text-white"
                        }`}
                      >
                        <Icon className="h-4 w-4" />
                        {item.label}
                      </NavLink>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        <div className="absolute bottom-0 left-0 right-0 border-t border-slate-800 p-4 text-[11px] text-slate-500">
          <div className="flex items-center gap-2">
            <Server className="h-3.5 w-3.5" />
            Single-user local mode
          </div>
        </div>
      </aside>

      {open && (
        <div
          className="fixed inset-0 z-20 bg-slate-900/50 lg:hidden"
          onClick={() => setOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Main */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-10 flex h-16 items-center justify-between gap-4 border-b border-slate-200 bg-white/90 px-4 backdrop-blur lg:px-8">
          <div className="flex items-center gap-3">
            <button
              className="rounded-lg p-2 text-slate-600 hover:bg-slate-100 lg:hidden"
              onClick={() => setOpen(true)}
              aria-label="Open navigation"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="hidden items-center gap-2 text-sm text-slate-500 sm:flex">
              <BarChart3 className="h-4 w-4" />
              Self-Healing CI/CD Control Plane
            </div>
          </div>
          <ConnectionPill />
        </header>

        <main className="flex-1 px-4 py-6 lg:px-8">
          <Outlet />
        </main>

        <footer className="border-t border-slate-200 px-4 py-4 text-center text-xs text-slate-400 lg:px-8">
          <AppWindow className="mr-1 inline h-3.5 w-3.5" />
          SelfHealOps · local development build — no production authentication is enabled.
        </footer>
      </div>
    </div>
  );
}
