import { useState, useRef, useEffect, type MouseEvent } from "react"
import { useNavigate, useLocation } from "react-router-dom"
import {
  Plus,
  Search,
  MoreHorizontal,
  Pin,
  Pencil,
  Trash2,
  MessageSquare,
  Settings,
  User,
} from "lucide-react"
import { Modal } from "../ui/Modal"
import { Tooltip } from "../ui/Tooltip"
import { useToast } from "../ui/Toast"
import type { Session } from "../../types"

interface SidebarProps {
  sessions: Session[]
  activeId: string | null
  onSelectSession: (id: string) => void
  onCreateSession: (title: string) => void
  onRenameSession: (id: string, title: string) => void
  onDeleteSession: (id: string) => void
  onPinSession: (id: string) => void
  collapsed: boolean
  onToggleCollapse: () => void
}

export function Sidebar({
  sessions,
  activeId,
  onSelectSession,
  onCreateSession,
  onRenameSession,
  onDeleteSession,
  onPinSession,
  collapsed,
  onToggleCollapse,
}: SidebarProps) {
  const [search, setSearch] = useState("")
  const [newSessionModal, setNewSessionModal] = useState(false)
  const [newSessionTitle, setNewSessionTitle] = useState("")
  const [renameModal, setRenameModal] = useState<{
    id: string
    title: string
  } | null>(null)
  const [deleteModal, setDeleteModal] = useState<string | null>(null)
  const [menuOpen, setMenuOpen] = useState<string | null>(null)
  const searchRef = useRef<HTMLInputElement>(null)
  const navigate = useNavigate()
  const location = useLocation()
  const { showToast } = useToast()

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "k") {
        e.preventDefault()
        searchRef.current?.focus()
      }
    }
    document.addEventListener("keydown", handler)
    return () => document.removeEventListener("keydown", handler)
  }, [])

  useEffect(() => {
    const closeMenu = () => setMenuOpen(null)
    document.addEventListener("click", closeMenu)
    return () => document.removeEventListener("click", closeMenu)
  }, [])

  const filtered = sessions.filter((s) =>
    s.title.toLowerCase().includes(search.toLowerCase()),
  )
  const pinned = filtered.filter((s) => s.pinned)
  const regular = filtered.filter((s) => !s.pinned)

  function handleCreate() {
    if (!newSessionTitle.trim()) return
    onCreateSession(newSessionTitle.trim())
    setNewSessionTitle("")
    setNewSessionModal(false)
    navigate("/")
    showToast("Session created")
  }

  function handleRename() {
    if (!renameModal || !renameModal.title.trim()) return
    onRenameSession(renameModal.id, renameModal.title.trim())
    setRenameModal(null)
    showToast("Session renamed")
  }

  function handleDelete(id: string) {
    onDeleteSession(id)
    setDeleteModal(null)
    showToast("Session deleted", "info")
  }

  function handlePin(id: string, pinned: boolean) {
    onPinSession(id)
    showToast(pinned ? "Session unpinned" : "Session pinned")
  }

  function formatTime(date: Date) {
    const now = Date.now()
    const diff = now - date.getTime()
    if (diff < 60000) return "Just now"
    if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`
    if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`
    return `${Math.floor(diff / 86400000)}d ago`
  }

  const navItems = [
    { icon: MessageSquare, label: "Chats", path: "/" },
    { icon: Settings, label: "Settings", path: "/settings" },
  ]

  if (collapsed) {
    return (
      <aside
        className="flex flex-col items-center py-4 gap-3 border-r border-[var(--border-color)] bg-[var(--bg-sidebar)]"
        style={{ width: 56 }}
      >
        <button
          onClick={onToggleCollapse}
          className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
          aria-label="Expand sidebar"
        >
          <div className="w-4 h-4 flex flex-col gap-1 justify-center">
            <div className="h-0.5 bg-current rounded" />
            <div className="h-0.5 bg-current rounded" />
            <div className="h-0.5 bg-current rounded" />
          </div>
        </button>
        <Tooltip content="New Session" side="right">
          <button
            onClick={() => {
              onToggleCollapse()
              setNewSessionModal(true)
            }}
            className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5"
          >
            <Plus size={18} />
          </button>
        </Tooltip>
        <div className="flex-1" />
        {navItems.map((n) => (
          <Tooltip key={n.path} content={n.label} side="right">
            <button
              onClick={() => navigate(n.path)}
              className={`p-2 rounded-lg transition-colors ${
                location.pathname === n.path
                  ? "text-[var(--accent)]"
                  : "text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              } hover:bg-white/5`}
            >
              <n.icon size={18} />
            </button>
          </Tooltip>
        ))}
      </aside>
    )
  }

  return (
    <>
      <aside
        className="flex flex-col h-full bg-[var(--bg-sidebar)] border-r border-[var(--border-color)]"
        style={{ width: 280 }}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--border-color)]">
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 rounded-lg bg-[var(--accent)] flex items-center justify-center flex-shrink-0">
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path
                  d="M7 1L9.5 5.5H12L8.5 8.5L9.5 13L7 10.5L4.5 13L5.5 8.5L2 5.5H4.5L7 1Z"
                  fill="white"
                  fillRule="evenodd"
                />
              </svg>
            </div>
            <div>
              <div className="text-sm font-semibold text-[var(--text-primary)] leading-tight">
                Nimbus Zero
              </div>
              <div className="text-[10px] font-medium tracking-widest text-[var(--text-muted)] uppercase leading-tight">
                On-Premise
              </div>
            </div>
          </div>
          <button
            onClick={onToggleCollapse}
            className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
            aria-label="Collapse sidebar"
          >
            <div className="w-4 h-4 flex flex-col gap-1 justify-center">
              <div className="h-0.5 bg-current rounded" />
              <div className="h-0.5 bg-current rounded" />
              <div className="h-0.5 bg-current rounded" />
            </div>
          </button>
        </div>

        {/* New Session */}
        <div className="px-3 pt-3">
          <button
            onClick={() => setNewSessionModal(true)}
            className="w-full flex items-center gap-2 px-3 py-2.5 rounded-lg border border-dashed border-[var(--border-color)] text-[var(--text-secondary)] hover:border-[var(--accent)] hover:text-[var(--accent)] transition-all text-sm font-medium group"
          >
            <Plus
              size={15}
              className="group-hover:rotate-90 transition-transform"
            />
            New Session
          </button>
        </div>

        {/* Search */}
        <div className="px-3 pt-2">
          <div className="relative">
            <Search
              size={13}
              className="absolute left-2.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
            />
            <input
              ref={searchRef}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search conversations..."
              className="w-full bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg pl-8 pr-3 py-2 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
            />
            <span className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[9px] text-[var(--text-muted)] hidden md:block">
              ⌘K
            </span>
          </div>
        </div>

        {/* Sessions */}
        <div className="flex-1 overflow-y-auto px-2 pt-3 pb-2">
          {pinned.length > 0 && (
            <>
              <div className="px-2 pb-1.5 text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase flex items-center gap-1.5">
                <Pin size={9} /> Pinned
              </div>
              {pinned.map((s) => (
                <SessionItem
                  key={s.id}
                  session={s}
                  active={s.id === activeId}
                  menuOpen={menuOpen === s.id}
                  onSelect={() => {
                    onSelectSession(s.id)
                    navigate("/")
                  }}
                  onMenuToggle={(e) => {
                    e.stopPropagation()
                    setMenuOpen(menuOpen === s.id ? null : s.id)
                  }}
                  onRename={() => setRenameModal({ id: s.id, title: s.title })}
                  onPin={() => handlePin(s.id, s.pinned)}
                  onDelete={() => setDeleteModal(s.id)}
                  formatTime={formatTime}
                />
              ))}
              <div className="my-2 border-t border-[var(--border-color)]" />
            </>
          )}

          <div className="px-2 pb-1.5 text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase">
            Sessions
          </div>

          {regular.length === 0 && search && (
            <div className="px-2 py-4 text-xs text-[var(--text-muted)] text-center">
              No conversations found
            </div>
          )}
          {regular.length === 0 && !search && (
            <div className="px-2 py-4 text-xs text-[var(--text-muted)] text-center">
              No sessions yet. Create one above.
            </div>
          )}
          {regular.map((s) => (
            <SessionItem
              key={s.id}
              session={s}
              active={s.id === activeId}
              menuOpen={menuOpen === s.id}
              onSelect={() => {
                onSelectSession(s.id)
                navigate("/")
              }}
              onMenuToggle={(e) => {
                e.stopPropagation()
                setMenuOpen(menuOpen === s.id ? null : s.id)
              }}
              onRename={() => setRenameModal({ id: s.id, title: s.title })}
              onPin={() => handlePin(s.id, s.pinned)}
              onDelete={() => setDeleteModal(s.id)}
              formatTime={formatTime}
            />
          ))}
        </div>

        {/* Bottom Nav */}
        <div className="border-t border-[var(--border-color)] px-2 py-2 flex flex-col gap-0.5">
          {navItems.map((n) => (
            <button
              key={n.path}
              onClick={() => navigate(n.path)}
              className={`w-full flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-colors ${
                location.pathname === n.path
                  ? "bg-white/5 text-[var(--text-primary)]"
                  : "text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5"
              }`}
            >
              <n.icon size={15} />
              {n.label}
            </button>
          ))}
        </div>
      </aside>

      {/* New Session Modal */}
      <Modal
        open={newSessionModal}
        onClose={() => setNewSessionModal(false)}
        title="New Session"
      >
        <div className="flex flex-col gap-4">
          <div>
            <label className="block text-xs text-[var(--text-secondary)] mb-1.5">
              Session Name
            </label>
            <input
              autoFocus
              value={newSessionTitle}
              onChange={(e) => setNewSessionTitle(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreate()
              }}
              placeholder="e.g. Hydrotreater Unit 3 Analysis"
              className="w-full bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg px-3 py-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setNewSessionModal(false)}
              className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleCreate}
              disabled={!newSessionTitle.trim()}
              className="px-4 py-2 text-sm bg-[var(--accent)] text-white rounded-lg font-medium disabled:opacity-40 hover:bg-[var(--accent-light)] transition-colors"
            >
              Create Session
            </button>
          </div>
        </div>
      </Modal>

      {/* Rename Modal */}
      <Modal
        open={!!renameModal}
        onClose={() => setRenameModal(null)}
        title="Rename Session"
      >
        <div className="flex flex-col gap-4">
          <input
            autoFocus
            value={renameModal?.title || ""}
            onChange={(e) =>
              setRenameModal((r) =>
                r ? { ...r, title: e.target.value } : null,
              )
            }
            onKeyDown={(e) => {
              if (e.key === "Enter") handleRename()
            }}
            className="w-full bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg px-3 py-2.5 text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] transition-colors"
          />
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setRenameModal(null)}
              className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleRename}
              className="px-4 py-2 text-sm bg-[var(--accent)] text-white rounded-lg font-medium hover:bg-[var(--accent-light)] transition-colors"
            >
              Rename
            </button>
          </div>
        </div>
      </Modal>

      {/* Delete Modal */}
      <Modal
        open={!!deleteModal}
        onClose={() => setDeleteModal(null)}
        title="Delete Session"
      >
        <div className="flex flex-col gap-4">
          <p className="text-sm text-[var(--text-secondary)]">
            Delete this session? This action cannot be undone.
          </p>
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => setDeleteModal(null)}
              className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={() => deleteModal && handleDelete(deleteModal)}
              className="px-4 py-2 text-sm bg-[var(--danger)] text-white rounded-lg font-medium hover:opacity-90 transition-opacity"
            >
              Delete
            </button>
          </div>
        </div>
      </Modal>
    </>
  )
}

