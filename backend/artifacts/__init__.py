"""Artifact specifications and local generators."""

from backend.artifacts.contracts import (
    ApprovalNoteSpec,
    Artifact,
    ArtifactValidation,
    ColumnDef,
    PresentationSpec,
    SheetSpec,
    SlideLayout,
    SlideSpec,
    SpreadsheetSpec,
)
from backend.artifacts.docx_generator import DocxGenerator
from backend.artifacts.pptx_generator import PptxGenerator
from backend.artifacts.pdf_generator import PdfApprovalNoteGenerator
from backend.artifacts.xlsx_generator import XlsxGenerator
from backend.artifacts.pdf_validator import PdfArtifactValidator
from backend.artifacts.office_validator import OfficeArtifactValidator
from backend.artifacts.office_renderer import LibreOfficeRenderer
from backend.artifacts.tools import DocumentCreateTool, PdfCreateTool, PresentationCreateTool, SpreadsheetCreateTool
from backend.artifacts.validation_tool import ArtifactValidateTool

__all__ = [
    "ApprovalNoteSpec",
    "Artifact",
    "ArtifactValidation",
    "ColumnDef",
    "PresentationSpec",
    "SheetSpec",
    "SlideLayout",
    "SlideSpec",
    "SpreadsheetSpec",
    "DocxGenerator",
    "PptxGenerator",
    "PdfApprovalNoteGenerator",
    "XlsxGenerator",
    "PdfArtifactValidator",
    "OfficeArtifactValidator",
    "LibreOfficeRenderer",
    "DocumentCreateTool",
    "PdfCreateTool",
    "PresentationCreateTool",
    "SpreadsheetCreateTool",
    "ArtifactValidateTool",
]
