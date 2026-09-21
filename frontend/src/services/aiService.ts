import type { Message, Attachment, AgentStep, GeneratedFile } from '../types';
import { streamTask } from './sseClient';
import { BACKEND_CONFIG } from './backendConfig';

// ---------------------------------------------------------------------------
// BACKEND HOOK
// ---------------------------------------------------------------------------
// When VITE_API_BASE_URL is set, generateResponse() calls the real backend SSE
// endpoint and dispatches typed events to the onAgentEvent callbacks.
// When it is NOT set (local dev without backend), the existing mock simulation
// below is used so the UI can be developed independently.
//
// Connect your backend: set VITE_API_BASE_URL=http://localhost:8000 in .env.local
// ---------------------------------------------------------------------------

const BACKEND_AVAILABLE = Boolean(BACKEND_CONFIG.baseUrl);

// ---------------------------------------------------------------------------
// Mock responses (used when backend is not configured)
// ---------------------------------------------------------------------------

const RESPONSES = {
  sensor: `I've completed analysis of the sensor data provided.

## KEY FINDINGS

The dataset reveals several operational patterns requiring attention:

- **Pressure variance**: ±12% above nominal operating range during peak load hours
- **Temperature correlation**: Elevated readings coincide with pressure deviations, suggesting thermal expansion effects
- **Flow rate**: Within acceptable bounds, though trending 8% lower than baseline over the measurement period

## ANOMALY SUMMARY

Three distinct anomaly clusters were identified in the time series data. The most significant occurred during the night shift cycle, where sustained readings exceeded safety thresholds for over 40 minutes before auto-correction engaged.

## RECOMMENDED ACTIONS

1. Schedule inspection of pressure control valves before next operational cycle
2. Review thermal insulation on primary feed lines
3. Calibrate flow sensors — drift detected in units F-07 and F-12
4. Increase monitoring frequency on Segment B during peak load windows`,

  document: `I've processed and analyzed the document.

## DOCUMENT SUMMARY

The document contains **regulatory compliance requirements** and **operational procedures** relevant to your facility. Key sections have been indexed for future retrieval.

## CRITICAL ITEMS IDENTIFIED

- Section 4.2: Maintenance intervals require update to reflect 2024 regulatory amendments
- Section 7.1: Emergency response procedures reference outdated contact information
- Appendix C: Equipment specifications list three components that have reached end-of-life

## GAP ANALYSIS

Comparing against current operational practices, **5 compliance gaps** were identified. Two require immediate remediation, three can be addressed in the next scheduled review cycle.

## NEXT STEPS

A detailed gap report has been generated with prioritized remediation recommendations.`,

  image: `I've analyzed the uploaded image.

## IMAGE ANALYSIS

### OBSERVATIONS
- Visible surface wear on the primary component face
- Possible corrosion buildup at junction points — yellowish-brown discoloration consistent with oxidation
- Minor scoring marks along the operational contact surface
- No obvious structural fracture or catastrophic failure visible

### POSSIBLE ISSUE
Surface degradation consistent with extended operational use beyond recommended service interval. The corrosion pattern suggests moisture ingress, possibly from a compromised seal.

### SEVERITY ASSESSMENT
**Moderate** — Component is functional but approaching the threshold for mandatory replacement.

### RECOMMENDED ACTION
Schedule physical inspection within the next 72 hours. Replace seals and apply corrosion inhibitor. Plan for full component replacement at next scheduled maintenance window.`,

  general: `I've processed your request using the Sovereign AI Engine.

## ANALYSIS COMPLETE

Based on the information provided and cross-referencing against the organizational knowledge base, here is my assessment:

The operational context you've described aligns with patterns observed in similar industrial environments. The data points suggest a systematic issue rather than an isolated incident, which warrants a structured investigation approach.

## KEY INSIGHTS

- The primary indicators point to a process drift rather than equipment failure
- Historical data from similar units shows this pattern precedes larger events in approximately 73% of cases
- Early intervention at this stage significantly reduces remediation cost and downtime risk

## RECOMMENDATIONS

1. **Immediate**: Increase monitoring cadence on affected systems
2. **Short-term**: Schedule diagnostic review with maintenance team
3. **Medium-term**: Review and update operating procedures for this process segment

This analysis has been logged to the audit trail for compliance purposes.`,

  report: `I've generated a comprehensive analysis report.

## REPORT GENERATED

The report has been compiled with the following sections:

- Executive Summary
- Detailed Findings
- Risk Assessment Matrix
- Recommended Actions
- Compliance Notes

The document is ready for download and review.`,

  docx: `I've generated your Word document (.docx).

## DOCUMENT COMPILED

The document has been formatted according to enterprise documentation standards:

- Structured Typography & Heading Hierarchy (H1, H2, H3)
- Executive Summary & Operational Scope
- Technical Analysis with Embedded Data Tables
- Risk Mitigation & Recommended Actions
- Compliance & Sign-off Appendix

The editable document is ready for download and distribution.`,

  pptx: `I've generated your PowerPoint presentation (.pptx).

## PRESENTATION READY

The slide deck has been compiled with a professional 16:9 widescreen layout:

- **Slide 1**: Title Slide & Executive Context
- **Slide 2**: Strategic Objectives & Scope Overview
- **Slide 3**: Key Findings & Metric Comparison Table
- **Slides 4-6**: Detailed Breakdown & Core Analyses
- **Slide 7**: Risk Matrix & Implementation Roadblocks
- **Slide 8**: Action Plan, Timeline & Q&A

All shapes, typography, and charts are fully editable in PowerPoint.`,

  xlsx: `I've generated your Excel workbook (.xlsx).

## WORKBOOK GENERATED

The spreadsheet has been constructed with multi-sheet organization and dynamic formulas:

- **Sheet 1 (Dashboard)**: High-level KPI summary, totals, and variance metrics
- **Sheet 2 (Data Model)**: Granular tabular records with standardized headers
- **Sheet 3 (Calculations)**: Dynamic formula models (=SUM, =AVERAGE, =STDEV.S)
- Number Formatting: Currency, percentages, and ISO date styling applied
- Column Auto-Fitting: Widths adjusted to ensure clean visual readability

The workbook is ready for financial and operational modeling.`,
};

