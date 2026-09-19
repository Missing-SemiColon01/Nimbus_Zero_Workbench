# Skill: General-Purpose Document Design with `pdf_helpers`

The `pdf_helpers` library is a document rendering and visual design SDK, **NOT a fixed template**.
The LLM writing the code is the document designer and has complete freedom and responsibility to decide:
- **Document structure and sections**: Select and order sections based on the specific topic and audience.
- **Titles and headings**: Formulate clear, topic-specific headings and hierarchical levels.
- **Page count and flow**: From a concise 1-page brief or memo to an extensive multi-page manual, guide, or technical document.
- **Layout and positioning**: Choose single-column narratives, multi-column comparisons, highlighted callouts, cards, or structured tables.
- **Typography, fonts, sizes, and colors**: Select appropriate font sizes, weights, alignments, leading, and palettes.
- **Visual components**: Incorporate tables, cards, callouts, KPI blocks, images, dividers, and spacers wherever they best communicate the content.
- **Information architecture**: Place information where it makes logical and narrative sense for the user's prompt.

Do NOT force documents into rigid industrial/report templates, fixed themes, or mandatory title→heading→paragraph sequences. For example, if asked to "Create a PDF explaining AI agents", decide the appropriate pedagogical structure and create a comprehensive, well-crafted educational document.

---

## SDK API Reference (`pdf_helpers.py`)

All primitives are accessed through `PdfBuilder`. Import only what exists:

```python
from pdf_helpers import PdfBuilder
```

### 1. Initialization & Page Setup

```python
pdf = PdfBuilder(
    theme="modern",              # Built-in theme or custom styling
    page_size="letter",          # "letter" or "a4"
    orientation="portrait",      # "portrait" or "landscape"
    margins=(54, 54, 54, 54)     # (left, right, top, bottom) in points (72 pt = 1 inch)
)
```

**Color Palette & Themes:**
- Built-in theme presets: `"modern"`, `"teal"`, `"midnight"`, `"forest"`, `"corporate"`.
- Each theme provides keys: `"primary"`, `"secondary"`, `"accent"`, `"surface"`, `"line"`, `"text"`, `"muted"`, `"highlight"`.
- Resolve theme colors with `pdf.color("accent")` or pass custom hex color strings directly (e.g. `"#1E293B"` or `"1E293B"`).

### 2. Typography Primitives

- `pdf.heading(text, level=1, size=None, color=None, bold=True, space_before=14, space_after=6, align="left")`
  - Adds a heading directly to the document flow.
  - `level`: Heading level (1 to 4). Default sizes: Level 1 (22pt), Level 2 (16pt), Level 3 (13pt), Level 4 (11pt).
  - `size`: Override font size in points.
  - `color`: Hex color or theme key.
  - `align`: `"left"`, `"center"`, `"right"`.

- `pdf.create_heading(text, level=1, size=None, color=None, bold=True, space_before=14, space_after=6, align="left")`
  - Creates and returns a heading `Paragraph` Flowable without appending it to the document story. Use this when nesting headings inside `columns` or `card`.

- `pdf.text(text, size=10.5, color=None, bold=False, italic=False, align="left", space_before=0, space_after=6, leading=None)`
  - Adds a paragraph directly to the document flow.
  - `leading`: Line height in points (defaults to `size * 1.35`).
  - `align`: `"left"`, `"center"`, `"right"`, `"justify"`.

- `pdf.create_text(text, size=10.5, color=None, bold=False, italic=False, align="left", space_before=0, space_after=6, leading=None)`
  - Creates and returns a paragraph `Paragraph` Flowable without appending it to the document story (for nesting inside `columns` or `card`).

### 3. Layout, Banners & Containers

- `pdf.banner(title, subtitle=None, bg_color=None, text_color="#FFFFFF", padding=16)`
  - Creates a full-width colored header band. Appends directly to the document story.
  - `bg_color`: Background hex or theme key (defaults to theme `"primary"`).

- `pdf.columns(column_elements, widths=None, spacing=14)`
  - Arranges content side-by-side in 2, 3, or more columns.
  - `column_elements`: A list of lists of Flowables, e.g. `[[flowable1, flowable2], [flowable3]]`.
  - `widths`: Point widths for each column (e.g. `[250, 250]`) or percentages (e.g. `["50%", "50%"]`). If `None`, columns share equal width.
  - `spacing`: Horizontal spacing between columns in points.

- `pdf.card(content, bg_color=None, border_color=None, border_width=1.0, padding=12)`
  - Adds a styled container card with background fill and border.
  - `content`: A Flowable, a list of Flowables (created via `pdf.create_*`), or a plain string.

