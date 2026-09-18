"""Tool adapter for sandboxed code execution."""

from __future__ import annotations

import logging
from typing import Any

from backend.sandbox.contracts import SandboxRequest
from backend.sandbox.executor import SandboxExecutor
from backend.tools.contracts import Tool, ToolResult

from pathlib import Path

logger = logging.getLogger(__name__)


class SandboxTool(Tool):
    """Execute Python code in an isolated sandbox and capture results."""

    name = "sandbox.execute"
    description = "Execute Python code in a network-disabled sandbox with optional pytest tests."
    parameters = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "test_code": {"type": "string"},
            "language": {"type": "string"},
            "timeout_seconds": {"type": "integer"},
        },
        "required": ["code"],
    }

    def __init__(self, executor: SandboxExecutor, artifacts_dir: Path | str | None = None) -> None:
        self.executor = executor
        self.artifacts_dir = str(artifacts_dir) if artifacts_dir else None

    async def execute(self, arguments: dict[str, Any], context: dict[str, Any]) -> ToolResult:
        code = arguments.get("code", "")
        if not isinstance(code, str) or not code.strip():
            return ToolResult(success=False, output=None, error="No code provided.")

        task_id = context.get("task_id")
        artifacts_dir = context.get("artifacts_dir") or self.artifacts_dir

        request = SandboxRequest(
            code=code,
            test_code=arguments.get("test_code", "") or "",
            language=arguments.get("language", "python") or "python",
            timeout_seconds=int(arguments.get("timeout_seconds", 30) or 30),
            task_id=str(task_id) if task_id else None,
            artifacts_dir=str(artifacts_dir) if artifacts_dir else None,
        )

        try:
            result = self.executor.run(request)
        except Exception as exc:
            logger.exception("Sandbox execution failed.")
            return ToolResult(success=False, output=None, error=str(exc))

        return ToolResult(
            success=result.success,
            output={
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "test_passed": result.test_passed,
                "timed_out": result.timed_out,
                "summary": result.short_summary(),
                "artifacts": result.artifacts,
                "generated_files": result.generated_files,
            },
            error=result.error,
            artifacts=result.artifacts,
        )
