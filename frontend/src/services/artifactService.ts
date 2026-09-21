/**
 * frontend/src/services/artifactService.ts
 *
 * Service for fetching and downloading locally generated deliverables
 * (PowerPoint presentations, Word documents, Excel workbooks, PDF reports).
 */

import { apiRequest } from "./apiClient"
import { BACKEND_CONFIG, backendUrl } from "./backendConfig"

export interface ArtifactInfo {
  filename: string
  file_type: string
  size_bytes: number
  download_url: string
  preview_url?: string | null
  modified_at: string
}

export const artifactService = {
  async fetchArtifacts(): Promise<ArtifactInfo[]> {
    try {
      return await apiRequest<ArtifactInfo[]>(
        BACKEND_CONFIG.endpoints.artifacts.list,
      )
    } catch {
      return []
    }
  },

  getDownloadUrl(filename: string): string {
    return backendUrl(BACKEND_CONFIG.endpoints.artifacts.download(filename))
  },

  getPreviewUrl(previewName: string): string {
    return backendUrl(BACKEND_CONFIG.endpoints.artifacts.preview(previewName))
  },
}