export function detectArtifactType(content: string): 'pptx' | 'docx' | 'xlsx' | 'pdf' | null {
  const lower = content.toLowerCase();
  if (/\b(presentation|slides?|deck|pptx|powerpoint)\b/.test(lower)) return 'pptx';
  if (/\b(spreadsheet|excel|xlsx|workbook|sheets?)\b/.test(lower)) return 'xlsx';
  if (/\b(docx?|word|doc|approval\s+note|memo|contract|sop)\b/.test(lower)) return 'docx';
  if (/\b(pdf)\b/.test(lower)) return 'pdf';
  if (/\b(report)\b/.test(lower)) return 'pdf';
  return null;
}

function detectIntent(content: string, attachments?: Attachment[]): string {
  const artifact = detectArtifactType(content);
  if (artifact) return artifact;
  const lower = content.toLowerCase();
  if (attachments?.some(a => a.type === 'image')) return 'image';
  if (attachments?.some(a => a.type === 'csv' || a.type === 'xlsx')) return 'sensor';
  if (attachments?.some(a => a.type === 'pdf' || a.type === 'docx' || a.type === 'txt'))
    return 'document';
  if (
    lower.includes('sensor') ||
    lower.includes('data') ||
    lower.includes('pressure') ||
    lower.includes('temperature')
  )
    return 'sensor';
  if (
    lower.includes('document') ||
    lower.includes('report') ||
    lower.includes('manual') ||
    lower.includes('compliance')
  )
    return 'document';
  if (lower.includes('image') || lower.includes('photo') || lower.includes('inspect'))
    return 'image';
  if (
    lower.includes('generate') ||
    lower.includes('create report') ||
    lower.includes('summary')
  )
    return 'report';
  return 'general';
}

// ---------------------------------------------------------------------------
// Agent event callbacks (used with real backend)
// ---------------------------------------------------------------------------

export interface AgentEventCallbacks {
  onThought?: (text: string, phase: string) => void;
  onToolCallStart?: (tool: string, description: string) => void;
  onToolCallLog?: (tool: string, line: string) => void;
  onToolCallEnd?: (tool: string, success: boolean, duration_ms?: number) => void;
  onArtifactReady?: (name: string, fileType: string, sizeBytes: number, downloadUrl: string, previewUrl?: string) => void;
  onTaskComplete?: (durationMs: number, model?: string) => void;
  onTaskError?: (error: string) => void;
}

