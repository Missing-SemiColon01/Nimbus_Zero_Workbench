# Skill: Dynamic Presentation Design with `pptx_helpers`

The helper library provides rendering primitives; **YOU are responsible for the design.**
Do NOT follow one rigid template for every presentation. Analyze the user's intent and choose visual compositions, layouts, and structures that best present their specific content.

## Slide Count Freedom
- **There is NO fixed number of slides.**
- If the user asks for a 1-slide executive summary or dashboard, create **1 slide**.
- If the user asks for a 3-slide brief, create **3 slides**.
- If the topic requires a comprehensive walkthrough, create **6, 8, 10, or more slides**.
- Always plan the number of slides based on the user's explicit request and the depth of the information.

## Themes & Visual Palettes
Initialize with a theme that fits the mood:
- `midnight`: Deep navy & blue, authoritative, corporate, technical.
- `teal`: Vibrant teal & mint, fresh, clinical, engineering, operations.
- `forest`: Deep green & olive, sustainability, safety, growth.
- `coral`: Navy & vibrant coral red, dynamic, consumer, modern.
- `terracotta`: Earthy rust & warm slate, industrial, architectural.
- `charcoal`: Cool dark grey & safety orange, industrial, mechanical.

Or pass custom hex color codes directly into any primitive (`"0F172A"`, `"FFFFFF"`, etc.).

## Core Primitives Reference

```python
from pptx_helpers import Deck, split, vsplit, grid, pad, SW, SH, CW, CH, BODY

d = Deck(theme="teal")

# 1. Slide Creation (Zero layout constraints)
s = d.add_slide(bg="0B192C")         # Custom dark background
s2 = d.add_slide(bg="FFFFFF")        # Clean white background
s3 = d.add_slide(bg="surface")       # Soft themed background

# 2. Text Box Primitive
d.textbox(s, "Revenue Doubled in Q3", box=(0.8, 0.6, 11.7, 0.8),
          size=32, color="FFFFFF", bold=True, align="left")
d.textbox(s, "Secondary body text with exact spacing", box=(0.8, 1.4, 11.7, 0.5),
          size=15, color="CADCFC", align="left")

# 3. Shape & Card Primitives
d.shape(s, kind="rounded_rect", box=(0.8, 2.2, 5.6, 4.5), fill="1E3E62", border="00A6A6", radius=0.06)
d.shape(s, kind="circle", box=(10.0, 1.0, 2.0, 2.0), fill="primary")

# 4. Lines & Dividers
d.line(s, start=(0.8, 1.3), end=(12.5, 1.3), color="00A6A6", width=1.5)

# 5. Table Primitive
d.table(s, rows=[
    ["Facility", "Inspections", "Pass Rate", "Status"],
    ["Sector Alpha", "142", "99.4%", "Compliant"],
    ["Sector Beta", "98", "97.8%", "Review"],
], box=(0.8, 2.4, 11.7, 3.8), header=True, header_bg="primary", alt_bg="surface")

# 6. Chart Primitive
d.chart(s, kind="column", categories=["Q1", "Q2", "Q3", "Q4"],
        series={"Target": [80, 85, 90, 95], "Actual": [82, 89, 94, 102]},
        box=(6.8, 2.2, 5.7, 4.5), title="Production Output")

# 7. High-Level Composable Helpers (place them into ANY box)
d.kpis(s, [{"value": "99.9%", "label": "Reliability", "delta": "+0.4%"},
           {"value": "-28%", "label": "Latency", "delta": "Target Met"}],
       box=(0.8, 2.2, 11.7, 2.2))

d.cards(s, [{"title": "Cloud Scale", "body": "Deployed to 4 regions."},
            {"title": "Zero Loss", "body": "No data dropped in failover."}],
        cols=2, box=(0.8, 4.6, 11.7, 2.2))

d.timeline(s, [{"title": "Phase 1", "body": "Audit"},
               {"title": "Phase 2", "body": "Execution"}],
           orient="h", box=(0.8, 2.5, 11.7, 4.0))

# 8. Save output
print(d.save("presentation.pptx"))
```

## Professional Design Guidelines

1. **Visual Hierarchy**:
   - Primary headlines: 28pt – 42pt (bold, strong contrast).
   - Section subheads / kickers: 11pt – 14pt (uppercase, accent color).
   - Body & data labels: 13pt – 16pt (clean readability).
2. **Whitespace & Breathing Room**:
   - Never pack text edge-to-edge. Keep at least `0.6"` margins from slide edges.
   - Use `pad(box, 0.25)` inside shapes so text does not collide with container borders.
3. **Contrast & Theming**:
   - On dark backgrounds (`"dark"`, `"0F172A"`), use white or light sub text (`"FFFFFF"`, `"E2E8F0"`).
   - On light backgrounds (`"bg"`, `"surface"`), use dark ink (`"1E293B"`).
4. **Layout Diversity**:
   - Vary your layouts between slides:
     - Slide A: Asymmetric split (35% KPI callout left, 65% chart right).
     - Slide B: 3-column structured architecture grid.
     - Slide C: High-density comparison table with alternating rows.
     - Slide D: Phased timeline roadmap.
     - Slide E: Focused 2-column pros/cons or before/after comparison.
5. **No Clutter & No Truncation**:
   - One core idea per slide.
   - Bullets should be punchy (under 12 words). Cards under 15 words.
