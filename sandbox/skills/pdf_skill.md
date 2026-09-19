# Skill: General-Purpose Document Design with `pdf_helpers`

The `pdf_helpers` library is a document-generation and design SDK.
**The LLM decides the document structure, layout, typography, colors, spacing, hierarchy, and components based on the specific task.**

Do NOT follow a rigid template or force every document into a fixed title → headings → paragraphs sequence. Choose an appropriate visual composition and document structure for the requested artifact.

## Supported Document Types
Adapt your design for any user-requested document, including:
- **Reports & Briefs**: Executive summaries, metric callouts, multi-column key takeaways, and structured findings.
- **Proposals & Business Documents**: Formal headers, scope tables, deliverables matrices, and action steps.
- **Research Papers & Technical Documentation**: Abstract callouts, multi-level numbering, data tables, and appendix sections.
- **Resumes & Bios**: Compact header banners, two-column profile layouts, skills chips, and timeline entries.
- **Guides, Manuals & Educational Material**: Highlight boxes, step-by-step instructions, and warning/tip callouts.
- **Meeting Notes & Agendas**: Attendee tables, discussion summaries, and next-step action checklists.
- **Invoices & Statements**: Itemized billing tables, total summaries, and payment terms.
- **Formal Letters & Memos**: Date/recipient blocks, concise body paragraphs, and sign-off sections.

## Document Length Freedom
- **Zero fixed page count**: Match the user's explicit request or the topic's natural depth.
- A memo or invoice can be **1 concise page**.
- A technical specification, research paper, or proposal can span multiple pages. Use `pdf.page_break()` when starting major sections or standalone pages.

## Design Primitives Reference

```python
from pdf_helpers import PdfBuilder

# 1. Page Configuration & Theme Setup
# Themes: "modern", "corporate", "teal", "midnight", "forest", "minimal"
pdf = PdfBuilder(
    theme="modern",
    page_size="letter",          # "letter" or "a4"
    orientation="portrait",      # "portrait" or "landscape"
    margins=(54, 54, 54, 54)     # left, right, top, bottom in points (72 pt = 1 inch)
)

# 2. Header & Banner Primitives
pdf.banner("Project Horizon: Commercial Proposal", subtitle="Prepared for Acme Corp • Q4 Scope of Work", padding=14)

# 3. Typography Primitives
pdf.heading("1. Executive Overview", level=1, size=18, space_before=12, space_after=6)
pdf.text("This proposal outlines our strategic approach to modernizing your digital platform.")

# 4. Multi-Column & Side-by-Side Composition
# Supports 2-column, 3-column, or asymmetric widths (e.g. 1/3 sidebar + 2/3 main body)
pdf.columns([
    [
        pdf.create_heading("Project Goals", level=2, size=13),
        pdf.create_text("• Accelerate time-to-market by 40%.\n• Eliminate legacy platform maintenance debt."),
        pdf.create_callout("Guaranteed delivery within 12 business weeks.", label="Key Commitment")
    ],
    [
        pdf.create_heading("Resource Allocation", level=2, size=13),
        pdf.create_table([
            ["Role", "Allocation", "Location"],
            ["Lead Architect", "Full-time", "On-site"],
            ["Senior Engineers (3)", "Full-time", "Hybrid"],
            ["QA / Release Lead", "Half-time", "Remote"]
        ], col_widths=[105, 75, 65])
    ]
], widths=[255, 255], spacing=16)

# 5. Highlight & Container Primitives
pdf.card([
    pdf.create_heading("Scope Inclusions", level=3, size=12),
    pdf.create_text("1. Cloud-native architecture design and infrastructure-as-code automation.\n"
                    "2. Complete CI/CD pipeline implementation with automated security gates.")
], padding=10)

pdf.callout("All intellectual property developed under this engagement transfers directly upon milestone completion.", label="Legal Terms")

# 6. Data & Tabular Presentation
pdf.heading("Milestone & Investment Schedule", level=2, size=14)
pdf.table([
    ["Phase", "Key Deliverable", "Timeline", "Target Date", "Investment"],
    ["Discovery", "Architecture Blueprint & Threat Model", "Weeks 1–3", "Nov 15", "$24,000"],
    ["Core Build", "API Framework & Microservices Alpha", "Weeks 4–8", "Dec 20", "$52,000"],
    ["Validation", "Integration Testing & Staging Deploy", "Weeks 9–11", "Jan 18", "$30,000"],
    ["Production", "Zero-downtime Rollout & Handover", "Week 12", "Feb 01", "$14,000"],
], col_widths=[65, 180, 75, 75, 75], header=True)

# 7. Metrics & KPI Grid
pdf.kpis([
    {"value": "$120,000", "label": "Total Project Investment"},
    {"value": "12 Weeks", "label": "Estimated Duration"},
    {"value": "100%", "label": "Milestone Acceptance Guarantee"}
], cols=3)

# 8. Visual Spacers & Dividers
pdf.divider(thickness=1, space_before=12, space_after=12)
pdf.spacer(height=8)

# 9. Multi-Page Flow
# pdf.page_break()  # Use when content should begin cleanly on a new page

# 10. Save Contract
pdf.save("proposal.pdf")
```

## Composition Guidelines
1. **Match Structure to Purpose**:
   - For letters or memos: Skip big banners; use a clean recipient block, date, subject line, concise body, and sign-off.
   - For resumes: Use compact headers, two-column sidebars, skill bullet grids, and chronological entries.
   - For proposals or technical docs: Use banners, executive summaries, structured tables, and highlighted callouts.
2. **Visual Hierarchy & Balance**:
   - Establish clear typographical contrast between headings and body text.
   - Use whitespace (`pdf.spacer`, cell padding, column spacing) to avoid visual fatigue.
3. **Safety Constraints**:
   - Do NOT write raw Low-level ReportLab drawing primitives or manipulate internal flowable pointers. Use `pdf_helpers` primitives directly.
