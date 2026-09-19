export type MessageRole = 'user' | 'assistant';

export interface Attachment {
  id: string;
  name: string;
  type: 'pdf' | 'csv' | 'xlsx' | 'docx' | 'txt' | 'image' | 'other';
  size: number;
  url?: string;
  dataUrl?: string;
}

export interface AgentStep {
  id: string;
  label: string;
  status: 'done' | 'active' | 'pending';
  duration?: string;
}

export interface GeneratedFile {
  id: string;
  name: string;
  type: string;
  size: string;
}

export interface Message {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: Date;
  attachments?: Attachment[];
  agentSteps?: AgentStep[];
  generatedFiles?: GeneratedFile[];
  liked?: boolean;
  disliked?: boolean;
}

export interface Session {
  id: string;
  title: string;
  subtitle: string;
  createdAt: Date;
  updatedAt: Date;
  pinned: boolean;
  messages: Message[];
}

export interface KnowledgeDoc {
  id: string;
  name: string;
  type: string;
  size: string;
  uploadedAt: Date;
  indexed: boolean;
  category: 'maintenance' | 'safety' | 'engineering' | 'operations';
}

export interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  category: string;
  lastRun?: Date;
  status: 'ready' | 'running' | 'error';
}

export interface WorkflowNode {
  id: string;
  type: string;
  label: string;
  x: number;
  y: number;
  config?: Record<string, string>;
}

export interface Workflow {
  id: string;
  name: string;
  nodes: WorkflowNode[];
  createdAt: Date;
  updatedAt: Date;
}

export type Theme = 'dark' | 'light';

export interface AppSettings {
  theme: Theme;
  notifications: {
    aiCompletion: boolean;
    agentCompletion: boolean;
    securityAlerts: boolean;
  };
  security: {
    sessionTimeout: boolean;
    auditLogging: boolean;
    secureProcessing: boolean;
  };
}
