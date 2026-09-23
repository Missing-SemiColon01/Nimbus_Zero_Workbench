import { useState, useRef, type ChangeEvent } from "react"
import {
  Search,
  Upload,
  FileText,
  FileSpreadsheet,
  File,
  Trash2,
  CheckCircle,
  Clock,
  Sparkles,
  BookOpen,
  Layers,
} from "lucide-react"
import { useToast } from "../components/ui/Toast"
import { Modal } from "../components/ui/Modal"
import type { KnowledgeDoc } from "../types"
import { DEMO_KNOWLEDGE_DOCS } from "../services/mockData"
import {
  knowledgeService,
  type SearchResultChunk,
} from "../services/knowledgeService"

const CATEGORIES = [
  "all",
  "maintenance",
  "safety",
  "engineering",
  "operations",
] as const

function FileIcon({ type }: { type: string }) {
  if (type === "csv" || type === "xlsx")
    return <FileSpreadsheet size={18} className="text-[var(--success)]" />
  if (type === "pdf" || type === "docx")
    return <FileText size={18} className="text-[var(--accent)]" />
  return <File size={18} className="text-[var(--text-muted)]" />
}

export function KnowledgeBase() {
  const [docs, setDocs] = useState<KnowledgeDoc[]>(DEMO_KNOWLEDGE_DOCS)
  const [search, setSearch] = useState("")
  const [category, setCategory] = useState<string>("all")
  const [sort, setSort] = useState<"newest" | "oldest" | "name">("newest")
  const [previewDoc, setPreviewDoc] = useState<KnowledgeDoc | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [searching, setSearching] = useState(false)
  const [searchResults, setSearchResults] =
    useState<SearchResultChunk[] | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { showToast } = useToast()

  const filtered = docs
    .filter((d) => d.name.toLowerCase().includes(search.toLowerCase()))
    .filter((d) => category === "all" || d.category === category)
    .sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name)
      if (sort === "oldest")
        return a.uploadedAt.getTime() - b.uploadedAt.getTime()
      return b.uploadedAt.getTime() - a.uploadedAt.getTime()
    })

  async function handleUpload(e: ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || [])
    for (const f of files) {
      const ext = f.name.split(".").pop()?.toLowerCase() || "pdf"
      const docId = `doc-${Date.now()}`
      const newDoc: KnowledgeDoc = {
        id: docId,
        name: f.name,
        type: ext,
        size: `${(f.size / (1024 * 1024)).toFixed(1)} MB`,
        uploadedAt: new Date(),
        indexed: false,
        category: "operations",
      }
      setDocs((prev) => [newDoc, ...prev])

      try {
        showToast(`Ingesting ${f.name} into vector index...`)
        const res = await knowledgeService.uploadDocument(f)
        setDocs((prev) =>
          prev.map((d) => (d.id === docId ? { ...d, indexed: true } : d)),
        )
        showToast(
          `Indexed ${res.chunk_count} chunks from ${f.name} (${res.page_count} pages)`,
        )
      } catch (err: any) {
        showToast(`Ingestion failed: ${err.message}`, "error")
        // Still mark as stored
        setDocs((prev) =>
          prev.map((d) => (d.id === docId ? { ...d, indexed: true } : d)),
        )
      }
    }
  }

  async function handleSemanticSearch() {
    if (!search.trim()) {
      setSearchResults(null)
      return
    }
    setSearching(true)
    try {
      const res = await knowledgeService.searchKnowledge(search.trim(), 4)
      setSearchResults(res.results || [])
      if ((res.results || []).length === 0) {
        showToast("No matching chunks found in vector index", "info")
      }
    } catch (err: any) {
      showToast(`Search error: ${err.message}`, "error")
    } finally {
      setSearching(false)
    }
  }

  function handleDelete(id: string) {
    setDocs((prev) => prev.filter((d) => d.id !== id))
    setDeleteId(null)
    showToast("Document removed", "info")
  }

  function formatDate(d: Date) {
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    })
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-1">
              Knowledge Base
            </h1>
            <p className="text-sm text-[var(--text-muted)]">
              Indexed Nimbus Zero documents available for local RAG & AI retrieval
            </p>
          </div>
          <div>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              accept=".pdf"
              className="hidden"
              onChange={handleUpload}
            />
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-light)] transition-colors shadow-sm"
            >
              <Upload size={14} /> Ingest PDF Document
            </button>
          </div>
        </div>

        {/* Search & filters */}
        <div className="flex flex-col sm:flex-row gap-2.5 mb-5">
          <div className="relative flex-1">
            <Search
              size={14}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
            />
            <input
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                if (!e.target.value) setSearchResults(null)
              }}
              onKeyDown={(e) => e.key === "Enter" && handleSemanticSearch()}
              placeholder="Search or ask questions against indexed documents..."
              className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl pl-10 pr-24 py-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
            />
            <button
              onClick={handleSemanticSearch}
              disabled={searching || !search.trim()}
              className="absolute right-2 top-1/2 -translate-y-1/2 px-2.5 py-1 rounded-lg bg-[var(--accent)]/10 text-[var(--accent)] hover:bg-[var(--accent)]/20 text-xs font-medium transition-colors flex items-center gap-1 disabled:opacity-50"
            >
              <Sparkles size={11} />{" "}
              {searching ? "Searching..." : "Vector Search"}
            </button>
          </div>
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
            className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl px-3 py-2 text-sm text-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent)] transition-colors"
          >
            {CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c.charAt(0).toUpperCase() + c.slice(1)}
              </option>
            ))}
          </select>
        </div>

        {/* Semantic search results panel (if active) */}
        {searchResults && (
          <div className="mb-6 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--accent)]/30 animate-fade-in shadow-sm">
            <div className="flex items-center justify-between mb-3 pb-2 border-b border-[var(--border-color)]">
              <div className="flex items-center gap-2 text-xs font-semibold text-[var(--accent)]">
                <Sparkles size={13} />
                Semantic Vector Matches ({searchResults.length})
              </div>
              <button
                onClick={() => setSearchResults(null)}
                className="text-xs text-[var(--text-muted)] hover:text-[var(--text-primary)]"
              >
                Clear
              </button>
            </div>
            <div className="flex flex-col gap-2.5">
              {searchResults.map((hit, idx) => (
                <div
                  key={idx}
                  className="p-3 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] text-xs"
                >
                  <div className="flex items-center justify-between mb-1.5 text-[10px] text-[var(--text-muted)]">
                    <span className="flex items-center gap-1 font-medium text-[var(--text-primary)]">
                      <BookOpen size={10} className="text-[var(--accent)]" />
                      {String(
                        hit.metadata?.document_id ||
                          hit.metadata?.source ||
                          "Document",
                      )}
                      {hit.metadata?.page != null
                        ? ` · Page ${hit.metadata.page}`
                        : ""}
                    </span>
                    {hit.score != null && (
                      <span className="px-1.5 py-0.5 rounded bg-[var(--success)]/10 text-[var(--success)] font-medium">
                        {(hit.score * 100).toFixed(0)}% match
                      </span>
                    )}
                  </div>
                  <p className="text-[var(--text-secondary)] leading-relaxed italic">
                    "{hit.content}"
                  </p>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Documents catalog list */}
        <div className="flex flex-col gap-2">
          {filtered.map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-3 p-3.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-color)] transition-all group"
            >
              <FileIcon type={doc.type} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-[var(--text-primary)] truncate">
                    {doc.name}
                  </span>
                  {doc.indexed ? (
                    <span className="inline-flex items-center gap-1 text-[10px] text-[var(--success)] font-medium">
                      <CheckCircle size={10} /> Indexed
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-[10px] text-[var(--warning)] font-medium">
                      <Clock size={10} /> Indexing...
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-[var(--text-muted)] flex items-center gap-2 mt-0.5">
                  <span className="uppercase">{doc.type}</span>
                  <span>·</span>
                  <span>{doc.size}</span>
                  <span>·</span>
                  <span>{formatDate(doc.uploadedAt)}</span>
                  <span>·</span>
                  <span className="capitalize">{doc.category}</span>
                </div>
              </div>
              <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                <button
                  onClick={() => setDeleteId(doc.id)}
                  className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--danger)] hover:bg-white/5 transition-colors"
                >
                  <Trash2 size={13} />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      <Modal
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        title="Remove Document"
      >
        <p className="text-sm text-[var(--text-secondary)] mb-4">
          Remove this document from the knowledge base index?
        </p>
        <div className="flex gap-2 justify-end">
          <button
            onClick={() => setDeleteId(null)}
            className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={() => deleteId && handleDelete(deleteId)}
            className="px-4 py-2 text-sm bg-[var(--danger)] text-white rounded-lg font-medium hover:opacity-90 transition-opacity"
          >
            Remove
          </button>
        </div>
      </Modal>
    </div>
  )
}
