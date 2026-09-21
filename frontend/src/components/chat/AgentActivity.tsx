import { useState, useEffect, useRef, type ElementType } from "react"
import {
  ChevronDown,
  ChevronRight,
  CheckCircle,
  Loader,
  Clock,
  Cpu,
  Terminal,
  Search,
  Eye,
  FileText,
  LayoutTemplate,
  Table,
  ShieldCheck,
  Zap,
  Sparkles,
} from "lucide-react"
import type { AgentStep } from "../../types"

interface AgentActivityProps {
  steps: AgentStep[]
  streaming?: boolean
}

// ── Tool icon map ───────────────────────────────────────────────────────────

const TOOL_ICONS: Record<string, ElementType> = {
  "sandbox.execute": Terminal,
  "rag.search": Search,
  "vision.analyze": Eye,
  "artifact.document.create": FileText,
  "artifact.presentation.create": LayoutTemplate,
  "artifact.pdf.create": FileText,
  "artifact.spreadsheet.create": Table,
  "artifact.validate": ShieldCheck,
  "python-pptx": LayoutTemplate,
  reportlab: FileText,
  "python-docx": FileText,
  openpyxl: Table,
  code: Terminal,
  js: Terminal,
}

const TOOL_LABELS: Record<string, string> = {
  "sandbox.execute": "Sandbox",
  "rag.search": "RAG Search",
  "vision.analyze": "Vision",
  "python-pptx": "python-pptx",
  reportlab: "ReportLab",
  "python-docx": "python-docx",
  openpyxl: "openpyxl",
  "artifact.presentation.create": "pptx.create",
  "artifact.pdf.create": "pdf.create",
  "artifact.document.create": "docx.create",
  "artifact.spreadsheet.create": "xlsx.create",
  "artifact.validate": "artifact.validate",
  code: "Python Script",
  js: "JavaScript",
}

function toolShortName(tool: string): string {
  return TOOL_LABELS[tool] ?? tool.split(".").pop() ?? tool
}

