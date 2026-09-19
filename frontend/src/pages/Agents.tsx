import { useState } from 'react';
import { Wrench, ShieldCheck, ScanEye, FileSearch, Play, CheckCircle, Loader, Clock } from 'lucide-react';
import { Modal } from '../components/ui/Modal';
import { AgentActivity } from '../components/chat/AgentActivity';
import { useToast } from '../components/ui/Toast';
import type { AgentStep } from '../types';
import { DEMO_AGENTS } from '../services/mockData';

const ICONS: Record<string, React.ComponentType<any>> = { Wrench, ShieldCheck, ScanEye, FileSearch };

const AGENT_STEPS: Record<string, string[]> = {
  'agent-1': ['Loaded maintenance records', 'Parsed equipment history', 'Identified anomaly patterns', 'Cross-referenced failure database', 'Generated maintenance report'],
  'agent-2': ['Parsed safety documents', 'Identified hazard categories', 'Checked regulatory compliance', 'Assessed risk levels', 'Prepared safety briefing'],
  'agent-3': ['Loaded equipment images', 'Ran visual inspection model', 'Detected surface anomalies', 'Assessed severity', 'Generated inspection report'],
  'agent-4': ['Extracted document content', 'Parsed document structure', 'Identified key entities', 'Cross-referenced knowledge base', 'Generated summary report'],
};

const RESULTS: Record<string, string> = {
  'agent-1': 'Analysis complete. Identified 3 equipment items approaching end-of-maintenance-interval. Pump P-203 shows bearing wear signatures consistent with imminent failure. Recommend proactive replacement within next 72-hour window.',
  'agent-2': 'Safety inspection complete. 2 high-priority gaps identified against ISO 45001 requirements. Hazardous materials storage procedure SOP-HM-04 requires immediate update. Fall protection inspection logs incomplete for Q4.',
  'agent-3': 'Image analysis complete. Visible corrosion detected on heat exchanger E-112 shell side nozzle. Classification: Moderate severity. Estimated remaining service life: 6-8 months at current degradation rate.',
  'agent-4': 'Document intelligence complete. Extracted 47 key technical specifications, 12 compliance requirements, and 8 action items. Full indexed summary available for knowledge base retrieval.',
};

export function Agents() {
  const [runModal, setRunModal] = useState<string | null>(null);
  const [task, setTask] = useState('');
  const [running, setRunning] = useState(false);
  const [steps, setSteps] = useState<AgentStep[]>([]);
  const [result, setResult] = useState<string | null>(null);
  const { showToast } = useToast();

  async function handleRun(agentId: string) {
    setRunning(true);
    setSteps([]);
    setResult(null);
    const agentSteps = AGENT_STEPS[agentId] || AGENT_STEPS['agent-1'];

    for (let i = 0; i < agentSteps.length; i++) {
      await new Promise(r => setTimeout(r, 700));
      setSteps(prev => [...prev, { id: `s-${i}`, label: agentSteps[i], status: 'done', duration: `${(0.5 + Math.random() * 2).toFixed(1)}s` }]);
    }
    setResult(RESULTS[agentId] || RESULTS['agent-1']);
    setRunning(false);
    showToast('Agent completed successfully');
  }

  const activeAgent = DEMO_AGENTS.find(a => a.id === runModal);

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-[var(--text-primary)] mb-1">AI Agents</h1>
          <p className="text-sm text-[var(--text-muted)]">Specialized industrial workflows powered by Sovereign AI Engine</p>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {DEMO_AGENTS.map(agent => {
            const Icon = ICONS[agent.icon] || Wrench;
            return (
              <div key={agent.id} className="p-5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] flex flex-col gap-3 hover:border-[var(--border-color)] transition-all">
                <div className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-xl bg-[var(--accent)]/10 border border-[var(--accent)]/20 flex items-center justify-center flex-shrink-0">
                    <Icon size={16} className="text-[var(--accent)]" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-[var(--text-primary)]">{agent.name}</div>
                    <div className="text-[11px] text-[var(--text-muted)] mt-0.5">{agent.category}</div>
                  </div>
                  <span className="flex items-center gap-1 text-[10px] text-[var(--success)] bg-[var(--success)]/10 px-2 py-0.5 rounded-full">
                    <span className="w-1 h-1 rounded-full bg-[var(--success)]" /> Ready
                  </span>
                </div>
                <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{agent.description}</p>
                {agent.lastRun && (
                  <div className="flex items-center gap-1 text-[10px] text-[var(--text-muted)]">
                    <Clock size={9} /> Last run: {agent.lastRun.toLocaleDateString()}
                  </div>
                )}
                <button onClick={() => { setRunModal(agent.id); setTask(''); setSteps([]); setResult(null); setRunning(false); }} className="flex items-center justify-center gap-2 px-4 py-2 rounded-lg bg-[var(--accent)]/10 border border-[var(--accent)]/20 text-xs font-medium text-[var(--accent)] hover:bg-[var(--accent)]/20 transition-colors mt-auto">
                  <Play size={12} /> Run Agent
                </button>
              </div>
            );
          })}
        </div>
      </div>

      <Modal open={!!runModal} onClose={() => { if (!running) setRunModal(null); }} title={`Run ${activeAgent?.name || ''}`} maxWidth="max-w-lg">
        <div className="flex flex-col gap-4">
          <div>
            <label className="block text-xs text-[var(--text-secondary)] mb-1.5">Task Description</label>
            <textarea
              value={task}
              onChange={e => setTask(e.target.value)}
              disabled={running || !!result}
              rows={3}
              placeholder="Describe what you want the agent to do..."
              className="w-full bg-[var(--bg-input)] border border-[var(--border-color)] rounded-lg px-3 py-2.5 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:border-[var(--accent)] transition-colors resize-none"
            />
          </div>

          {steps.length > 0 && <AgentActivity steps={steps} streaming={running} />}

          {result && (
            <div className="rounded-lg bg-[var(--bg-input)] border border-[var(--border-color)] p-4">
              <div className="flex items-center gap-1.5 text-[11px] font-semibold text-[var(--success)] mb-2">
                <CheckCircle size={12} /> RESULT
              </div>
              <p className="text-xs text-[var(--text-secondary)] leading-relaxed">{result}</p>
            </div>
          )}

          <div className="flex gap-2 justify-end">
            <button onClick={() => { if (!running) setRunModal(null); }} disabled={running} className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors disabled:opacity-50">Cancel</button>
            {!result ? (
              <button onClick={() => runModal && handleRun(runModal)} disabled={running} className="flex items-center gap-2 px-4 py-2 text-sm bg-[var(--accent)] text-white rounded-lg font-medium disabled:opacity-60 hover:bg-[var(--accent-light)] transition-colors">
                {running ? <><Loader size={13} className="animate-spin" /> Running...</> : <><Play size={13} /> Run Agent</>}
              </button>
            ) : (
              <button onClick={() => setRunModal(null)} className="px-4 py-2 text-sm bg-[var(--accent)] text-white rounded-lg font-medium hover:bg-[var(--accent-light)] transition-colors">Done</button>
            )}
          </div>
        </div>
      </Modal>
    </div>
  );
}
