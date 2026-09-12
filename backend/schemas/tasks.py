from pydantic import BaseModel, Field


class TaskCreate(BaseModel):
    request: str = Field(min_length=1, max_length=20000)
    capabilities: set[str] = Field(default_factory=lambda: {"reasoning"})
    modality: str = "text"


class TaskResponse(BaseModel):
    task_id: str
    status: str
    selected_model: str | None
    plan: list[str]
    response: str
