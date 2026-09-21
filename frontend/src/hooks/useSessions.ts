import { useCallback, useMemo } from 'react';
import { useLocalStorage } from './useLocalStorage';
import type { Session, Message } from '../types';

const INITIAL_SESSIONS: Session[] = [
  {
    id: 'session-1',
    title: 'Industrial Workspace',
    subtitle: 'New session',
    createdAt: new Date(),
    updatedAt: new Date(),
    pinned: false,
    messages: [],
  },
];

function reviveDates(sessions: Session[]): Session[] {
  if (!Array.isArray(sessions) || sessions.length === 0) {
    return INITIAL_SESSIONS;
  }
  return sessions.map(s => ({
    ...s,
    createdAt: s.createdAt ? new Date(s.createdAt) : new Date(),
    updatedAt: s.updatedAt ? new Date(s.updatedAt) : new Date(),
    messages: (s.messages || []).map(m => ({
      ...m,
      timestamp: m.timestamp ? new Date(m.timestamp) : new Date(),
    })),
  }));
}

function makeId() {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export function useSessions() {
  const [sessions, setSessions] = useLocalStorage<Session[]>('sovereign-sessions', INITIAL_SESSIONS);
  const [activeId, setActiveId] = useLocalStorage<string | null>('sovereign-active-session', 'session-1');

  const safeSessions = Array.isArray(sessions) && sessions.length > 0 ? sessions : INITIAL_SESSIONS;
  const revivedSessions = useMemo(() => reviveDates(safeSessions), [safeSessions]);
  const activeSession = useMemo(
    () => revivedSessions.find(s => s.id === activeId) || revivedSessions[0] || null,
    [revivedSessions, activeId],
  );

  const createSession = useCallback((title: string) => {
    const id = makeId();
    const newSession: Session = {
      id,
      title,
      subtitle: 'New session',
      createdAt: new Date(),
      updatedAt: new Date(),
      pinned: false,
      messages: [],
    };
    setSessions(prev => [newSession, ...(Array.isArray(prev) ? prev : [])]);
    setActiveId(id);
    return id;
  }, [setSessions, setActiveId]);

  const renameSession = useCallback((id: string, title: string) => {
    setSessions(prev => {
      const current = Array.isArray(prev) && prev.length > 0 ? prev : INITIAL_SESSIONS;
      return current.map(s => (s.id === id ? { ...s, title } : s));
    });
  }, [setSessions]);

  const deleteSession = useCallback((id: string) => {
    setSessions(prev => {
      const current = Array.isArray(prev) && prev.length > 0 ? prev : INITIAL_SESSIONS;
      const next = current.filter(s => s.id !== id);
      const safeNext = next.length > 0 ? next : INITIAL_SESSIONS;
      setActiveId(currentActive => {
        if (currentActive === id) {
          return safeNext[0]?.id || null;
        }
        return currentActive;
      });
      return safeNext;
    });
  }, [setSessions, setActiveId]);

  const pinSession = useCallback((id: string) => {
    setSessions(prev => {
      const current = Array.isArray(prev) && prev.length > 0 ? prev : INITIAL_SESSIONS;
      return current.map(s => (s.id === id ? { ...s, pinned: !s.pinned } : s));
    });
  }, [setSessions]);

  const addMessage = useCallback((sessionId: string, message: Message) => {
    setSessions(prev => {
      const current = Array.isArray(prev) && prev.length > 0 ? prev : INITIAL_SESSIONS;
      return current.map(s => {
        if (s.id !== sessionId) return s;
        const subtitle = message.role === 'user' ? message.content.slice(0, 50) + '...' : s.subtitle;
        return { ...s, messages: [...(s.messages || []), message], updatedAt: new Date(), subtitle };
      });
    });
  }, [setSessions]);

  const addMessages = useCallback((sessionId: string, newMessages: Message[]) => {
    setSessions(prev => {
      const current = Array.isArray(prev) && prev.length > 0 ? prev : INITIAL_SESSIONS;
      return current.map(s => {
        if (s.id !== sessionId) return s;
        const userMsg = newMessages.find(m => m.role === 'user');
        const subtitle = userMsg ? userMsg.content.slice(0, 50) + '...' : s.subtitle;
        return { ...s, messages: [...(s.messages || []), ...newMessages], updatedAt: new Date(), subtitle };
      });
    });
  }, [setSessions]);

  const updateMessage = useCallback((sessionId: string, messageId: string, updates: Partial<Message>) => {
    setSessions(prev => {
      const current = Array.isArray(prev) && prev.length > 0 ? prev : INITIAL_SESSIONS;
      return current.map(s => {
        if (s.id !== sessionId) return s;
        const msgs = s.messages || [];
        const exists = msgs.some(m => m.id === messageId);
        if (!exists) {
          const fallbackMsg: Message = {
            id: messageId,
            role: 'assistant',
            content: updates.content || '',
            timestamp: new Date(),
            ...updates,
          };
          return {
            ...s,
            updatedAt: new Date(),
            messages: [...msgs, fallbackMsg],
          };
        }
        return {
          ...s,
          updatedAt: new Date(),
          messages: msgs.map(m => (m.id === messageId ? { ...m, ...updates } : m)),
        };
      });
    });
  }, [setSessions]);

  const clearSessionMessages = useCallback((sessionId: string) => {
    setSessions(prev => {
      const current = Array.isArray(prev) && prev.length > 0 ? prev : INITIAL_SESSIONS;
      return current.map(s => (s.id === sessionId ? { ...s, messages: [] } : s));
    });
  }, [setSessions]);

  const clearAllHistory = useCallback(() => {
    setSessions(prev => {
      const current = Array.isArray(prev) && prev.length > 0 ? prev : INITIAL_SESSIONS;
      return current.map(s => ({ ...s, messages: [] }));
    });
  }, [setSessions]);

  return {
    sessions: revivedSessions,
    activeSession,
    activeId,
    setActiveId,
    createSession,
    renameSession,
    deleteSession,
    pinSession,
    addMessage,
    addMessages,
    updateMessage,
    clearSessionMessages,
    clearAllHistory,
  };
}
