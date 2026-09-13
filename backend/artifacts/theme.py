"""Shared visual language for local DOCX and PPTX deliverables."""

from docx.shared import RGBColor as DocxRGBColor
from pptx.dml.color import RGBColor as PptxRGBColor


class WorkbenchTheme:
    name = "Sovereign Engineering"
    navy = "102A43"
    blue = "1F6FEB"
    teal = "00A6A6"
    slate = "52606D"
    light_blue = "EAF2FF"
    light_gray = "F5F7FA"
    white = "FFFFFF"
    dark = "1F2933"
    font = "Aptos"
    title_font = "Aptos Display"

    @classmethod
    def ppt_color(cls, value: str) -> PptxRGBColor:
        return PptxRGBColor.from_string(value)

    @classmethod
    def docx_color(cls, value: str) -> DocxRGBColor:
        return DocxRGBColor.from_string(value)
