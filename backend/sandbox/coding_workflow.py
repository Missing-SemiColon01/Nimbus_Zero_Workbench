"""Coding workflow that verifies model-generated code in the sandbox."""

from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
import uuid
from typing import Any

from backend.models.contracts import ModelRequest
from backend.models.providers import ProviderError, ProviderRequestError
from backend.models.router import NoCompatibleModelError, ModelRouter
from backend.tools.registry import ToolRegistry


_FENCED_CODE = re.compile(r"```(?:python|py)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


@dataclass(frozen=True)
class CodingAttempt:
    attempt: int
    code: str
    exit_code: int
    stdout: str
    stderr: str
    test_passed: bool
    timed_out: bool
    error: str | None = None


@dataclass(frozen=True)
class CodingWorkflowResult:
    task_id: str
    status: str
    selected_model: str | None
    provider: str | None
    attempted_models: list[str]
    verified_code: str
    attempts: list[CodingAttempt] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    execution_duration: float | None = None


class CodingWorkflow:
    """Generate code with a coding model, run tests, and retry with feedback."""

    def __init__(
        self,
        router: ModelRouter,
        providers: Any,
        tools: ToolRegistry,
        *,
        max_retries: int = 3,
        timeout_seconds: int = 30,
    ) -> None:
        self.router = router
        self.providers = providers
        self.tools = tools
        self.max_retries = max_retries
        self.timeout_seconds = timeout_seconds

    async def run(
        self,
        requirement: str,
        test_code: str,
        *,
        task_id: str | None = None,
        max_retries: int | None = None,
        timeout_seconds: int | None = None,
    ) -> CodingWorkflowResult:
        start = time.perf_counter()
        resolved_task_id = task_id or str(uuid.uuid4())
        retry_limit = self.max_retries if max_retries is None else max_retries
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        attempts: list[CodingAttempt] = []
        errors: list[str] = []
        attempted_models: list[str] = []
        selected_model = None
        provider = None
        last_code = ""

        try:
            candidates = self.router.candidates(ModelRequest(requirement, {"coding"}, "text"))
            if not candidates:
                self.router.select(ModelRequest(requirement, {"coding"}, "text"))
        except NoCompatibleModelError as error:
            return self._failed(
                resolved_task_id,
                attempts,
                attempted_models,
                errors=[str(error)],
                started_at=start,
                selected_model=None,
                provider=None,
                verified_code="",
            )

        feedback = ""
        total_rounds = max(retry_limit, 0) + 1
        for round_index in range(total_rounds):
            for model in candidates:
                if model.id not in attempted_models:
                    attempted_models.append(model.id)
                selected_model = model.id
                provider = model.runtime
                prompt = self._prompt(requirement, test_code, feedback, round_index + 1)

                try:
                    response = await self.providers.generate(
                        model,
                        ModelRequest(prompt=prompt, required_capabilities={"coding"}, required_modality="text"),
                    )
                except ProviderRequestError as error:
                    errors.append(str(error))
                    return self._failed(
                        resolved_task_id,
                        attempts,
                        attempted_models,
                        errors=errors,
                        started_at=start,
                        selected_model=selected_model,
                        provider=provider,
                        verified_code=last_code,
                    )
                except ProviderError as error:
                    errors.append(str(error))
                    continue

                code = extract_python_code(response.content)
                last_code = code
                attempt = await self._run_sandbox(len(attempts) + 1, code, test_code, timeout)
                attempts.append(attempt)
                if attempt.test_passed:
                    return CodingWorkflowResult(
                        task_id=resolved_task_id,
                        status="completed",
                        selected_model=selected_model,
                        provider=provider,
                        attempted_models=attempted_models,
                        verified_code=code,
                        attempts=attempts,
                        errors=errors,
                        execution_duration=round(time.perf_counter() - start, 4),
                    )
                feedback = self._feedback(attempt)

        return self._failed(
            resolved_task_id,
            attempts,
            attempted_models,
            errors=[*errors, f"Tests did not pass after {len(attempts)} attempt(s)."],
            started_at=start,
            selected_model=selected_model,
            provider=provider,
            verified_code=last_code,
        )

    async def _run_sandbox(self, attempt: int, code: str, test_code: str, timeout_seconds: int) -> CodingAttempt:
        tool = self.tools.get("sandbox.execute")
        result = await tool.execute(
            {
                "code": code,
                "test_code": test_code,
                "language": "python",
                "timeout_seconds": timeout_seconds,
            },
            context={},
        )
        output = result.output if isinstance(result.output, dict) else {}
        return CodingAttempt(
            attempt=attempt,
            code=code,
            exit_code=int(output.get("exit_code", -1)),
            stdout=str(output.get("stdout", "")),
            stderr=str(output.get("stderr", result.error or "")),
            test_passed=bool(output.get("test_passed", False)),
            timed_out=bool(output.get("timed_out", False)),
            error=result.error,
        )

    @staticmethod
    def _prompt(requirement: str, test_code: str, feedback: str, attempt: int) -> str:
        repair = f"\nPrevious sandbox failure:\n{feedback}\nFix the code." if feedback else ""
        return (
            "Generate a single Python solution file for this requirement. "
            "Return only Python code, or one Python fenced code block. "
            "Do not include markdown explanations.\n\n"
            f"Requirement:\n{requirement}\n\n"
            f"Tests that must pass:\n{test_code}\n"
            f"{repair}\n"
            f"Attempt: {attempt}"
        )

    @staticmethod
    def _feedback(attempt: CodingAttempt) -> str:
        return (
            f"exit_code={attempt.exit_code}\n"
            f"timed_out={attempt.timed_out}\n"
            f"stdout:\n{attempt.stdout[-4000:]}\n"
            f"stderr:\n{attempt.stderr[-4000:]}\n"
            f"error={attempt.error or ''}"
        )

    @staticmethod
    def _failed(
        task_id: str,
        attempts: list[CodingAttempt],
        attempted_models: list[str],
        *,
        errors: list[str],
        started_at: float,
        selected_model: str | None,
        provider: str | None,
        verified_code: str,
    ) -> CodingWorkflowResult:
        return CodingWorkflowResult(
            task_id=task_id,
            status="failed",
            selected_model=selected_model,
            provider=provider,
            attempted_models=attempted_models,
            verified_code=verified_code,
            attempts=attempts,
            errors=errors,
            execution_duration=round(time.perf_counter() - started_at, 4),
        )


def extract_python_code(content: str) -> str:
    """Extract Python from a model response while tolerating fenced output."""
    match = _FENCED_CODE.search(content)
    if match:
        return match.group(1).strip()
    return content.strip()
