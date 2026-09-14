"""
backend/schemas/artifacts.py
============================
Pydantic schemas for listing, previewing, and downloading locally generated artifacts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ArtifactInfo(BaseModel):
    """Information about a locally generated artifact."""

    filename: str = Field(..., description="File name of the artifact.")
    file_type: str = Field(..., description="Type of artifact (docx, pptx, pdf, etc.).")
    size_bytes: int = Field(..., description="Size in bytes.")
    download_url: str = Field(..., description="Relative API download endpoint.")
    preview_url: str | None = Field(None, description="Relative preview image endpoint, if available.")
    modified_at: datetime = Field(..., description="File modification timestamp.")

