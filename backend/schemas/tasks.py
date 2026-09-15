from typing import Literal

from pydantic import BaseModel, Field


TASK_TYPE_CAPABILITIES: dict[str, set[str]] = {
    "reasoning": {"reasoning"},
    "planning": {"planning"},
    "coding": {"coding"},
    "debugging": {"debugging"},
    "vision": {"vision"},
    "document_understanding": {"document_understanding"},
}

TaskType = Literal[
    "reasoning", "planning", "coding", "debugging", "vision", "document_understanding"
]


class TaskCreate(BaseModel):
    request: str = Field(min_length=1, max_length=20000)
    task_type: TaskType | None = None
    capabilities: set[str] = Field(default_factory=set)
    modality: str = "text"
    images: list[str] = Field(default_factory=list, description="Optional base64-encoded image inputs.")
    documents: list[str] = Field(default_factory=list, description="Optional encoded document inputs.")

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
