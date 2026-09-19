import { useState } from 'react';
import { ChevronDown, ChevronRight, CheckCircle, Loader, Clock } from 'lucide-react';
import type { AgentStep } from '../../types';

interface AgentActivityProps {
  steps: AgentStep[];
  streaming?: boolean;
}

export function AgentActivity({ steps, streaming }: AgentActivityProps) {
  const [expanded, setExpanded] = useState(false);
  const doneCount = steps.filter(s => s.status === 'done').length;

  return (
    <div className="rounded-lg border border-[var(--border-color)] bg-[var(--bg-input)] mt-3">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center gap-2 px-3 py-2.5 text-left hover:bg-white/3 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-[var(--text-secondary)] flex-1">
          {streaming ? <Loader size={11} className="animate-spin text-[var(--accent)]" /> : <CheckCircle size={11} className="text-[var(--success)]" />}
          Agent activity · {streaming ? `${doneCount} steps completed` : `${steps.length} steps completed`}
        </div>
        {expanded ? <ChevronDown size={12} className="text-[var(--text-muted)]" /> : <ChevronRight size={12} className="text-[var(--text-muted)]" />}
      </button>
      {expanded && (
        <div className="px-3 pb-3 flex flex-col gap-1.5">
          {steps.map(step => (
            <div key={step.id} className="flex items-center gap-2 text-[11px]">
              {step.status === 'done' ? (
                <CheckCircle size={11} className="text-[var(--success)] flex-shrink-0" />
              ) : step.status === 'active' ? (
                <Loader size={11} className="animate-spin text-[var(--accent)] flex-shrink-0" />
              ) : (
                <Clock size={11} className="text-[var(--text-muted)] flex-shrink-0" />
              )}
              <span className={step.status === 'done' ? 'text-[var(--text-secondary)]' : step.status === 'active' ? 'text-[var(--text-primary)]' : 'text-[var(--text-muted)]'}>
                {step.label}
              </span>
              {step.duration && <span className="ml-auto text-[10px] text-[var(--text-muted)]">{step.duration}</span>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
