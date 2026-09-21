/**
 * frontend/src/services/knowledgeService.ts
 *
 * Service for PDF document ingestion, OCR fallback, and semantic vector retrieval.
 */

import { apiRequest } from './apiClient';
import { BACKEND_CONFIG } from './backendConfig';

export interface IngestResponse {
  document_id: string;
  filename: string;
  document_path?: string | null;
  page_count: number;
  chunk_count: number;
  ocr_pages: number;
  duration_seconds: number;
  status: string;
  error?: string | null;
}

export interface SearchResultChunk {
  content: string;
  metadata?: {
    document_id?: string;
    source?: string;
    page?: number;
    [key: string]: unknown;
  };
  score?: number;
}

export interface KnowledgeSearchResponse {
  query: string;
  total_results: number;
  results: SearchResultChunk[];
}

export const knowledgeService = {
  /**
   * Upload and ingest a PDF document via multipart form data.
   */
  async uploadDocument(
    file: File,
    documentId?: string,
    chunkSize = 500,
    chunkOverlap = 50,
  ): Promise<IngestResponse> {
    const formData = new FormData();
    formData.append('file', file);
    if (documentId) formData.append('document_id', documentId);
    formData.append('chunk_size', String(chunkSize));
    formData.append('chunk_overlap', String(chunkOverlap));

    return await apiRequest<IngestResponse>(BACKEND_CONFIG.endpoints.knowledge.upload, {
      method: 'POST',
      body: formData,
    });
  },

  /**
   * Perform semantic vector search across ingested sovereign documents.
   */
  async searchKnowledge(
    query: string,
    topK = 5,
    scoreThreshold?: number,
    documentId?: string,
  ): Promise<KnowledgeSearchResponse> {
    return await apiRequest<KnowledgeSearchResponse>(BACKEND_CONFIG.endpoints.knowledge.search, {
      method: 'POST',
      body: JSON.stringify({
        query,
        top_k: topK,
        score_threshold: scoreThreshold,
        document_id: documentId,
      }),
    });
  },
};

