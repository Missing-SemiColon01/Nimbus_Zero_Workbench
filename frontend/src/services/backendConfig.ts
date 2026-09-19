/**
 * Backend integration placeholder.
 *
 * This frontend intentionally does NOT include a backend implementation.
 * Set VITE_API_BASE_URL when the backend is ready, then connect the existing
 * service functions/pages to these endpoints.
 */

export const BACKEND_CONFIG = {
  baseUrl: (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, ''),
  endpoints: {
    auth: {
      login: '/auth/login',
      verify: '/auth/verify',
      register: '/auth/register',
      forgotPassword: '/auth/forgot-password',
      logout: '/auth/logout',
    },
    chat: '/chat',
    sessions: '/sessions',
    documents: '/documents',
    knowledgeBase: '/knowledge-base',
    agents: '/agents',
    workflows: '/workflows',
    systemStatus: '/system/status',
    security: '/security',
    profile: '/user/profile',
    // Real backend endpoints
    tasks: '/api/v1/tasks',
    tasksStream: '/api/v1/tasks/stream',
  },
} as const;

export function backendUrl(path: string) {
  if (!BACKEND_CONFIG.baseUrl) return path;
  return `${BACKEND_CONFIG.baseUrl}${path.startsWith('/') ? path : `/${path}`}`;
}
