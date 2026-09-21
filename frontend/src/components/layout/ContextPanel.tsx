import { useState, type ReactNode } from "react"
import {
  ChevronRight,
  FileText,
  Wrench,
  Shield,
  Database,
  BarChart2,
  FileSearch,
  X,
  CheckCircle,
} from "lucide-react"
import { Modal } from "../ui/Modal"
import type { Session } from "../../types"

interface ContextPanelProps {
  session: Session | null
  onClose?: () => void
  asDrawer?: boolean
}

export function ContextPanel({
  session,
  onClose,
  asDrawer,
}: ContextPanelProps) {
  const [toolModal, setToolModal] = useState<string | null>(null)
  const [docModal, setDocModal] = useState<string | null>(null)

  const knowledgeSources = [
    { name: "Maintenance Manual", type: "PDF", id: "km-1" },
    { name: "Safety Guidelines", type: "PDF", id: "km-2" },
    { name: "Equipment Specifications", type: "PDF", id: "km-3" },
  ]

  const tools = [
    {
      icon: FileSearch,
      name: "Document Search",
      desc: "Semantic search across indexed knowledge base documents.",
    },
    {
      icon: BarChart2,
      name: "Sensor Analytics",
      desc: "Time-series analysis and anomaly detection for industrial sensor data.",
    },
    {
      icon: FileText,
      name: "Report Generator",
      desc: "Automated report generation from AI analysis results.",
    },
  ]

  const capabilities = [
    "Text Analysis",
    "Image Understanding",
    "Document Analysis",
    "Data Analysis",
    "Knowledge Retrieval",
    "Report Generation",
  ]
  const security = [
    "Local Processing",
    "No External API",
    "Encrypted Storage",
    "Audit Logging",
  ]

  const panelClass = asDrawer
    ? "flex flex-col h-full bg-[var(--bg-sidebar)] w-full max-w-[320px]"
    : "flex flex-col h-full bg-[var(--bg-sidebar)] border-l border-[var(--border-color)]"

  return (
    <div className={panelClass} style={!asDrawer ? { width: 300 } : undefined}>
      <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-color)] flex-shrink-0">
        <span className="text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase">
          Workspace
        </span>
        {onClose && (
          <button
            onClick={onClose}
            className="text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-colors"
          >
            <X size={15} />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Active Session */}
        <Section title="Active Session">
          <div className="text-xs font-medium text-[var(--text-primary)]">
            {session?.title || "No active session"}
          </div>
          <div className="text-[11px] text-[var(--text-muted)] mt-0.5">
            {session?.messages.length || 0} messages
          </div>
        </Section>

        {/* Capabilities */}
        <Section title="Capabilities">
          <div className="grid grid-cols-1 gap-1">
            {capabilities.map((c) => (
              <div
                key={c}
                className="flex items-center gap-2 text-[11px] text-[var(--text-secondary)]"
              >
                <CheckCircle
                  size={11}
                  className="text-[var(--success)] flex-shrink-0"
                />{" "}
                {c}
              </div>
            ))}
          </div>
        </Section>

        {/* Knowledge Sources */}
        <Section title="Knowledge Sources">
          <div className="flex flex-col gap-1">
            {knowledgeSources.map((k) => (
              <button
                key={k.id}
                onClick={() => setDocModal(k.name)}
                className="flex items-center gap-2 text-[11px] text-[var(--text-secondary)] hover:text-[var(--accent)] transition-colors py-1 text-left"
              >
                <FileText size={11} className="flex-shrink-0" />
                <span className="truncate">{k.name}</span>
                <span className="ml-auto text-[10px] text-[var(--text-muted)]">
                  {k.type}
                </span>
              </button>
            ))}
          </div>
        </Section>

        {/* Tools */}
        <Section title="Tools">
          {tools.map((t) => (
            <button
              key={t.name}
              onClick={() => setToolModal(t.name)}
              className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--accent)]/40 transition-colors text-left mb-1.5"
            >
              <t.icon
                size={13}
                className="text-[var(--accent)] flex-shrink-0"
              />
              <span className="text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
                {t.name}
              </span>
              <ChevronRight
                size={11}
                className="ml-auto text-[var(--text-muted)]"
              />
            </button>
          ))}
        </Section>

        {/* Security */}
        <Section title="Security">
          <div className="rounded-lg border border-[var(--success)]/20 bg-[var(--success)]/5 p-3">
            <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--success)] mb-2">
              <Shield size={12} /> SECURE ENVIRONMENT
            </div>
            {security.map((s) => (
              <div
                key={s}
                className="flex items-center gap-1.5 text-[11px] text-[var(--text-secondary)] py-0.5"
              >
                <span className="text-[var(--success)] text-[10px]">✓</span> {s}
              </div>
            ))}
          </div>
        </Section>
      </div>

      {/* Tool Modal */}
      <Modal
        open={!!toolModal}
        onClose={() => setToolModal(null)}
        title={toolModal || ""}
      >
        <div className="text-sm text-[var(--text-secondary)]">
          {tools.find((t) => t.name === toolModal)?.desc}
          <div className="mt-4 p-3 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-xs text-[var(--text-muted)]">
            This tool is available in your chat session. Mention it in your
            message or attach relevant files to activate it automatically.
          </div>
        </div>
      </Modal>

      {/* Doc Modal */}
      <Modal
        open={!!docModal}
        onClose={() => setDocModal(null)}
        title={docModal || ""}
      >
        <div className="text-sm text-[var(--text-secondary)]">
          <p className="mb-3">
            This document is indexed in your knowledge base and available for
            retrieval during AI analysis.
          </p>
          <div className="flex gap-2">
            <button className="px-4 py-2 text-sm bg-[var(--accent)] text-white rounded-lg font-medium hover:bg-[var(--accent-light)] transition-colors">
              Download
            </button>
            <button
              onClick={() => setDocModal(null)}
              className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="px-4 py-3 border-b border-[var(--border-color)]">
      <div className="text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase mb-2">
        {title}
      </div>
      {children}
    </div>
  )
}
