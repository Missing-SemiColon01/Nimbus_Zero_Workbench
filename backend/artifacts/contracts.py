"""Typed, framework-independent contracts for generated deliverables."""

from datetime import date, datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class Artifact(BaseModel):
    """A generated file stored inside the local artifact directory."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    type: str
    filename: str
    mime_type: str
    storage_uri: str
    task_id: str
    version: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ArtifactValidation(BaseModel):
    """Local validation result for a generated deliverable."""

    artifact_id: str | None = None
    valid: bool
    checks: dict[str, bool] = Field(default_factory=dict)
    findings: list[str] = Field(default_factory=list)
    preview_path: str | None = None


class ApprovalNoteSpec(BaseModel):
    """Structured input for a professional, traceable approval-note DOCX."""

    title: str = "Approval Note"
    subject: str = Field(min_length=1, max_length=500)
    recipient: str | None = None
    reference_number: str | None = None
    purpose: str = Field(min_length=1)
    background: str | None = None
    findings: list[str] = Field(default_factory=list)
    recommendation: str = Field(min_length=1)
    requested_approval: str = Field(min_length=1)
    prepared_by: str | None = None
    document_date: date = Field(default_factory=date.today)
    source_references: list[str] = Field(default_factory=list)

    @field_validator("findings", "source_references")
    @classmethod
    def remove_blank_items(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class SlideLayout(str, Enum):
    TITLE = "title"
    EXECUTIVE_SUMMARY = "executive_summary"
    TWO_COLUMN = "two_column"
    ARCHITECTURE = "architecture"
    DATA_CHART = "data_chart"
    RECOMMENDATION = "recommendation"


class ChartSeries(BaseModel):
    name: str = Field(min_length=1)
    values: list[float] = Field(min_length=1)


class SlideSpec(BaseModel):
    """Content for one of the six supported presentation layouts."""

    layout: SlideLayout
    title: str = Field(min_length=1, max_length=180)
    subtitle: str | None = None
    bullets: list[str] = Field(default_factory=list)
    left_heading: str | None = None
    left_items: list[str] = Field(default_factory=list)
    right_heading: str | None = None
    right_items: list[str] = Field(default_factory=list)
    diagram_nodes: list[str] = Field(default_factory=list)
    chart_categories: list[str] = Field(default_factory=list)
    chart_series: list[ChartSeries] = Field(default_factory=list)
    recommendation: str | None = None
    decision_points: list[str] = Field(default_factory=list)

    @field_validator(
        "bullets", "left_items", "right_items", "diagram_nodes", "chart_categories", "decision_points"
    )
    @classmethod
    def clean_lists(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]

    def model_post_init(self, __context: Any) -> None:
        if self.layout == SlideLayout.DATA_CHART:
            if not self.chart_categories or not self.chart_series:
                raise ValueError("data_chart slides require chart_categories and chart_series")
            if any(len(series.values) != len(self.chart_categories) for series in self.chart_series):
                raise ValueError("every chart series must have one value per chart category")


class PresentationSpec(BaseModel):
    """LLM-safe intermediate representation; generators own PowerPoint objects."""

    title: str = Field(min_length=1, max_length=180)
    subtitle: str | None = None
    author: str | None = None
    slides: list[SlideSpec] = Field(min_length=1, max_length=30)


class ColumnDef(BaseModel):
    """Definition for a spreadsheet column."""

    key: str = Field(min_length=1)
    header: str = Field(min_length=1)
    width: float | None = None


class SheetSpec(BaseModel):
    """Specification for a single worksheet in an Excel workbook."""

    title: str = Field(default="Sheet1", min_length=1, max_length=31)
    columns: list[ColumnDef] = Field(min_length=1)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    summary_row: bool = False


class SpreadsheetSpec(BaseModel):
    """Structured input for a sovereign, styled XLSX workbook."""

    title: str = Field(min_length=1, max_length=100)
    sheets: list[SheetSpec] = Field(min_length=1, max_length=10)
    author: str | None = None



def artifact_from_path(path: Path, *, artifact_type: str, mime_type: str, task_id: str, metadata: dict[str, Any]) -> Artifact:
    return Artifact(
        type=artifact_type,
        filename=path.name,
        mime_type=mime_type,
        storage_uri=str(path.resolve()),
        task_id=task_id,
        metadata=metadata,
    )
