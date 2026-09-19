import { useState, useRef, useEffect, useCallback } from 'react';
import { FileText, BarChart2, Image, AlertTriangle } from 'lucide-react';
import { ChatMessage } from '../components/chat/ChatMessage';
import { ChatComposer } from '../components/chat/ChatComposer';
import { generateResponse, generateAgentSteps } from '../services/aiService';
import { useToast } from '../components/ui/Toast';
import type { Session, Message, Attachment } from '../types';

interface ChatProps {
  session: Session | null;
  onAddMessage: (sessionId: string, message: Message) => void;
  onUpdateMessage: (sessionId: string, messageId: string, updates: Partial<Message>) => void;
}

const SUGGESTIONS = [
  { icon: BarChart2, label: 'Analyze sensor data', prompt: 'Analyze the latest sensor data from the process unit and identify any anomalies or deviations from operating thresholds.' },
  { icon: FileText, label: 'Analyze a maintenance report', prompt: 'Review the attached maintenance report and summarize key findings, upcoming service requirements, and any safety-critical items.' },
  { icon: Image, label: 'Inspect equipment image', prompt: 'Analyze this equipment image and identify visible signs of wear, corrosion, or damage that may require maintenance attention.' },
  { icon: AlertTriangle, label: 'Generate an incident report', prompt: 'Generate a structured safety incident report based on the provided information, including root cause analysis and corrective actions.' },
];

