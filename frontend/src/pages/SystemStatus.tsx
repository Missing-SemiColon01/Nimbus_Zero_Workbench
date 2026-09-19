import { useState } from 'react';
import { RefreshCw, Cpu, MemoryStick, Zap, Database, FileText, Shield, CheckCircle } from 'lucide-react';
import { useToast } from '../components/ui/Toast';

function ProgressBar({ value, color = 'var(--accent)' }: { value: number; color?: string }) {
  const c = value > 85 ? 'var(--danger)' : value > 65 ? 'var(--warning)' : color;
  return (
    <div className="w-full h-1.5 bg-[var(--bg-input)] rounded-full overflow-hidden">
      <div className="h-full rounded-full transition-all duration-700" style={{ width: `${value}%`, background: c }} />
    </div>
  );
}

export function SystemStatus() {
  const [metrics, setMetrics] = useState({ gpu: 68, cpu: 42, memory: 71, disk: 38, temp: 62 });
  const [refreshing, setRefreshing] = useState(false);
  const { showToast } = useToast();

  function handleRefresh() {
    setRefreshing(true);
    setTimeout(() => {
      setMetrics({
        gpu: Math.floor(50 + Math.random() * 40),
        cpu: Math.floor(25 + Math.random() * 50),
        memory: Math.floor(55 + Math.random() * 35),
        disk: Math.floor(30 + Math.random() * 20),
        temp: Math.floor(55 + Math.random() * 20),
      });
      setRefreshing(false);
      showToast('Status refreshed');
    }, 1200);
  }

  const services = [
    { name: 'AI Engine', status: 'Online', uptime: '99.97%', color: 'var(--success)' },
    { name: 'Knowledge Base', status: 'Online', uptime: '99.99%', color: 'var(--success)' },
    { name: 'Document Processor', status: 'Online', uptime: '100%', color: 'var(--success)' },
    { name: 'Security Gateway', status: 'Active', uptime: '100%', color: 'var(--success)' },
  ];

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-3xl mx-auto">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h1 className="text-xl font-semibold text-[var(--text-primary)]">System Status</h1>
            <p className="text-sm text-[var(--text-muted)]">Real-time infrastructure monitoring</p>
          </div>
          <button onClick={handleRefresh} disabled={refreshing} className="flex items-center gap-2 px-3 py-2 rounded-lg bg-[var(--bg-card)] border border-[var(--border-color)] text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors disabled:opacity-60">
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} /> Refresh
          </button>
        </div>

        {/* Services */}
        <div className="grid grid-cols-2 gap-3 mb-6">
          {services.map(s => (
            <div key={s.name} className="flex items-center gap-3 p-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)]">
              <CheckCircle size={16} style={{ color: s.color }} className="flex-shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="text-sm font-medium text-[var(--text-primary)]">{s.name}</div>
                <div className="text-[11px] text-[var(--text-muted)]">Uptime: {s.uptime}</div>
              </div>
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full" style={{ color: s.color, background: `${s.color}18` }}>{s.status}</span>
            </div>
          ))}
        </div>

        {/* Resource metrics */}
        <div className="rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] p-5">
          <div className="text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase mb-4">Resource Usage</div>
          <div className="flex flex-col gap-4">
            {[
              { icon: Zap, label: 'GPU', value: metrics.gpu, unit: '%' },
              { icon: Cpu, label: 'CPU', value: metrics.cpu, unit: '%' },
              { icon: MemoryStick, label: 'Memory', value: metrics.memory, unit: '%' },
              { icon: Database, label: 'Disk', value: metrics.disk, unit: '%' },
              { icon: Zap, label: 'Temperature', value: metrics.temp, unit: '°C', max: 100 },
            ].map(m => {
              const pct = m.max ? Math.round((m.value / m.max) * 100) : m.value;
              return (
                <div key={m.label}>
                  <div className="flex items-center justify-between mb-1.5">
                    <div className="flex items-center gap-2 text-xs text-[var(--text-secondary)]">
                      <m.icon size={12} className="text-[var(--text-muted)]" /> {m.label}
                    </div>
                    <span className="text-xs font-semibold text-[var(--text-primary)]">{m.value}{m.unit}</span>
                  </div>
                  <ProgressBar value={pct} />
                </div>
              );
            })}
          </div>
        </div>

        {/* Log sample */}
        <div className="mt-4 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] p-4">
          <div className="text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase mb-3">Recent Activity</div>
          {[
            { time: '09:41:22', event: 'AI inference completed — session SIH26117', level: 'info' },
            { time: '09:38:05', event: 'Document indexed: safety_briefing_unit3.pdf', level: 'info' },
            { time: '09:22:14', event: 'Agent activity: Maintenance Analyst completed', level: 'info' },
            { time: '08:55:03', event: 'Security gateway: session authenticated', level: 'success' },
            { time: '08:12:47', event: 'System health check passed', level: 'success' },
          ].map((log, i) => (
            <div key={i} className="flex items-start gap-3 py-1.5 border-b border-[var(--border-color)] last:border-0">
              <span className="font-mono text-[10px] text-[var(--text-muted)] flex-shrink-0 mt-0.5">{log.time}</span>
              <span className={`text-[11px] ${log.level === 'success' ? 'text-[var(--success)]' : 'text-[var(--text-secondary)]'}`}>{log.event}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