function SessionItem({
  session,
  active,
  menuOpen,
  onSelect,
  onMenuToggle,
  onRename,
  onPin,
  onDelete,
  formatTime,
}: {
  session: Session
  active: boolean
  menuOpen: boolean
  onSelect: () => void
  onMenuToggle: (e: MouseEvent) => void
  onRename: () => void
  onPin: () => void
  onDelete: () => void
  formatTime: (d: Date) => string
}) {
  return (
    <div
      onClick={onSelect}
      className={`relative group flex items-center px-2 py-2 rounded-lg cursor-pointer transition-all mb-0.5 ${
        active ? "bg-white/8" : "hover:bg-white/4"
      }`}
      style={active ? { background: "rgba(124,92,255,0.1)" } : undefined}
    >
      <div className="flex-1 min-w-0">
        <div
          className={`text-xs font-medium truncate ${
            active
              ? "text-[var(--text-primary)]"
              : "text-[var(--text-secondary)] group-hover:text-[var(--text-primary)]"
          }`}
        >
          {session.title}
        </div>
        <div className="text-[11px] text-[var(--text-muted)] truncate mt-0.5 flex items-center gap-1">
          {session.pinned && <Pin size={8} />}
          {session.subtitle} · {formatTime(session.updatedAt)}
        </div>
      </div>
      <div className="relative flex-shrink-0 ml-1">
        <button
          onClick={onMenuToggle}
          className={`p-1 rounded transition-opacity ${
            menuOpen ? "opacity-100" : "opacity-0 group-hover:opacity-100"
          } hover:bg-white/10 text-[var(--text-muted)] hover:text-[var(--text-primary)]`}
          aria-label="Session options"
        >
          <MoreHorizontal size={13} />
        </button>
        {menuOpen && (
          <div
            className="absolute right-0 top-full mt-1 z-50 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg shadow-xl py-1 min-w-[130px]"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              onClick={onRename}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
            >
              <Pencil size={12} /> Rename
            </button>
            <button
              onClick={onPin}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
            >
              <Pin size={12} /> {session.pinned ? "Unpin" : "Pin"}
            </button>
            <button
              onClick={onDelete}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-[var(--danger)] hover:bg-white/5 transition-colors"
            >
              <Trash2 size={12} /> Delete
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
