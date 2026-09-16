from typing import Any, Literal

from pydantic import BaseModel, Field

from backend.schemas.artifacts import ArtifactInfo


TASK_TYPE_CAPABILITIES: dict[str, set[str]] = {
    "reasoning": {"reasoning"},
    "planning": {"planning"},
    "coding": {"coding"},
    "debugging": {"debugging"},
    "vision": {"vision"},
    "document_understanding": {"document_understanding"},
    "report": {"reasoning"},
}

TaskType = Literal[
    "reasoning", "planning", "coding", "debugging", "vision", "document_understanding", "report"
]


class TaskCreate(BaseModel):
    request: str = Field(min_length=1, max_length=20000)
    task_type: TaskType | None = None
    capabilities: set[str] = Field(default_factory=set)
    modality: str = "text"
    images: list[str] = Field(default_factory=list, description="Optional base64-encoded image inputs.")
    documents: list[str] = Field(default_factory=list, description="Optional encoded document inputs.")
    document_paths: list[str] = Field(
        default_factory=list,
        description="Optional local uploaded document paths returned by /ingest/upload.",
    )
    approved_tools: set[str] = Field(
        default_factory=set,
        description="Tool names explicitly approved by a human for this task run.",
    )

    @property
    def required_capabilities(self) -> set[str]:
        """Map a task type, while keeping the existing capability API compatible."""
        if self.task_type is not None:
            return TASK_TYPE_CAPABILITIES[self.task_type] | self.capabilities
        return self.capabilities or {"reasoning"}


class TaskResponse(BaseModel):
    task_id: str
    status: str
    selected_model: str | None
    provider: str | None
    fallback_used: bool
    attempted_models: list[str]
    plan: list[str]
    response: str
    execution_duration: float | None = None
    artifacts: list[str] = Field(default_factory=list)
    generated_artifacts: list[ArtifactInfo] = Field(default_factory=list)
    tool_results: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    approval_required: bool = False
    approval_requests: list[dict[str, Any]] = Field(default_factory=list)
