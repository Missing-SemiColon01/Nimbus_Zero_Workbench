import { useState, useRef, useEffect } from "react"
import {
  Search,
  Upload,
  Trash2,
  Download,
  Eye,
  FileText,
  FileSpreadsheet,
  File,
  RefreshCw,
} from "lucide-react"
import { useToast } from "../components/ui/Toast"
import { Modal } from "../components/ui/Modal"
import { artifactService, type ArtifactInfo } from "../services/artifactService"
import { knowledgeService } from "../services/knowledgeService"

function FileIcon({ type }: { type: string }) {
  const t = type.toLowerCase()
  if (t === "csv" || t === "xlsx")
    return <FileSpreadsheet size={18} className="text-[var(--success)]" />
  if (t === "pdf" || t === "docx" || t === "pptx")
    return <FileText size={18} className="text-[var(--accent)]" />
  return <File size={18} className="text-[var(--text-muted)]" />
}

interface DisplayDoc {
  id: string
  name: string
  type: string
  size: string
  uploadedAt: Date
  downloadUrl?: string
  previewUrl?: string | null
}

export function Documents() {
  const [docs, setDocs] = useState<DisplayDoc[]>([])
  const [loading, setLoading] = useState(true)
  const [search, setSearch] = useState("")
  const [sort, setSort] = useState<"newest" | "oldest" | "name">("newest")
  const [preview, setPreview] = useState<DisplayDoc | null>(null)
  const [deleteId, setDeleteId] = useState<string | null>(null)
  const [dragging, setDragging] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { showToast } = useToast()

  const loadArtifacts = async () => {
    setLoading(true)
    try {
      const artifacts = await artifactService.fetchArtifacts()
      const mapped: DisplayDoc[] = artifacts.map((a: ArtifactInfo) => ({
        id: a.filename,
        name: a.filename,
        type: a.file_type,
        size:
          a.size_bytes > 1024 * 1024
            ? `${(a.size_bytes / (1024 * 1024)).toFixed(1)} MB`
            : `${Math.round(a.size_bytes / 1024)} KB`,
        uploadedAt: new Date(a.modified_at),
        downloadUrl: artifactService.getDownloadUrl(a.filename),
        previewUrl: a.preview_url
          ? artifactService.getPreviewUrl(a.preview_url.split("/").pop() || "")
          : null,
      }))
      setDocs(mapped)
    } catch {
      showToast("Could not load deliverables", "error")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadArtifacts()
  }, [])

  const filtered = docs
    .filter((d) => d.name.toLowerCase().includes(search.toLowerCase()))
    .sort((a, b) => {
      if (sort === "name") return a.name.localeCompare(b.name)
      if (sort === "oldest")
        return a.uploadedAt.getTime() - b.uploadedAt.getTime()
      return b.uploadedAt.getTime() - a.uploadedAt.getTime()
    })

  async function handleUpload(files: FileList | File[]) {
    const list = Array.from(files)
    for (const f of list) {
      try {
        showToast(`Uploading ${f.name}...`)
        await knowledgeService.uploadDocument(f)
        showToast(`${f.name} ingested successfully.`)
      } catch (err: any) {
        showToast(`Upload failed for ${f.name}: ${err.message}`, "error")
      }
    }
    loadArtifacts()
  }

  function handleDelete(id: string) {
    setDocs((prev) => prev.filter((d) => d.id !== id))
    setDeleteId(null)
    showToast("Removed from view", "info")
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-color)] flex-shrink-0">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">
            Documents & Deliverables
          </h1>
          <p className="text-sm text-[var(--text-muted)]">
            {docs.length} generated deliverables & files
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={loadArtifacts}
            disabled={loading}
            className="p-2 rounded-lg border border-[var(--border-color)] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
          >
            <RefreshCw size={14} className={loading ? "animate-spin" : ""} />
          </button>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => e.target.files && handleUpload(e.target.files)}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-light)] transition-colors"
          >
            <Upload size={14} /> Upload Document
          </button>
        </div>
      </div>

      <div className="px-6 py-3 border-b border-[var(--border-color)] flex gap-3 flex-shrink-0">
        <div className="relative flex-1">
          <Search
            size={13}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]"
          />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search documents..."
            className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg pl-9 pr-3 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
          />
        </div>
        <select
          value={sort}
          onChange={(e) => setSort(e.target.value as any)}
          className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg px-3 py-2 text-sm text-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent)] transition-colors"
        >
          <option value="newest">Newest</option>
          <option value="oldest">Oldest</option>
          <option value="name">Name</option>
        </select>
      </div>

      {/* Drop zone + list */}
      <div
        className={`flex-1 overflow-y-auto ${
          dragging ? "ring-2 ring-[var(--accent)] ring-inset" : ""
        }`}
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          handleUpload(e.dataTransfer.files)
        }}
      >
        {dragging && (
          <div className="absolute inset-0 z-10 flex items-center justify-center bg-[var(--accent)]/5">
            <div className="text-[var(--accent)] text-sm font-medium">
              Drop files to upload and ingest
            </div>
          </div>
        )}
        <div className="p-6">
          {loading && docs.length === 0 ? (
            <div className="text-center py-16 text-[var(--text-muted)] text-sm flex items-center justify-center gap-2">
              <RefreshCw
                size={16}
                className="animate-spin text-[var(--accent)]"
              />{" "}
              Loading deliverables...
            </div>
          ) : filtered.length === 0 ? (
            <div className="text-center py-16 text-[var(--text-muted)] text-sm">
              {search
                ? "No documents match your search"
                : "No deliverables generated yet. Ask Sovereign AI in Chat to create a presentation (.pptx), report (.docx/.pdf), or spreadsheet (.xlsx)."}
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {/* Header */}
              <div className="grid grid-cols-[1fr_90px_120px_100px] gap-4 px-3 py-1 text-[10px] text-[var(--text-muted)] uppercase tracking-wide">
                <span>Name</span>
                <span>Size</span>
                <span>Modified</span>
                <span className="text-right">Actions</span>
              </div>
              {filtered.map((doc) => (
                <div
                  key={doc.id}
                  className="grid grid-cols-[1fr_90px_120px_100px] gap-4 items-center px-3 py-3 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-color)] transition-all group"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <FileIcon type={doc.type} />
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-[var(--text-primary)] truncate">
                        {doc.name}
                      </div>
                      <div className="text-[10px] text-[var(--text-muted)] uppercase">
                        {doc.type} deliverable
                      </div>
                    </div>
                  </div>
                  <span className="text-xs text-[var(--text-secondary)]">
                    {doc.size}
                  </span>
                  <span className="text-xs text-[var(--text-secondary)]">
                    {doc.uploadedAt.toLocaleDateString()}
                  </span>
                  <div className="flex gap-1 justify-end">
                    {doc.previewUrl && (
                      <button
                        onClick={() => setPreview(doc)}
                        className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
                        title="Preview"
                      >
                        <Eye size={13} />
                      </button>
                    )}
                    {doc.downloadUrl ? (
                      <a
                        href={doc.downloadUrl}
                        download={doc.name}
                        target="_blank"
                        rel="noreferrer"
                        className="p-1.5 rounded-lg text-[var(--accent)] hover:bg-[var(--accent)]/10 transition-colors"
                        title="Download"
                      >
                        <Download size={13} />
                      </a>
                    ) : (
                      <button
                        onClick={() => showToast("Download started")}
                        className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
                      >
                        <Download size={13} />
                      </button>
                    )}
                    <button
                      onClick={() => setDeleteId(doc.id)}
                      className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--danger)] hover:bg-white/5 transition-colors"
                      title="Remove"
                    >
                      <Trash2 size={13} />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      <Modal
        open={!!preview}
        onClose={() => setPreview(null)}
        title={preview?.name || ""}
        maxWidth="max-w-2xl"
      >
        <div className="text-sm text-[var(--text-secondary)]">
          {preview?.previewUrl ? (
            <div className="rounded-lg overflow-hidden border border-[var(--border-color)] mb-4 bg-black/20 flex items-center justify-center p-2">
              <img
                src={preview.previewUrl}
                alt={preview.name}
                className="max-h-[480px] w-auto object-contain rounded shadow"
              />
            </div>
          ) : (
            <div className="rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] p-6 text-center text-[var(--text-muted)] mb-4">
              Preview thumbnail is not available for this format.
            </div>
          )}
          <div className="flex gap-2">
            {preview?.downloadUrl && (
              <a
                href={preview.downloadUrl}
                download={preview.name}
                className="px-4 py-2 bg-[var(--accent)] text-white rounded-lg text-sm font-medium hover:bg-[var(--accent-light)] transition-colors inline-flex items-center gap-1.5"
              >
                <Download size={14} /> Download File
              </a>
            )}
            <button
              onClick={() => setPreview(null)}
              className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors"
            >
              Close
            </button>
          </div>
        </div>
      </Modal>

      <Modal
        open={!!deleteId}
        onClose={() => setDeleteId(null)}
        title="Remove Document"
      >
        <p className="text-sm text-[var(--text-secondary)] mb-4">
          Remove this document from the local list view?
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
