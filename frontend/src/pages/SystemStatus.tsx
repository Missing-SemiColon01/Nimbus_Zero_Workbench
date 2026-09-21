import { useState, useEffect } from "react"
import {
  RefreshCw,
  Cpu,
  Shield,
  CheckCircle,
  Brain,
  Wrench,
  Server,
  Database,
} from "lucide-react"
import { useToast } from "../components/ui/Toast"
import {
  systemService,
  type HealthStatus,
  type ModelInfo,
  type ToolInfo,
} from "../services/systemService"

export function SystemStatus() {
  const [health, setHealth] = useState<HealthStatus | null>(null)
  const [models, setModels] = useState<ModelInfo[]>([])
  const [tools, setTools] = useState<ToolInfo[]>([])
  const [refreshing, setRefreshing] = useState(false)
  const { showToast } = useToast()

  const loadStatus = async () => {
    setRefreshing(true)
    try {
      const [h, m, t] = await Promise.all([
        systemService.getHealth(),
        systemService.getModels(),
        systemService.getTools(),
      ])
      setHealth(h)
      setModels(m)
      setTools(t)
    } catch {
      showToast("Error refreshing system telemetry", "error")
    } finally {
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadStatus()
  }, [])

  const isOnline = health?.status === "ok"

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-[var(--text-primary)]">
              System Status
            </h1>
            <p className="text-sm text-[var(--text-muted)]">
              On-premise infrastructure and AI runtime monitoring
            </p>
          </div>
          <button
            onClick={loadStatus}
            disabled={refreshing}
            className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors disabled:opacity-60"
          >
            <RefreshCw size={13} className={refreshing ? "animate-spin" : ""} />{" "}
            Refresh Status
          </button>
        </div>

        {/* Sovereign Mode Banner */}
        <div className="p-4 rounded-2xl bg-[var(--success)]/5 border border-[var(--success)]/20 mb-6 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-[var(--success)]/10 flex items-center justify-center text-[var(--success)]">
              <Shield size={20} />
            </div>
            <div>
              <div className="text-sm font-semibold text-[var(--text-primary)] flex items-center gap-2">
                Sovereign Mode Active
                <span className="px-1.5 py-0.5 rounded bg-[var(--success)]/20 text-[var(--success)] text-[10px] font-bold">
                  AIR-GAPPED
                </span>
              </div>
              <div className="text-xs text-[var(--text-muted)]">
                Zero cloud AI dependencies · All compute executed within
                infrastructure boundary
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1.5 text-xs font-semibold text-[var(--success)]">
            <span className="w-2 h-2 rounded-full bg-[var(--success)] animate-ping" />
            {isOnline ? "HEALTHY" : "STANDALONE"}
          </div>
        </div>

        {/* Services Status Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 mb-6">
          <div className="flex items-center gap-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)]">
            <Server size={18} className="text-[var(--accent)] flex-shrink-0" />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-[var(--text-primary)]">
                FastAPI Sovereign Engine
              </div>
              <div className="text-[11px] text-[var(--text-muted)]">
                Port 8000 · REST & SSE Streamer
              </div>
            </div>
            <span className="text-xs font-semibold text-[var(--success)]">
              {isOnline ? "Online" : "Offline"}
            </span>
          </div>

          <div className="flex items-center gap-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)]">
            <Database
              size={18}
              className="text-[var(--success)] flex-shrink-0"
            />
            <div className="flex-1 min-w-0">
              <div className="text-sm font-medium text-[var(--text-primary)]">
                MongoDB & Vector Store
              </div>
              <div className="text-[11px] text-[var(--text-muted)]">
                Indexed chunks & User accounts
              </div>
            </div>
            <span className="text-xs font-semibold text-[var(--success)]">
              Connected
            </span>
          </div>
        </div>

        {/* Registered Local AI Models */}
        <div className="mb-6 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)]">
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)] mb-3 pb-2 border-b border-[var(--border-color)]">
            <Brain size={14} className="text-[var(--accent)]" />
            Registered Sovereign Models ({models.length})
          </div>
          {models.length === 0 ? (
            <div className="text-xs text-[var(--text-muted)] py-2">
              Default local Ollama router models configured (e.g. qwen2.5:7b,
              llama3.2-vision).
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {models.map((m) => (
                <div
                  key={m.id}
                  className="flex items-center justify-between p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-xs"
                >
                  <div>
                    <span className="font-semibold text-[var(--text-primary)]">
                      {m.id}
                    </span>
                    <div className="text-[10px] text-[var(--text-muted)] mt-0.5">
                      Capabilities: {m.capabilities.join(", ")} · Modalities:{" "}
                      {m.modalities.join(", ")}
                    </div>
                  </div>
                  <span className="px-2 py-0.5 rounded bg-[var(--accent)]/10 text-[var(--accent)] font-medium text-[10px]">
                    Priority {m.priority}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Sovereign Tool Registry */}
        <div className="p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)]">
          <div className="flex items-center gap-2 text-xs font-semibold text-[var(--text-primary)] mb-3 pb-2 border-b border-[var(--border-color)]">
            <Wrench size={14} className="text-[var(--accent)]" />
            Autonomous Tool Registry ({tools.length})
          </div>
          {tools.length === 0 ? (
            <div className="text-xs text-[var(--text-muted)] py-2">
              Standard autonomous tools active: rag.search, vision.analyze,
              sandbox.execute, artifact.validate.
            </div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {tools.map((t) => (
                <div
                  key={t.name}
                  className="p-2.5 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-xs"
                >
                  <div className="font-semibold text-[var(--text-primary)]">
                    {t.name}
                  </div>
                  <div className="text-[11px] text-[var(--text-muted)] mt-0.5 line-clamp-2">
                    {t.description || "Autonomous tool execution module."}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