// ---------------------------------------------------------------------------
// Main API: generateResponse
// ---------------------------------------------------------------------------

/**
 * Generate an AI response, either via the real backend SSE stream or the
 * local mock simulation.
 *
 * @param messages      - Current conversation messages
 * @param onChunk       - Called with each text token/chunk as it arrives
 * @param signal        - Optional AbortSignal
 * @param agentEvents   - Optional SSE agent event callbacks (real backend only)
 */
export interface GenerateOptions {
  sessionId?: string;
  taskType?: string;
  images?: string[];
  documents?: string[];
  documentPaths?: string[];
}

export async function generateResponse(
  messages: Message[],
  onChunk: (chunk: string) => void,
  signal?: AbortSignal,
  agentEvents?: AgentEventCallbacks,
  options?: GenerateOptions,
): Promise<void> {
  const last = messages[messages.length - 1];

  if (BACKEND_AVAILABLE) {
    // Format previous messages for conversation history
    const formattedMessages = messages.map(m => ({
      role: m.role as 'user' | 'assistant',
      content: m.content,
    }));

    // --- Real backend SSE path ---
    await streamTask(
      {
        request: last.content,
        messages: formattedMessages,
        session_id: options?.sessionId,
        task_type: options?.taskType,
        images: options?.images,
        documents: options?.documents,
        document_paths: options?.documentPaths,
      },
      {
        onTaskInit() {
          /* task started */
        },
        onThought(text, phase) {
          agentEvents?.onThought?.(text, phase);
        },
        onToolCallStart(payload) {
          agentEvents?.onToolCallStart?.(payload.tool, payload.description);
        },
        onToolCallLog(tool, line) {
          agentEvents?.onToolCallLog?.(tool, line);
        },
        onToolCallEnd(payload) {
          agentEvents?.onToolCallEnd?.(payload.tool, payload.success, payload.duration_ms);
        },
        onContentDelta(delta) {
          onChunk(delta);
        },
        onArtifactReady(payload) {
          agentEvents?.onArtifactReady?.(
            payload.name,
            payload.file_type,
            payload.size_bytes,
            payload.download_url,
            payload.preview_url,
          );
        },
        onTaskComplete(payload) {
          agentEvents?.onTaskComplete?.(payload.duration_ms, payload.model);
        },
        onTaskError(error) {
          agentEvents?.onTaskError?.(error);
        },
      },
      signal,
    );
    return;
  }

  // --- Mock simulation (no backend configured) ---
  const intent = detectIntent(last.content, last.attachments);
  const fullResponse = RESPONSES[intent as keyof typeof RESPONSES] || RESPONSES.general;

  // ── Live mock agent events (simulate what the real backend would stream) ──
  if (agentEvents) {
    await simulateMockAgentEvents(intent, last.content, agentEvents, signal);
    if (signal?.aborted) return;
  }

  // ── Stream the final response word-by-word ────────────────────────────────
  const words = fullResponse.split(' ');
  for (let i = 0; i < words.length; i++) {
    if (signal?.aborted) return;
    await new Promise(r => setTimeout(r, 18 + Math.random() * 20));
    onChunk((i === 0 ? '' : ' ') + words[i]);
  }
}

// ---------------------------------------------------------------------------
// Mock agent event simulation — intent-specific live steps
// ---------------------------------------------------------------------------

const sleep = (ms: number) => new Promise<void>(r => setTimeout(r, ms));

