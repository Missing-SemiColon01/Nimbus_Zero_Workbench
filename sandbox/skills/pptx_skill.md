# Skill: General-Purpose Presentation Design with `pptx_helpers`

The `pptx_helpers` library is a presentation rendering and visual design SDK, **NOT a fixed template**.
The LLM writing the code is the presentation designer and has complete freedom and responsibility to decide:
- **Presentation structure and narrative flow**: Design the slide sequence, story arc, and depth to match the prompt.
- **Slide count**: Dynamically choose the number of slides—from a 1-slide executive dashboard to a 15-slide technical breakdown. There is no artificial limit or fixed slide count.
- **Titles, headings, and kickers**: Craft concise, impactful slide titles tailored to the topic.
- **Layout and spatial composition**: Arrange components freely across the 16:9 canvas using coordinate boxes, multi-column splits, stacked panels, or grids.
- **Typography, fonts, sizes, and colors**: Select font sizes, weights, alignments, and color palettes that suit the topic and tone.
- **Visual elements and data presentation**: Choose tables, charts, cards, metrics, timelines, diagrams, badges, or images when and where they best communicate the ideas.
- **Information hierarchy**: Balance density, scannability, and whitespace across every slide.

Do NOT force presentations into rigid templates, fixed theme recipes, industrial/inspection examples, or mandatory slide sequences. For example, if asked to "Create a presentation explaining AI agents", decide the appropriate conceptual breakdown and build a clear, well-structured slide deck.

---

## SDK API Reference (`pptx_helpers.py`)

Import the SDK classes, layout helpers, and canvas constants:

```python
from pptx_helpers import Deck, split, vsplit, grid, pad, SW, SH, CW, CH, M, BODY
```

### 1. Canvas Geometry & Layout Constants

The canvas uses a widescreen 16:9 aspect ratio measured in inches:
- `SW, SH = 13.333, 7.5`: Total slide width and height in inches.
- `M = 0.7`: Standard outer margin.
- `GAP = 0.35`: Standard spacing between sibling elements.
- `CW = SW - 2 * M`: Printable content width (`11.933` in).
- `CH = SH - 2 * M`: Printable content height (`6.1` in).
- `BODY = (M, 1.95, CW, 4.85)`: Standard content bounding box below header areas.

### 2. Coordinate & Bounding Box Helpers

Boxes are defined as tuples of `(x, y, width, height)` in inches:
- `split(box, ratios, gap=GAP) -> list[tuple]`: Splits a box horizontally into side-by-side columns based on ratio weights (e.g. `split(BODY, [1, 1])` for two equal columns, or `split(BODY, [2, 1])` for an asymmetric 2/3 + 1/3 layout).
- `vsplit(box, ratios, gap=GAP) -> list[tuple]`: Splits a box vertically into stacked rows based on ratio weights (e.g. `vsplit(box, [1, 2])`).
- `grid(box, cols, rows=1, gap=GAP) -> list[tuple]`: Generates a row-major list of equal bounding boxes.
- `pad(box, p) -> tuple`: Insets a box by `p` inches on all four sides: `(x + p, y + p, w - 2*p, h - 2*p)`. Useful for placing content cleanly inside shapes.

### 3. Initialization & Theming

```python
d = Deck(
    theme="midnight",            # Built-in theme or custom styling
    overrides=None,              # Optional dict of color overrides
    head_font="Calibri",         # Heading font family
    body_font="Calibri"          # Body font family
)
```

**Themes & Colors:**
- Built-in theme presets: `"midnight"`, `"teal"`, `"forest"`, `"coral"`, `"terracotta"`, `"charcoal"`.
- Available theme color keys: `"primary"`, `"accent"`, `"dark"`, `"dark2"`, `"surface"`, `"line"`, `"ink"`, `"muted"`, `"sub"`, `"bg"`, `"on_accent"`, `"accent_text"`, `"chart"`.
- Resolve theme colors using `d.color("primary")` or pass 6-digit hex color strings directly (e.g. `"0F172A"`, `"FFFFFF"`).

### 4. Core Slide & Primitive Methods

- `d.add_slide(bg=None) -> slide`
  - Creates a blank slide. `bg` accepts a theme key (e.g. `"dark"`, `"bg"`, `"surface"`) or a custom hex code (e.g. `"FFFFFF"`, `"0B192C"`).

- `d.textbox(slide, text, box=BODY, font=None, size=14, bold=False, italic=False, color=None, align="left", vertical_align="top", margin=0, wrap=True, line_spacing=None, space_after=0, fit=True, min_pt=10)`
  - Renders text in a box with auto-wrapping and automatic font scaling (`fit=True`).
  - `align`: `"left"`, `"center"`, `"right"`.
  - `vertical_align`: `"top"`, `"middle"`, `"bottom"`.

- `d.shape(slide, kind="rounded_rect", box=BODY, fill=None, border=None, border_width=1.0, radius=0.05, shadow=False, decor=False)`
  - Adds a vector shape. `kind`: `"rect"`, `"rounded_rect"`, `"circle"`, `"oval"`.
  - `radius`: Corner curvature for rounded rectangles.
  - `shadow`: When `True`, applies a subtle shadow.

