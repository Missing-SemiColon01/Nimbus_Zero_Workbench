/**
 * frontend/src/services/systemService.ts
 *
 * Telemetry and system health service for the Sovereign AI Workbench.
 */

import { apiRequest } from './apiClient';
import { BACKEND_CONFIG } from './backendConfig';

export interface HealthStatus {
  status: string;
  sovereign_mode: boolean;
}

export interface ModelInfo {
  id: string;
  capabilities: string[];
  modalities: string[];
  priority: number;
  enabled: boolean;
}

export interface ToolInfo {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
}

export const systemService = {
  async getHealth(): Promise<HealthStatus> {
    try {
      return await apiRequest<HealthStatus>(BACKEND_CONFIG.endpoints.system.health);
    } catch {
      return { status: 'offline', sovereign_mode: true };
    }
  },

  async getModels(): Promise<ModelInfo[]> {
    try {
      return await apiRequest<ModelInfo[]>(BACKEND_CONFIG.endpoints.system.models);
    } catch {
      return [];
    }
  },

  async getTools(): Promise<ToolInfo[]> {
    try {
      return await apiRequest<ToolInfo[]>(BACKEND_CONFIG.endpoints.system.tools);
    } catch {
      return [];
    }
  },
};

