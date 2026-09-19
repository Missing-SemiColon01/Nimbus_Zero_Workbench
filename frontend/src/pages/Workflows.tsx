import { useState, useRef } from 'react';
import { Plus, Save, Trash2, Edit2, Copy, GitBranch, Upload, Brain, Database, BarChart2, AlertTriangle, FileText, CheckSquare } from 'lucide-react';
import { Modal } from '../components/ui/Modal';
import { useToast } from '../components/ui/Toast';
import type { WorkflowNode } from '../types';
import { DEFAULT_WORKFLOW_NODES } from '../services/mockData';

const NODE_TYPES = [
  { type: 'input', label: 'Document Upload', icon: Upload, color: '#7C5CFF' },
  { type: 'process', label: 'Document Extraction', icon: FileText, color: '#20C997' },
  { type: 'ai', label: 'AI Analysis', icon: Brain, color: '#9B87FF' },
  { type: 'search', label: 'Knowledge Retrieval', icon: Database, color: '#F5B942' },
  { type: 'analytics', label: 'Data Analysis', icon: BarChart2, color: '#20C997' },
  { type: 'condition', label: 'Risk Assessment', icon: AlertTriangle, color: '#FF5C5C' },
  { type: 'output', label: 'Report Generation', icon: FileText, color: '#7C5CFF' },
  { type: 'approval', label: 'Human Approval', icon: CheckSquare, color: '#8B91A1' },
];

function getNodeConfig(type: string) {
  return NODE_TYPES.find(n => n.type === type) || NODE_TYPES[0];
}

