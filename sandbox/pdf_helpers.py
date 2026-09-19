"""
pdf_helpers.py - Flexible PDF document design SDK using ReportLab.

The LLM has full visual and composition freedom:
- Page geometry, margins, orientation (portrait/landscape), and themes.
- Typography: custom font sizes, weights, colors, line spacing (leading), and alignments.
- Structural layout: multi-column side-by-side layouts, cards, callouts, and banners.
- Data presentation: formatted tables, KPI blocks, dividers, images, and spacers.
- Unconstrained page counts: single-page executive memos or multi-page technical reports.

Example:
    from pdf_helpers import PdfBuilder

    pdf = PdfBuilder(theme="teal")
    pdf.banner("Quarterly Engineering & Safety Audit", subtitle="Facility Alpha & Beta Review - Q3")
    
    # KPI row
    pdf.kpis([
        {"value": "99.98%", "label": "System Availability", "delta": "+0.4%"},
        {"value": "0", "label": "Lost Time Incidents", "delta": "Goal Met"},
        {"value": "-24%", "label": "MTTR Latency", "delta": "Exceeded Target"}
    ])

    # 2-column layout: left observations, right data table
    pdf.columns([
        [
            pdf.create_heading("Key Observations", level=2),
            pdf.create_text("All primary telemetry streams remained healthy throughout peak hours."),
            pdf.create_callout("Preventative maintenance reduced component failure rate by 34%.", label="Impact")
        ],
        [
            pdf.create_heading("Audit Metrics", level=2),
            pdf.create_table([
                ["Facility", "Pass Rate", "Status"],
                ["Plant Alpha", "99.2%", "Certified"],
                ["Plant Beta", "98.7%", "Certified"],
                ["Assembly Line 4", "100.0%", "Exemplary"],
            ], col_widths=[90, 70, 70])
        ]
    ], widths=[250, 250], spacing=20)

    pdf.save("audit_report.pdf")
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4, landscape as rl_landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    HRFlowable,
    Image,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


PDF_THEMES: dict[str, dict[str, str]] = {
    "modern": {
        "primary": "#0F172A",     # Slate 900
        "secondary": "#1E293B",   # Slate 800
        "accent": "#2563EB",      # Blue 600
        "surface": "#F8FAFC",     # Slate 50
        "line": "#E2E8F0",        # Slate 200
        "text": "#334155",        # Slate 700
        "muted": "#64748B",       # Slate 500
        "highlight": "#EFF6FF",   # Blue 50
    },
    "teal": {
        "primary": "#064E5A",     # Deep Teal
        "secondary": "#028090",   # Medium Teal
        "accent": "#00A6A6",      # Bright Teal
        "surface": "#F0FDFA",     # Mint Surface
        "line": "#CCFBF1",        # Mint Border
        "text": "#134E4A",        # Dark Teal Text
        "muted": "#5EEAD4",       # Muted Accent
        "highlight": "#E6FFFA",   # Light Teal BG
    },
    "midnight": {
        "primary": "#1E2761",
        "secondary": "#2F3C7E",
        "accent": "#3B6FE8",
        "surface": "#F4F7FE",
        "line": "#CADCFC",
        "text": "#1A1F3D",
        "muted": "#5A6483",
        "highlight": "#EBF2FE",
    },
    "forest": {
        "primary": "#1E4620",
        "secondary": "#2C5F2D",
        "accent": "#97BC62",
        "surface": "#F4F8F4",
        "line": "#D6E8B8",
        "text": "#1D2A1E",
        "muted": "#5B6B5C",
        "highlight": "#E8F5E9",
    },
    "corporate": {
        "primary": "#102A43",
        "secondary": "#1F6FEB",
        "accent": "#00A6A6",
        "surface": "#F5F7FA",
        "line": "#DCE3EC",
        "text": "#1F2933",
        "muted": "#52606D",
        "highlight": "#EAF2FF",
    },
}


def _color(hex_str: str) -> colors.HexColor:
    """Normalize hex string to ReportLab HexColor."""
    clean = hex_str.strip()
    if not clean.startswith("#"):
        clean = "#" + clean
    return colors.HexColor(clean)


class PdfBuilder:
    """Flexible PDF document builder with rich typography, layouts, and cards."""

    def __init__(
        self,
        theme: str = "modern",
        page_size: str = "letter",       # letter | a4
        orientation: str = "portrait",   # portrait | landscape
        margins: tuple[float, float, float, float] = (54, 54, 54, 54),  # left, right, top, bottom (pt)
    ) -> None:
        self.theme_name = theme
        self.t = dict(PDF_THEMES.get(theme, PDF_THEMES["modern"]))
        self.elements: list[Any] = []
        self._style_idx = 0

        # Page geometry
        base_size = A4 if page_size.lower() == "a4" else letter
        self.pagesize = rl_landscape(base_size) if orientation.lower() == "landscape" else base_size
        self.left_margin, self.right_margin, self.top_margin, self.bottom_margin = margins

        # Base stylesheet
        self.stylesheet = getSampleStyleSheet()

    def color(self, name_or_hex: str) -> str:
        """Resolve a theme key or return hex."""
        return self.t.get(name_or_hex, name_or_hex)

    def _unique_style_name(self, prefix: str) -> str:
        self._style_idx += 1
        return f"{prefix}_{self._style_idx}"

    # ---- Typography Primitives -------------------------------------------- #
    def create_heading(
        self,
        text: str,
        level: int = 1,
        size: float | None = None,
        color: str | None = None,
        bold: bool = True,
        space_before: float = 14,
        space_after: float = 6,
        align: str = "left",   # left | center | right
    ) -> Paragraph:
        """Create a heading Flowable without adding it immediately to the story."""
        size_map = {1: 22, 2: 16, 3: 13, 4: 11}
        font_size = size or size_map.get(level, 14)
        c = self.color(color or (self.t["primary"] if level <= 2 else self.t["secondary"]))
        
        a_map = {"left": 0, "center": 1, "right": 2}
        style = ParagraphStyle(
            name=self._unique_style_name("heading"),
            fontName="Helvetica-Bold" if bold else "Helvetica",
            fontSize=font_size,
            leading=font_size * 1.25,
            textColor=_color(c),
            spaceBefore=space_before,
            spaceAfter=space_after,
            alignment=a_map.get(align.lower(), 0),
        )
        return Paragraph(text, style)

    def heading(self, text: str, **kwargs: Any) -> Paragraph:
        """Add a heading directly to the document story."""
        h = self.create_heading(text, **kwargs)
        self.elements.append(h)
        return h

    def create_text(
        self,
        text: str,
        size: float = 10.5,
        color: str | None = None,
        bold: bool = False,
        italic: bool = False,
        align: str = "left",
        space_before: float = 0,
        space_after: float = 6,
        leading: float | None = None,
    ) -> Paragraph:
        """Create a paragraph Flowable with exact typography."""
        font_name = "Helvetica"
        if bold and italic:
            font_name = "Helvetica-BoldOblique"
        elif bold:
            font_name = "Helvetica-Bold"
        elif italic:
            font_name = "Helvetica-Oblique"

        c = self.color(color or self.t["text"])
        lead = leading or (size * 1.35)
        a_map = {"left": 0, "center": 1, "right": 2, "justify": 4}

        style = ParagraphStyle(
            name=self._unique_style_name("text"),
            fontName=font_name,
            fontSize=size,
            leading=lead,
            textColor=_color(c),
            spaceBefore=space_before,
            spaceAfter=space_after,
            alignment=a_map.get(align.lower(), 0),
        )
        return Paragraph(text, style)

    def text(self, text: str, **kwargs: Any) -> Paragraph:
        """Add a paragraph directly to the document story."""
        p = self.create_text(text, **kwargs)
        self.elements.append(p)
        return p

    # Backward compatibility wrappers
    def add_title(self, text: str) -> None:
        self.heading(text, level=1, size=24, space_before=0, space_after=12)

    def add_heading(self, text: str) -> None:
        self.heading(text, level=2, size=16, space_before=14, space_after=6)

    def add_paragraph(self, text: str) -> None:
        self.text(text, size=11, space_after=8)

    # ---- Structural Layout: Banners & Cards ------------------------------- #
    def banner(
        self,
        title: str,
        subtitle: str | None = None,
        bg_color: str | None = None,
        text_color: str = "#FFFFFF",
        padding: float = 16,
    ) -> Table:
        """Full-width colored header band with title and subtitle."""
        bg = self.color(bg_color or self.t["primary"])
        content: list[Any] = [
            Paragraph(
                f"<b>{title}</b>",
                ParagraphStyle(
                    name=self._unique_style_name("b_title"),
                    fontName="Helvetica-Bold",
                    fontSize=22,
                    leading=26,
                    textColor=_color(text_color),
                ),
            )
        ]
        if subtitle:
            content.append(Spacer(1, 4))
            content.append(
                Paragraph(
                    subtitle,
                    ParagraphStyle(
                        name=self._unique_style_name("b_sub"),
                        fontName="Helvetica",
                        fontSize=12,
                        leading=15,
                        textColor=_color(text_color),
                    ),
                )
            )

        tbl = Table([[content]], colWidths=["100%"])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _color(bg)),
            ("TOPPADDING", (0, 0), (-1, -1), padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
            ("LEFTPADDING", (0, 0), (-1, -1), padding),
            ("RIGHTPADDING", (0, 0), (-1, -1), padding),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        self.elements.append(tbl)
        self.elements.append(Spacer(1, 14))
        return tbl

    def create_card(
        self,
        content: Any,
        bg_color: str | None = None,
        border_color: str | None = None,
        border_width: float = 1.0,
        padding: float = 12,
    ) -> Table:
        """Wrap content (flowables or string) in a styled container card."""
        bg = self.color(bg_color or self.t["surface"])
        bc = self.color(border_color or self.t["line"])
        
        cells = content if isinstance(content, list) else [self.create_text(str(content))]
        tbl = Table([[cells]], colWidths=["100%"])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _color(bg)),
            ("BOX", (0, 0), (-1, -1), border_width, _color(bc)),
            ("TOPPADDING", (0, 0), (-1, -1), padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
            ("LEFTPADDING", (0, 0), (-1, -1), padding),
            ("RIGHTPADDING", (0, 0), (-1, -1), padding),
        ]))
        return tbl

    def card(self, content: Any, **kwargs: Any) -> Table:
        """Add a styled container card to the document story."""
        c = self.create_card(content, **kwargs)
        self.elements.append(c)
        self.elements.append(Spacer(1, 10))
        return c

    def create_callout(
        self,
        text: str,
        label: str | None = None,
        bg_color: str | None = None,
        border_color: str | None = None,
        text_color: str | None = None,
    ) -> Table:
        """Create an emphasized statement callout box."""
        bg = self.color(bg_color or self.t["highlight"])
        bc = self.color(border_color or self.t["accent"])
        tc = self.color(text_color or self.t["primary"])

        items: list[Any] = []
        if label:
            items.append(
                Paragraph(
                    label.upper(),
                    ParagraphStyle(
                        name=self._unique_style_name("co_lbl"),
                        fontName="Helvetica-Bold",
                        fontSize=9,
                        leading=11,
                        textColor=_color(bc),
                        spaceAfter=3,
                    ),
                )
            )
        items.append(
            Paragraph(
                text,
                ParagraphStyle(
                    name=self._unique_style_name("co_txt"),
                    fontName="Helvetica",
                    fontSize=11,
                    leading=14,
                    textColor=_color(tc),
                ),
            )
        )

        tbl = Table([[items]], colWidths=["100%"])
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _color(bg)),
            ("LINELEFT", (0, 0), (0, -1), 4, _color(bc)),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ]))
        return tbl

    def callout(self, text: str, **kwargs: Any) -> Table:
        """Add an emphasized statement callout box to the document."""
        co = self.create_callout(text, **kwargs)
        self.elements.append(co)
        self.elements.append(Spacer(1, 10))
        return co

    # ---- Multi-Column Layout ---------------------------------------------- #
    def columns(
        self,
        column_elements: Sequence[Sequence[Any]],
        widths: Sequence[float] | None = None,
        spacing: float = 14,
    ) -> Table:
        """Place multiple columns side-by-side (asymmetric or equal widths)."""
        num_cols = len(column_elements)
        if num_cols == 0:
            return None

        # Format column flowables into cells
        row_cells = []
        for col_items in column_elements:
            if isinstance(col_items, list):
                row_cells.append(col_items)
            else:
                row_cells.append([col_items])

        col_w = widths if (widths and len(widths) == num_cols) else [f"{100 / num_cols}%"] * num_cols

        tbl = Table([row_cells], colWidths=col_w)
        tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), spacing / 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), spacing / 2),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        self.elements.append(tbl)
        self.elements.append(Spacer(1, 10))
        return tbl

    # ---- Data Tables ------------------------------------------------------ #
    def create_table(
        self,
        data: Sequence[Sequence[Any]],
        col_widths: Sequence[float] | None = None,
        header: bool = True,
        header_bg: str | None = None,
        header_color: str = "#FFFFFF",
        alt_row_bg: str | None = None,
        border_color: str | None = None,
        padding: float = 6,
        align: str = "CENTER",
    ) -> Table:
        """Create a styled tabular presentation Flowable."""
        h_bg = self.color(header_bg or self.t["primary"])
        b_border = self.color(border_color or self.t["line"])
        alt_bg = self.color(alt_row_bg or self.t["surface"]) if alt_row_bg else None

        # Convert strings in data to styled Paragraphs so text auto-wraps inside cells
        formatted_data = []
        for r_idx, row in enumerate(data):
            is_hdr = header and r_idx == 0
            row_cells = []
            for val in row:
                if isinstance(val, (Paragraph, Table)):
                    row_cells.append(val)
                else:
                    style = ParagraphStyle(
                        name=self._unique_style_name("td"),
                        fontName="Helvetica-Bold" if is_hdr else "Helvetica",
                        fontSize=10 if is_hdr else 9.5,
                        leading=12,
                        textColor=_color(header_color if is_hdr else self.t["text"]),
                    )
                    row_cells.append(Paragraph(str(val), style))
            formatted_data.append(row_cells)

        tbl = Table(formatted_data, colWidths=col_widths, hAlign=align.upper())
        style_cmds = [
            ("TOPPADDING", (0, 0), (-1, -1), padding),
            ("BOTTOMPADDING", (0, 0), (-1, -1), padding),
            ("LEFTPADDING", (0, 0), (-1, -1), padding + 2),
            ("RIGHTPADDING", (0, 0), (-1, -1), padding + 2),
            ("GRID", (0, 0), (-1, -1), 0.5, _color(b_border)),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
        if header:
            style_cmds.append(("BACKGROUND", (0, 0), (-1, 0), _color(h_bg)))
        if alt_bg:
            for r in range(1 if header else 0, len(data), 2):
                style_cmds.append(("BACKGROUND", (0, r), (-1, r), _color(alt_bg)))

        tbl.setStyle(TableStyle(style_cmds))
        return tbl

    def table(self, data: Sequence[Sequence[Any]], **kwargs: Any) -> Table:
        """Add a styled tabular presentation to the document."""
        tbl = self.create_table(data, **kwargs)
        self.elements.append(tbl)
        self.elements.append(Spacer(1, 10))
        return tbl

    # ---- KPI Metrics ------------------------------------------------------ #
    def kpis(
        self,
        items: Sequence[dict[str, Any]],
        cols: int | None = None,
        bg_color: str | None = None,
        border_color: str | None = None,
    ) -> Table:
        """Render a row/grid of highlighted KPI metric blocks."""
        n = len(items)
        if n == 0:
            return None
        num_cols = cols or n
        bg = self.color(bg_color or self.t["surface"])
        bc = self.color(border_color or self.t["line"])

        kpi_cells = []
        for it in items:
            cell_items: list[Any] = [
                Paragraph(
                    f"<b>{it.get('value', '')}</b>",
                    ParagraphStyle(
                        name=self._unique_style_name("kpi_val"),
                        fontName="Helvetica-Bold",
                        fontSize=22,
                        leading=26,
                        textColor=_color(self.t["primary"]),
                        alignment=1,
                    ),
                ),
                Spacer(1, 2),
                Paragraph(
                    it.get("label", ""),
                    ParagraphStyle(
                        name=self._unique_style_name("kpi_lab"),
                        fontName="Helvetica",
                        fontSize=9.5,
                        leading=12,
                        textColor=_color(self.t["muted"]),
                        alignment=1,
                    ),
                ),
            ]
            delta = it.get("delta")
            if delta:
                cell_items.append(Spacer(1, 2))
                delta_col = "#2E7D32" if str(delta).startswith("+") else ("#C62828" if str(delta).startswith("-") else self.t["muted"])
                cell_items.append(
                    Paragraph(
                        f"<b>{delta}</b>",
                        ParagraphStyle(
                            name=self._unique_style_name("kpi_del"),
                            fontName="Helvetica-Bold",
                            fontSize=9,
                            leading=11,
                            textColor=_color(delta_col),
                            alignment=1,
                        ),
                    )
                )
            kpi_cells.append(cell_items)

        # Build table with cells
        row_list = []
        curr_row: list[Any] = []
        for cell in kpi_cells:
            curr_row.append(cell)
            if len(curr_row) == num_cols:
                row_list.append(curr_row)
                curr_row = []
        if curr_row:
            while len(curr_row) < num_cols:
                curr_row.append([])
            row_list.append(curr_row)

        tbl = Table(row_list, colWidths=[f"{100 / num_cols}%"] * num_cols)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _color(bg)),
            ("BOX", (0, 0), (-1, -1), 1, _color(bc)),
            ("INNERGRID", (0, 0), (-1, -1), 1, _color(bc)),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        self.elements.append(tbl)
        self.elements.append(Spacer(1, 12))
        return tbl

    # ---- Spacers, Dividers & Page Flow ------------------------------------ #
    def divider(
        self,
        color: str | None = None,
        thickness: float = 1.0,
        space_before: float = 10,
        space_after: float = 10,
    ) -> None:
        """Horizontal divider line."""
        c = self.color(color or self.t["line"])
        self.elements.append(
            HRFlowable(
                width="100%",
                thickness=thickness,
                color=_color(c),
                spaceBefore=space_before,
                spaceAfter=space_after,
            )
        )

    def spacer(self, height: float = 12) -> None:
        """Add vertical breathing room."""
        self.elements.append(Spacer(1, height))

    def page_break(self) -> None:
        """Force subsequent content onto a new page."""
        self.elements.append(PageBreak())

    def image(
        self,
        path: str | Path,
        width: float | None = None,
        height: float | None = None,
    ) -> None:
        """Embed an image into the document flow."""
        if Path(path).exists():
            self.elements.append(Image(str(path), width=width, height=height))
            self.elements.append(Spacer(1, 8))

    # ---- Save Contract ---------------------------------------------------- #
    def save(self, path: str | Path = "document.pdf") -> dict[str, Any]:
        """Compile document and return result dict."""
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        doc = SimpleDocTemplate(
            str(dest),
            pagesize=self.pagesize,
            leftMargin=self.left_margin,
            rightMargin=self.right_margin,
            topMargin=self.top_margin,
            bottomMargin=self.bottom_margin,
        )
        doc.build(self.elements)
        return {"status": "success", "file": str(dest)}
