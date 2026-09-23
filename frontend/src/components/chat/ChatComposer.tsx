import {
  useState,
  useRef,
  type KeyboardEvent,
  type DragEvent,
  type ClipboardEvent,
} from "react"
import { Send, Square, Paperclip, Image as ImageIcon, UploadCloud } from "lucide-react"
import { AttachmentChip } from "./FileAttachment"
import { Tooltip } from "../ui/Tooltip"
import { useToast } from "../ui/Toast"
import type { Attachment } from "../../types"

const ALL_ACCEPTED_TYPES =
  ".pdf,.docx,.doc,.txt,.md,.json,.csv,.xlsx,.xls,.pptx,.ppt,.png,.jpg,.jpeg,.webp,.gif,.svg,.bmp"
const IMAGE_ACCEPTED_TYPES = ".png,.jpg,.jpeg,.webp,.gif,.svg,.bmp"
const MAX_SIZE = 50 * 1024 * 1024 // 50MB

interface ChatComposerProps {
  onSend: (content: string, attachments: Attachment[]) => void
  streaming: boolean
  onStop: () => void
  disabled?: boolean
}

export function ChatComposer({
  onSend,
  streaming,
  onStop,
  disabled,
}: ChatComposerProps) {
  const [value, setValue] = useState("")
  const [attachments, setAttachments] = useState<Attachment[]>([])
  const [dragOver, setDragOver] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const imageInputRef = useRef<HTMLInputElement>(null)
  const { showToast } = useToast()

  function autoResize() {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = "auto"
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`
  }

  function handleKeyDown(e: KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  function handleSend() {
    if (!value.trim() && attachments.length === 0) return
    if (streaming) return

    let contentToSend = value.trim()
    if (!contentToSend && attachments.length > 0) {
      const imgCount = attachments.filter((a) => a.type === "image").length
      const docCount = attachments.length - imgCount
      if (imgCount > 0 && docCount === 0) {
        contentToSend = `Please analyze the attached image${imgCount > 1 ? "s" : ""}: ${attachments.map((a) => a.name).join(", ")}`
      } else if (docCount > 0 && imgCount === 0) {
        contentToSend = `Please inspect and summarize the attached document${docCount > 1 ? "s" : ""}: ${attachments.map((a) => a.name).join(", ")}`
      } else {
        contentToSend = `Please review and analyze the attached files: ${attachments.map((a) => a.name).join(", ")}`
      }
    }

    onSend(contentToSend, attachments)
    setValue("")
    setAttachments([])
    if (textareaRef.current) textareaRef.current.style.height = "auto"
  }

  async function processFile(file: File): Promise<Attachment | null> {
    if (file.size > MAX_SIZE) {
      showToast(`${file.name}: File too large (max 50MB)`, "error")
      return null
    }

    const ext = file.name.split(".").pop()?.toLowerCase() || ""
    const typeMap: Record<string, Attachment["type"]> = {
      pdf: "pdf",
      docx: "docx",
      doc: "docx",
      txt: "txt",
      md: "txt",
      json: "txt",
      log: "txt",
      csv: "csv",
      xlsx: "xlsx",
      xls: "xlsx",
      pptx: "other",
      ppt: "other",
      png: "image",
      jpg: "image",
      jpeg: "image",
      webp: "image",
      gif: "image",
      svg: "image",
      bmp: "image",
    }

    let type: Attachment["type"] = typeMap[ext]
    if (!type) {
      if (file.type.startsWith("image/")) {
        type = "image"
      } else if (file.type.startsWith("text/")) {
        type = "txt"
      } else {
        type = "other"
      }
    }

    const att: Attachment = {
      id: `att-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      name: file.name || (type === "image" ? `pasted_image_${Date.now()}.png` : "attached_file"),
      type,
      size: file.size,
    }

    try {
      att.dataUrl = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader()
        reader.onload = (e) => resolve(e.target?.result as string)
        reader.onerror = (err) => reject(err)
        reader.readAsDataURL(file)
      })
      att.url = att.dataUrl
      return att
    } catch {
      showToast(`Failed to read file ${file.name}`, "error")
      return null
    }
  }

  async function handleFiles(files: FileList | File[]) {
    const arr = Array.from(files)
    if (!arr.length) return
    const results = await Promise.all(arr.map(processFile))
    const valid = results.filter(Boolean) as Attachment[]
    if (valid.length > 0) {
      setAttachments((prev) => [...prev, ...valid])
      showToast(`${valid.length} file${valid.length > 1 ? "s" : ""} attached`)
    }
  }

  function handlePaste(e: ClipboardEvent<HTMLTextAreaElement>) {
    const items = e.clipboardData?.items
    if (!items) return

    const filesToProcess: File[] = []
    for (let i = 0; i < items.length; i++) {
      const item = items[i]
      if (item.kind === "file") {
        const file = item.getAsFile()
        if (file) {
          filesToProcess.push(file)
        }
      }
    }

    if (filesToProcess.length > 0) {
      handleFiles(filesToProcess)
    }
  }

  function handleDragEnter(e: DragEvent) {
    e.preventDefault()
    setDragOver(true)
  }

  function handleDragOver(e: DragEvent) {
    e.preventDefault()
    setDragOver(true)
  }

  function handleDragLeave(e: DragEvent) {
    e.preventDefault()
    if (!e.currentTarget.contains(e.relatedTarget as Node)) {
      setDragOver(false)
    }
  }

  function handleDrop(e: DragEvent) {
    e.preventDefault()
    setDragOver(false)
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFiles(e.dataTransfer.files)
    }
  }

  const canSend =
    (value.trim().length > 0 || attachments.length > 0) &&
    !streaming &&
    !disabled

  return (
    <div className="px-4 pb-4 pt-2 flex-shrink-0">
      <div
        className={`relative rounded-2xl border transition-all ${
          dragOver
            ? "border-[var(--accent)] shadow-[0_0_0_3px_rgba(124,92,255,0.2)]"
            : "border-[var(--border-color)] hover:border-[var(--accent)]/40"
        }`}
        style={{ background: "var(--bg-input)" }}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {/* Drop overlay indicator */}
        {dragOver && (
          <div className="absolute inset-0 z-20 rounded-2xl bg-[var(--bg-card)]/90 backdrop-blur-sm border-2 border-dashed border-[var(--accent)] flex items-center justify-center gap-2 pointer-events-none text-[var(--accent-light)] font-medium text-xs">
            <UploadCloud size={20} className="animate-bounce" />
            <span>Drop images or documents here to attach</span>
          </div>
        )}

        {/* Attachments preview */}
        {attachments.length > 0 && (
          <div className="px-4 pt-3 flex flex-wrap gap-2">
            {attachments.map((att) => (
              <AttachmentChip
                key={att.id}
                attachment={att}
                onRemove={() => {
                  setAttachments((prev) => prev.filter((a) => a.id !== att.id))
                  showToast("Attachment removed", "info")
                }}
              />
            ))}
          </div>
        )}

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => {
            setValue(e.target.value)
            autoResize()
          }}
          onKeyDown={handleKeyDown}
          onPaste={handlePaste}
          placeholder="Ask anything, paste screenshots, or attach files..."
          rows={1}
          disabled={disabled}
          className="w-full bg-transparent px-4 pt-4 pb-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] resize-none focus:outline-none leading-relaxed"
          style={{ minHeight: "52px", maxHeight: "200px" }}
          aria-label="Chat input"
        />

        {/* Bottom row */}
        <div className="flex items-center gap-2 px-4 pb-3 pt-1">
          {/* Document / general file input */}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ALL_ACCEPTED_TYPES}
            className="hidden"
            onChange={(e) => {
              if (e.target.files) handleFiles(e.target.files)
              e.target.value = ""
            }}
          />
          {/* Dedicated image input */}
          <input
            ref={imageInputRef}
            type="file"
            multiple
            accept={IMAGE_ACCEPTED_TYPES}
            className="hidden"
            onChange={(e) => {
              if (e.target.files) handleFiles(e.target.files)
              e.target.value = ""
            }}
          />

          <Tooltip content="Attach documents or data files">
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors cursor-pointer"
              aria-label="Attach files"
            >
              <Paperclip size={14} /> Attach
            </button>
          </Tooltip>

          <Tooltip content="Upload image (or paste directly)">
            <button
              type="button"
              onClick={() => imageInputRef.current?.click()}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors cursor-pointer"
              aria-label="Upload image"
            >
              <ImageIcon size={14} /> Image
            </button>
          </Tooltip>

          <div className="flex-1" />

          {streaming ? (
            <Tooltip content="Stop generation">
              <button
                type="button"
                onClick={onStop}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium bg-[var(--danger)]/10 text-[var(--danger)] border border-[var(--danger)]/30 hover:bg-[var(--danger)]/20 transition-colors cursor-pointer"
                aria-label="Stop generation"
              >
                <Square size={12} /> Stop
              </button>
            </Tooltip>
          ) : (
            <Tooltip content="Send message (Enter)">
              <button
                type="button"
                onClick={handleSend}
                disabled={!canSend}
                className={`flex items-center justify-center w-8 h-8 rounded-xl transition-all ${
                  canSend
                    ? "bg-[var(--accent)] text-white hover:bg-[var(--accent-light)] shadow-lg cursor-pointer"
                    : "bg-[var(--bg-card)] text-[var(--text-muted)] cursor-not-allowed"
                }`}
                aria-label="Send message"
              >
                <Send size={14} />
              </button>
            </Tooltip>
          )}
        </div>
      </div>
      <div className="text-center text-[10px] text-[var(--text-muted)] mt-2">
        Nimbus Zero processes all data on-premise · No external transmission
      </div>
    </div>
  )
}
