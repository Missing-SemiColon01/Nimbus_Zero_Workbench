/**
 * frontend/src/services/sseClient.ts
 * ====================================
 * Typed SSE streaming client for the AgenticAI-Workbench backend.
 *
 * Uses fetch() + ReadableStream instead of EventSource because the streaming
 * endpoint requires a POST body. Parses "data: {...}\n\n" lines from the stream
 * and dispatches them to typed callbacks.
 */

import { backendUrl } from "./backendConfig"
import type {
  TaskInitPayload,
  ToolCallStartPayload,
  ToolCallEndPayload,
  ArtifactPayload,
  TaskCompletePayload,
} from "../types"

export interface StreamCallbacks {
  onTaskInit?: (payload: TaskInitPayload) => void
  onThought?: (text: string, phase: string) => void
  onToolCallStart?: (payload: ToolCallStartPayload) => void
  onToolCallLog?: (tool: string, line: string) => void
  onToolCallEnd?: (payload: ToolCallEndPayload) => void
  onContentDelta?: (delta: string) => void
  onArtifactReady?: (payload: ArtifactPayload) => void
  onTaskComplete?: (payload: TaskCompletePayload) => void
  onTaskError?: (error: string) => void
  onDone?: () => void
}

export interface TaskChatMessage {
  role: "user" | "assistant" | "system"
  content: string
  images?: string[]
}

export interface TaskPayload {
  request: string
  task_type?: string
  modality?: string
  images?: string[]
  documents?: string[]
  document_paths?: string[]
  approved_tools?: string[]
  generation_mode?: string
  messages?: TaskChatMessage[]
  session_id?: string
}

/**
 * Stream a task from the backend SSE endpoint.
 *
 * @param payload   - TaskCreate payload to POST to /api/v1/tasks/stream
 * @param callbacks - Typed event callbacks (all optional)
 * @param signal    - Optional AbortSignal to cancel the stream
 */
export async function streamTask(
  payload: TaskPayload,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const url = backendUrl("/api/v1/tasks/stream")
  const token = localStorage.getItem("sovereign-jwt-token")

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  }

  const response = await fetch(url, {
    method: "POST",
    headers,
    body: JSON.stringify(payload),
    signal,
  })

  if (!response.ok) {
    const text = await response.text().catch(() => `HTTP ${response.status}`)
    throw new Error(
      text || `Stream request failed with status ${response.status}`,
    )
  }

  if (!response.body) {
    throw new Error("Streaming response body is not available")
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      // SSE messages are separated by double newlines
      const parts = buffer.split("\n\n")
      // Keep the last (potentially incomplete) part in the buffer
      buffer = parts.pop() ?? ""

      for (const part of parts) {
        const trimmed = part.trim()
        if (!trimmed || trimmed.startsWith(":")) continue // keepalive or comment

        // Extract "data: ..." line(s)
        const dataLine = trimmed.split("\n").find((l) => l.startsWith("data: "))
        if (!dataLine) continue

        const jsonStr = dataLine.slice("data: ".length)
        let event: { type: string; payload?: Record<string, unknown> }
        try {
          event = JSON.parse(jsonStr)
        } catch {
          continue
        }

        dispatchEvent(event, callbacks)
      }
    }
  } finally {
    reader.cancel().catch(() => undefined)
  }
}

function dispatchEvent(
  event: { type: string; payload?: Record<string, unknown> },
  cb: StreamCallbacks,
): void {
  const p = event.payload ?? {}
  switch (event.type) {
    case "task_init":
      cb.onTaskInit?.({
        task_id: String(p["task_id"] ?? ""),
        model: p["model"] != null ? String(p["model"]) : undefined,
        intent: p["intent"] != null ? String(p["intent"]) : undefined,
        capabilities: Array.isArray(p["capabilities"])
          ? p["capabilities"] as string[]
          : [],
      })
      break
    case "thought":
      cb.onThought?.(String(p["text"] ?? ""), String(p["phase"] ?? "reasoning"))
      break
    case "tool_call_start":
      cb.onToolCallStart?.({
        tool: String(p["tool"] ?? ""),
        description: String(p["description"] ?? ""),
        args_preview: p["args_preview"] as Record<string, unknown> ?? {},
      })
      break
    case "tool_call_log":
      cb.onToolCallLog?.(String(p["tool"] ?? ""), String(p["line"] ?? ""))
      break
    case "tool_call_end":
      cb.onToolCallEnd?.({
        tool: String(p["tool"] ?? ""),
        success: Boolean(p["success"]),
        duration_ms:
          p["duration_ms"] != null ? Number(p["duration_ms"]) : undefined,
        summary: p["summary"] != null ? String(p["summary"]) : undefined,
      })
      break
    case "content_delta":
      cb.onContentDelta?.(String(p["delta"] ?? ""))
      break
    case "artifact_ready":
      cb.onArtifactReady?.({
        name: String(p["name"] ?? ""),
        file_type: String(p["file_type"] ?? ""),
        size_bytes: Number(p["size_bytes"] ?? 0),
        download_url: String(p["download_url"] ?? ""),
        preview_url:
          p["preview_url"] != null ? String(p["preview_url"]) : undefined,
      })
      break
    case "task_complete":
      cb.onTaskComplete?.({
        task_id: String(p["task_id"] ?? ""),
        duration_ms: Number(p["duration_ms"] ?? 0),
        model: p["model"] != null ? String(p["model"]) : undefined,
        provider: p["provider"] != null ? String(p["provider"]) : undefined,
        tool_count: Number(p["tool_count"] ?? 0),
      })
      break
    case "task_error":
      cb.onTaskError?.(String(p["error"] ?? "Unknown error"))
      break
    case "done":
      cb.onDone?.()
      break
    default:
      break
  }
}