function ToolIcon({ tool, size = 11 }: { tool?: string size?: number }) {
  const Icon = tool ? (TOOL_ICONS[tool] ?? Zap) : Cpu
  return <Icon size={size} />
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function stepTotalDuration(steps: AgentStep[]): string {
  let total = 0
  for (const step of steps) {
    if (step.duration) {
      const n = parseFloat(step.duration)
      if (!isNaN(n)) total += n
    }
  }
  return total > 0 ? `${total.toFixed(1)}s` : ""
}

// ── Elapsed timer ──────────────────────────────────────────────────────────

function useElapsed(startedAt?: number, active?: boolean): string {
  const [elapsed, setElapsed] = useState("")
  const raf = useRef<number | null>(null)

  useEffect(() => {
    if (!active || !startedAt) {
      setElapsed("")
      return
    }
    const tick = () => {
      const ms = Date.now() - startedAt
      setElapsed(`${(ms / 1000).toFixed(1)}s`)
      raf.current = requestAnimationFrame(tick)
    }
    raf.current = requestAnimationFrame(tick)
    return () => {
      if (raf.current !== null) cancelAnimationFrame(raf.current)
    }
  }, [active, startedAt])

  return elapsed
}

// ── Step row ───────────────────────────────────────────────────────────────

function StepRow({ step }: { step: AgentStep }) {
  const [logsOpen, setLogsOpen] = useState(false)
  const logEndRef = useRef<HTMLDivElement>(null)
  const elapsed = useElapsed(step.startedAt, step.status === "active")
  const haslogs = (step.logs?.length ?? 0) > 0

  useEffect(() => {
    if (logsOpen) logEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [step.logs?.length, logsOpen])

  const displayDuration =
    step.status === "done"
      ? step.duration
      : step.status === "active"
        ? elapsed || undefined
        : undefined

  return (
    <div className="flex flex-col gap-0">
      <div
        className={`flex items-start gap-2 text-[11px] py-1 px-1 rounded-lg transition-all duration-200 ${
          step.status === "active" ? "bg-[var(--accent)]/6" : ""
        }`}
      >
        {/* Status icon */}
        <div className="flex-shrink-0 mt-0.5">
          {step.status === "done" ? (
            <CheckCircle size={11} className="text-[var(--success)]" />
          ) : step.status === "active" ? (
            <Loader size={11} className="animate-spin text-[var(--accent)]" />
          ) : (
            <Clock size={11} className="text-[var(--text-muted)] opacity-40" />
          )}
        </div>

        {/* Tool icon badge */}
        {step.tool && (
          <span
            className={`flex-shrink-0 mt-0.5 ${
              step.status === "active"
                ? "text-[var(--accent)]"
                : step.status === "done"
                  ? "text-[var(--text-secondary)]"
                  : "text-[var(--text-muted)]"
            }`}
          >
            <ToolIcon tool={step.tool} size={11} />
          </span>
        )}

        {/* Label */}
        <span
          className={`flex-1 leading-relaxed ${
            step.status === "done"
              ? "text-[var(--text-secondary)]"
              : step.status === "active"
                ? "text-[var(--text-primary)] font-medium"
                : "text-[var(--text-muted)] opacity-50"
          }`}
        >
          {step.label}
        </span>

        {/* Tool name pill — only when active or done */}
        {step.tool && step.status !== "pending" && (
          <span className="flex-shrink-0 px-1.5 py-0.5 rounded text-[9px] font-mono bg-[var(--bg-input)] text-[var(--text-muted)] border border-[var(--border-color)]">
            {toolShortName(step.tool)}
          </span>
        )}

        {/* Duration / elapsed */}
        <span className="flex-shrink-0 text-[10px] text-[var(--text-muted)] ml-auto min-w-[32px] text-right tabular-nums">
          {displayDuration}
        </span>

        {/* Log toggle */}
        {haslogs && (
          <button
            onClick={() => setLogsOpen((v) => !v)}
            className="flex-shrink-0 ml-1 text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
            title={logsOpen ? "Hide logs" : "Show logs"}
          >
            {logsOpen ? <ChevronDown size={10} /> : <ChevronRight size={10} />}
          </button>
        )}
      </div>

      {/* Log terminal panel */}
      {logsOpen && haslogs && (
        <div className="ml-5 mt-1 mb-1 rounded-lg overflow-hidden border border-[var(--border-color)] bg-[#0d0d0f]">
          <div className="flex items-center gap-1.5 px-2.5 py-1.5 border-b border-[var(--border-color)] bg-[#111113]">
            <div className="w-2 h-2 rounded-full bg-[#ff5f57]" />
            <div className="w-2 h-2 rounded-full bg-[#febc2e]" />
            <div className="w-2 h-2 rounded-full bg-[#28c840]" />
            <span className="ml-1 text-[9px] text-[var(--text-muted)] font-mono">
              {step.tool ?? "output"}
            </span>
          </div>
          <div className="max-h-[140px] overflow-y-auto p-2.5 font-mono text-[10px] leading-relaxed space-y-0.5">
            {step.logs!.map((line, i) => (
              <div
                key={i}
                className={`whitespace-pre-wrap break-all ${
                  line.startsWith("[stderr]")
                    ? "text-[var(--danger)]/80"
                    : "text-emerald-400/80"
                }`}
              >
                {line}
              </div>
            ))}
            <div ref={logEndRef} />
          </div>
        </div>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export function AgentActivity({ steps, streaming }: AgentActivityProps) {
  // Auto-expand during streaming; auto-collapse to discreet pill on completion
  const [expanded, setExpanded] = useState(!!streaming)
  const prevStreaming = useRef(streaming)

  const elapsed = useElapsed(
    steps.find((s) => s.startedAt)?.startedAt,
    streaming,
  )

  // Capture the last elapsed value right before streaming stops (for the pill label)
  const finalElapsed = useRef("")
  if (streaming) finalElapsed.current = elapsed

  const doneCount = steps.filter((s) => s.status === "done").length
  const activeStep = steps.find((s) => s.status === "active")
  const toolCount = steps.filter((s) => s.tool).length

  // When streaming ends → collapse. When new stream starts → expand.
  useEffect(() => {
    if (prevStreaming.current && !streaming) {
      setExpanded(false) // auto-collapse to pill so result is prominent
    }
    if (!prevStreaming.current && streaming) {
      setExpanded(true)
    }
    prevStreaming.current = streaming
  }, [streaming])

  if (steps.length === 0) return null

  // ── Collapsed pill — shown when done and user hasn't re-expanded ────────────
  if (!streaming && !expanded) {
    const elapsedLabel = finalElapsed.current || stepTotalDuration(steps)
    return (
      <button
        onClick={() => setExpanded(true)}
        className="flex items-center gap-1.5 mt-2 px-2.5 py-1 rounded-lg text-[11px] text-[var(--text-muted)] hover:text-[var(--text-secondary)] hover:bg-[var(--bg-input)] border border-transparent hover:border-[var(--border-color)] transition-all duration-200 group"
        title="Click to view agent activity"
      >
        <CheckCircle
          size={10}
          className="text-[var(--success)] flex-shrink-0"
        />
        <span>
          {elapsedLabel ? `Thought for ${elapsedLabel}` : "Agent activity"}
          {toolCount > 0
            ? ` · ${toolCount} tool${toolCount !== 1 ? "s" : ""}`
            : ""}
        </span>
        <ChevronRight
          size={10}
          className="opacity-50 group-hover:opacity-100 transition-opacity"
        />
      </button>
    )
  }

  // ── Active streaming panel OR manually re-expanded ─────────────────────────
  return (
    <div
      className={`rounded-xl border mt-2 transition-all duration-300 ${
        streaming
          ? "border-[var(--accent)]/35 shadow-[0_0_12px_-3px_var(--accent)] bg-[var(--accent)]/3"
          : "border-[var(--border-color)] bg-[var(--bg-input)]"
      }`}
    >
      {/* Header */}
      <button
        onClick={() => setExpanded((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-white/3 transition-colors rounded-xl"
      >
        {/* Left: icon + label */}
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          {streaming ? (
            <Sparkles
              size={11}
              className="text-[var(--accent)] animate-pulse flex-shrink-0"
            />
          ) : (
            <CheckCircle
              size={11}
              className="text-[var(--success)] flex-shrink-0"
            />
          )}

          <span className="text-[11px] font-medium text-[var(--text-secondary)] truncate">
            {streaming && activeStep ? (
              <span className="flex items-center gap-1">
                {activeStep.tool && (
                  <span className="text-[var(--accent)] flex-shrink-0">
                    <ToolIcon tool={activeStep.tool} size={10} />
                  </span>
                )}
                <span className="text-[var(--text-primary)]">
                  {activeStep.label.length > 48
                    ? activeStep.label.slice(0, 48) + "…"
                    : activeStep.label}
                </span>
              </span>
            ) : streaming ? (
              <span className="text-[var(--text-primary)] animate-pulse">
                Thinking…
              </span>
            ) : (
              `Agent activity · ${steps.length} step${
                steps.length !== 1 ? "s" : ""
              }`
            )}
          </span>
        </div>

        {/* Right: counters + elapsed + chevron */}
        <div className="flex items-center gap-2 flex-shrink-0">
          {toolCount > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-muted)]">
              {toolCount} tool{toolCount !== 1 ? "s" : ""}
            </span>
          )}
          {streaming && elapsed && (
            <span className="text-[10px] text-[var(--accent)] font-mono tabular-nums">
              {elapsed}
            </span>
          )}
          {!streaming && (
            <span className="text-[10px] text-[var(--text-muted)]">
              {doneCount}/{steps.length}
            </span>
          )}
          {expanded ? (
            <ChevronDown size={12} className="text-[var(--text-muted)]" />
          ) : (
            <ChevronRight size={12} className="text-[var(--text-muted)]" />
          )}
        </div>
      </button>

      {/* Step list */}
      {expanded && (
        <div className="px-3 pb-3 flex flex-col gap-0.5 border-t border-[var(--border-color)]/50 pt-2">
          {steps.map((step) => (
            <StepRow key={step.id} step={step} />
          ))}
        </div>
      )}
    </div>
  )
}
