import { useState, useRef, useEffect, useCallback } from "react"
import { FileText, BarChart2, Image, AlertTriangle } from "lucide-react"
import { ChatMessage } from "../components/chat/ChatMessage"
import { ChatComposer } from "../components/chat/ChatComposer"
import { generateResponse } from "../services/aiService"
import { isBackendAvailable } from "../hooks/useAgentStream"
import { BACKEND_CONFIG } from "../services/backendConfig"
import { useToast } from "../components/ui/Toast"
import type {
  Session,
  Message,
  Attachment,
  AgentStep,
  GeneratedFile,
} from "../types"

interface ChatProps {
  session: Session | null
  onAddMessage: (sessionId: string, message: Message) => void
  onAddMessages?: (sessionId: string, messages: Message[]) => void
  onUpdateMessage: (
    sessionId: string,
    messageId: string,
    updates: Partial<Message>,
  ) => void
}

const SUGGESTIONS = [
  {
    icon: BarChart2,
    label: "Analyze sensor data",
    prompt:
      "Analyze the latest sensor data from the process unit and identify any anomalies or deviations from operating thresholds.",
  },
  {
    icon: FileText,
    label: "Analyze a maintenance report",
    prompt:
      "Review the attached maintenance report and summarize key findings, upcoming service requirements, and any safety-critical items.",
  },
  {
    icon: Image,
    label: "Inspect equipment image",
    prompt:
      "Analyze this equipment image and identify visible signs of wear, corrosion, or damage that may require maintenance attention.",
  },
  {
    icon: AlertTriangle,
    label: "Generate an incident report",
    prompt:
      "Generate a structured safety incident report based on the provided information, including root cause analysis and corrective actions.",
  },
]

