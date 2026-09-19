# Skill: General-Purpose Document Design with `docx_helpers`

The `docx_helpers` library is a document-generation and design SDK.
**The LLM decides the document structure, layout, typography, colors, spacing, hierarchy, and components based on the specific task.**

Do NOT follow a rigid template or force every document into a fixed title → headings → paragraphs sequence. Choose an appropriate visual composition and document structure for the requested artifact.

## Supported Document Types
Adapt your design for any user-requested document, including:
- **Reports & Briefs**: Executive summaries, metric cards, two-column layouts, and findings tables.
- **Proposals & Business Documents**: Scope tables, milestones, team matrices, and fee schedules.
- **Research Papers & Technical Documentation**: Abstract callouts, multi-level numbering, data tables, and appendix sections.
- **Resumes & Bios**: Compact header blocks, two-column profile layouts, skills chips, and experience entries.
- **Guides, Manuals & Educational Material**: Highlight boxes, step-by-step instructions, and warning/tip callouts.
- **Meeting Notes & Agendas**: Attendee tables, discussion points, and action-item bullet lists.
- **Invoices & Statements**: Itemized billing tables, total summaries, and payment terms.
- **Formal Letters & Memos**: Date/recipient blocks, concise body paragraphs, and sign-off blocks.

## Document Length Freedom
- **Zero fixed page count**: Match the user's explicit request or the topic's natural depth.
- A memo or invoice can be **1 concise page**.
- A technical manual, proposal, or report can span multiple pages. Use `doc.page_break()` when starting major sections or standalone chapters.

## Design Primitives Reference

```python
from docx_helpers import DocxBuilder

# 1. Document Initialization & Page Setup
# Themes: "modern", "corporate", "teal", "midnight", "minimal"
doc = DocxBuilder(theme="modern", font_name="Calibri")
doc.page_setup(margins=(1.0, 1.0, 1.0, 1.0), orientation="portrait")

# 2. Header & Title Primitives
doc.heading("Project Horizon: Commercial Proposal", level=1, size=24, space_before=0, space_after=4)
doc.text("Prepared for Acme Corp • Q4 Scope of Work", size=12, color="64748B", italic=True, space_after=14)

# 3. Typography Primitives
doc.heading("1. Executive Overview", level=1, size=16, space_before=12, space_after=6)
doc.text("This proposal outlines our strategic approach to modernizing your digital platform.")

# 4. Highlight & Callout Primitives
doc.callout(
    "All intellectual property developed under this engagement transfers directly upon milestone completion.",
    label="Key Term"
)

# 5. Formatted Data Tables
doc.heading("2. Milestone & Investment Schedule", level=2, size=14)
doc.table([
    ["Phase", "Key Deliverable", "Timeline", "Investment"],
    ["Discovery", "Architecture Blueprint & Threat Model", "Weeks 1–3", "$24,000"],
    ["Core Build", "API Framework & Microservices Alpha", "Weeks 4–8", "$52,000"],
    ["Validation", "Integration Testing & Staging Deploy", "Weeks 9–11", "$30,000"],
    ["Production", "Zero-downtime Rollout & Handover", "Week 12", "$14,000"],
], col_widths=[1.2, 3.1, 1.1, 1.1], header=True)

# 6. Structured Card & Action Items
doc.card(
    title="Scope Inclusions",
    body="The engagement encompasses the following key engineering streams:",
    items=[
        "Cloud-native architecture design and infrastructure-as-code automation.",
        "Complete CI/CD pipeline implementation with automated security gates.",
        "Comprehensive operational handover documentation and team training."
    ]
)

# 7. Bullet Lists & Dividers
doc.divider()
doc.bullet("Delivery will be conducted via bi-weekly sprint reviews with dedicated staging access.", bold_prefix="Cadence: ")
doc.bullet("All production assets undergo pre-deployment vulnerability scans.", bold_prefix="Security: ")

# 8. Multi-Page Flow
# doc.page_break()  # Use when content should start cleanly on a new page

# 9. Save Contract
doc.save("proposal.docx")
```

## Composition Guidelines
1. **Match Structure to Purpose**:
   - For formal letters: Use a clean address/date block, polite salutation, formatted body, and sign-off.
   - For invoices: Use a compact vendor/client header, itemized pricing table, subtotal/tax rows, and payment remittance note.
   - For technical reports: Use numbered section headings, structured code/data callouts, and summary tables.
2. **Visual Hierarchy & Balance**:
   - Use distinct font sizes and weights for titles (22–24pt), major sections (16pt), subsections (13–14pt), and body copy (10.5–11pt).
   - Use table cell padding and spacing between elements to maintain a clean layout.
3. **Safety Constraints**:
   - Do NOT manipulate raw low-level Word XML (`w:tc`, `w:r`, etc.) directly unless abstracted. Use `DocxBuilder` primitives.
