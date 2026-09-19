# Skill: Dynamic PDF Document Design with `pdf_helpers`

The helper library provides rendering primitives; **YOU are responsible for the design.**
Do NOT force every document into a single linear title-and-paragraph template. Use multi-column layouts, KPI callouts, formatted data tables, and structured cards to craft publication-grade reports.

## Page Count Freedom
- **There is NO fixed number of pages.**
- If the user requests a 1-page executive memo or briefing note, make it **1 concise page**.
- If the user requests an in-depth audit report or multi-section deliverable, structure it across multiple pages with `pdf.page_break()`.
- Content naturally flows across pages while tables, columns, and cards format cleanly.

## Themes & Visual Palettes
- `modern`: Deep slate (`#0F172A`), blue accents (`#2563EB`), neutral light gray surfaces (`#F8FAFC`).
- `teal`: Industrial teal (`#064E5A`), vibrant mint accents (`#00A6A6`), clean engineering feel.
- `midnight`: Deep navy (`#1E2761`), royal blue (`#3B6FE8`), technical and authoritative.
- `forest`: Deep forest green (`#1E4620`), olive accents (`#97BC62`), safety and environmental reviews.
- `corporate`: Classic sovereign navy (`#102A43`), steel blue (`#1F6FEB`), formal audits.

## Core Primitives Reference

```python
from pdf_helpers import PdfBuilder

# 1. Document Initialization
pdf = PdfBuilder(theme="modern", page_size="letter", orientation="portrait")

# 2. Executive Header Banner
pdf.banner("Safety & Compliance Incident Briefing", subtitle="Plant Alpha Facility Audit - Q3 2026")

# 3. KPI Metric Row
pdf.kpis([
    {"value": "99.98%", "label": "Telemetry Uptime", "delta": "+0.4%"},
    {"value": "0", "label": "Safety Violations", "delta": "Target Met"},
    {"value": "-34%", "label": "Near-Miss Reports", "delta": "Year-over-Year"}
], cols=3)

# 4. Multi-Column Layout (Side-by-side)
pdf.columns([
    [
        pdf.create_heading("Executive Summary", level=2),
        pdf.create_text("The automated production cells completed all scheduled cycles with zero critical alerts."),
        pdf.create_callout("All safety thresholds complied with ISO-45001 standards during the observation window.", label="Compliance Verified")
    ],
    [
        pdf.create_heading("Inspection Results", level=2),
        pdf.create_table([
            ["Component", "Score", "Status"],
            ["Conveyor A", "99.4%", "Pass"],
            ["Hydraulics", "98.1%", "Pass"],
            ["Emergency Stop", "100.0%", "Pass"]
        ], col_widths=[95, 75, 75])
    ]
], widths=[250, 250], spacing=20)

# 5. Full-Width Data Table
pdf.heading("Detailed Incident Breakdown", level=2)
pdf.table([
    ["ID", "Equipment", "Severity", "Timestamp", "Resolution"],
    ["INC-101", "Zone 4 Sensor", "Low", "14:22 UTC", "Auto-recalibrated"],
    ["INC-102", "Bearing B-12", "Medium", "18:05 UTC", "Lubricant replenished"],
    ["INC-103", "Exhaust Valve", "Low", "21:40 UTC", "Inspected - Nominal"],
], col_widths=[70, 110, 80, 90, 150], header=True)

# 6. Styled Card / Callout
pdf.card([
    pdf.create_heading("Actionable Recommendations", level=3),
    pdf.create_text("1. Schedule quarterly thermal imaging inspection on main gearboxes."),
    pdf.create_text("2. Retain backup PLC configuration snapshots on sovereign encrypted storage.")
], bg_color="#F8FAFC", border_color="#E2E8F0", padding=12)

# 7. Dividers & Spacers
pdf.divider(thickness=1, space_before=15, space_after=15)
pdf.spacer(height=10)

# 8. Save
pdf.save("audit_brief.pdf")
```

## Professional PDF Design Guidelines
1. **Clear Typographical Scale**:
   - Title: 20pt – 24pt bold.
   - Section Headings: 14pt – 16pt bold.
   - Subheadings: 12pt – 13pt bold.
   - Body text: 10pt – 11pt with 13pt – 15pt line leading.
2. **Visual Rhythm & Chunking**:
   - Break walls of text into styled cards, callouts, or tables.
   - Pair textual narrative with a structured table or KPI summary.
3. **Margins & Padding**:
   - Maintain at least 54pt (0.75 in) page margins for print and digital readability.
   - Use table cell padding (6pt–8pt) so numbers and labels have breathing room.