async function simulateMockAgentEvents(
  intent: string,
  userContent: string,
  events: AgentEventCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const check = () => signal?.aborted ?? false;

  const docxSequence: Array<() => Promise<void>> = [
    async () => {
      events.onThought?.('Analyzing document requirements, typography standards, and structural sections...', 'reasoning');
      await sleep(380);
    },
    async () => {
      events.onToolCallStart?.('python-docx', 'Authoring Word document (.docx)');
      await sleep(180);
      events.onToolCallLog?.('python-docx', 'Initializing Document with corporate letterhead geometry (Letter / 1" margins)');
      await sleep(220);
      events.onToolCallLog?.('python-docx', 'Configuring typography styles: Title (24pt bold), Heading 1 (16pt), Body (11pt Calibri)');
      await sleep(200);
      events.onToolCallLog?.('python-docx', 'Drafting Executive Summary & Project Scope section');
      await sleep(220);
      events.onToolCallLog?.('python-docx', 'Inserting structured findings table with bold headers, zebra striping & cell padding');
      await sleep(240);
      events.onToolCallLog?.('python-docx', 'Appending Risk Matrix, Actionable Recommendations & Sign-off block');
      await sleep(180);
      events.onToolCallLog?.('python-docx', 'Saved deliverable: technical_document.docx (384 KB)');
      await sleep(160);
      events.onToolCallEnd?.('python-docx', true, 1250);
    },
    async () => {
      events.onThought?.('Validating OOXML document integrity, XML tag closure, and style consistency...', 'validation');
      await sleep(280);
    },
    async () => {
      events.onToolCallStart?.('artifact.validate', 'Validating Word document schema & style relationships');
      await sleep(160);
      events.onToolCallLog?.('artifact.validate', 'Parsing word/document.xml and word/styles.xml');
      await sleep(180);
      events.onToolCallLog?.('artifact.validate', 'Auditing table column widths, cell borders, and paragraph spacing');
      await sleep(160);
      events.onToolCallLog?.('artifact.validate', 'Verification passed: 100% compliant OpenXML document');
      await sleep(140);
      events.onToolCallEnd?.('artifact.validate', true, 640);
    },
    async () => {
      events.onArtifactReady?.('technical_document.docx', 'docx', 393216, '/api/v1/artifacts/technical_document.docx/download');
      await sleep(100);
    },
  ];

  const pptxSequence: Array<() => Promise<void>> = [
    async () => {
      events.onThought?.('Analyzing presentation narrative, slide layout rhythm, and design theme...', 'reasoning');
      await sleep(380);
    },
    async () => {
      events.onToolCallStart?.('python-pptx', 'Generating PowerPoint presentation (.pptx)');
      await sleep(180);
      events.onToolCallLog?.('python-pptx', 'Setting up presentation with 16:9 widescreen canvas (13.33" × 7.5")');
      await sleep(220);
      events.onToolCallLog?.('python-pptx', 'Slide 1/8: Title slide — modern dark theme & typography hierarchy');
      await sleep(200);
      events.onToolCallLog?.('python-pptx', 'Slide 2/8: Executive Summary & agenda bullet points');
      await sleep(200);
      events.onToolCallLog?.('python-pptx', 'Slide 3/8: Quantitative metrics comparison table with formatted cells');
      await sleep(220);
      events.onToolCallLog?.('python-pptx', 'Slides 4-6/8: Detailed analyses, architecture schematics & milestone cards');
      await sleep(200);
      events.onToolCallLog?.('python-pptx', 'Slide 7/8: Risk assessment & mitigation priority matrix');
      await sleep(180);
      events.onToolCallLog?.('python-pptx', 'Slide 8/8: Next steps, action items & contact summary');
      await sleep(160);
      events.onToolCallLog?.('python-pptx', 'Saved deliverable: presentation.pptx (2.1 MB)');
      await sleep(150);
      events.onToolCallEnd?.('python-pptx', true, 1400);
    },
    async () => {
      events.onThought?.('Validating presentation slide geometry, shapes, and font embedding...', 'validation');
      await sleep(280);
    },
    async () => {
      events.onToolCallStart?.('artifact.validate', 'Validating PPTX slide structure & layout geometry');
      await sleep(150);
      events.onToolCallLog?.('artifact.validate', 'Inspecting ppt/presentation.xml and slide master relationships');
      await sleep(180);
      events.onToolCallLog?.('artifact.validate', 'Auditing shape bounding boxes, text frames, and table alignments');
      await sleep(160);
      events.onToolCallLog?.('artifact.validate', 'Verification passed: 8/8 slides structurally validated');
      await sleep(140);
      events.onToolCallEnd?.('artifact.validate', true, 630);
    },
    async () => {
      events.onArtifactReady?.('presentation.pptx', 'pptx', 2202009, '/api/v1/artifacts/presentation.pptx/download');
      await sleep(100);
    },
  ];

  const xlsxSequence: Array<() => Promise<void>> = [
    async () => {
      events.onThought?.('Designing spreadsheet schema, multi-tab data model, and calculation formulas...', 'reasoning');
      await sleep(380);
    },
    async () => {
      events.onToolCallStart?.('openpyxl', 'Building structured Excel workbook (.xlsx)');
      await sleep(180);
      events.onToolCallLog?.('openpyxl', 'Initializing workbook with 3 worksheets: [Executive_Summary, Data_Model, Calculations]');
      await sleep(220);
      events.onToolCallLog?.('openpyxl', 'Styling header rows: navy background, white bold text, frozen top panes');
      await sleep(200);
      events.onToolCallLog?.('openpyxl', 'Populating 1,250 rows across 8 structured data fields');
      await sleep(220);
      events.onToolCallLog?.('openpyxl', 'Injecting dynamic formulas: =SUM(), =AVERAGE(), =STDEV.S(), =XLOOKUP()');
      await sleep(220);
      events.onToolCallLog?.('openpyxl', 'Applying accounting number formats ($#,##0.00), percentages, and dates');
      await sleep(180);
      events.onToolCallLog?.('openpyxl', 'Auto-fitting column dimensions to avoid truncation');
      await sleep(160);
      events.onToolCallLog?.('openpyxl', 'Saved deliverable: financial_model.xlsx (780 KB)');
      await sleep(150);
      events.onToolCallEnd?.('openpyxl', true, 1350);
    },
    async () => {
      events.onThought?.('Auditing formula references, cell ranges, and OpenPyXL XML structures...', 'validation');
      await sleep(280);
    },
    async () => {
      events.onToolCallStart?.('artifact.validate', 'Validating XLSX formula calculation chain & cell ranges');
      await sleep(150);
      events.onToolCallLog?.('artifact.validate', 'Parsing xl/calcChain.xml and cell dependency graph');
      await sleep(180);
      events.onToolCallLog?.('artifact.validate', 'Auditing circular references: 0 circular loops detected');
      await sleep(160);
      events.onToolCallLog?.('artifact.validate', 'Checking sheet boundaries and formula syntax across all 3 sheets');
      await sleep(140);
      events.onToolCallLog?.('artifact.validate', 'Verification passed: valid OpenXML spreadsheet');
      await sleep(120);
      events.onToolCallEnd?.('artifact.validate', true, 610);
    },
    async () => {
      events.onArtifactReady?.('financial_model.xlsx', 'xlsx', 798720, '/api/v1/artifacts/financial_model.xlsx/download');
      await sleep(100);
    },
  ];

  const pdfSequence: Array<() => Promise<void>> = [
    async () => {
      events.onThought?.('Configuring Platypus flowable document template, page geometry, and styles...', 'reasoning');
      await sleep(380);
    },
    async () => {
      events.onToolCallStart?.('reportlab', 'Composing formal PDF report (.pdf)');
      await sleep(180);
      events.onToolCallLog?.('reportlab', 'Building SimpleDocTemplate (A4, 20mm margins, 2-column layout)');
      await sleep(220);
      events.onToolCallLog?.('reportlab', 'Applying typography stylesheet: Title (24pt), Heading 1 (16pt), BodyText (10pt/14pt leading)');
      await sleep(200);
      events.onToolCallLog?.('reportlab', 'Rendering Executive Summary and Operational Findings');
      await sleep(220);
      events.onToolCallLog?.('reportlab', 'Rendering Risk Assessment Matrix (8×4 Table with TableStyle colors)');
      await sleep(200);
      events.onToolCallLog?.('reportlab', 'Adding dynamic Page X of Y canvas footer');
      await sleep(180);
      events.onToolCallLog?.('reportlab', 'Saved deliverable: compliance_report.pdf (412 KB)');
      await sleep(150);
      events.onToolCallEnd?.('reportlab', true, 1300);
    },
    async () => {
      events.onThought?.('Validating PDF xref table, fonts, and bounding boxes...', 'validation');
      await sleep(280);
    },
    async () => {
      events.onToolCallStart?.('artifact.validate', 'Validating PDF document structure & stream objects');
      await sleep(150);
      events.onToolCallLog?.('artifact.validate', 'Inspecting PDF header %PDF-1.7 and xref cross-reference table');
      await sleep(180);
      events.onToolCallLog?.('artifact.validate', 'Checking embedded fonts (Helvetica, Helvetica-Bold) and color spaces');
      await sleep(160);
      events.onToolCallLog?.('artifact.validate', 'Verifying page stream flow: 6 pages rendered without clipping');
      await sleep(140);
      events.onToolCallLog?.('artifact.validate', 'Verification passed: 6 pages structurally valid');
      await sleep(120);
      events.onToolCallEnd?.('artifact.validate', true, 630);
    },
    async () => {
      events.onArtifactReady?.('compliance_report.pdf', 'pdf', 421888, '/api/v1/artifacts/compliance_report.pdf/download');
      await sleep(100);
    },
  ];

  const sequences: Record<string, Array<() => Promise<void>>> = {
    docx: docxSequence,
    pptx: pptxSequence,
    xlsx: xlsxSequence,
    pdf: pdfSequence,
    document: docxSequence,
    report: pdfSequence,

    sensor: [
      async () => {
        events.onThought?.('Parsing sensor data file and detecting time-series structure...', 'reasoning');
        await sleep(420);
      },
      async () => {
        events.onToolCallStart?.('rag.search', 'Searching knowledge base for relevant thresholds and baselines');
        await sleep(320);
        events.onToolCallLog?.('rag.search', 'Querying vector index for "pressure variance operational limits"');
        await sleep(280);
        events.onToolCallLog?.('rag.search', 'Retrieved 4 relevant knowledge chunks (similarity ≥ 0.82)');
        await sleep(200);
        events.onToolCallEnd?.('rag.search', true, 820);
      },
      async () => {
        events.onThought?.('Running statistical anomaly detection across 3 sensor streams...', 'analysis');
        await sleep(550);
      },
      async () => {
        events.onToolCallStart?.('sandbox.execute', 'Computing anomaly score using IQR + rolling-window z-score');
        await sleep(150);
        events.onToolCallLog?.('sandbox.execute', 'Loading pandas DataFrame: 8640 rows × 12 columns');
        await sleep(200);
        events.onToolCallLog?.('sandbox.execute', 'Detected 3 anomaly clusters. Peak at row 4821 (z=3.4)');
        await sleep(180);
        events.onToolCallLog?.('sandbox.execute', 'Generating summary statistics...');
        await sleep(280);
        events.onToolCallEnd?.('sandbox.execute', true, 810);
      },
    ],

    image: [
      async () => {
        events.onThought?.('Loading image and selecting visual inspection model...', 'reasoning');
        await sleep(350);
      },
      async () => {
        events.onToolCallStart?.('vision.analyze', 'Running visual anomaly detection on uploaded image');
        await sleep(200);
        events.onToolCallLog?.('vision.analyze', 'Image dimensions: 1920×1080 — splitting into 4 tiles');
        await sleep(280);
        events.onToolCallLog?.('vision.analyze', 'Tile 1/4: no anomalies detected');
        await sleep(180);
        events.onToolCallLog?.('vision.analyze', 'Tile 2/4: surface irregularity at (x=814, y=423) — confidence 0.87');
        await sleep(220);
        events.onToolCallLog?.('vision.analyze', 'Tile 3/4 & 4/4: no anomalies detected');
        await sleep(150);
        events.onToolCallEnd?.('vision.analyze', true, 1030);
      },
      async () => {
        events.onThought?.('Correlating visual findings with equipment maintenance records...', 'reasoning');
        await sleep(380);
      },
    ],

    general: [
      async () => {
        events.onThought?.('Understanding request and identifying relevant knowledge sources...', 'reasoning');
        await sleep(380);
      },
      async () => {
        events.onToolCallStart?.('rag.search', 'Searching knowledge base for context');
        await sleep(280);
        events.onToolCallLog?.('rag.search', 'Retrieved 3 relevant knowledge chunks');
        await sleep(200);
        events.onToolCallEnd?.('rag.search', true, 480);
      },
      async () => {
        events.onThought?.('Synthesizing findings into coherent response...', 'generation');
        await sleep(420);
      },
    ],
  };

  const detectedArtifact = detectArtifactType(userContent);
  const selectedKey = detectedArtifact || intent;
  const steps = sequences[selectedKey] ?? sequences.general;

  for (const step of steps) {
    if (check()) return;
    await step();
    if (check()) return;
  }
}

