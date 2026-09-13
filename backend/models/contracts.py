from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelRequest:
    prompt: str
    required_capabilities: set[str] = field(default_factory=set)
    required_modality: str = "text"
    images: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ModelResponse:
    content: str
    model_id: str
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ModelDefinition:
    id: str
    runtime: str
    model: str
    capabilities: set[str]
    modalities: set[str]
    priority: int = 0
    enabled: bool = True
