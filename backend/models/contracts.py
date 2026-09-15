from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolCall:
    name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    id: str | None = None


@dataclass(frozen=True)
class ToolExecutionResult:
    name: str
    success: bool
    output: Any
    error: str | None = None
    artifacts: list[str] = field(default_factory=list)
    id: str | None = None


@dataclass(frozen=True)
class ModelRequest:
    prompt: str
    required_capabilities: set[str] = field(default_factory=set)
    required_modality: str = "text"
    images: list[str] = field(default_factory=list)
    # Provider-neutral document attachments.  Providers may accept encoded
    # documents directly or transform them into their native attachment form.
    documents: list[str] = field(default_factory=list)
    tools: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[ToolExecutionResult] = field(default_factory=list)


@dataclass(frozen=True)
class ModelResponse:
    content: str
    model_id: str
    raw: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[ToolCall] = field(default_factory=list)


@dataclass(frozen=True)
class ModelDefinition:
    id: str
    runtime: str
    model: str
    capabilities: set[str]
    modalities: set[str]
    priority: int = 0
    enabled: bool = True
