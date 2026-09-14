"""Local XLSX spreadsheet generator using openpyxl with Sovereign Workbench theme."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from backend.artifacts.contracts import Artifact, SheetSpec, SpreadsheetSpec, artifact_from_path
from backend.artifacts.theme import WorkbenchTheme


class XlsxGenerator:
    """Generate professional, styled XLSX workbooks from SpreadsheetSpec."""

    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)

    def generate(self, spec: SpreadsheetSpec, *, task_id: str) -> Artifact:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        wb = Workbook()
        # Remove default active sheet if sheets are defined
        wb.remove(wb.active)

        for sheet_spec in spec.sheets:
            ws = wb.create_sheet(title=sheet_spec.title[:31])
            self._render_sheet(ws, sheet_spec, title=spec.title)

        filename = f"{self._safe_name(spec.title)}.xlsx"
        path = self.output_dir / filename
        wb.save(path)

        return artifact_from_path(
            path,
            artifact_type="xlsx",
            mime_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            task_id=task_id,
            metadata={
                "title": spec.title,
                "sheet_count": len(spec.sheets),
                "sheets": [s.title for s in spec.sheets],
                "theme": WorkbenchTheme.name,
            },
        )

    def _render_sheet(self, ws, sheet_spec: SheetSpec, title: str) -> None:
        # Title block
        ws.append([title])
        title_cell = ws.cell(row=1, column=1)
        title_cell.font = Font(name=WorkbenchTheme.title_font, size=14, bold=True, color=WorkbenchTheme.navy)
        ws.row_dimensions[1].height = 28

        # Sheet section subtitle
        ws.append([sheet_spec.title])
        subtitle_cell = ws.cell(row=2, column=1)
        subtitle_cell.font = Font(name=WorkbenchTheme.font, size=11, italic=True, color=WorkbenchTheme.slate)
        ws.row_dimensions[2].height = 20

        # Blank row
        ws.append([])
        ws.row_dimensions[3].height = 10

        # Table Headers (Row 4)
        header_row = [col.header for col in sheet_spec.columns]
        ws.append(header_row)
        header_row_idx = 4
        ws.row_dimensions[header_row_idx].height = 24

        header_fill = PatternFill(start_color=WorkbenchTheme.navy, end_color=WorkbenchTheme.navy, fill_type="solid")
        header_font = Font(name=WorkbenchTheme.font, size=11, bold=True, color=WorkbenchTheme.white)
        header_align = Alignment(horizontal="center", vertical="center")
        thin_border_side = Side(style="thin", color="CCCCCC")
        border = Border(left=thin_border_side, right=thin_border_side, top=thin_border_side, bottom=thin_border_side)

        for col_idx in range(1, len(sheet_spec.columns) + 1):
            cell = ws.cell(row=header_row_idx, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = header_align
            cell.border = border

        # Data rows
        zebra_fill = PatternFill(start_color=WorkbenchTheme.light_gray, end_color=WorkbenchTheme.light_gray, fill_type="solid")
        data_font = Font(name=WorkbenchTheme.font, size=10, color=WorkbenchTheme.dark)
        current_row = 5

        for r_idx, row_dict in enumerate(sheet_spec.rows):
            row_values = []
            for col in sheet_spec.columns:
                val = row_dict.get(col.key, "")
                row_values.append(val)
            ws.append(row_values)

            # Apply styling
            for col_idx, val in enumerate(row_values, start=1):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.font = data_font
                cell.border = border
                if r_idx % 2 == 1:
                    cell.fill = zebra_fill
                if isinstance(val, (int, float)):
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    if isinstance(val, float):
                        cell.number_format = "#,##0.00"
                    else:
                        cell.number_format = "#,##0"
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
            current_row += 1

        # Summary / Totals row if requested
        if sheet_spec.summary_row and sheet_spec.rows:
            summary_values = []
            for col_idx, col in enumerate(sheet_spec.columns, start=1):
                numeric_vals = [
                    row.get(col.key)
                    for row in sheet_spec.rows
                    if isinstance(row.get(col.key), (int, float))
                ]
                if numeric_vals:
                    col_letter = get_column_letter(col_idx)
                    formula = f"=SUM({col_letter}5:{col_letter}{current_row - 1})"
                    summary_values.append(formula)
                elif col_idx == 1:
                    summary_values.append("Total")
                else:
                    summary_values.append("")

            ws.append(summary_values)
            summary_fill = PatternFill(start_color=WorkbenchTheme.light_blue, end_color=WorkbenchTheme.light_blue, fill_type="solid")
            summary_font = Font(name=WorkbenchTheme.font, size=11, bold=True, color=WorkbenchTheme.navy)
            double_bottom_border = Border(
                top=Side(style="thin", color="000000"),
                bottom=Side(style="double", color="000000"),
                left=thin_border_side,
                right=thin_border_side,
            )

            for col_idx, val in enumerate(summary_values, start=1):
                cell = ws.cell(row=current_row, column=col_idx)
                cell.fill = summary_fill
                cell.font = summary_font
                cell.border = double_bottom_border
                if str(val).startswith("="):
                    cell.alignment = Alignment(horizontal="right", vertical="center")
                    cell.number_format = "#,##0.00"
                else:
                    cell.alignment = Alignment(horizontal="left", vertical="center")
            current_row += 1

        # Auto-adjust column widths
        for col_idx, col in enumerate(sheet_spec.columns, start=1):
            col_letter = get_column_letter(col_idx)
            if col.width:
                ws.column_dimensions[col_letter].width = col.width
            else:
                max_len = max(
                    len(col.header),
                    max((len(str(r.get(col.key, ""))) for r in sheet_spec.rows), default=0),
                )
                ws.column_dimensions[col_letter].width = max(max_len + 4, 12)

    @staticmethod
    def _safe_name(value: str) -> str:
        return re.sub(r"[^A-Za-z0-9._-]+", "-", value).strip("-.")[:80] or "spreadsheet"