export function Workflows() {
  const [nodes, setNodes] = useState<WorkflowNode[]>(DEFAULT_WORKFLOW_NODES as WorkflowNode[]);
  const [dragging, setDragging] = useState<string | null>(null);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [editNode, setEditNode] = useState<WorkflowNode | null>(null);
  const [editLabel, setEditLabel] = useState('');
  const [deleteNodeId, setDeleteNodeId] = useState<string | null>(null);
  const [addModal, setAddModal] = useState(false);
  const canvasRef = useRef<HTMLDivElement>(null);
  const { showToast } = useToast();

  function handleMouseDown(e: React.MouseEvent, nodeId: string) {
    const node = nodes.find(n => n.id === nodeId);
    if (!node || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    setDragging(nodeId);
    setDragOffset({ x: e.clientX - rect.left - node.x, y: e.clientY - rect.top - node.y });
  }

  function handleMouseMove(e: React.MouseEvent) {
    if (!dragging || !canvasRef.current) return;
    const rect = canvasRef.current.getBoundingClientRect();
    const x = Math.max(0, Math.min(e.clientX - rect.left - dragOffset.x, rect.width - 180));
    const y = Math.max(0, e.clientY - rect.top - dragOffset.y);
    setNodes(prev => prev.map(n => n.id === dragging ? { ...n, x, y } : n));
  }

  function addNode(type: string, label: string) {
    const newNode: WorkflowNode = { id: `wn-${Date.now()}`, type, label, x: 300, y: 100 + nodes.length * 80 };
    setNodes(prev => [...prev, newNode]);
    setAddModal(false);
    showToast('Node added');
  }

  function handleEdit() {
    if (!editNode) return;
    setNodes(prev => prev.map(n => n.id === editNode.id ? { ...n, label: editLabel } : n));
    setEditNode(null);
    showToast('Node updated');
  }

  function handleDelete(id: string) {
    setNodes(prev => prev.filter(n => n.id !== id));
    setDeleteNodeId(null);
    showToast('Node deleted', 'info');
  }

  function handleSave() {
    showToast('Workflow saved');
  }

  const sortedByY = [...nodes].sort((a, b) => a.y - b.y);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-6 py-4 border-b border-[var(--border-color)] flex-shrink-0">
        <div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">Industrial AI Workflows</h1>
          <p className="text-sm text-[var(--text-muted)]">Design automated analysis pipelines</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setAddModal(true)} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">
            <Plus size={14} /> Add Node
          </button>
          <button onClick={handleSave} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--accent)] text-white text-sm font-medium hover:bg-[var(--accent-light)] transition-colors">
            <Save size={14} /> Save
          </button>
        </div>
      </div>

      <div className="flex-1 flex overflow-hidden">
        {/* Canvas */}
        <div
          ref={canvasRef}
          className="flex-1 relative overflow-auto select-none"
          style={{ background: 'var(--bg-base)', backgroundImage: 'radial-gradient(var(--border-color) 1px, transparent 1px)', backgroundSize: '24px 24px', minHeight: 600 }}
          onMouseMove={handleMouseMove}
          onMouseUp={() => setDragging(null)}
          onMouseLeave={() => setDragging(null)}
        >
          {/* Draw edges */}
          <svg className="absolute inset-0 w-full h-full pointer-events-none" style={{ minHeight: 700 }}>
            {sortedByY.slice(0, -1).map((node, i) => {
              const next = sortedByY[i + 1];
              const x1 = node.x + 90;
              const y1 = node.y + 40;
              const x2 = next.x + 90;
              const y2 = next.y;
              return (
                <line key={`edge-${node.id}`} x1={x1} y1={y1} x2={x2} y2={y2}
                  stroke="var(--border-color)" strokeWidth="1.5" strokeDasharray="4 3" />
              );
            })}
          </svg>

          {/* Nodes */}
          {nodes.map(node => {
            const cfg = getNodeConfig(node.type);
            const Icon = cfg.icon;
            return (
              <div
                key={node.id}
                className="absolute group rounded-xl border bg-[var(--bg-card)] cursor-move select-none"
                style={{ left: node.x, top: node.y, width: 180, borderColor: dragging === node.id ? cfg.color : 'var(--border-color)', boxShadow: dragging === node.id ? `0 0 0 2px ${cfg.color}33` : undefined }}
                onMouseDown={e => handleMouseDown(e, node.id)}
              >
                <div className="flex items-center gap-2 px-3 py-2.5">
                  <div className="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0" style={{ background: `${cfg.color}20` }}>
                    <Icon size={12} style={{ color: cfg.color }} />
                  </div>
                  <span className="text-xs font-medium text-[var(--text-primary)] truncate flex-1">{node.label}</span>
                  <div className="flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity" onMouseDown={e => e.stopPropagation()}>
                    <button onClick={() => { setEditNode(node); setEditLabel(node.label); }} className="p-0.5 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                      <Edit2 size={10} />
                    </button>
                    <button onClick={() => { addNode(node.type, `${node.label} (copy)`); }} className="p-0.5 rounded text-[var(--text-muted)] hover:text-[var(--text-primary)]">
                      <Copy size={10} />
                    </button>
                    <button onClick={() => setDeleteNodeId(node.id)} className="p-0.5 rounded text-[var(--text-muted)] hover:text-[var(--danger)]">
                      <Trash2 size={10} />
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Sidebar */}
        <div className="w-48 border-l border-[var(--border-color)] bg-[var(--bg-sidebar)] p-3 flex-shrink-0 overflow-y-auto hidden md:block">
          <div className="text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase mb-2">Node Types</div>
          {NODE_TYPES.map(nt => {
            const Icon = nt.icon;
            return (
              <button key={nt.type} onClick={() => addNode(nt.type, nt.label)} className="w-full flex items-center gap-2 px-2.5 py-2 rounded-lg text-left text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors mb-0.5">
                <Icon size={12} style={{ color: nt.color }} />
                {nt.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Add Node Modal (mobile) */}
      <Modal open={addModal} onClose={() => setAddModal(false)} title="Add Node">
        <div className="grid grid-cols-2 gap-2">
          {NODE_TYPES.map(nt => {
            const Icon = nt.icon;
            return (
              <button key={nt.type} onClick={() => addNode(nt.type, nt.label)} className="flex items-center gap-2 p-3 rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] hover:border-[var(--accent)]/40 text-left transition-colors">
                <Icon size={14} style={{ color: nt.color }} />
                <span className="text-xs text-[var(--text-secondary)]">{nt.label}</span>
              </button>
            );
          })}
        </div>
      </Modal>

      {/* Edit Node Modal */}
      <Modal open={!!editNode} onClose={() => setEditNode(null)} title="Edit Node">
        <div className="flex flex-col gap-4">
          <input value={editLabel} onChange={e => setEditLabel(e.target.value)} onKeyDown={e => { if (e.key === 'Enter') handleEdit(); }} className="w-full bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg px-3 py-2.5 text-sm text-[var(--text-primary)] focus:outline-none focus:border-[var(--accent)] transition-colors" />
          <div className="flex gap-2 justify-end">
            <button onClick={() => setEditNode(null)} className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Cancel</button>
            <button onClick={handleEdit} className="px-4 py-2 text-sm bg-[var(--accent)] text-white rounded-lg font-medium hover:bg-[var(--accent-light)] transition-colors">Save</button>
          </div>
        </div>
      </Modal>

      {/* Delete Modal */}
      <Modal open={!!deleteNodeId} onClose={() => setDeleteNodeId(null)} title="Delete Node">
        <p className="text-sm text-[var(--text-secondary)] mb-4">Remove this node from the workflow?</p>
        <div className="flex gap-2 justify-end">
          <button onClick={() => setDeleteNodeId(null)} className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Cancel</button>
          <button onClick={() => deleteNodeId && handleDelete(deleteNodeId)} className="px-4 py-2 text-sm bg-[var(--danger)] text-white rounded-lg font-medium hover:opacity-90 transition-opacity">Delete</button>
        </div>
      </Modal>
    </div>
  );
}
