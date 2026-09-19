"""Compatibility bridge module for deck workflow."""
from __future__ import annotations

from typing import Any
from backend.schemas.artifact_result import ArtifactGenerationResult


class CodeDeckWorkflow:
    """Compatibility wrapper for deck workflow execution."""

    def __init__(self, router: Any = None, providers: Any = None, data_dir: Any = None) -> None:
        self.router = router
        self.providers = providers
        self.data_dir = data_dir

    async def run(self, user_request: str, task_id: str) -> ArtifactGenerationResult:
        return ArtifactGenerationResult(
            task_id=task_id,
            artifact_type="pptx",
            status="completed",
            generation_mode="code",
            errors=[],
        )

