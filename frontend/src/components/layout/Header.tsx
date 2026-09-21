import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Menu, Sun, Moon, Shield, ChevronDown, LogOut, User, Settings } from 'lucide-react';
import { Tooltip } from '../ui/Tooltip';
import { Modal } from '../ui/Modal';
import type { Theme } from '../../types';

interface HeaderProps {
  sessionTitle: string;
  theme: Theme;
  onToggleTheme: () => void;
  onToggleSidebar: () => void;
  onToggleContext?: () => void;
  isMobile?: boolean;
  onLogout: () => void;
  userEmail?: string;
  userName?: string;
  userOrg?: string;
}

export function Header({ sessionTitle, theme, onToggleTheme, onToggleSidebar, onToggleContext, isMobile, onLogout, userEmail, userName, userOrg }: HeaderProps) {
  const [securityPopover, setSecurityPopover] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const [signOutModal, setSignOutModal] = useState(false);
  const navigate = useNavigate();

  return (
    <header className="flex items-center h-16 px-4 border-b border-[var(--border-color)] bg-[var(--bg-base)] flex-shrink-0 gap-3">
      <Tooltip content="Toggle sidebar">
        <button onClick={onToggleSidebar} className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors" aria-label="Toggle sidebar">
          <Menu size={18} />
        </button>
      </Tooltip>

      <div className="flex-1 min-w-0">
        <div className="text-sm font-semibold text-[var(--text-primary)] truncate">{sessionTitle}</div>
        <div className="flex items-center gap-1.5 text-[11px] text-[var(--text-muted)]">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-[var(--success)]" />
          SIH26117 · <span className="text-[var(--warning)] font-medium">Confidential</span>
        </div>
      </div>

      <div className="flex items-center gap-1.5">
        {/* ON-PREMISE Badge */}
        <div className="relative">
          <button
            onClick={() => setSecurityPopover(!securityPopover)}
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-[var(--bg-card)] border border-[var(--border-color)] text-[10px] font-semibold tracking-wider text-[var(--success)] hover:border-[var(--success)]/50 transition-colors"
          >
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--success)] pulse-dot" />
            ON-PREMISE
          </button>
          {securityPopover && (
            <div className="absolute right-0 top-full mt-2 z-50 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xl p-4 min-w-[240px] animate-fade-in">
              <div className="text-xs font-semibold text-[var(--text-primary)] mb-3 flex items-center gap-1.5">
                <Shield size={13} className="text-[var(--success)]" /> SECURE ENVIRONMENT
              </div>
              {['Processing on-premise', 'Data remains within infrastructure', 'No external AI API dependency'].map(item => (
                <div key={item} className="flex items-center gap-2 text-xs text-[var(--text-secondary)] py-1">
                  <span className="text-[var(--success)] text-xs">✓</span> {item}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Theme toggle */}
        <Tooltip content={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}>
          <button onClick={onToggleTheme} className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors">
            {theme === 'dark' ? <Sun size={16} /> : <Moon size={16} />}
          </button>
        </Tooltip>

        {/* Context panel toggle on tablet */}
        {onToggleContext && isMobile && (
          <button onClick={onToggleContext} className="p-2 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors">
            <ChevronDown size={16} />
          </button>
        )}

        {/* Avatar + Profile dropdown */}
        <div className="relative">
          <button
            onClick={() => setProfileOpen(!profileOpen)}
            className="w-8 h-8 rounded-full bg-[var(--accent)] flex items-center justify-center text-white text-xs font-semibold hover:opacity-90 transition-opacity"
            aria-label="Profile menu"
          >
            {userName ? userName.charAt(0).toUpperCase() : (userEmail ? userEmail.charAt(0).toUpperCase() : 'U')}
          </button>
          {profileOpen && (
            <div className="absolute right-0 top-full mt-2 z-50 bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl shadow-xl py-1 min-w-[180px] animate-fade-in">
              <div className="px-3 py-2 border-b border-[var(--border-color)] mb-1">
                <div className="text-xs font-medium text-[var(--text-primary)]">{userName || userEmail || "Demo Operator"}</div>
                <div className="text-[11px] text-[var(--text-muted)]">{userOrg || "Operations"} · {userEmail}</div>
              </div>
              <button onClick={() => { setProfileOpen(false); }} className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors">
                <User size={12} /> Profile
              </button>
              <button onClick={() => { setProfileOpen(false); navigate('/settings'); }} className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-[var(--text-secondary)] hover:text-[var(--text-primary)] hover:bg-white/5 transition-colors">
                <Settings size={12} /> Settings
              </button>
              <div className="border-t border-[var(--border-color)] mt-1 pt-1">
                <button onClick={() => { setProfileOpen(false); setSignOutModal(true); }} className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-[var(--danger)] hover:bg-white/5 transition-colors">
                  <LogOut size={12} /> Sign Out
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      {securityPopover && <div className="fixed inset-0 z-40" onClick={() => setSecurityPopover(false)} />}
      {profileOpen && <div className="fixed inset-0 z-40" onClick={() => setProfileOpen(false)} />}

      <Modal open={signOutModal} onClose={() => setSignOutModal(false)} title="Sign Out">
        <p className="text-sm text-[var(--text-secondary)] mb-4">Are you sure you want to sign out of Sovereign AI Workbench?</p>
        <div className="flex gap-2 justify-end">
          <button onClick={() => setSignOutModal(false)} className="px-4 py-2 text-sm text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors">Cancel</button>
          <button onClick={() => { setSignOutModal(false); onLogout(); }} className="px-4 py-2 text-sm bg-[var(--danger)] text-white rounded-lg font-medium hover:opacity-90 transition-opacity">Sign Out</button>
        </div>
      </Modal>
    </header>
  );
}
