"""
docx_helpers.py - Flexible Word document design SDK using python-docx.

The LLM has full visual and structural composition freedom:
- Page geometry, margins, orientation, and professional themes.
- Typography: custom heading levels, font sizes, weights, colors, and alignments.
- Components: styled tables, container cards, callout blocks, bulleted lists, and dividers.
- General-purpose document creation: proposals, research papers, resumes, technical manuals,
  invoices, guides, meeting notes, executive briefs, letters, and reports.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION_START
from docx.enum.table import WD_ALIGN_VERTICAL, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import nsdecls, qn
from docx.shared import Inches, Pt, RGBColor


DOCX_THEMES: dict[str, dict[str, str]] = {
    "modern": {
        "primary": "0F172A",     # Slate 900
        "secondary": "1E293B",   # Slate 800
        "accent": "2563EB",      # Blue 600
        "surface": "F8FAFC",     # Slate 50
        "line": "E2E8F0",        # Slate 200
        "text": "334155",        # Slate 700
        "muted": "64748B",       # Slate 500
        "highlight": "EFF6FF",   # Blue 50
    },
    "corporate": {
        "primary": "102A43",     # Navy
        "secondary": "1F6FEB",   # Blue
        "accent": "00A6A6",      # Teal
        "surface": "F5F7FA",     # Neutral light
        "line": "DCE3EC",        # Light border
        "text": "1F2933",        # Dark charcoal
        "muted": "52606D",       # Neutral muted
        "highlight": "EAF2FF",
    },
    "teal": {
        "primary": "064E5A",
        "secondary": "028090",
        "accent": "00A6A6",
        "surface": "F0FDFA",
        "line": "CCFBF1",
        "text": "134E4A",
        "muted": "5EEAD4",
        "highlight": "E6FFFA",
    },
    "midnight": {
        "primary": "1E2761",
        "secondary": "2F3C7E",
        "accent": "3B6FE8",
        "surface": "F4F7FE",
        "line": "CADCFC",
        "text": "1A1F3D",
        "muted": "5A6483",
        "highlight": "EBF2FE",
    },
    "minimal": {
        "primary": "111827",
        "secondary": "374151",
        "accent": "4B5563",
        "surface": "F9FAFB",
        "line": "E5E7EB",
        "text": "1F2937",
        "muted": "6B7280",
        "highlight": "F3F4F6",
    },
}


def _rgb(hex_str: str) -> RGBColor:
    """Normalize hex string to docx RGBColor."""
    clean = hex_str.strip().lstrip("#")
    if len(clean) != 6:
        clean = "000000"
    return RGBColor(int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))


def _set_cell_bg(cell: Any, hex_color: str) -> None:
    """Set the background shading of a table cell."""
    clean = hex_color.lstrip("#")
    shading_xml = f'<w:shd {nsdecls("w")} w:fill="{clean}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shading_xml))


def _set_cell_margins(cell: Any, top: int = 100, bottom: int = 100, left: int = 150, right: int = 150) -> None:
    """Set cell padding in twentieths of a point (dxa)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for name, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{name}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


