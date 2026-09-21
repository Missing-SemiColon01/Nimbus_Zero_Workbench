import {
  X,
  FileText,
  FileSpreadsheet,
  Image as ImageIcon,
  File,
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
  return (
    <div className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] max-w-[240px]">
      {attachment.type === "image" && attachment.dataUrl ? (
        <img
          src={attachment.dataUrl}
          alt={attachment.name}
          className="w-8 h-8 rounded object-cover flex-shrink-0"
        />
      ) : (
        <FileIcon type={attachment.type} />
      )}
      <div className="min-w-0 flex-1">
        <div className="text-xs font-medium text-[var(--text-primary)] truncate">
          {attachment.name}
        </div>
        <div className="text-[10px] text-[var(--text-muted)] uppercase">
          {attachment.type} · {formatSize(attachment.size)}
        </div>
      </div>
      {onRemove && (
        <button
          onClick={onRemove}
          className="text-[var(--text-muted)] hover:text-[var(--danger)] transition-colors flex-shrink-0"
        >
          <X size={12} />
        </button>
      )}
    </div>
  )
}

export function MessageAttachment({
  attachment,
  onClick,
}: {
  attachment: Attachment
  onClick?: () => void
}) {
  return (
    <div
      onClick={onClick}
      className={`inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-black/20 border border-white/10 max-w-[220px] ${
        onClick
          ? "cursor-pointer hover:border-[var(--accent)]/40 transition-colors"
          : ""
      }`}
    >
      {attachment.type === "image" && attachment.dataUrl ? (
        <img
          src={attachment.dataUrl}
          alt={attachment.name}
          className="w-10 h-10 rounded object-cover flex-shrink-0"
        />
      ) : (
        <FileIcon type={attachment.type} />
      )}
      <div className="min-w-0 flex-1">
        <div className="text-[11px] font-medium text-white/90 truncate">
          {attachment.name}
        </div>
        <div className="text-[10px] text-white/50 uppercase">
          {attachment.type} · {formatSize(attachment.size)}
        </div>
      </div>
    </div>
  )
}
