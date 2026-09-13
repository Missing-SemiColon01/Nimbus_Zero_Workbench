"""Artifact specifications and local generators."""

from backend.artifacts.contracts import ApprovalNoteSpec, Artifact, PresentationSpec, SlideLayout, SlideSpec
from backend.artifacts.docx_generator import DocxGenerator
from backend.artifacts.pptx_generator import PptxGenerator
from backend.artifacts.pdf_generator import PdfApprovalNoteGenerator
from backend.artifacts.tools import DocumentCreateTool, PresentationCreateTool

__all__ = [
    "ApprovalNoteSpec",
    "Artifact",
    "PresentationSpec",
    "SlideLayout",
    "SlideSpec",
    "DocxGenerator",
    "PptxGenerator",
    "PdfApprovalNoteGenerator",
    "DocumentCreateTool",
    "PresentationCreateTool",
]
