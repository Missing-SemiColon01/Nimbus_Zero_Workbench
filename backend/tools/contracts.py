from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    success: bool
    output: Any
    error: str | None = None
    artifacts: list[str] = field(default_factory=list)


class Tool:
    name: str
    async def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        raise NotImplementedError