export function Chat({
  session,
  onAddMessage,
  onAddMessages,
  onUpdateMessage,
}: ChatProps) {
  const [streaming, setStreaming] = useState(false)
  const [streamingId, setStreamingId] = useState<string | null>(null)
  const [streamContent, setStreamContent] = useState("")
  /** Live agent steps built in real time from SSE events (or mock) */
  const [liveSteps, setLiveSteps] = useState<AgentStep[]>([])

  const abortRef = useRef<AbortController | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const stepCounterRef = useRef(0)
  const stepsRef = useRef<AgentStep[]>([])
  const filesRef = useRef<GeneratedFile[]>([])
  const { showToast } = useToast()

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [session?.messages.length, streamContent])

  // ── Step helpers ────────────────────────────────────────────────────────────

  const nextStepId = () => `step-${++stepCounterRef.current}`

  const addStep = useCallback((step: AgentStep) => {
    stepsRef.current = [...stepsRef.current, step]
    setLiveSteps([...stepsRef.current])
  }, [])

  const updateLastStep = useCallback((updater: (s: AgentStep) => AgentStep) => {
    if (!stepsRef.current.length) return
    const updated = [...stepsRef.current]
    updated[updated.length - 1] = updater(updated[updated.length - 1])
    stepsRef.current = updated
    setLiveSteps([...stepsRef.current])
  }, [])

  const updateStepByTool = useCallback(
    (tool: string, updater: (s: AgentStep) => AgentStep) => {
      const reversed = [...stepsRef.current].reverse()
      const idx = reversed.findIndex((s) => s.tool === tool)
      if (idx < 0) return
      const realIdx = stepsRef.current.length - 1 - idx
      const updated = [...stepsRef.current]
      updated[realIdx] = updater(updated[realIdx])
      stepsRef.current = updated
      setLiveSteps([...stepsRef.current])
    },
    [],
  )

  // ── Send message ────────────────────────────────────────────────────────────

  const sendMessage = useCallback(
    async (content: string, attachments: Attachment[]) => {
      if (!session) return

      const targetSessionId = session.id

      // Reset live step state
      stepsRef.current = []
      filesRef.current = []
      stepCounterRef.current = 0
      setLiveSteps([])

      const userMsg: Message = {
        id: `msg-${Date.now()}`,
        role: "user",
        content,
        timestamp: new Date(),
        attachments: attachments.length > 0 ? attachments : undefined,
      }

      const aiMsgId = `msg-${Date.now() + 1}`
      const aiMsg: Message = {
        id: aiMsgId,
        role: "assistant",
        content: "",
        timestamp: new Date(),
      }

      if (onAddMessages) {
        onAddMessages(targetSessionId, [userMsg, aiMsg])
      } else {
        onAddMessage(targetSessionId, userMsg)
        onAddMessage(targetSessionId, aiMsg)
      }

      setStreamingId(aiMsgId)
      setStreamContent("")
      setStreaming(true)

      const controller = new AbortController()
      abortRef.current = controller

      let accumulated = ""

      try {
        const allMsgs = [...(session.messages || []), userMsg]

        // ── Real backend SSE execution ─────────────────────────────────────────
        await generateResponse(
          allMsgs,
          (chunk) => {
            accumulated += chunk
            setStreamContent(accumulated)
          },
          controller.signal,
          {
            onThought(text, phase) {
              updateLastStep((s) =>
                s.status === "active" ? { ...s, status: "done" } : s,
              )
              addStep({
                id: nextStepId(),
                label: text,
                status: "active",
                startedAt: Date.now(),
              })
            },
            onToolCallStart(tool, description) {
              updateLastStep((s) =>
                s.status === "active" ? { ...s, status: "done" } : s,
              )
              addStep({
                id: nextStepId(),
                label: description,
                status: "active",
                tool,
                logs: [],
                startedAt: Date.now(),
              })
            },
            onToolCallLog(tool, line) {
              updateStepByTool(tool, (s) => ({
                ...s,
                logs: [...(s.logs ?? []), line],
              }))
            },
            onToolCallEnd(tool, success, duration_ms) {
              updateStepByTool(tool, (s) => ({
                ...s,
                status: "done",
                duration:
                  duration_ms != null
                    ? `${(duration_ms / 1000).toFixed(1)}s`
                    : undefined,
              }))
            },
            onArtifactReady(
              name,
              fileType,
              sizeBytes,
              downloadUrl,
              previewUrl,
            ) {
              const file: GeneratedFile = {
                id: `gf-${Date.now()}`,
                name,
                type: fileType,
                size: `${Math.round(sizeBytes / 1024)} KB`,
                download_url: downloadUrl,
                preview_url: previewUrl,
              }
              filesRef.current = [...filesRef.current, file]
            },
            onTaskComplete(durationMs, model) {
              stepsRef.current = stepsRef.current.map((s) =>
                s.status === "active" ? { ...s, status: "done" } : s,
              )
              stepsRef.current.push({
                id: nextStepId(),
                label: `Completed in ${(durationMs / 1000).toFixed(1)}s${
                  model ? ` · ${model}` : ""
                }`,
                status: "done",
              })
              setLiveSteps([...stepsRef.current])
            },
            onTaskError(error) {
              addStep({
                id: nextStepId(),
                label: `Error: ${error}`,
                status: "done",
              })
              if (!accumulated) {
                accumulated = `Agent encountered an issue: ${error}`
                setStreamContent(accumulated)
              }
            },
          },
          {
            sessionId: targetSessionId,
            images: attachments
              .filter((a) => a.type === "image" && (a.dataUrl || a.url))
              .map((a) => a.dataUrl || a.url!),
            documents: attachments
              .filter((a) => a.type !== "image" && (a.dataUrl || a.url))
              .map((a) => a.dataUrl || a.url!),
          },
        )

        const finalSteps = stepsRef.current.map((s) =>
          s.status === "active" ? { ...s, status: "done" as const } : s,
        )

        onUpdateMessage(targetSessionId, aiMsgId, {
          content: accumulated || "No response received from agent.",
          agentSteps: finalSteps.length > 0 ? finalSteps : undefined,
          generatedFiles:
            filesRef.current.length > 0 ? filesRef.current : undefined,
        })
      } catch (err: any) {
        const finalSteps = stepsRef.current.map((s) =>
          s.status === "active" ? { ...s, status: "done" as const } : s,
        )
        if (!controller.signal.aborted) {
          const errorMsg =
            err?.message ||
            "Unable to connect to Sovereign backend at http://localhost:8000. Please ensure the backend is running."
          onUpdateMessage(targetSessionId, aiMsgId, {
            content: accumulated || errorMsg,
            agentSteps:
              finalSteps.length > 0 ? finalSteps : undefined,
          })
        } else {
          onUpdateMessage(targetSessionId, aiMsgId, { content: accumulated })
        }
      } finally {
        setStreaming(false)
        setStreamingId(null)
        setStreamContent("")
        setLiveSteps([])
        abortRef.current = null
      }
    },
    [
      session,
      onAddMessage,
      onAddMessages,
      onUpdateMessage,
      addStep,
      updateLastStep,
      updateStepByTool,
    ],
  )

  function handleStop() {
    abortRef.current?.abort()
    showToast("Generation stopped", "info")
  }

  function handleSuggestion(prompt: string) {
    sendMessage(prompt, [])
  }

  if (!session) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 text-center">
        <div>
          <div className="w-12 h-12 rounded-2xl bg-[var(--accent)] flex items-center justify-center mx-auto mb-4">
            <svg width="22" height="22" viewBox="0 0 14 14" fill="none">
              <path
                d="M7 1L9.5 5.5H12L8.5 8.5L9.5 13L7 10.5L4.5 13L5.5 8.5L2 5.5H4.5L7 1Z"
                fill="white"
                fillRule="evenodd"
              />
            </svg>
          </div>
          <div className="text-lg font-semibold text-[var(--text-primary)] mb-1">
            No active session
          </div>
          <div className="text-sm text-[var(--text-muted)]">
            Select a session or create a new one to begin.
          </div>
        </div>
      </div>
    )
  }

  const messages = session.messages || []
  const isEmpty = messages.length === 0

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[860px] mx-auto px-4 py-6">
          {/* Status line */}
          <div className="flex items-center gap-2 text-[11px] text-[var(--text-muted)] mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--success)]" />
            Secure session initialized · Processing on-premise
            {isBackendAvailable && (
              <span className="ml-1 px-1.5 py-0.5 rounded bg-[var(--accent)]/10 text-[var(--accent)] text-[10px] font-medium">
                LIVE
              </span>
            )}
          </div>

          {/* Empty state */}
          {isEmpty && (
            <div className="flex flex-col items-center text-center py-12">
              <div className="w-14 h-14 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-color)] flex items-center justify-center mb-5">
                <svg width="24" height="24" viewBox="0 0 14 14" fill="none">
                  <path
                    d="M7 1L9.5 5.5H12L8.5 8.5L9.5 13L7 10.5L4.5 13L5.5 8.5L2 5.5H4.5L7 1Z"
                    fill="var(--accent)"
                    fillRule="evenodd"
                  />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
                How can I help with your industrial operations?
              </h2>
              <p className="text-sm text-[var(--text-muted)] max-w-[420px] mb-8 leading-relaxed">
                Analyze confidential documents, inspect equipment, analyze
                industrial data, and generate reports securely on-premise.
              </p>
              <div className="grid grid-cols-2 gap-2 w-full max-w-[520px]">
                {SUGGESTIONS.map((s) => (
                  <button
                    key={s.label}
                    onClick={() => handleSuggestion(s.prompt)}
                    className="flex items-center gap-2.5 p-3.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--accent)]/40 hover:bg-[var(--bg-card)] transition-all text-left group"
                  >
                    <s.icon
                      size={15}
                      className="text-[var(--accent)] flex-shrink-0"
                    />
                    <span className="text-xs text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">
                      {s.label}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              message={msg}
              streaming={streaming && msg.id === streamingId}
              streamContent={
                streaming && msg.id === streamingId ? streamContent : undefined
              }
              liveSteps={
                streaming && msg.id === streamingId ? liveSteps : undefined
              }
              onLike={() =>
                onUpdateMessage(session.id, msg.id, {
                  liked: !msg.liked,
                  disliked: false,
                })
              }
              onDislike={() =>
                onUpdateMessage(session.id, msg.id, {
                  disliked: !msg.disliked,
                  liked: false,
                })
              }
              onRegenerate={() => {
                if (streaming) return
                showToast("Regenerating response...")
                onUpdateMessage(session.id, msg.id, {
                  content: "Regenerating...",
                })
                setTimeout(() => {
                  const prev = messages[messages.indexOf(msg) - 1]
                  if (prev) sendMessage(prev.content, prev.attachments || [])
                }, 500)
              }}
            />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Composer */}
      <ChatComposer
        onSend={sendMessage}
        streaming={streaming}
        onStop={handleStop}
      />
    </div>
  )
}
