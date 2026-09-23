import { useState, useEffect } from "react"
import {
  Shield,
  Lock,
  Server,
  Database,
  Eye,
  FileText,
  ChevronRight,
  RefreshCw,
  Activity,
  Terminal,
} from "lucide-react"
import { Modal } from "../components/ui/Modal"
import { auditService, type AuditEvent } from "../services/auditService"

const SECURITY_CARDS = [
  {
    id: "on-premise",
    icon: Server,
    title: "On-Premise Processing",
    subtitle: "All AI inference runs locally",
    color: "var(--success)",
    detail:
      "The Nimbus Zero Engine runs entirely on your organization's infrastructure. Model weights, inference, and data processing never leave your network boundary. GPU compute is allocated from your on-premise hardware pool.",
  },
  {
    id: "no-external",
    icon: Shield,
    title: "No External API Dependency",
    subtitle: "Zero cloud API calls",
    color: "var(--accent)",
    detail:
      "Nimbus Zero does not call any external AI APIs including OpenAI, Anthropic, Google, or any other cloud provider. The system is fully air-gapped from external AI services and operates independently.",
  },
  {
    id: "encrypted",
    icon: Lock,
    title: "Encrypted Storage & Password Hashing",
    subtitle: "Bcrypt + AES-256 at rest",
    color: "var(--warning)",
    detail:
      "All user passwords are encrypted using bcrypt with high salt rounds. Stored data including session history, uploaded documents, and MongoDB indices remain protected within local infrastructure boundaries.",
  },
  {
    id: "rbac",
    icon: Eye,
    title: "JWT Role-Based Access Control",
    subtitle: "Granular token permission management",
    color: "var(--accent-light)",
    detail:
      "Access to sessions, documents, and AI capabilities is governed by signed JWT tokens. Roles include Operator, Analyst, Engineer, and Administrator, each with configurable capability scopes.",
  },
  {
    id: "audit",
    icon: FileText,
    title: "Immutable Audit Trail",
    subtitle: "Local JSONL activity trail",
    color: "var(--success)",
    detail:
      "Every tool execution, sandbox run, and system event is logged to an immutable append-only JSONL audit trail. Logs are tamper-evident and can be exported for compliance reporting.",
  },
]