class DocxBuilder:
    """General-purpose Word document design SDK."""

    def __init__(self, theme: str = "modern", font_name: str = "Calibri") -> None:
        self.doc = Document()
        self.theme_name = theme
        self.font_name = font_name
        self.t = dict(DOCX_THEMES.get(theme, DOCX_THEMES["modern"]))
        self._setup_defaults()

    def _setup_defaults(self) -> None:
        # Default normal text style
        style = self.doc.styles["Normal"]
        font = style.font
        font.name = self.font_name
        font.size = Pt(11)
        font.color.rgb = _rgb(self.t["text"])

    def color(self, name_or_hex: str) -> str:
        """Resolve a theme key or return hex."""
        return self.t.get(name_or_hex, name_or_hex).lstrip("#")

    # ---- Page Layout Primitives ------------------------------------------- #
    def page_setup(
        self,
        margins: tuple[float, float, float, float] = (1.0, 1.0, 1.0, 1.0),  # top, bottom, left, right (inches)
        orientation: str = "portrait",                                      # portrait | landscape
    ) -> None:
        """Configure page margins and orientation."""
        section = self.doc.sections[0]
        top, bottom, left, right = margins
        section.top_margin = Inches(top)
        section.bottom_margin = Inches(bottom)
        section.left_margin = Inches(left)
        section.right_margin = Inches(right)
        if orientation.lower() == "landscape":
            section.orientation = WD_ORIENT.LANDSCAPE
            section.page_width, section.page_height = Inches(11.0), Inches(8.5)
        else:
            section.orientation = WD_ORIENT.PORTRAIT
            section.page_width, section.page_height = Inches(8.5), Inches(11.0)

    def page_break(self) -> None:
        """Insert a page break."""
        self.doc.add_page_break()

    # ---- Typography Primitives -------------------------------------------- #
    def heading(
        self,
        text: str,
        level: int = 1,
        size: float | None = None,
        color: str | None = None,
        bold: bool = True,
        align: str = "left",
        space_before: float | None = None,
        space_after: float | None = None,
    ) -> Any:
        """Add a heading with exact typography and spacing control."""
        size_map = {1: 22, 2: 16, 3: 13, 4: 11}
        font_size = size or size_map.get(level, 14)
        col_hex = self.color(color or (self.t["primary"] if level <= 2 else self.t["secondary"]))
        before = space_before if space_before is not None else (18 if level == 1 else 12)
        after = space_after if space_after is not None else (6 if level == 1 else 4)

        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(before)
        p.paragraph_format.space_after = Pt(after)
        p.paragraph_format.keep_with_next = True

        a_map = {"left": WD_ALIGN_PARAGRAPH.LEFT, "center": WD_ALIGN_PARAGRAPH.CENTER, "right": WD_ALIGN_PARAGRAPH.RIGHT}
        p.alignment = a_map.get(align.lower(), WD_ALIGN_PARAGRAPH.LEFT)

        run = p.add_run(text)
        run.font.name = self.font_name
        run.font.size = Pt(font_size)
        run.font.bold = bold
        run.font.color.rgb = _rgb(col_hex)
        return p

    def text(
        self,
        text: str,
        size: float = 11,
        color: str | None = None,
        bold: bool = False,
        italic: bool = False,
        align: str = "left",
        space_before: float = 0,
        space_after: float = 6,
        line_spacing: float = 1.15,
    ) -> Any:
        """Add a paragraph with fine-grained styling."""
        col_hex = self.color(color or self.t["text"])
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(space_before)
        p.paragraph_format.space_after = Pt(space_after)
        p.paragraph_format.line_spacing = line_spacing

        a_map = {
            "left": WD_ALIGN_PARAGRAPH.LEFT,
            "center": WD_ALIGN_PARAGRAPH.CENTER,
            "right": WD_ALIGN_PARAGRAPH.RIGHT,
            "justify": WD_ALIGN_PARAGRAPH.JUSTIFY,
        }
        p.alignment = a_map.get(align.lower(), WD_ALIGN_PARAGRAPH.LEFT)

        run = p.add_run(text)
        run.font.name = self.font_name
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.italic = italic
        run.font.color.rgb = _rgb(col_hex)
        return p

    def bullet(
        self,
        text: str,
        level: int = 0,
        bold_prefix: str | None = None,
        space_after: float = 3,
    ) -> Any:
        """Add a bullet point item."""
        p = self.doc.add_paragraph(style="List Bullet")
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(space_after)
        if level > 0:
            p.paragraph_format.left_indent = Inches(0.25 * level)

        if bold_prefix:
            r_pre = p.add_run(bold_prefix)
            r_pre.font.name = self.font_name
            r_pre.font.size = Pt(10.5)
            r_pre.font.bold = True
            r_pre.font.color.rgb = _rgb(self.t["primary"])

        run = p.add_run(text)
        run.font.name = self.font_name
        run.font.size = Pt(10.5)
        run.font.color.rgb = _rgb(self.t["text"])
        return p

    # Backward compatibility aliases
    def add_title(self, text: str, subtitle: str | None = None) -> Any:
        self.heading(text, level=1, size=24, space_before=0, space_after=4)
        if subtitle:
            self.text(subtitle, size=13, color=self.t["muted"], italic=True, space_after=14)

    def add_heading(self, text: str, level: int = 1) -> Any:
        return self.heading(text, level=level)

    def add_paragraph(self, text: str) -> Any:
        return self.text(text, size=11, space_after=6)

    def add_bullet(self, text: str) -> Any:
        return self.bullet(text)

    # ---- Structural Primitives -------------------------------------------- #
    def card(
        self,
        title: str | None = None,
        body: str | None = None,
        items: list[str] | None = None,
        bg_color: str | None = None,
        border_color: str | None = None,
    ) -> Any:
        """Render a styled visual container card."""
        bg = self.color(bg_color or self.t["surface"])
        bc = self.color(border_color or self.t["line"])

        tbl = self.doc.add_table(rows=1, cols=1)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = False
        tbl.columns[0].width = Inches(6.5)

        cell = tbl.cell(0, 0)
        _set_cell_bg(cell, bg)
        _set_cell_margins(cell, top=140, bottom=140, left=180, right=180)

        p = cell.paragraphs[0]
        if title:
            r_title = p.add_run(f"{title}\n")
            r_title.font.name = self.font_name
            r_title.font.size = Pt(12)
            r_title.font.bold = True
            r_title.font.color.rgb = _rgb(self.t["primary"])
        if body:
            r_body = p.add_run(body)
            r_body.font.name = self.font_name
            r_body.font.size = Pt(10.5)
            r_body.font.color.rgb = _rgb(self.t["text"])
        if items:
            for it in items:
                p_it = cell.add_paragraph()
                p_it.paragraph_format.space_before = Pt(1)
                p_it.paragraph_format.space_after = Pt(2)
                r_it = p_it.add_run(f"• {it}")
                r_it.font.name = self.font_name
                r_it.font.size = Pt(10)
                r_it.font.color.rgb = _rgb(self.t["text"])

        # Spacing after card
        sp = self.doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(0)
        sp.paragraph_format.space_after = Pt(6)
        return tbl

    def callout(
        self,
        text: str,
        label: str | None = None,
        bg_color: str | None = None,
        border_color: str | None = None,
    ) -> Any:
        """Render an emphasized callout highlight panel."""
        bg = self.color(bg_color or self.t["highlight"])
        bc = self.color(border_color or self.t["accent"])
        return self.card(title=f"NOTE: {label}" if label else None, body=text, bg_color=bg, border_color=bc)

    def table(
        self,
        data: Sequence[Sequence[Any]],
        col_widths: Sequence[float] | None = None,
        header: bool = True,
        header_bg: str | None = None,
        header_color: str = "FFFFFF",
        alt_bg: str | None = None,
    ) -> Any:
        """Add a cleanly styled data table."""
        if not data:
            return None
        rows_cnt = len(data)
        cols_cnt = len(data[0])

        tbl = self.doc.add_table(rows=rows_cnt, cols=cols_cnt)
        tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        tbl.autofit = False

        h_bg = self.color(header_bg or self.t["primary"])
        alt_hex = self.color(alt_bg or self.t["surface"]) if alt_bg else None

        for r_idx, row in enumerate(data):
            is_hdr = header and r_idx == 0
            for c_idx, val in enumerate(row):
                cell = tbl.cell(r_idx, c_idx)
                cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
                _set_cell_margins(cell, top=100, bottom=100, left=120, right=120)

                if is_hdr:
                    _set_cell_bg(cell, h_bg)
                elif alt_hex and r_idx % 2 == 1:
                    _set_cell_bg(cell, alt_hex)
                else:
                    _set_cell_bg(cell, "FFFFFF")

                p = cell.paragraphs[0]
                p.paragraph_format.space_before = Pt(0)
                p.paragraph_format.space_after = Pt(0)
                run = p.add_run(str(val))
                run.font.name = self.font_name
                run.font.size = Pt(10 if is_hdr else 9.5)
                run.font.bold = is_hdr
                run.font.color.rgb = _rgb(header_color if is_hdr else self.t["text"])

        # Column widths
        if col_widths and len(col_widths) == cols_cnt:
            for r in tbl.rows:
                for c_idx, w in enumerate(col_widths):
                    r.cells[c_idx].width = Inches(w)

        # Spacing after table
        sp = self.doc.add_paragraph()
        sp.paragraph_format.space_before = Pt(0)
        sp.paragraph_format.space_after = Pt(6)
        return tbl

    def divider(self, color: str | None = None) -> Any:
        """Add a clean horizontal divider."""
        c = self.color(color or self.t["line"])
        p = self.doc.add_paragraph()
        p.paragraph_format.space_before = Pt(6)
        p.paragraph_format.space_after = Pt(8)
        run = p.add_run("―" * 45)
        run.font.name = self.font_name
        run.font.size = Pt(9)
        run.font.color.rgb = _rgb(c)
        return p

    def image(self, path: str | Path, width: float = 4.0) -> Any:
        """Add an image if file exists."""
        img_path = Path(path)
        if img_path.exists():
            return self.doc.add_picture(str(img_path), width=Inches(width))
        return None

    # ---- Save Contract ---------------------------------------------------- #
    def save(self, path: str | Path = "document.docx") -> dict[str, Any]:
        """Save file and return standard execution status dict."""
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        self.doc.save(str(dest))
        return {"status": "success", "file": str(dest)}
