import { useState, useRef, useCallback } from 'react';
import { Send, Square, Paperclip, Image as ImageIcon, X } from 'lucide-react';
import { AttachmentChip } from './FileAttachment';
import { Tooltip } from '../ui/Tooltip';
import { useToast } from '../ui/Toast';
import type { Attachment } from '../../types';

const ACCEPTED_TYPES = '.pdf,.docx,.txt,.csv,.xlsx,.png,.jpg,.jpeg';
const MAX_SIZE = 50 * 1024 * 1024; // 50MB

interface ChatComposerProps {
  onSend: (content: string, attachments: Attachment[]) => void;
  streaming: boolean;
  onStop: () => void;
  disabled?: boolean;
}

export function ChatComposer({ onSend, streaming, onStop, disabled }: ChatComposerProps) {
  const [value, setValue] = useState('');
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  function autoResize() {
    const ta = textareaRef.current;
    if (!ta) return;
    ta.style.height = 'auto';
    ta.style.height = `${Math.min(ta.scrollHeight, 200)}px`;
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  function handleSend() {
    if (!value.trim() && attachments.length === 0) return;
    if (streaming) return;
    onSend(value.trim(), attachments);
    setValue('');
    setAttachments([]);
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  }

  async function processFile(file: File): Promise<Attachment | null> {
    if (file.size > MAX_SIZE) {
      showToast(`${file.name}: File too large (max 50MB)`, 'error');
      return null;
    }
    const ext = file.name.split('.').pop()?.toLowerCase() || '';
    const typeMap: Record<string, Attachment['type']> = {
      pdf: 'pdf', docx: 'docx', txt: 'txt', csv: 'csv', xlsx: 'xlsx',
      png: 'image', jpg: 'image', jpeg: 'image'
    };
    const type = typeMap[ext];
    if (!type) {
      showToast(`${file.name}: Unsupported file type`, 'error');
      return null;
    }
    const att: Attachment = { id: `att-${Date.now()}-${Math.random()}`, name: file.name, type, size: file.size };
    if (type === 'image') {
      att.dataUrl = await new Promise<string>(resolve => {
        const reader = new FileReader();
        reader.onload = e => resolve(e.target?.result as string);
        reader.readAsDataURL(file);
      });
    }
    return att;
  }

  async function handleFiles(files: FileList | File[]) {
    const arr = Array.from(files);
    const results = await Promise.all(arr.map(processFile));
    const valid = results.filter(Boolean) as Attachment[];
    if (valid.length > 0) {
      setAttachments(prev => [...prev, ...valid]);
      showToast(`${valid.length} file${valid.length > 1 ? 's' : ''} attached`);
    }
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    handleFiles(e.dataTransfer.files);
  }

  const canSend = (value.trim().length > 0 || attachments.length > 0) && !streaming && !disabled;

  return (
    <div className="px-4 pb-4 pt-2 flex-shrink-0">
      <div
        className={`relative rounded-2xl border transition-all ${dragOver ? 'border-[var(--accent)] shadow-[0_0_0_3px_rgba(124,92,255,0.2)]' : 'border-[var(--border-color)] hover:border-[var(--accent)]/40'}`}
        style={{ background: 'var(--bg-input)' }}
        onDragOver={e => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
      >
        {/* Attachments preview */}
        {attachments.length > 0 && (
          <div className="px-4 pt-3 flex flex-wrap gap-2">
            {attachments.map(att => (
              <AttachmentChip key={att.id} attachment={att} onRemove={() => {
                setAttachments(prev => prev.filter(a => a.id !== att.id));
                showToast('Attachment removed', 'info');
              }} />
            ))}
          </div>
        )}

        {/* Textarea */}
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => { setValue(e.target.value); autoResize(); }}
          onKeyDown={handleKeyDown}
          placeholder="Ask anything or attach a file..."
          rows={1}
          disabled={disabled}
          className="w-full bg-transparent px-4 pt-4 pb-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] resize-none focus:outline-none leading-relaxed"
          style={{ minHeight: '52px', maxHeight: '200px' }}
          aria-label="Chat input"
        />

        {/* Bottom row */}
        <div className="flex items-center gap-2 px-4 pb-3 pt-1">
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept={ACCEPTED_TYPES}
            className="hidden"
            onChange={e => e.target.files && handleFiles(e.target.files)}
          />
          <Tooltip content="Attach files">
            <button
              onClick={() => fileInputRef.current?.click()}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
              aria-label="Attach files"
            >
              <Paperclip size={14} /> Attach
            </button>
          </Tooltip>
          <Tooltip content="Upload image">
            <button
              onClick={() => { fileInputRef.current && (fileInputRef.current.accept = '.png,.jpg,.jpeg'); fileInputRef.current?.click(); }}
              className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-[11px] text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors"
              aria-label="Upload image"
            >
              <ImageIcon size={14} /> Image
            </button>
          </Tooltip>

          <div className="flex-1" />

          {streaming ? (
            <Tooltip content="Stop generation">
              <button
                onClick={onStop}
                className="flex items-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium bg-[var(--danger)]/10 text-[var(--danger)] border border-[var(--danger)]/30 hover:bg-[var(--danger)]/20 transition-colors"
                aria-label="Stop generation"
              >
                <Square size={12} /> Stop
              </button>
            </Tooltip>
          ) : (
            <Tooltip content="Send message (Enter)">
              <button
                onClick={handleSend}
                disabled={!canSend}
                className={`flex items-center justify-center w-8 h-8 rounded-xl transition-all ${canSend ? 'bg-[var(--accent)] text-white hover:bg-[var(--accent-light)] shadow-lg' : 'bg-[var(--bg-card)] text-[var(--text-muted)] cursor-not-allowed'}`}
                aria-label="Send message"
              >
                <Send size={14} />
              </button>
            </Tooltip>
          )}
        </div>
      </div>
      <div className="text-center text-[10px] text-[var(--text-muted)] mt-2">
        Sovereign AI processes all data on-premise · No external transmission
      </div>
    </div>
  );
}
