import { type ReactElement, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { render } from "@testing-library/react";
import { vi } from "vitest";
import { ToastProvider } from "@/components/Toast";

export function createTestQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

interface RenderOptions {
  route?: string;
  path?: string;
}

export function renderWithProviders(ui: ReactElement, options: RenderOptions = {}) {
  const { route = "/", path } = options;
  const client = createTestQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <ToastProvider>
          <MemoryRouter initialEntries={[route]}>
            {path ? (
              <Routes>
                <Route path={path} element={children} />
              </Routes>
            ) : (
              children
            )}
          </MemoryRouter>
        </ToastProvider>
      </QueryClientProvider>
    );
  }

  return { client, ...render(ui, { wrapper: Wrapper }) };
}

export function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    text: async () => JSON.stringify(body),
  } as unknown as Response;
}

export interface RouteHandler {
  match: string;
  handler: (init?: RequestInit) => { status?: number; body: unknown };
}

export function mockFetch(handlers: RouteHandler[]) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = typeof input === "string" ? input : input.toString();
    for (const { match, handler } of handlers) {
      if (url.includes(match)) {
        const { status = 200, body } = handler(init);
        return jsonResponse(body, status);
      }
    }
    return jsonResponse({ detail: `No mock for ${url}` }, 404);
  });
  vi.stubGlobal("fetch", fn);
  return fn;
}
