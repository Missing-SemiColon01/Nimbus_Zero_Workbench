/**
 * frontend/src/services/backendConfig.ts
 *
 * Backend configuration and endpoint registry.
 * In development, VITE_API_BASE_URL defaults to '' so requests are
 * seamlessly routed through the Vite proxy (vite.config.ts) to http://localhost:8000.
 */

export const BACKEND_CONFIG = {
  baseUrl: (
    import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
  ).replace(/\/$/, ""),
  endpoints: {
    auth: {
      login: "/api/v1/auth/login",
      register: "/api/v1/auth/register",
      verify: "/api/v1/auth/verify",
      me: "/api/v1/auth/me",
      logout: "/api/v1/auth/logout",
    },
    tasks: {
      create: "/api/v1/tasks",
      stream: "/api/v1/tasks/stream",
    },
    artifacts: {
      list: "/api/v1/artifacts",
      download: (filename: string) =>
        `/api/v1/artifacts/${encodeURIComponent(filename)}/download`,
      preview: (previewName: string) =>
        `/api/v1/artifacts/previews/${encodeURIComponent(previewName)}`,
    },
    knowledge: {
      upload: "/api/v1/ingest/upload",
      ingestPath: "/api/v1/ingest",
      search: "/api/v1/knowledge/search",
    },
    system: {
      health: "/api/v1/health",
      models: "/api/v1/models",
      tools: "/api/v1/tools",
      auditEvents: "/api/v1/audit/events",
    },
    sandbox: {
      run: "/api/v1/sandbox/run",
      codingWorkflow: "/api/v1/coding/run",
    },
  },
} as const

export function backendUrl(path: string): string {
  if (!BACKEND_CONFIG.baseUrl) return path
  return `${BACKEND_CONFIG.baseUrl}${path.startsWith("/") ? path : `/${path}`}`
}
