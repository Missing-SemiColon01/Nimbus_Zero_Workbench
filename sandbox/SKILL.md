# Artifact Rendering SDK & Visual Design Guidelines

The helper libraries (`pptx_helpers`, `pdf_helpers`, `docx_helpers`) provide safe rendering primitives; **YOU are responsible for the design.**

Do NOT force artifacts into a single predefined template. Choose visual structures, layouts, color palettes, and component arrangements that best present the user's specific request.

## Core Rules

1. **Flexible Slide and Page Count**:
   - There is NO fixed number of slides or pages.
   - Tailor length directly to the user's explicit request and content depth (e.g. 1-page memo vs. 6-page report, 1-slide infographic vs. 8-slide pitch deck).
2. **Visual Hierarchy & Typography**:
   - Big, clear headlines with strong contrast.
   - Subtitle / kicker chips for metadata and category tags.
   - Clean body copy with comfortable line spacing and readable fonts.
3. **No Bare Wall of Text**:
   - For PPTX: Every content slide must have visual structure (cards, metrics, comparisons, timelines, tables, or charts).
   - For PDF: Use banners, 2-column sections, metric callouts, and styled tables to make documents immediately scannable.
4. **Safety & Primitives**:
   - Never write raw python-pptx XML or low-level layout hacks.
   - Use the helper SDK primitives (`Deck`, `PdfBuilder`, `DocxBuilder`) to ensure zero-crash sandbox execution.