- `d.line(slide, start=(x1, y1), end=(x2, y2), color=None, width=1.0, dashed=False)`
  - Draws a straight divider or connector line between two points.

- `d.table(slide, rows, box=BODY, header=True, col_widths=None, header_bg=None, header_color="FFFFFF", alt_bg=None, text_color=None, font_size=13, border_color=None)`
  - Renders a styled table inside `box`.
  - `col_widths`: List of column widths in inches (must sum to `box[2]`).
  - `alt_bg`: Optional alternating row shading color.

- `d.chart(slide, kind, categories, series, box=BODY, title=None, labels=None, legend=None, fmt="General", colors=None)`
  - Renders a data chart.
  - `kind`: `"column"`, `"bar"`, `"stacked"`, `"line"`, `"area"`, `"pie"`, `"doughnut"`.
  - `categories`: Sequence of category strings.
  - `series`: Dict mapping series names to numeric lists, e.g. `{"2025": [10, 20], "2026": [15, 25]}`.

- `d.badge(slide, x, y, d, label, fill=None, color=None, size=None)`
  - Places a circular badge, step counter, or pill indicator at `(x, y)` with diameter `d`.

- `d.image(slide, path, box=BODY)`
  - Embeds an image file positioned and scaled within `box`.

### 5. High-Level Composable Helpers

These helpers can be placed into any bounding box:

- `d.kpis(slide, items, box=(M, 2.1, CW, 2.8))`
  - Renders metric cards across a horizontal grid.
  - `items`: List of dicts, each with `"value"`, `"label"`, and optional `"delta"`.

- `d.cards(slide, items, cols=None, box=BODY, badges=True)`
  - Renders container cards in an auto-calculated grid.
  - `items`: List of dicts with `"title"`, `"body"`, and optional `"badge"`.

- `d.timeline(slide, steps, box=None, orient="h")`
  - Renders a horizontal (`orient="h"`) or vertical (`orient="v"`) phased process roadmap.
  - `steps`: List of dicts with `"title"` and `"body"`.

- `d.two_col(slide, left, right, box=BODY)`
  - Side-by-side comparison layout. Each column is a dict: `{"heading": str, "bullets": list[str]}`.

- `d.callout(slide, text, box, label=None)`
  - Emphasized statement or takeaway card.

- `d.bullets(slide, items, box=BODY, size=18, color=None)`
  - Formatted bullet point list with custom bullet markers.

- `d.notes(slide, text)`
  - Attaches speaker notes to the slide.

### 6. Convenience Slide Starters (Optional)

The SDK also provides optional helper methods for standard slide formats:
- `d.title_slide(title, subtitle="", notes=None)`: Title slide layout.
- `d.content_slide(title, kicker=None, notes=None)`: Content slide with header and slide number.
- `d.section_slide(title, number=None, notes=None)`: Section divider slide.
- `d.quote_slide(quote, who="", notes=None)`: Callout/quote slide.
- `d.closing_slide(title, lines=None, notes=None)`: Conclusion / next steps slide.

*(You are free to build slides from scratch using `d.add_slide()` and primitives or use these starters when convenient.)*

### 7. Output & Saving

- `d.save(path="deck.pptx") -> dict[str, Any]`
  - Saves presentation file and returns metadata: `{"path": path, "slides": int, "warnings": list}`.

---

## Rendering Constraints & Rules

1. **Canvas Coordinate System**: Coordinates `(x, y, width, height)` are in **inches** starting from `(0, 0)` at the top-left corner.
2. **Boundary Safety**: All elements must fit within the slide bounds:
   - `0 <= x` and `x + width <= 13.333`
   - `0 <= y` and `y + height <= 7.5`
3. **Margins & Padding**:
   - Maintain at least `0.6"` to `0.7"` margin from canvas edges.
   - When placing text inside filled cards or shapes, use `pad(box, 0.2)` to ensure text does not collide with the container borders.
4. **Text Fit & Overflows**: Text boxes automatically scale down font size when `fit=True`, but keep text concise and well-proportioned for slide presentation.

---

## General Design & Readability Principles

- **Visual Contrast**: Dark text (`d.color("ink")` or `"1A1F3D"`) on light backgrounds; light text (`"FFFFFF"` or `"E2E8F0"`) on dark backgrounds.
- **Hierarchy & Scale**: Main slide titles (28–40pt bold), section subheads / kickers (11–14pt uppercase), body copy / labels (13–16pt).
- **Whitespace**: Avoid cluttered edge-to-edge text. Leave room for elements to breathe.
- **Layout Diversity**: Select layouts that best match the content:
  - Conceptual architecture: Multi-column cards or step timelines.
  - Data / Performance: KPI metric rows paired with charts or comparison tables.
  - Comparisons: 2-column pros/cons or before/after cards.
  - High-level ideas: Single focused callouts or quote blocks.

---

## Validation & Code Requirements

- Produce complete, valid, self-contained Python code.
- Save the presentation using `d.save(...)`.
- **Zero invented data**: Do not fabricate statistics, operational figures, or test metrics. When explaining conceptual topics, use accurate, established knowledge without making up false numbers.
