import { useState } from "react"
import {
  X,
  FileText,
  FileSpreadsheet,
  Image as ImageIcon,
  File,
  Eye,
  Download,
} from "lucide-react"
import type { Attachment } from "../../types"

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function FileIcon({ type }: { type: Attachment["type"] }) {
  const classes = "flex-shrink-0"
  switch (type) {
    case "csv":
    case "xlsx":
      return (
        <FileSpreadsheet
          size={16}
          className={`${classes} text-[var(--success)]`}
        />
      )
    case "pdf":
    case "docx":
    case "txt":
      return (
        <FileText size={16} className={`${classes} text-[var(--accent)]`} />
      )
    case "image":
      return (
        <ImageIcon size={16} className={`${classes} text-[var(--warning)]`} />
      )
    default:
      return (
        <File size={16} className={`${classes} text-[var(--text-muted)]`} />
      )
  }
}

export function AttachmentChip({
  attachment,
  onRemove,
}: {
  attachment: Attachment
  onRemove?: () => void
}) {
  const [showPreview, setShowPreview] = useState(false)
  const isImage = attachment.type === "image" && (attachment.dataUrl || attachment.url)

  return (
    <>
      <div className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] max-w-[240px]">
        {isImage ? (
          <button
            type="button"
            onClick={() => setShowPreview(true)}
            className="relative group cursor-pointer focus:outline-none flex-shrink-0"
            title="Click to view image"
          >
            <img
              src={attachment.dataUrl || attachment.url}
              alt={attachment.name}
              className="w-8 h-8 rounded object-cover flex-shrink-0 border border-white/10 group-hover:opacity-80 transition-opacity"
            />
            <div className="absolute inset-0 bg-black/40 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <Eye size={12} className="text-white" />
            </div>
          </button>
        ) : (
          <FileIcon type={attachment.type} />
        )}
        <div className="min-w-0 flex-1">
          <div className="text-xs font-medium text-[var(--text-primary)] truncate" title={attachment.name}>
            {attachment.name}
          </div>
          <div className="text-[10px] text-[var(--text-muted)] uppercase">
            {attachment.type} · {formatSize(attachment.size)}
          </div>
        </div>
        {onRemove && (
          <button
            type="button"
            onClick={onRemove}
            className="text-[var(--text-muted)] hover:text-[var(--danger)] transition-colors flex-shrink-0"
            aria-label="Remove attachment"
          >
            <X size={12} />
          </button>
        )}
      </div>

      {showPreview && isImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/80 backdrop-blur-sm p-4 animate-fade-in"
          onClick={() => setShowPreview(false)}
        >
          <div
            className="relative max-w-4xl max-h-[90vh] bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl overflow-hidden shadow-2xl p-2 flex flex-col items-center"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="w-full flex items-center justify-between px-3 py-2 border-b border-[var(--border-color)] mb-2">
              <span className="text-xs font-medium text-[var(--text-primary)] truncate max-w-md">
                {attachment.name} ({formatSize(attachment.size)})
              </span>
              <button
                type="button"
                onClick={() => setShowPreview(false)}
                className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/10 transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <img
              src={attachment.dataUrl || attachment.url}
              alt={attachment.name}
              className="max-h-[75vh] max-w-full object-contain rounded"
            />
          </div>
        </div>
      )}
    </>
  )
}

export function MessageAttachment({
  attachment,
  onClick,
}: {
  attachment: Attachment
  onClick?: () => void
}) {
  const [showPreview, setShowPreview] = useState(false)
  const isImage = attachment.type === "image" && (attachment.dataUrl || attachment.url)

  const handleClick = () => {
    if (onClick) {
      onClick()
    } else if (isImage) {
      setShowPreview(true)
    } else if (attachment.dataUrl || attachment.url) {
      // Download non-image file
      const link = document.createElement("a")
      link.href = (attachment.dataUrl || attachment.url)!
      link.download = attachment.name
      link.click()
    }
  }

  return (
    <>
      <div
        onClick={handleClick}
        className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-black/20 border border-white/10 max-w-[240px] cursor-pointer hover:border-[var(--accent)]/40 hover:bg-black/30 transition-all group"
        title={isImage ? "Click to view full image" : "Click to download attachment"}
      >
        {isImage ? (
          <div className="relative flex-shrink-0">
            <img
              src={attachment.dataUrl || attachment.url}
              alt={attachment.name}
              className="w-10 h-10 rounded object-cover flex-shrink-0 border border-white/10"
            />
            <div className="absolute inset-0 bg-black/40 rounded flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <Eye size={14} className="text-white" />
            </div>
          </div>
        ) : (
          <FileIcon type={attachment.type} />
        )}
        <div className="min-w-0 flex-1">
          <div className="text-[11px] font-medium text-white/90 truncate group-hover:text-white">
            {attachment.name}
          </div>
          <div className="text-[10px] text-white/50 uppercase flex items-center gap-1">
            <span>{attachment.type} · {formatSize(attachment.size)}</span>
            {!isImage && <Download size={10} className="opacity-0 group-hover:opacity-100 transition-opacity ml-auto" />}
          </div>
        </div>
      </div>

      {showPreview && isImage && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4 animate-fade-in"
          onClick={() => setShowPreview(false)}
        >
          <div
            className="relative max-w-4xl max-h-[90vh] bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl overflow-hidden shadow-2xl p-2 flex flex-col items-center"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="w-full flex items-center justify-between px-3 py-2 border-b border-[var(--border-color)] mb-2">
              <span className="text-xs font-medium text-[var(--text-primary)] truncate max-w-md">
                {attachment.name} ({formatSize(attachment.size)})
              </span>
              <button
                type="button"
                onClick={() => setShowPreview(false)}
                className="p-1 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/10 transition-colors"
              >
                <X size={16} />
              </button>
            </div>
            <img
              src={attachment.dataUrl || attachment.url}
              alt={attachment.name}
              className="max-h-[75vh] max-w-full object-contain rounded"
            />
          </div>
        </div>
      )}
    </>
  )
}
