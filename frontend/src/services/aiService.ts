import type { Message, Attachment } from '../types';

// BACKEND HOOK: replace the local response generator below with a request to your
// single on-premise AI API when the backend is ready. The UI remains unchanged.
// Example endpoint is configured in src/services/backendConfig.ts.

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

The document is ready for download and review.`
};

function detectIntent(content: string, attachments?: Attachment[]): string {
  const lower = content.toLowerCase();
  if (attachments?.some(a => a.type === 'image')) return 'image';
  if (attachments?.some(a => a.type === 'csv' || a.type === 'xlsx')) return 'sensor';
  if (attachments?.some(a => a.type === 'pdf' || a.type === 'docx' || a.type === 'txt')) return 'document';
  if (lower.includes('sensor') || lower.includes('data') || lower.includes('pressure') || lower.includes('temperature')) return 'sensor';
  if (lower.includes('document') || lower.includes('report') || lower.includes('manual') || lower.includes('compliance')) return 'document';
  if (lower.includes('image') || lower.includes('photo') || lower.includes('inspect')) return 'image';
  if (lower.includes('generate') || lower.includes('create report') || lower.includes('summary')) return 'report';
  return 'general';
}

export async function generateResponse(
  messages: Message[],
  onChunk: (chunk: string) => void,
  signal?: AbortSignal
): Promise<void> {
  const last = messages[messages.length - 1];
  const intent = detectIntent(last.content, last.attachments);
  const fullResponse = RESPONSES[intent as keyof typeof RESPONSES] || RESPONSES.general;

  const words = fullResponse.split(' ');
  for (let i = 0; i < words.length; i++) {
    if (signal?.aborted) return;
    await new Promise(r => setTimeout(r, 18 + Math.random() * 20));
    onChunk((i === 0 ? '' : ' ') + words[i]);
  }
}

export function generateAgentSteps(intent: string) {
  const steps: Record<string, string[]> = {
    sensor: ['Ingested sensor data file', 'Processed time-series readings', 'Detected anomalies', 'Compared operating thresholds', 'Prepared analysis report'],
    document: ['Extracted document text', 'Parsed document structure', 'Indexed key sections', 'Cross-referenced knowledge base', 'Generated summary'],
    image: ['Loaded image data', 'Ran visual inspection model', 'Identified anomalies', 'Assessed severity', 'Prepared recommendations'],
    general: ['Parsed user request', 'Queried knowledge base', 'Synthesized findings', 'Generated response'],
    report: ['Gathered findings', 'Structured report sections', 'Applied formatting', 'Generated PDF report'],
  };
  return (steps[intent] || steps.general).map((label, i) => ({
    id: `step-${i}`,
    label,
    status: 'done' as const,
    duration: `${(0.5 + Math.random() * 3).toFixed(1)}s`
  }));
}