export function Chat({ session, onAddMessage, onUpdateMessage }: ChatProps) {
  const [streaming, setStreaming] = useState(false);
  const [streamingId, setStreamingId] = useState<string | null>(null);
  const [streamContent, setStreamContent] = useState('');
  const abortRef = useRef<AbortController | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { showToast } = useToast();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [session?.messages.length, streamContent]);

  const sendMessage = useCallback(async (content: string, attachments: Attachment[]) => {
    if (!session) return;

    const userMsg: Message = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content,
      timestamp: new Date(),
      attachments: attachments.length > 0 ? attachments : undefined,
    };
    onAddMessage(session.id, userMsg);

    const aiMsgId = `msg-${Date.now() + 1}`;
    const aiMsg: Message = {
      id: aiMsgId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
    };
    onAddMessage(session.id, aiMsg);
    setStreamingId(aiMsgId);
    setStreamContent('');
    setStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    let accumulated = '';
    try {
      const allMsgs = [...(session.messages || []), userMsg];
      await generateResponse(allMsgs, chunk => {
        accumulated += chunk;
        setStreamContent(accumulated);
      }, controller.signal);

      // detect intent for agent steps
      const lower = content.toLowerCase();
      const hasImage = attachments.some(a => a.type === 'image');
      const hasCsv = attachments.some(a => a.type === 'csv' || a.type === 'xlsx');
      const hasDoc = attachments.some(a => a.type === 'pdf' || a.type === 'docx' || a.type === 'txt');
      const intent = hasImage ? 'image' : hasCsv ? 'sensor' : hasDoc ? 'document' : lower.includes('sensor') || lower.includes('data') ? 'sensor' : lower.includes('report') ? 'report' : 'general';

      const agentSteps = generateAgentSteps(intent);
      const generatedFiles = (intent === 'sensor' || intent === 'report') ? [
        { id: `gf-${Date.now()}`, name: `analysis_report_${Date.now()}.pdf`, type: 'pdf', size: `${Math.floor(300 + Math.random() * 400)} KB` }
      ] : undefined;

      onUpdateMessage(session.id, aiMsgId, {
        content: accumulated,
        agentSteps,
        generatedFiles,
      });
    } catch {
      if (!controller.signal.aborted) {
        onUpdateMessage(session.id, aiMsgId, { content: accumulated || 'Unable to process request. Please try again.' });
      } else {
        onUpdateMessage(session.id, aiMsgId, { content: accumulated });
      }
    } finally {
      setStreaming(false);
      setStreamingId(null);
      setStreamContent('');
      abortRef.current = null;
    }
  }, [session, onAddMessage, onUpdateMessage]);

  function handleStop() {
    abortRef.current?.abort();
    showToast('Generation stopped', 'info');
  }

  function handleSuggestion(prompt: string) {
    sendMessage(prompt, []);
  }

  if (!session) {
    return (
      <div className="flex-1 flex items-center justify-center p-8 text-center">
        <div>
          <div className="w-12 h-12 rounded-2xl bg-[var(--accent)] flex items-center justify-center mx-auto mb-4">
            <svg width="22" height="22" viewBox="0 0 14 14" fill="none">
              <path d="M7 1L9.5 5.5H12L8.5 8.5L9.5 13L7 10.5L4.5 13L5.5 8.5L2 5.5H4.5L7 1Z" fill="white" fillRule="evenodd" />
            </svg>
          </div>
          <div className="text-lg font-semibold text-[var(--text-primary)] mb-1">No active session</div>
          <div className="text-sm text-[var(--text-muted)]">Select a session or create a new one to begin.</div>
        </div>
      </div>
    );
  }

  const messages = session.messages || [];
  const isEmpty = messages.length === 0;

  return (
    <div className="flex-1 flex flex-col min-h-0 overflow-hidden">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[860px] mx-auto px-4 py-6">
          {/* Status line */}
          <div className="flex items-center gap-2 text-[11px] text-[var(--text-muted)] mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-[var(--success)]" />
            Secure session initialized · Processing on-premise
          </div>

          {/* Empty state */}
          {isEmpty && (
            <div className="flex flex-col items-center text-center py-12">
              <div className="w-14 h-14 rounded-2xl bg-[var(--bg-card)] border border-[var(--border-color)] flex items-center justify-center mb-5">
                <svg width="24" height="24" viewBox="0 0 14 14" fill="none">
                  <path d="M7 1L9.5 5.5H12L8.5 8.5L9.5 13L7 10.5L4.5 13L5.5 8.5L2 5.5H4.5L7 1Z" fill="var(--accent)" fillRule="evenodd" />
                </svg>
              </div>
              <h2 className="text-xl font-semibold text-[var(--text-primary)] mb-2">
                How can I help with your industrial operations?
              </h2>
              <p className="text-sm text-[var(--text-muted)] max-w-[420px] mb-8 leading-relaxed">
                Analyze confidential documents, inspect equipment, analyze industrial data, and generate reports securely on-premise.
              </p>
              <div className="grid grid-cols-2 gap-2 w-full max-w-[520px]">
                {SUGGESTIONS.map(s => (
                  <button
                    key={s.label}
                    onClick={() => handleSuggestion(s.prompt)}
                    className="flex items-center gap-2.5 p-3.5 rounded-xl bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--accent)]/40 hover:bg-[var(--bg-card)] transition-all text-left group"
                  >
                    <s.icon size={15} className="text-[var(--accent)] flex-shrink-0" />
                    <span className="text-xs text-[var(--text-secondary)] group-hover:text-[var(--text-primary)] transition-colors">{s.label}</span>
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map(msg => (
            <ChatMessage
              key={msg.id}
              message={msg}
              streaming={streaming && msg.id === streamingId}
              streamContent={streaming && msg.id === streamingId ? streamContent : undefined}
              onLike={() => onUpdateMessage(session.id, msg.id, { liked: !msg.liked, disliked: false })}
              onDislike={() => onUpdateMessage(session.id, msg.id, { disliked: !msg.disliked, liked: false })}
              onRegenerate={() => {
                if (streaming) return;
                showToast('Regenerating response...');
                onUpdateMessage(session.id, msg.id, { content: 'Regenerating...' });
                setTimeout(() => {
                  const prev = messages[messages.indexOf(msg) - 1];
                  if (prev) sendMessage(prev.content, prev.attachments || []);
                }, 500);
              }}
            />
          ))}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Composer */}
      <ChatComposer onSend={sendMessage} streaming={streaming} onStop={handleStop} />
    </div>
  );
}
