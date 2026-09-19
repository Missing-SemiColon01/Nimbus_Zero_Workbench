import { useState } from 'react';
import { Shield, Lock, Server, Database, Eye, FileText, ChevronRight } from 'lucide-react';
import { Modal } from '../components/ui/Modal';

const SECURITY_CARDS = [
  {
    id: 'on-premise',
    icon: Server,
    title: 'On-Premise Processing',
    subtitle: 'All AI inference runs locally',
    color: 'var(--success)',
    detail: 'The Sovereign AI Engine runs entirely on your organization\'s infrastructure. Model weights, inference, and data processing never leave your network boundary. GPU compute is allocated from your on-premise hardware pool.',
  },
  {
    id: 'no-external',
    icon: Shield,
    title: 'No External API Dependency',
    subtitle: 'Zero cloud API calls',
    color: 'var(--accent)',
    detail: 'Sovereign AI does not call any external AI APIs including OpenAI, Anthropic, Google, or any other cloud provider. The system is fully air-gapped from external AI services and operates independently.',
  },
  {
    id: 'encrypted',
    icon: Lock,
    title: 'Encrypted Storage',
    subtitle: 'AES-256 encryption at rest',
    color: 'var(--warning)',
    detail: 'All stored data including session history, uploaded documents, and knowledge base indices are encrypted using AES-256 at rest. Encryption keys are managed locally through your HSM or key management infrastructure.',
  },
  {
    id: 'rbac',
    icon: Eye,
    title: 'Role-Based Access Control',
    subtitle: 'Granular permission management',
    color: 'var(--accent-light)',
    detail: 'Access to sessions, documents, and AI capabilities is governed by role-based access policies. Roles include Operator, Analyst, Engineer, and Administrator, each with configurable capability scopes.',
  },
  {
    id: 'audit',
    icon: FileText,
    title: 'Audit Logging',
    subtitle: 'Immutable activity trail',
    color: 'var(--success)',
    detail: 'Every user action, AI inference, document upload, and system event is logged to an immutable audit trail. Logs are tamper-evident and can be exported for compliance reporting against ISO 27001, SOC 2, and industry standards.',
  },
];

export function Security() {
  const [selected, setSelected] = useState<string | null>(null);
  const card = SECURITY_CARDS.find(c => c.id === selected);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        {/* Hero status */}
        <div className="rounded-2xl border border-[var(--success)]/30 bg-[var(--success)]/5 p-8 mb-6 text-center">
          <div className="flex justify-center mb-3">
            <div className="w-12 h-12 rounded-2xl bg-[var(--success)]/10 flex items-center justify-center">
              <Shield size={22} className="text-[var(--success)]" />
            </div>
          </div>
          <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-1">Security Center</h1>
          <div className="text-sm text-[var(--success)] font-medium mb-2">SECURE ENVIRONMENT · ALL SYSTEMS NOMINAL</div>
          <p className="text-xs text-[var(--text-muted)] max-w-md mx-auto">
            Sovereign AI Workbench operates in a fully on-premise, air-gapped configuration. All data remains within your organizational infrastructure.
          </p>
        </div>

        {/* Cards */}
        <div className="flex flex-col gap-3">
          {SECURITY_CARDS.map(c => {
            const Icon = c.icon;
            return (
              <button key={c.id} onClick={() => setSelected(c.id)} className="flex items-center gap-4 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-color)] text-left group transition-all hover:bg-[var(--bg-card)]">
                <div className="w-9 h-9 rounded-xl flex items-center justify-center flex-shrink-0" style={{ background: `${c.color}15`, border: `1px solid ${c.color}25` }}>
                  <Icon size={16} style={{ color: c.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium text-[var(--text-primary)]">{c.title}</div>
                  <div className="text-xs text-[var(--text-muted)]">{c.subtitle}</div>
                </div>
                <ChevronRight size={14} className="text-[var(--text-muted)] group-hover:text-[var(--text-primary)] transition-colors" />
              </button>
            );
          })}
        </div>
      </div>

      <Modal open={!!selected} onClose={() => setSelected(null)} title={card?.title || ''}>
        {card && (
          <div>
            <div className="flex items-center gap-2 mb-3">
              <span className="inline-block w-2 h-2 rounded-full" style={{ background: card.color }} />
              <span className="text-xs text-[var(--text-muted)]">{card.subtitle}</span>
            </div>
            <p className="text-sm text-[var(--text-secondary)] leading-relaxed">{card.detail}</p>
          </div>
        )}
      </Modal>
    </div>
  );
}
