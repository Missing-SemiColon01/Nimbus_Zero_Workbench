import { useState, type ReactNode } from 'react';
import { Sun, Moon, Monitor } from 'lucide-react';
import { Modal } from '../components/ui/Modal';
import { useToast } from '../components/ui/Toast';
import type { Theme, AppSettings } from '../types';

interface SettingsProps {
  theme: Theme;
  onSetTheme: (t: Theme) => void;
  onClearHistory: () => void;
}

function Toggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative w-9 h-5 rounded-full transition-colors flex-shrink-0 ${checked ? 'bg-[var(--accent)]' : 'bg-[var(--border-color)]'}`}
    >
      <span className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${checked ? 'translate-x-4' : 'translate-x-0.5'}`} />
    </button>
  );
}

export function Settings({ theme, onSetTheme, onClearHistory }: SettingsProps) {
  const [settings, setSettings] = useState<AppSettings>({
    theme,
    notifications: { aiCompletion: true, agentCompletion: true, securityAlerts: true },
    security: { sessionTimeout: true, auditLogging: true, secureProcessing: true },
  });
  const [clearModal, setClearModal] = useState(false);
  const { showToast } = useToast();

  function updateNotif(key: keyof AppSettings['notifications'], val: boolean) {
    setSettings(prev => ({ ...prev, notifications: { ...prev.notifications, [key]: val } }));
    showToast('Settings saved');
  }

  function updateSecurity(key: keyof AppSettings['security'], val: boolean) {
    setSettings(prev => ({ ...prev, security: { ...prev.security, [key]: val } }));
    showToast('Settings saved');
  }

  function handleClear() {
    onClearHistory();
    setClearModal(false);
    showToast('Chat history cleared', 'info');
  }

  return (
    <div className="flex-1 overflow-y-auto p-6">
      <div className="max-w-2xl mx-auto">
        <div className="mb-6">
          <h1 className="text-xl font-semibold text-[var(--text-primary)]">Settings</h1>
          <p className="text-sm text-[var(--text-muted)]">Configure your workbench preferences</p>
        </div>

        {/* Appearance */}
        <SettingsSection title="Appearance">
          <div>
            <div className="text-xs font-medium text-[var(--text-primary)] mb-3">Theme</div>
            <div className="flex gap-2">
              {([
                { val: 'dark', icon: Moon, label: 'Dark' },
                { val: 'light', icon: Sun, label: 'Light' },
              ] as const).map(t => {
                const Icon = t.icon;
                return (
                  <button
                    key={t.val}
                    onClick={() => { onSetTheme(t.val); showToast(`${t.label} mode enabled`); }}
                    className={`flex items-center gap-2 px-4 py-2.5 rounded-lg border text-sm transition-all ${theme === t.val ? 'border-[var(--accent)] bg-[var(--accent)]/10 text-[var(--accent)]' : 'border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'}`}
                  >
                    <Icon size={14} /> {t.label}
                  </button>
                );
              })}
            </div>
          </div>
        </SettingsSection>

        {/* Notifications */}
        <SettingsSection title="Notifications">
          {[
            { key: 'aiCompletion' as const, label: 'AI completion alerts', desc: 'Notify when AI response is ready' },
            { key: 'agentCompletion' as const, label: 'Agent completion alerts', desc: 'Notify when agent workflow completes' },
            { key: 'securityAlerts' as const, label: 'Security alerts', desc: 'Notify on security events' },
          ].map(item => (
            <SettingsRow key={item.key} label={item.label} desc={item.desc}>
              <Toggle checked={settings.notifications[item.key]} onChange={v => updateNotif(item.key, v)} />
            </SettingsRow>
          ))}
        </SettingsSection>

        {/* Security */}
        <SettingsSection title="Security">
          {[
            { key: 'sessionTimeout' as const, label: 'Session timeout', desc: 'Automatically lock after 30 minutes of inactivity' },
            { key: 'auditLogging' as const, label: 'Audit logging', desc: 'Log all user actions to secure audit trail' },
            { key: 'secureProcessing' as const, label: 'Secure processing mode', desc: 'Enhanced isolation for sensitive documents' },
          ].map(item => (
            <SettingsRow key={item.key} label={item.label} desc={item.desc}>
              <Toggle checked={settings.security[item.key]} onChange={v => updateSecurity(item.key, v)} />
            </SettingsRow>
          ))}
        </SettingsSection>

        {/* Data */}
        <SettingsSection title="Data">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-sm text-[var(--text-primary)]">Clear chat history</div>
              <div className="text-xs text-[var(--text-muted)]">Permanently delete all conversation history</div>
            </div>
            <button onClick={() => setClearModal(true)} className="px-4 py-2 text-sm rounded-lg border border-[var(--danger)]/30 text-[var(--danger)] hover:bg-[var(--danger)]/10 transition-colors">
              Clear History
            </button>
          </div>
        </SettingsSection>
      </div>

      <Modal open={clearModal} onClose={() => setClearModal(false)} title="Clear Chat History">
        <p className="text-sm text-[var(--text-secondary)] mb-4">This will permanently delete all conversation history. This action cannot be undone.</p>
        <div className="flex gap-2 justify-end">
          <button onClick={() => setClearModal(false)} className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Cancel</button>
          <button onClick={handleClear} className="px-4 py-2 text-sm bg-[var(--danger)] text-white rounded-lg font-medium hover:opacity-90 transition-opacity">Clear</button>
        </div>
      </Modal>
    </div>
  );
}

function SettingsSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div className="rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] p-5 mb-4">
      <div className="text-[10px] font-semibold tracking-widest text-[var(--text-muted)] uppercase mb-4">{title}</div>
      <div className="flex flex-col gap-4">{children}</div>
    </div>
  );
}

function SettingsRow({ label, desc, children }: { label: string; desc: string; children: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <div>
        <div className="text-sm text-[var(--text-primary)]">{label}</div>
        <div className="text-xs text-[var(--text-muted)]">{desc}</div>
      </div>
      {children}
    </div>
  );
}
