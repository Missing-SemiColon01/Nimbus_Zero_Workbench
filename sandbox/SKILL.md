# Artifact Rendering SDK & Visual Design Guidelines

The helper libraries (`pptx_helpers`, `pdf_helpers`, `docx_helpers`) provide safe rendering primitives; **YOU are responsible for the design.**

Do NOT force artifacts into a single predefined template. Choose visual structures, layouts, color palettes, and component arrangements that best present the user's specific request.

## Core Rules

1. **General-Purpose Across Document & Presentation Types**:
   - Tailor the structure and tone directly to the requested artifact: proposals, research papers, resumes, business documents, technical manuals, meeting notes, invoices, executive briefs, letters, guides, or presentations.
2. **Flexible Slide and Page Count**:
   - There is NO fixed number of slides or pages.
   - Tailor length directly to the user's explicit request and content depth (e.g. 1-page memo vs. 6-page proposal, 1-slide dashboard vs. 10-slide review).
3. **Visual Hierarchy & Typography**:
   - Big, clear titles with strong contrast.
   - Distinct section headings and comfortable line spacing.
   - Clean body copy with readable typography.
4. **No Bare Wall of Text**:
   - For PPTX: Every content slide must have visual structure (cards, metrics, comparisons, timelines, tables, or charts).
   - For PDF / DOCX: Use banners, multi-column sections, callouts, and styled tables to make documents immediately scannable and professional.
5. **Safety & Primitives**:
   - Never write raw XML or low-level layout hacks.
   - Use the helper SDK primitives (`Deck`, `PdfBuilder`, `DocxBuilder`) to ensure zero-crash sandbox execution.
