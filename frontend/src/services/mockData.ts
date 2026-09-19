import type { Session, KnowledgeDoc, Agent } from '../types';

export const DEMO_SESSIONS: Session[] = [
  {
    id: 'session-1',
    title: 'MRPL Process Optimization',
    subtitle: 'Analyzing refinery sensor data...',
    createdAt: new Date(Date.now() - 2 * 60 * 1000),
    updatedAt: new Date(Date.now() - 2 * 60 * 1000),
    pinned: false,
    messages: [
      {
        id: 'msg-1',
        role: 'user',
        content: 'Analyze the last 72 hours of pressure sensor data from Hydrotreater Unit 3.',
        timestamp: new Date(Date.now() - 2 * 60 * 1000 - 30000),
        attachments: [
          { id: 'att-1', name: 'hydrotreater_unit3_logs.csv', type: 'csv', size: 2516582 }
        ]
      },
      {
        id: 'msg-2',
        role: 'assistant',
        content: `I've reviewed the sensor logs for Hydrotreater Unit 3.

Over the 72-hour window I found **3 pressure anomalies** — two transient spikes on Day 1 and one sustained deviation starting at 06:11 on Day 3 that warrants immediate review.

## ANOMALIES DETECTED

The analysis identified the following critical events:

- **Day 1 — 02:14**: Transient pressure spike (+18 bar above baseline). Self-correcting within 4 minutes.
- **Day 1 — 14:37**: Second transient spike (+14 bar). Auto-relief valve activated. Self-correcting.
- **Day 3 — 06:11**: Sustained deviation began. Pressure 22 bar above operating threshold. Still active at end of log window.

## RECOMMENDED ACTION

Review the pressure control system on Hydrotreater Unit 3 and compare the sustained deviation against operating thresholds. Consider initiating controlled shutdown if pressure does not normalize within the next 4-hour monitoring window.`,
        timestamp: new Date(Date.now() - 2 * 60 * 1000),
        agentSteps: [
          { id: 'step-1', label: 'Ingested sensor CSV', status: 'done', duration: '1.2s' },
          { id: 'step-2', label: 'Processed 72 hours of readings', status: 'done', duration: '3.4s' },
          { id: 'step-3', label: 'Detected pressure anomalies', status: 'done', duration: '2.1s' },
          { id: 'step-4', label: 'Compared operating thresholds', status: 'done', duration: '0.8s' },
        ],
        generatedFiles: [
          { id: 'gf-1', name: 'safety_briefing_unit3.pdf', type: 'pdf', size: '540 KB' }
        ]
      }
    ]
  },
  {
    id: 'session-2',
    title: 'Safety Incident Report',
    subtitle: 'Cross-referencing hazard logs...',
    createdAt: new Date(Date.now() - 18 * 60 * 1000),
    updatedAt: new Date(Date.now() - 18 * 60 * 1000),
    pinned: false,
    messages: []
  },
  {
    id: 'session-3',
    title: 'Equipment Fault Diagnosis',
    subtitle: 'Turbine anomaly detection...',
    createdAt: new Date(Date.now() - 60 * 60 * 1000),
    updatedAt: new Date(Date.now() - 60 * 60 * 1000),
    pinned: false,
    messages: []
  },
  {
    id: 'session-4',
    title: 'Compliance Document Review',
    subtitle: 'ISO 45001 gap analysis...',
    createdAt: new Date(Date.now() - 3 * 60 * 60 * 1000),
    updatedAt: new Date(Date.now() - 3 * 60 * 60 * 1000),
    pinned: false,
    messages: []
  },
  {
    id: 'session-5',
    title: 'Supply Chain Forecast',
    subtitle: 'Crude oil demand prediction...',
    createdAt: new Date(Date.now() - 5 * 60 * 60 * 1000),
    updatedAt: new Date(Date.now() - 5 * 60 * 60 * 1000),
    pinned: false,
    messages: []
  }
];

export const DEMO_KNOWLEDGE_DOCS: KnowledgeDoc[] = [
  { id: 'doc-1', name: 'Maintenance_Manual_Rev4.pdf', type: 'pdf', size: '12.4 MB', uploadedAt: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000), indexed: true, category: 'maintenance' },
  { id: 'doc-2', name: 'Safety_Procedures_2024.pdf', type: 'pdf', size: '8.1 MB', uploadedAt: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000), indexed: true, category: 'safety' },
  { id: 'doc-3', name: 'Pump_Specifications_v2.pdf', type: 'pdf', size: '3.7 MB', uploadedAt: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000), indexed: true, category: 'engineering' },
  { id: 'doc-4', name: 'Emergency_Response_Plan.pdf', type: 'pdf', size: '5.2 MB', uploadedAt: new Date(Date.now() - 10 * 24 * 60 * 60 * 1000), indexed: true, category: 'safety' },
  { id: 'doc-5', name: 'ISO_45001_Checklist.xlsx', type: 'xlsx', size: '1.1 MB', uploadedAt: new Date(Date.now() - 12 * 24 * 60 * 60 * 1000), indexed: false, category: 'safety' },
  { id: 'doc-6', name: 'Operations_SOP_Q4.docx', type: 'docx', size: '2.3 MB', uploadedAt: new Date(Date.now() - 14 * 24 * 60 * 60 * 1000), indexed: true, category: 'operations' },
];

export const DEMO_AGENTS: Agent[] = [
  { id: 'agent-1', name: 'Maintenance Analyst', description: 'Analyze maintenance records and identify potential equipment issues before they cause downtime.', icon: 'Wrench', category: 'Maintenance', lastRun: new Date(Date.now() - 2 * 60 * 60 * 1000), status: 'ready' },
  { id: 'agent-2', name: 'Safety Inspector', description: 'Analyze safety documents and identify potential risks against regulatory compliance standards.', icon: 'ShieldCheck', category: 'Safety', lastRun: new Date(Date.now() - 5 * 60 * 60 * 1000), status: 'ready' },
  { id: 'agent-3', name: 'Equipment Analyst', description: 'Analyze equipment images and sensor data to identify visible anomalies and performance deviations.', icon: 'ScanEye', category: 'Equipment', lastRun: undefined, status: 'ready' },
  { id: 'agent-4', name: 'Document Intelligence', description: 'Extract, summarize, and cross-reference industrial documents to surface actionable insights.', icon: 'FileSearch', category: 'Documents', lastRun: new Date(Date.now() - 24 * 60 * 60 * 1000), status: 'ready' },
];

export const DEFAULT_WORKFLOW_NODES = [
  { id: 'wn-1', type: 'input', label: 'Document Upload', x: 200, y: 80 },
  { id: 'wn-2', type: 'process', label: 'Document Extraction', x: 200, y: 180 },
  { id: 'wn-3', type: 'ai', label: 'AI Analysis', x: 200, y: 280 },
  { id: 'wn-4', type: 'search', label: 'Knowledge Retrieval', x: 200, y: 380 },
  { id: 'wn-5', type: 'process', label: 'Risk Assessment', x: 200, y: 480 },
  { id: 'wn-6', type: 'output', label: 'Report Generation', x: 200, y: 580 },
];