- `pdf.create_card(content, bg_color=None, border_color=None, border_width=1.0, padding=12)`
  - Returns a card `Table` Flowable without appending it (for nesting in `columns`).

- `pdf.callout(text, label=None, bg_color=None, border_color=None, text_color=None)`
  - Adds an emphasized statement callout box with a prominent left accent border.
  - `label`: Optional uppercase label displayed above text (e.g. `"KEY TAKEAWAY"`, `"NOTE"`).

- `pdf.create_callout(text, label=None, bg_color=None, border_color=None, text_color=None)`
  - Returns a callout `Table` Flowable without appending it (for nesting in `columns`).

### 4. Data & Visual Components

- `pdf.table(data, col_widths=None, header=True, header_bg=None, header_color="#FFFFFF", alt_row_bg=None, border_color=None, padding=6, align="CENTER")`
  - Adds a styled table. Text cells automatically wrap.
  - `data`: 2D list of strings, numbers, or Flowables.
  - `col_widths`: List of column widths in points (e.g. `[120, 200, 80]`).
  - `header`: When `True`, styles the first row using `header_bg` and `header_color`.
  - `alt_row_bg`: Hex color or theme key for alternating row background shading.

- `pdf.create_table(data, ...)`
  - Returns a table Flowable without appending it to the document story (for nesting in `columns`).

- `pdf.kpis(items, cols=None, bg_color=None, border_color=None)`
  - Renders a row or grid of highlighted KPI metric blocks.
  - `items`: List of dicts, each with keys:
    - `"value"`: Primary metric string (e.g. `"99.9%"`, `"$4.2M"`, `"120ms"`).
    - `"label"`: Descriptive label string below the metric.
    - `"delta"`: Optional trend indicator (e.g. `"+14%"`, `"-5ms"`, `"On track"`).
  - `cols`: Number of columns in grid (defaults to `len(items)`).

- `pdf.image(path, width=None, height=None)`
  - Embeds an image file if the path exists.

- `pdf.divider(color=None, thickness=1.0, space_before=10, space_after=10)`
  - Adds a horizontal dividing line.

- `pdf.spacer(height=12)`
  - Adds vertical breathing space in points.

- `pdf.page_break()`
  - Forces subsequent content onto a fresh page.

### 5. Document Output & Compilation

- `pdf.save(path="document.pdf") -> dict[str, Any]`
  - Compiles the Flowables story into the final PDF document.
  - Returns status dictionary: `{"status": "success", "file": str(dest)}`.

---

## Rendering Constraints & Rules

1. **Measurement Units**: All coordinates, dimensions, padding, margins, and spacers use **points** (`72 points = 1 inch`).
2. **Page Width Bounds**:
   - Printable width for `letter` (8.5 x 11 in) with 54pt margins: `612 - 108 = 504 pt`.
   - Printable width for `a4` (595.27 x 841.89 pt) with 54pt margins: `595 - 108 = 487 pt`.
   - When specifying `col_widths` or column `widths`, ensure the sum plus spacing does not exceed printable width.
3. **Flowables Story vs. Nesting**:
   - Direct methods (`pdf.heading`, `pdf.text`, `pdf.card`, `pdf.callout`, `pdf.table`, `pdf.banner`) append directly to the top-level story.
   - When putting elements inside `pdf.columns(...)` or `pdf.card(...)`, use the `create_*` variants (`pdf.create_heading`, `pdf.create_text`, `pdf.create_table`, `pdf.create_callout`) so they are returned as Flowables and placed in their parent container.
4. **No Raw Low-Level Overrides**: Do not invoke private ReportLab drawing primitives or manipulate internal frame pointers; use `PdfBuilder` primitives.

---

## General Design & Readability Principles

- **Clear Typographic Hierarchy**: Differentiate titles (20–24pt), major headings (15–18pt), section subheads (12–14pt), and body text (10–11pt).
- **Adequate Leading & Spacing**: Keep line leading proportional to font size (`leading=size * 1.35`) to avoid text overlap. Use `pdf.spacer` between distinct content groups.
- **Intentional Structure**: Use multi-column layouts, callout panels, KPI grids, or tables where they clarify information. If the topic is purely narrative or expository, a clean single-column layout with section headings is completely appropriate.
- **Contrast & Legibility**: Maintain high contrast between text and background fills (e.g. dark text on light surfaces, light text on dark banners).

---

## Validation & Code Requirements

- Generate complete, self-contained, and directly executable Python code.
- Always finish with `pdf.save("...")`.
- **Zero invented data**: Do not fabricate statistics, facts, or user requirements. When details are not provided by the user, explain concepts accurately using verified knowledge without inventing fake statistics.
