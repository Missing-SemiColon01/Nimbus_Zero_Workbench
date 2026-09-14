"""Artifact specifications and local generators."""

from backend.artifacts.contracts import ApprovalNoteSpec, Artifact, ArtifactValidation, PresentationSpec, SlideLayout, SlideSpec
from backend.artifacts.docx_generator import DocxGenerator
from backend.artifacts.pptx_generator import PptxGenerator
from backend.artifacts.pdf_generator import PdfApprovalNoteGenerator
from backend.artifacts.pdf_validator import PdfArtifactValidator
from backend.artifacts.office_validator import OfficeArtifactValidator
from backend.artifacts.office_renderer import LibreOfficeRenderer
from backend.artifacts.tools import DocumentCreateTool, PdfCreateTool, PresentationCreateTool
from backend.artifacts.validation_tool import ArtifactValidateTool

__all__ = [
    "ApprovalNoteSpec",
    "Artifact",
    "ArtifactValidation",
    "PresentationSpec",
    "SlideLayout",
    "SlideSpec",
    "DocxGenerator",
    "PptxGenerator",
    "PdfApprovalNoteGenerator",
    "PdfArtifactValidator",
    "OfficeArtifactValidator",
    "LibreOfficeRenderer",
    "DocumentCreateTool",
    "PdfCreateTool",
    "PresentationCreateTool",
    "ArtifactValidateTool",
]
