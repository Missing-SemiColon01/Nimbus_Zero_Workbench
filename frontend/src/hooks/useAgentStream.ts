/**
 * frontend/src/hooks/useAgentStream.ts
 * =====================================
 * Custom hook that encapsulates all streaming state management for SSE-based
 * agent execution. Handles live agent steps, content accumulation, generated
 * file cards, and abort control.
 *
 * Usage:
 *   const { liveSteps, streamContent, generatedFiles, streaming, start, stop } = useAgentStream();
 */

import { useCallback, useRef, useState } from 'react';
import { streamTask } from '../services/sseClient';
import { BACKEND_CONFIG } from '../services/backendConfig';
import type { AgentStep, GeneratedFile, ArtifactPayload } from '../types';

/** Callbacks yielded to Chat.tsx to wire into message state updates */
export interface AgentStreamState {
  /** Steps being built in real time during streaming */
  liveSteps: AgentStep[];
  /** Accumulated text content for the AI message bubble */
  streamContent: string;
  /** Files generated during this stream (shown as download cards) */
  generatedFiles: GeneratedFile[];
  /** Whether streaming is currently active */
  streaming: boolean;
  /**
   * Start a streaming task.
   * @param request  - Natural language task prompt
   * @param options  - Optional task metadata
   * @param onDone   - Called with final steps + files when stream ends
   */
  start(
    request: string,
    options?: { task_type?: string; images?: string[]; documents?: string[] },
    onDone?: (steps: AgentStep[], files: GeneratedFile[], content: string) => void,
  ): void;
  /** Cancel the active stream */
  stop(): void;
}

const backendAvailable = Boolean(BACKEND_CONFIG.baseUrl);

export function useAgentStream(): AgentStreamState {
  const [liveSteps, setLiveSteps] = useState<AgentStep[]>([]);
  const [streamContent, setStreamContent] = useState('');
  const [generatedFiles, setGeneratedFiles] = useState<GeneratedFile[]>([]);
  const [streaming, setStreaming] = useState(false);

  // Internal refs for accumulation without triggering extra renders
  const stepsRef = useRef<AgentStep[]>([]);
  const contentRef = useRef('');
  const filesRef = useRef<GeneratedFile[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const stepCounterRef = useRef(0);

  const nextStepId = () => `sse-step-${++stepCounterRef.current}`;

  const start = useCallback(
    (
      request: string,
      options: { task_type?: string; images?: string[]; documents?: string[] } = {},
      onDone?: (steps: AgentStep[], files: GeneratedFile[], content: string) => void,
    ) => {
      // Reset state
      stepsRef.current = [];
      contentRef.current = '';
      filesRef.current = [];
      stepCounterRef.current = 0;
      setLiveSteps([]);
      setStreamContent('');
      setGeneratedFiles([]);
      setStreaming(true);

      const controller = new AbortController();
      abortRef.current = controller;

      const addStep = (step: AgentStep) => {
        stepsRef.current = [...stepsRef.current, step];
        setLiveSteps([...stepsRef.current]);
      };

      const updateLastStep = (updater: (s: AgentStep) => AgentStep) => {
        if (stepsRef.current.length === 0) return;
        const updated = [...stepsRef.current];
        updated[updated.length - 1] = updater(updated[updated.length - 1]);
        stepsRef.current = updated;
        setLiveSteps([...stepsRef.current]);
      };

      const updateStepByTool = (tool: string, updater: (s: AgentStep) => AgentStep) => {
        const idx = [...stepsRef.current].reverse().findIndex(s => s.tool === tool);
        if (idx < 0) return;
        const realIdx = stepsRef.current.length - 1 - idx;
        const updated = [...stepsRef.current];
        updated[realIdx] = updater(updated[realIdx]);
        stepsRef.current = updated;
        setLiveSteps([...stepsRef.current]);
      };

      void streamTask(
        {
          request,
          task_type: options.task_type,
          images: options.images,
          documents: options.documents,
          document_paths: [],
          approved_tools: [],
        },
        {
          onTaskInit(payload) {
            addStep({
              id: nextStepId(),
              label: `Starting task${payload.model ? ` · ${payload.model}` : ''}`,
              status: 'done',
            });
          },
          onThought(text) {
            // Mark previous active thought as done
            updateLastStep(s =>
              s.status === 'active' ? { ...s, status: 'done' } : s,
            );
            addStep({
              id: nextStepId(),
              label: text,
              status: 'active',
              startedAt: Date.now(),
            });
          },
          onToolCallStart(payload) {
            // Mark any active thought as done
            updateLastStep(s =>
              s.status === 'active' ? { ...s, status: 'done' } : s,
            );
            addStep({
              id: nextStepId(),
              label: payload.description,
              status: 'active',
              tool: payload.tool,
              logs: [],
              startedAt: Date.now(),
            });
          },
          onToolCallLog(tool, line) {
            updateStepByTool(tool, s => ({
              ...s,
              logs: [...(s.logs ?? []), line],
            }));
          },
          onToolCallEnd(payload) {
            updateStepByTool(payload.tool, s => ({
              ...s,
              status: payload.success ? 'done' : 'done',
              duration: payload.duration_ms != null
                ? `${(payload.duration_ms / 1000).toFixed(1)}s`
                : undefined,
            }));
          },
          onContentDelta(delta) {
            contentRef.current += delta;
            setStreamContent(contentRef.current);
          },
          onArtifactReady(payload: ArtifactPayload) {
            const file: GeneratedFile = {
              id: `gf-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
              name: payload.name,
              type: payload.file_type,
              size: `${Math.round(payload.size_bytes / 1024)} KB`,
              download_url: payload.download_url,
              preview_url: payload.preview_url,
            };
            filesRef.current = [...filesRef.current, file];
            setGeneratedFiles([...filesRef.current]);
          },
          onTaskComplete(payload) {
            // Mark all remaining active steps as done
            stepsRef.current = stepsRef.current.map(s =>
              s.status === 'active' ? { ...s, status: 'done' } : s,
            );
            stepsRef.current.push({
              id: nextStepId(),
              label: `Completed in ${(payload.duration_ms / 1000).toFixed(1)}s`,
              status: 'done',
            });
            setLiveSteps([...stepsRef.current]);
          },
          onTaskError(error) {
            addStep({ id: nextStepId(), label: `Error: ${error}`, status: 'done' });
          },
          onDone() {
            setStreaming(false);
            abortRef.current = null;
            onDone?.(stepsRef.current, filesRef.current, contentRef.current);
          },
        },
        controller.signal,
      ).catch(err => {
        if ((err as Error).name !== 'AbortError') {
          addStep({ id: nextStepId(), label: `Stream error: ${(err as Error).message}`, status: 'done' });
        }
        setStreaming(false);
        onDone?.(stepsRef.current, filesRef.current, contentRef.current);
      });
    },
    [],
  );

  const stop = useCallback(() => {
    abortRef.current?.abort();
    setStreaming(false);
  }, []);

  return { liveSteps, streamContent, generatedFiles, streaming, start, stop };
}

/** Whether the real backend is configured */
export const isBackendAvailable = backendAvailable;
