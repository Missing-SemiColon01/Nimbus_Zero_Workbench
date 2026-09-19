# Skill: General-Purpose Document Design with `docx_helpers`

The `docx_helpers` library is a Word document rendering and visual design SDK, **NOT a fixed template**.
The LLM writing the code is the document designer and has complete freedom and responsibility to decide:
- **Document structure and sections**: Design the sections, headings, and hierarchy to fit the specific prompt.
- **Titles and headings**: Formulate clear, topic-specific titles, headers, and subheaders.
- **Page count and flow**: Create single-page memos or extensive multi-page documents as appropriate.
- **Layout and formatting**: Organize content using paragraphs, bullet lists, callout boxes, styled container cards, or structured tables.
- **Typography, fonts, sizes, and colors**: Select appropriate font sizes, weights, alignments, line spacing, and color palettes.
- **Visual elements**: Incorporate tables, cards, callouts, images, and dividers where they enhance clarity and presentation.
- **Information architecture**: Place information where it makes logical and narrative sense for the user's prompt.

Do NOT force documents into rigid industrial/report templates, fixed theme recipes, or mandatory title→heading→paragraph sequences. For example, if asked to "Create a document explaining AI agents", decide the appropriate educational structure and create a comprehensive, well-designed document.

---

## SDK API Reference (`docx_helpers.py`)

All primitives are accessed through `DocxBuilder`. Import only what exists:

```python
from docx_helpers import DocxBuilder
```

### 1. Initialization & Page Setup

```python
doc = DocxBuilder(
    theme="modern",              # Built-in theme preset
    font_name="Calibri"          # Primary typeface (e.g. "Calibri", "Arial")
)

doc.page_setup(
    margins=(1.0, 1.0, 1.0, 1.0), # (top, bottom, left, right) in inches
    orientation="portrait"        # "portrait" or "landscape"
)
```

**Color Palette & Themes:**
- Built-in theme presets: `"modern"`, `"corporate"`, `"teal"`, `"midnight"`, `"minimal"`.
- Each theme provides keys: `"primary"`, `"secondary"`, `"accent"`, `"surface"`, `"line"`, `"text"`, `"muted"`, `"highlight"`.
- Resolve theme colors with `doc.color("accent")` or pass custom hex color strings directly (e.g. `"1E293B"`).

### 2. Typography Primitives

- `doc.heading(text, level=1, size=None, color=None, bold=True, align="left", space_before=None, space_after=None)`
  - Adds a heading paragraph to the document.
  - `level`: Heading level (1 to 4). Default sizes: Level 1 (22pt), Level 2 (16pt), Level 3 (13pt), Level 4 (11pt).
  - `size`: Override font size in points.
  - `color`: Hex color or theme key.
  - `align`: `"left"`, `"center"`, `"right"`.
  - `space_before` / `space_after`: Paragraph spacing in points.

- `doc.text(text, size=11, color=None, bold=False, italic=False, align="left", space_before=0, space_after=6, line_spacing=1.15)`
  - Adds a styled paragraph to the document.
  - `align`: `"left"`, `"center"`, `"right"`, `"justify"`.
  - `line_spacing`: Multiple of line height (defaults to `1.15`).

- `doc.bullet(text, level=0, bold_prefix=None, space_after=3)`
  - Adds a bullet point item.
  - `level`: Indentation level (0 for top-level, 1+ for nested).
  - `bold_prefix`: Optional bold leading label (e.g. `"Note: "`, `"Key Feature: "`).

### 3. Structural Containers & Callouts

- `doc.card(title=None, body=None, items=None, bg_color=None, border_color=None)`
  - Adds a styled visual container card with background shading.
  - `title`: Bold title line at the top of the card.
  - `body`: Descriptive body text inside the card.
  - `items`: Optional list of bulleted string items inside the card.

- `doc.callout(text, label=None, bg_color=None, border_color=None)`
  - Adds an emphasized highlight panel.
  - `label`: Optional label prefix (e.g. `"IMPORTANT"`).

### 4. Data & Visual Components

- `doc.table(data, col_widths=None, header=True, header_bg=None, header_color="FFFFFF", alt_bg=None)`
  - Adds a styled data table with cell padding and shading.
  - `data`: 2D list of strings or values.
  - `col_widths`: List of column widths in inches (e.g. `[2.0, 3.5, 1.0]`).
  - `header`: When `True`, styles the top row with `header_bg` and `header_color`.
  - `alt_bg`: Optional alternating row background color.

- `doc.divider(color=None)`
  - Adds a clean horizontal divider line.

- `doc.image(path, width=4.0)`
  - Embeds an image file scaled to `width` inches if the file exists.

- `doc.page_break()`
  - Inserts a page break.

### 5. Document Output & Saving

- `doc.save(path="document.docx") -> dict[str, Any]`
  - Saves the document and returns a status dictionary: `{"status": "success", "file": str(dest)}`.

---

## Rendering Constraints & Rules

1. **Measurement Units**: Margins and table column widths are in **inches**; typography font sizes and spacing are in **points**.
2. **Page Width Bounds**: Standard letter page width is `8.5"` with default `1.0"` margins on left and right, leaving `6.5"` printable width. Ensure `col_widths` sum to approximately `6.5"` (or current page printable width).
3. **No Low-Level XML Manipulation**: Do not write raw WordprocessingML tags (`<w:p>`, `<w:tc>`) directly; use `DocxBuilder` primitives.

---

## General Design & Readability Principles

- **Clear Typographic Hierarchy**: Distinguish document titles (22–26pt), section headings (15–18pt), subsections (12–14pt), and body copy (10.5–11pt).
- **Whitespace & Rhythm**: Ensure proper paragraph spacing (`space_before` / `space_after`) so elements do not feel crowded.
- **Purpose-Driven Layout**: Use tables for structured comparisons, callouts for highlights, and container cards for grouped information. If the request calls for narrative or academic style, standard headings and paragraphs are completely appropriate.

---

## Validation & Code Requirements

- Generate self-contained, executable Python code.
- Always finish with `doc.save("...")`.
- **Zero invented data**: Do not fabricate statistics, metrics, or factual statements. Accurately articulate concepts using verified knowledge.