// ---------------------------------------------------------------------------
// Mock agent step generation (used when backend is not configured)
// ---------------------------------------------------------------------------

export function generateAgentSteps(intent: string, content?: string): AgentStep[] {
  const artifactType = content ? detectArtifactType(content) : null;
  const effectiveType = artifactType || intent;

  const steps: Record<string, string[]> = {
    docx: [
      'Configured document typography & page geometry',
      'Structured executive sections & body headings',
      'Formatted tabular data and cell alignment',
      'Validated OpenXML document schema & style relationships',
    ],
    pptx: [
      'Planned 16:9 widescreen presentation outline',
      'Applied corporate color palette & slide master',
      'Rendered content cards, bullet blocks & metrics table',
      'Validated PPTX slide geometry and shape hierarchy',
    ],
    xlsx: [
      'Constructed multi-sheet workbook structure',
      'Applied frozen headers & accounting cell formatting',
      'Calculated dynamic formula models (=SUM, =AVERAGE)',
      'Validated calculation chain and zero circular references',
    ],
    pdf: [
      'Designed Platypus document layout and A4 margins',
      'Compiled custom ParagraphStyles & color palette',
      'Rendered risk assessment table & page numbering canvas',
      'Validated PDF xref structure and embedded fonts',
    ],
    sensor: [
      'Ingested sensor data file',
      'Processed time-series readings',
      'Detected anomalies',
      'Compared operating thresholds',
      'Prepared analysis report',
    ],
    document: [
      'Extracted document text',
      'Parsed document structure',
      'Indexed key sections',
      'Cross-referenced knowledge base',
      'Generated summary',
    ],
    image: [
      'Loaded image data',
      'Ran visual inspection model',
      'Identified anomalies',
      'Assessed severity',
      'Prepared recommendations',
    ],
    general: [
      'Parsed user request',
      'Queried knowledge base',
      'Synthesized findings',
      'Generated response',
    ],
    report: [
      'Gathered findings',
      'Structured report sections',
      'Applied formatting',
      'Generated PDF report',
    ],
  };
  return (steps[effectiveType] || steps.general).map((label, i) => ({
    id: `step-${i}`,
    label,
    status: 'done' as const,
    duration: `${(0.5 + Math.random() * 2).toFixed(1)}s`,
  }));
}

