import { useCallback } from 'react';
import { useLocalStorage } from './useLocalStorage';
import type { Session, Message } from '../types';
import { DEMO_SESSIONS } from '../services/mockData';

function reviveDates(sessions: Session[]): Session[] {
  return sessions.map(s => ({
    ...s,
    createdAt: new Date(s.createdAt),
    updatedAt: new Date(s.updatedAt),
    messages: s.messages.map(m => ({ ...m, timestamp: new Date(m.timestamp) }))
  }));
}

function makeId() {
  return `session-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
}

export function useSessions() {
  const [sessions, setSessions] = useLocalStorage<Session[]>('sovereign-sessions', DEMO_SESSIONS);
  const [activeId, setActiveId] = useLocalStorage<string | null>('sovereign-active-session', 'session-1');

  const revivedSessions = reviveDates(sessions);
  const activeSession = revivedSessions.find(s => s.id === activeId) || null;

  const createSession = useCallback((title: string) => {
    const id = makeId();
    const newSession: Session = {
      id,
      title,
      subtitle: 'New session',
      createdAt: new Date(),
      updatedAt: new Date(),
      pinned: false,
      messages: []
    };
    setSessions(prev => [newSession, ...prev]);
    setActiveId(id);
    return id;
  }, [setSessions, setActiveId]);

  const renameSession = useCallback((id: string, title: string) => {
    setSessions(prev => prev.map(s => s.id === id ? { ...s, title } : s));
  }, [setSessions]);

  const deleteSession = useCallback((id: string) => {
    setSessions(prev => {
      const next = prev.filter(s => s.id !== id);
      return next;
    });
    setActiveId(prev => {
      if (prev === id) {
        const remaining = sessions.filter(s => s.id !== id);
        return remaining[0]?.id || null;
      }
      return prev;
    });
  }, [setSessions, setActiveId, sessions]);

  const pinSession = useCallback((id: string) => {
    setSessions(prev => prev.map(s => s.id === id ? { ...s, pinned: !s.pinned } : s));
  }, [setSessions]);

  const addMessage = useCallback((sessionId: string, message: Message) => {
    setSessions(prev => prev.map(s => {
      if (s.id !== sessionId) return s;
      const subtitle = message.role === 'user' ? message.content.slice(0, 50) + '...' : s.subtitle;
      return { ...s, messages: [...s.messages, message], updatedAt: new Date(), subtitle };
    }));
  }, [setSessions]);

  const updateMessage = useCallback((sessionId: string, messageId: string, updates: Partial<Message>) => {
    setSessions(prev => prev.map(s => {
      if (s.id !== sessionId) return s;
      return { ...s, messages: s.messages.map(m => m.id === messageId ? { ...m, ...updates } : m) };
    }));
  }, [setSessions]);

  const clearSessionMessages = useCallback((sessionId: string) => {
    setSessions(prev => prev.map(s => s.id === sessionId ? { ...s, messages: [] } : s));
  }, [setSessions]);

  const clearAllHistory = useCallback(() => {
    setSessions(prev => prev.map(s => ({ ...s, messages: [] })));
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
    updateMessage,
    clearSessionMessages,
    clearAllHistory,
  };
}