export function Security() {
  const [selected, setSelected] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<"overview" | "audit">("overview")
  const [auditEvents, setAuditEvents] = useState<AuditEvent[]>([])
  const [loadingAudit, setLoadingAudit] = useState(false)
  const [selectedAudit, setSelectedAudit] = useState<AuditEvent | null>(null)

  const card = SECURITY_CARDS.find((c) => c.id === selected)

  const loadAuditEvents = async () => {
    setLoadingAudit(true)
    try {
      const events = await auditService.getAuditEvents(50)
      setAuditEvents(events.reverse())
    } finally {
      setLoadingAudit(false)
    }
  }

  useEffect(() => {
    if (activeTab === "audit") {
      loadAuditEvents()
    }
  }, [activeTab])

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        {/* Navigation Tabs */}
        <div className="flex gap-2 mb-6 border-b border-[var(--border-color)] pb-3">
          <button
            onClick={() => setActiveTab("overview")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors ${
              activeTab === "overview"
                ? "bg-[var(--accent)] text-white"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            Security Guarantees
          </button>
          <button
            onClick={() => setActiveTab("audit")}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-colors flex items-center gap-1.5 ${
              activeTab === "audit"
                ? "bg-[var(--accent)] text-white"
                : "text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
            }`}
          >
            <Activity size={13} />
            Live Audit Trail
          </button>
        </div>

        {activeTab === "overview" ? (
          <>
            {/* Hero status */}
            <div className="rounded-2xl border border-[var(--success)]/30 bg-[var(--success)]/5 p-8 mb-6 text-center">
              <div className="flex justify-center mb-3">
                <div className="w-12 h-12 rounded-2xl bg-[var(--success)]/10 flex items-center justify-center">
                  <Shield size={22} className="text-[var(--success)]" />
                </div>
              </div>
              <h2 className="text-lg font-semibold text-[var(--text-primary)] mb-1">
                Air-Gapped Nimbus Zero Environment Active
              </h2>
              <p className="text-sm text-[var(--text-muted)] max-w-md mx-auto">
                All data, inference, and embeddings remain strictly within your
                infrastructure boundary.
              </p>
            </div>

            {/* Security pillars */}
            <div className="flex flex-col gap-2 mb-6">
              {SECURITY_CARDS.map((c) => {
                const Icon = c.icon
                return (
                  <div
                    key={c.id}
                    onClick={() => setSelected(c.id)}
                    className="flex items-center gap-4 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-color)] cursor-pointer transition-all group"
                  >
                    <div
                      className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0"
                      style={{ background: `${c.color}15`, color: c.color }}
                    >
                      <Icon size={18} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm font-medium text-[var(--text-primary)]">
                        {c.title}
                      </div>
                      <div className="text-xs text-[var(--text-muted)]">
                        {c.subtitle}
                      </div>
                    </div>
                    <ChevronRight
                      size={14}
                      className="text-[var(--text-muted)] group-hover:text-[var(--text-primary)] transition-colors"
                    />
                  </div>
                )
              })}
            </div>
          </>
        ) : (
          /* Live Audit Trail Tab */
          <div>
            <div className="flex items-center justify-between mb-4">
              <div>
                <h2 className="text-base font-semibold text-[var(--text-primary)]">
                  System Audit Events
                </h2>
                <p className="text-xs text-[var(--text-muted)]">
                  Real-time immutable log of all autonomous tool invocations &
                  sandbox runs
                </p>
              </div>
              <button
                onClick={loadAuditEvents}
                disabled={loadingAudit}
                className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border-color)] text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
              >
                <RefreshCw
                  size={11}
                  className={loadingAudit ? "animate-spin" : ""}
                />{" "}
                Refresh
              </button>
            </div>

            {auditEvents.length === 0 ? (
              <div className="p-12 text-center text-sm text-[var(--text-muted)] rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)]">
                No audit events recorded yet. Run a chat task or sandbox
                execution to view live events.
              </div>
            ) : (
              <div className="flex flex-col gap-2">
                {auditEvents.map((ev, idx) => (
                  <div
                    key={idx}
                    onClick={() => setSelectedAudit(ev)}
                    className="p-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--accent)]/30 cursor-pointer transition-all text-xs"
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-semibold text-[var(--text-primary)] flex items-center gap-1.5">
                        <Terminal size={12} className="text-[var(--accent)]" />
                        {String(
                          ev.event_type ||
                            ev.event ||
                            ev.action ||
                            "task.execution",
                        )}
                      </span>
                      <span className="text-[10px] text-[var(--text-muted)]">
                        {ev.timestamp
                          ? new Date(ev.timestamp).toLocaleTimeString()
                          : "Recent"}
                      </span>
                    </div>
                    {ev.task_id && (
                      <div className="text-[10px] text-[var(--text-muted)] font-mono truncate">
                        Task: {ev.task_id}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Security Info Modal */}
      <Modal
        open={!!card}
        onClose={() => setSelected(null)}
        title={card?.title || ""}
        maxWidth="max-w-lg"
      >
        <p className="text-sm text-[var(--text-secondary)] leading-relaxed mb-4">
          {card?.detail}
        </p>
        <button
          onClick={() => setSelected(null)}
          className="w-full py-2 bg-[var(--bg-input)] hover:bg-[var(--bg-card)] rounded-lg text-xs font-medium text-[var(--text-primary)] transition-colors"
        >
          Close
        </button>
      </Modal>

      {/* Audit Detail Modal */}
      <Modal
        open={!!selectedAudit}
        onClose={() => setSelectedAudit(null)}
        title="Audit Event Payload"
        maxWidth="max-w-xl"
      >
        <div className="p-3 rounded-lg bg-[var(--bg-input)] font-mono text-[11px] text-[var(--text-secondary)] overflow-x-auto max-h-96">
          <pre>{JSON.stringify(selectedAudit, null, 2)}</pre>
        </div>
        <button
          onClick={() => setSelectedAudit(null)}
          className="w-full mt-4 py-2 bg-[var(--bg-input)] hover:bg-[var(--bg-card)] rounded-lg text-xs font-medium text-[var(--text-primary)] transition-colors"
        >
          Close
        </button>
      </Modal>
    </div>
  )
}
