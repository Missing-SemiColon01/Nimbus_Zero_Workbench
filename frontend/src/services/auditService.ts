/**
 * frontend/src/services/auditService.ts
 *
 * Immutable audit trail service.
 * Fetches tamper-evident execution logs from the backend audit recorder.
 */

import { apiRequest } from "./apiClient"
import { BACKEND_CONFIG } from "./backendConfig"

export interface AuditEvent {
  timestamp?: string
  event_type?: string
  event?: string
  action?: string
  task_id?: string
  data?: Record<string, unknown>
  [key: string]: unknown
}

export const auditService = {
  async getAuditEvents(limit = 100): Promise<AuditEvent[]> {
    try {
      return await apiRequest<AuditEvent[]>(
        `${BACKEND_CONFIG.endpoints.system.auditEvents}?limit=${limit}`,
      )
    } catch {
      return []
    }
  },
}
