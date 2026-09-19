import { useState, useRef } from 'react';
import { Search, Upload, FileText, FileSpreadsheet, File, Trash2, Download, Eye, CheckCircle, Clock, Filter } from 'lucide-react';
import { useToast } from '../components/ui/Toast';
import { Modal } from '../components/ui/Modal';
import type { KnowledgeDoc } from '../types';
import { DEMO_KNOWLEDGE_DOCS } from '../services/mockData';

const CATEGORIES = ['all', 'maintenance', 'safety', 'engineering', 'operations'] as const;

function FileIcon({ type }: { type: string }) {
  if (type === 'csv' || type === 'xlsx') return <FileSpreadsheet size={18} className="text-[var(--success)]" />;
  if (type === 'pdf' || type === 'docx') return <FileText size={18} className="text-[var(--accent)]" />;
  return <File size={18} className="text-[var(--text-muted)]" />;
}

export function KnowledgeBase() {
  const [docs, setDocs] = useState<KnowledgeDoc[]>(DEMO_KNOWLEDGE_DOCS);
  const [search, setSearch] = useState('');
  const [category, setCategory] = useState<string>('all');
  const [sort, setSort] = useState<'newest' | 'oldest' | 'name'>('newest');
  const [previewDoc, setPreviewDoc] = useState<KnowledgeDoc | null>(null);
  const [deleteId, setDeleteId] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  const filtered = docs
    .filter(d => d.name.toLowerCase().includes(search.toLowerCase()))
    .filter(d => category === 'all' || d.category === category)
    .sort((a, b) => {
      if (sort === 'name') return a.name.localeCompare(b.name);
      if (sort === 'oldest') return a.uploadedAt.getTime() - b.uploadedAt.getTime();
      return b.uploadedAt.getTime() - a.uploadedAt.getTime();
    });

  function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files || []);
    files.forEach(f => {
      const ext = f.name.split('.').pop()?.toLowerCase() || 'pdf';
      const newDoc: KnowledgeDoc = {
        id: `doc-${Date.now()}-${Math.random()}`,
        name: f.name,
        type: ext,
        size: `${(f.size / (1024 * 1024)).toFixed(1)} MB`,
        uploadedAt: new Date(),
        indexed: false,
        category: 'operations',
      };
      setDocs(prev => [newDoc, ...prev]);
      setTimeout(() => setDocs(prev => prev.map(d => d.id === newDoc.id ? { ...d, indexed: true } : d)), 2000);
    });
    showToast(`${files.length} document${files.length > 1 ? 's' : ''} uploaded`);
  }

  function handleDelete(id: string) {
    setDocs(prev => prev.filter(d => d.id !== id));
    setDeleteId(null);
    showToast('Document deleted', 'info');
  }

  function formatDate(d: Date) {
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-1">Knowledge Base</h1>
          <p className="text-sm text-[var(--text-muted)]">Indexed documents available for AI retrieval</p>
        </div>

        {/* Controls */}
        <div className="flex flex-col sm:flex-row gap-3 mb-5">
          <div className="relative flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)]" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search knowledge base..."
              className="w-full bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg pl-9 pr-3 py-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors"
            />
          </div>
          <select value={sort} onChange={e => setSort(e.target.value as any)} className="bg-[var(--bg-card)] border border-[var(--border-color)] rounded-lg px-3 py-2.5 text-sm text-[var(--text-secondary)] focus:outline-none focus:border-[var(--accent)] transition-colors">
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="name">Name</option>
          </select>
          <input ref={fileInputRef} type="file" multiple accept=".pdf,.docx,.txt,.csv,.xlsx" className="hidden" onChange={handleUpload} />
          <button onClick={() => fileInputRef.current?.click()} className="flex items-center gap-2 px-4 py-2.5 bg-[var(--accent)] text-white rounded-lg text-sm font-medium hover:bg-[var(--accent-light)] transition-colors flex-shrink-0">
            <Upload size={14} /> Upload
          </button>
        </div>

        {/* Category filters */}
        <div className="flex gap-2 mb-5 flex-wrap">
          {CATEGORIES.map(c => (
            <button key={c} onClick={() => setCategory(c)} className={`px-3 py-1 rounded-full text-xs font-medium transition-colors capitalize ${category === c ? 'bg-[var(--accent)] text-white' : 'bg-[var(--bg-card)] border border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'}`}>
              {c}
            </button>
          ))}
        </div>

        {/* Doc grid */}
        {filtered.length === 0 ? (
          <div className="text-center py-16 text-[var(--text-muted)] text-sm">No documents found</div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {filtered.map(doc => (
              <div key={doc.id} className="flex items-center gap-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-color)] transition-all group">
                <FileIcon type={doc.type} />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-[var(--text-primary)] truncate">{doc.name}</div>
                  <div className="text-[11px] text-[var(--text-muted)] mt-0.5 flex items-center gap-2">
                    <span className="uppercase">{doc.type}</span>
                    <span>·</span>
                    <span>{doc.size}</span>
                    <span>·</span>
                    <span>{formatDate(doc.uploadedAt)}</span>
                  </div>
                  <div className="flex items-center gap-1 mt-1">
                    {doc.indexed ? (
                      <span className="flex items-center gap-1 text-[10px] text-[var(--success)]"><CheckCircle size={9} /> Indexed</span>
                    ) : (
                      <span className="flex items-center gap-1 text-[10px] text-[var(--warning)]"><Clock size={9} /> Indexing...</span>
                    )}
                    <span className="text-[10px] text-[var(--text-muted)] ml-2 capitalize">{doc.category}</span>
                  </div>
                </div>
                <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button onClick={() => setPreviewDoc(doc)} className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors" title="Preview">
                    <Eye size={13} />
                  </button>
                  <button onClick={() => showToast('Download started')} className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors" title="Download">
                    <Download size={13} />
                  </button>
                  <button onClick={() => setDeleteId(doc.id)} className="p-1.5 rounded-lg text-[var(--text-muted)] hover:text-[var(--danger)] hover:bg-white/5 transition-colors" title="Delete">
                    <Trash2 size={13} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Preview modal */}
      <Modal open={!!previewDoc} onClose={() => setPreviewDoc(null)} title={previewDoc?.name || ''} maxWidth="max-w-2xl">
        <div className="text-sm text-[var(--text-secondary)] mb-4">
          <div className="flex gap-4 text-xs text-[var(--text-muted)] mb-4">
            <span className="uppercase">{previewDoc?.type}</span>
            <span>{previewDoc?.size}</span>
            <span>{previewDoc && formatDate(previewDoc.uploadedAt)}</span>
          </div>
          <div className="rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] p-6 text-center text-[var(--text-muted)] text-sm">
            Preview unavailable in demo mode
          </div>
        </div>
        <div className="flex gap-2">
          <button onClick={() => showToast('Download started')} className="px-4 py-2 bg-[var(--accent)] text-white rounded-lg text-sm font-medium hover:bg-[var(--accent-light)] transition-colors">Download</button>
          <button onClick={() => setPreviewDoc(null)} className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Close</button>
        </div>
      </Modal>

      {/* Delete modal */}
      <Modal open={!!deleteId} onClose={() => setDeleteId(null)} title="Delete Document">
        <p className="text-sm text-[var(--text-secondary)] mb-4">Permanently remove this document from the knowledge base?</p>
        <div className="flex gap-2 justify-end">
          <button onClick={() => setDeleteId(null)} className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Cancel</button>
          <button onClick={() => deleteId && handleDelete(deleteId)} className="px-4 py-2 text-sm bg-[var(--danger)] text-white rounded-lg font-medium hover:opacity-90 transition-opacity">Delete</button>
        </div>
      </Modal>
    </div>
  );
}
