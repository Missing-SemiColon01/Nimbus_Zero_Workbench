"""Typed result schema for artifact-generation orchestration."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ArtifactGenerationResult(BaseModel):
    """Structured response from the artifact-generation orchestration flow."""

    task_id: str = Field(..., description="Unique identifier for the generation task.")
    artifact_type: str = Field(
        ...,
        description="Kind of artifact produced: document, presentation, pdf, or spreadsheet.",
    )
    status: str = Field(
        ...,
        description="Outcome of the orchestration: completed, failed, or validation_failed.",
    )
    path: str | None = Field(
        None,
        description="Local filesystem path (storage_uri) of the generated artifact.",
    )
    download_url: str | None = Field(
        None,
        description="Relative API download endpoint for the artifact.",
    )
    artifact_metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Full artifact metadata returned by the creation tool.",
    )
    errors: list[str] = Field(
        default_factory=list,
        description="Error messages accumulated during orchestration.",
    )
    generation_mode: str = Field(
        default="structured",
        description="Generation strategy used: 'structured' or 'code'.",
    )
    code: str | None = Field(
        default=None,
        description="Python code generated when code-based artifact generation is used.",
    )
    attempts: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Iteration attempts during code generation and sandbox verification.",
    )
    # Keep artifact runs observable through the same task trace returned by
    # POST /tasks.  Defaults retain the small result contract used by callers
    # that only need artifact metadata.
    selected_model: str | None = None
    provider: str | None = None
    fallback_used: bool = False
    attempted_models: list[str] = Field(default_factory=list)
    plan: list[str] = Field(default_factory=list)
    response: str = ""
    execution_duration: float | None = None
    artifacts: list[str] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    approval_required: bool = False
    approval_requests: list[dict[str, Any]] = Field(default_factory=list)