/** Generate mock files for demo mode (no backend) */
export function generateMockFiles(intent: string, content?: string): GeneratedFile[] {
  const artifactType = content ? detectArtifactType(content) : null;
  const effectiveType =
    artifactType ||
    (intent === 'docx' || intent === 'document'
      ? 'docx'
      : intent === 'pptx'
      ? 'pptx'
      : intent === 'xlsx'
      ? 'xlsx'
      : intent === 'report' || intent === 'pdf' || intent === 'sensor'
      ? 'pdf'
      : null);

  if (!effectiveType) return [];

  const timestamp = Date.now();
  const fileConfigs: Record<string, { name: string; type: string; size: string }> = {
    docx: {
      name: `document_${timestamp.toString().slice(-4)}.docx`,
      type: 'docx',
      size: `${Math.floor(280 + Math.random() * 150)} KB`,
    },
    pptx: {
      name: `presentation_${timestamp.toString().slice(-4)}.pptx`,
      type: 'pptx',
      size: `${(1.8 + Math.random() * 0.8).toFixed(1)} MB`,
    },
    xlsx: {
      name: `financial_model_${timestamp.toString().slice(-4)}.xlsx`,
      type: 'xlsx',
      size: `${Math.floor(620 + Math.random() * 250)} KB`,
    },
    pdf: {
      name: `analysis_report_${timestamp.toString().slice(-4)}.pdf`,
      type: 'pdf',
      size: `${Math.floor(320 + Math.random() * 200)} KB`,
    },
  };

  const cfg = fileConfigs[effectiveType] ?? fileConfigs.pdf;
  return [
    {
      id: `gf-${timestamp}`,
      name: cfg.name,
      type: cfg.type,
      size: cfg.size,
    },
  ];
}
