"""Typed, framework-independent contracts for generated deliverables."""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


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


def artifact_from_path(path: Path, *, artifact_type: str, mime_type: str, task_id: str, metadata: dict[str, Any]) -> Artifact:
    return Artifact(
        type=artifact_type,
        filename=path.name,
        mime_type=mime_type,
        storage_uri=str(path.resolve()),
        task_id=task_id,
        metadata=metadata,
    )
