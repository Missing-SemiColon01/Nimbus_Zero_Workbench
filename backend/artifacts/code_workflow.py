"""Code-based artifact generation workflow inside the isolated Docker sandbox."""

from __future__ import annotations

import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from backend.artifacts.contracts import Artifact, artifact_from_path
from backend.artifacts.office_validator import OfficeArtifactValidator
from backend.artifacts.pdf_validator import PdfArtifactValidator
from backend.models.contracts import ModelRequest
from backend.models.providers import ProviderError, ProviderRequestError
from backend.models.router import ModelRouter, NoCompatibleModelError
from backend.sandbox.coding_workflow import extract_python_code
from backend.tools.registry import ToolRegistry
from backend.agents.events import AgentEventStreamer

logger = logging.getLogger(__name__)


MIME_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "document": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "presentation": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

EXTENSION_MAP = {
    "pdf": ".pdf",
    "docx": ".docx",
    "document": ".docx",
    "pptx": ".pptx",
    "presentation": ".pptx",
    "xlsx": ".xlsx",
    "spreadsheet": ".xlsx",
}


@dataclass(frozen=True)
class CodeArtifactAttempt:
    """One code generation and sandbox execution attempt."""

    attempt: int
    code: str
    exit_code: int
    stdout: str
    stderr: str
    timed_out: bool
    generated_files: list[str]
    verification_passed: bool
    findings: list[str] = field(default_factory=list)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "attempt": self.attempt,
            "code": self.code,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "timed_out": self.timed_out,
            "generated_files": self.generated_files,
            "verification_passed": self.verification_passed,
            "findings": self.findings,
            "error": self.error,
        }


@dataclass(frozen=True)
class CodeArtifactResult:
    """Outcome of the code-based artifact generation workflow."""

    task_id: str
    artifact_type: str
    status: str
    verified_code: str
    artifact: Artifact | None = None
    path: str | None = None
    download_url: str | None = None
    preview_url: str | None = None
    artifact_metadata: dict[str, Any] = field(default_factory=dict)
    attempts: list[CodeArtifactAttempt] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    selected_model: str | None = None
    provider: str | None = None
    attempted_models: list[str] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    execution_duration: float | None = None


class CodeArtifactWorkflow:
    """Orchestrate code-based artifact generation inside the Docker sandbox.

    Flow:
    1. Select prompt tailored to requested deliverable (reportlab / python-docx / python-pptx).
    2. Prompt coding model to produce a self-contained Python script.
    3. Execute strictly inside the existing network-disabled Docker sandbox.
    4. Harvest generated files and verify artifact validity and readability.
    5. If verification fails, send traceback and findings back through the loop.
    6. Stop when verification passes or max_iterations is reached.
    """

    def __init__(
        self,
        router: ModelRouter,
        providers: Any,
        tools: ToolRegistry,
        *,
        artifacts_dir: Path | None = None,
        previews_dir: Path | None = None,
        max_iterations: int = 3,
        timeout_seconds: int = 45,
    ) -> None:
        self.router = router
        self.providers = providers
        self.tools = tools
        self.artifacts_dir = artifacts_dir or Path("data/artifacts")
        self.previews_dir = previews_dir or Path("data/tmp/artifact-previews")
        self.max_iterations = max(1, max_iterations)
        self.timeout_seconds = timeout_seconds

        # Validators
        self.pdf_validator = PdfArtifactValidator(self.previews_dir)
        self.office_validator = OfficeArtifactValidator()

    async def run(
        self,
        user_request: str,
        artifact_type: str,
        *,
        task_id: str | None = None,
        max_iterations: int | None = None,
        timeout_seconds: int | None = None,
        required_text: list[str] | None = None,
        streamer: AgentEventStreamer | None = None,
    ) -> CodeArtifactResult:
        start_time = time.perf_counter()
        resolved_task_id = task_id or str(uuid.uuid4())
        limit = self.max_iterations if max_iterations is None else max(1, max_iterations)
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        norm_type = self._normalize_artifact_type(artifact_type)
        expected_ext = EXTENSION_MAP.get(norm_type, ".pdf")
        mime_type = MIME_TYPES.get(norm_type, "application/octet-stream")

        attempts: list[CodeArtifactAttempt] = []
        errors: list[str] = []
        attempted_models: list[str] = []
        tool_results: list[dict[str, Any]] = []
        selected_model = None
        provider = None
        last_code = ""

        # Ensure target directories exist
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)
        self.previews_dir.mkdir(parents=True, exist_ok=True)

        # Select model candidates capable of coding
        try:
            candidates = self.router.candidates(ModelRequest(user_request, {"coding"}, "text"))
            if not candidates:
                candidates = self.router.candidates(ModelRequest(user_request, {"reasoning"}, "text"))
            if not candidates:
                self.router.select(ModelRequest(user_request, {"coding"}, "text"))
        except NoCompatibleModelError as error:
            return CodeArtifactResult(
                task_id=resolved_task_id,
                artifact_type=norm_type,
                status="failed",
                verified_code="",
                errors=[str(error)],
                execution_duration=round(time.perf_counter() - start_time, 4),
            )

        feedback = ""
        for round_index in range(limit):
            for model in candidates:
                if model.id not in attempted_models:
                    attempted_models.append(model.id)
                selected_model = model.id
                provider = model.runtime

                prompt = self._build_prompt(
                    user_request=user_request,
                    artifact_type=norm_type,
                    expected_ext=expected_ext,
                    task_id=resolved_task_id,
                    feedback=feedback,
                    attempt=round_index + 1,
                )

                try:
                    response = await self.providers.generate(
                        model,
                        ModelRequest(
                            prompt=prompt,
                            required_capabilities={"coding"},
                            required_modality="text",
                        ),
                    )
                except ProviderRequestError as exc:
                    errors.append(str(exc))
                    return CodeArtifactResult(
                        task_id=resolved_task_id,
                        artifact_type=norm_type,
                        status="failed",
                        verified_code=last_code,
                        attempts=attempts,
                        errors=errors,
                        selected_model=selected_model,
                        provider=provider,
                        attempted_models=attempted_models,
                        tool_results=tool_results,
                        execution_duration=round(time.perf_counter() - start_time, 4),
                    )
                except ProviderError as exc:
                    errors.append(str(exc))
                    continue

                code = extract_python_code(response.content)
                last_code = code

                if streamer is not None:
                    streamer.emit_thought(f"Attempt {round_index + 1}: executing generated code in Docker sandbox...")

                # Execute inside the isolated sandbox (NEVER on the host)
                attempt, candidate_artifact, tool_res_dict = await self._execute_and_verify(
                    code=code,
                    attempt_index=len(attempts) + 1,
                    artifact_type=norm_type,
                    expected_ext=expected_ext,
                    mime_type=mime_type,
                    task_id=resolved_task_id,
                    timeout_seconds=timeout,
                    required_text=required_text,
                )
                attempts.append(attempt)
                if tool_res_dict:
                    tool_results.append(tool_res_dict)

                # Stream sandbox stdout/stderr as log events
                if streamer is not None:
                    for log_line in (attempt.stdout or "").splitlines():
                        if log_line.strip():
                            streamer.emit_tool_call_log("sandbox.execute", log_line)
                    for err_line in (attempt.stderr or "").splitlines():
                        if err_line.strip():
                            streamer.emit_tool_call_log("sandbox.execute", f"[stderr] {err_line}")

                if attempt.verification_passed and candidate_artifact is not None:
                    duration = round(time.perf_counter() - start_time, 4)
                    download_url = f"/api/v1/artifacts/{candidate_artifact.filename}/download"
                    return CodeArtifactResult(
                        task_id=resolved_task_id,
                        artifact_type=norm_type,
                        status="completed",
                        verified_code=code,
                        artifact=candidate_artifact,
                        path=candidate_artifact.storage_uri,
                        download_url=download_url,
                        artifact_metadata=candidate_artifact.model_dump(mode="json"),
                        attempts=attempts,
                        errors=errors,
                        selected_model=selected_model,
                        provider=provider,
                        attempted_models=attempted_models,
                        tool_results=tool_results,
                        execution_duration=duration,
                    )

                # Verification failed; build feedback for next round
                feedback = self._build_feedback(attempt)
                if attempt.error and attempt.error not in errors:
                    errors.append(attempt.error)

        duration = round(time.perf_counter() - start_time, 4)
        return CodeArtifactResult(
            task_id=resolved_task_id,
            artifact_type=norm_type,
            status="failed",
            verified_code=last_code,
            attempts=attempts,
            errors=[*errors, f"Artifact verification did not pass after {len(attempts)} attempt(s)."],
            selected_model=selected_model,
            provider=provider,
            attempted_models=attempted_models,
            tool_results=tool_results,
            execution_duration=duration,
        )

    async def _execute_and_verify(
        self,
        *,
        code: str,
        attempt_index: int,
        artifact_type: str,
        expected_ext: str,
        mime_type: str,
        task_id: str,
        timeout_seconds: int,
        required_text: list[str] | None = None,
    ) -> tuple[CodeArtifactAttempt, Artifact | None, dict[str, Any] | None]:
        """Execute generated code inside Docker sandbox and inspect/verify result."""
        sandbox_tool = self.tools.get("sandbox.execute")

        tool_exec_res = await sandbox_tool.execute(
            {
                "code": code,
                "language": "python",
                "timeout_seconds": timeout_seconds,
            },
            context={
                "task_id": task_id,
                "artifacts_dir": str(self.artifacts_dir.resolve()),
            },
        )

        output = tool_exec_res.output if isinstance(tool_exec_res.output, dict) else {}
        exit_code = int(output.get("exit_code", -1))
        stdout = str(output.get("stdout", ""))
        stderr = str(output.get("stderr", tool_exec_res.error or ""))
        timed_out = bool(output.get("timed_out", False))
        harvested_artifacts: list[str] = list(output.get("artifacts") or tool_exec_res.artifacts or [])

        tool_record = {
            "tool": "sandbox.execute",
            "success": tool_exec_res.success,
            "output": output,
            "error": tool_exec_res.error,
            "artifacts": harvested_artifacts,
        }

        # Check basic execution success
        findings: list[str] = []
        if exit_code != 0:
            findings.append(f"Execution failed with exit code {exit_code}.")
        if timed_out:
            findings.append(f"Execution timed out after {timeout_seconds}s.")
        if tool_exec_res.error:
            findings.append(f"Sandbox error: {tool_exec_res.error}")

        if findings:
            attempt = CodeArtifactAttempt(
                attempt=attempt_index,
                code=code,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                timed_out=timed_out,
                generated_files=harvested_artifacts,
                verification_passed=False,
                findings=findings,
                error=tool_exec_res.error or f"Sandbox returned exit code {exit_code}",
            )
            return attempt, None, tool_record

        # Check for generated artifact file
        matching_file: Path | None = None
        for artifact_path_str in harvested_artifacts:
            p = Path(artifact_path_str)
            if p.suffix.lower() == expected_ext.lower() and p.exists() and p.stat().st_size > 0:
                matching_file = p
                break

        if matching_file is None:
            # Check directly in artifacts_dir for recently created file
            candidates = list(self.artifacts_dir.glob(f"*{expected_ext}"))
            candidates.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            if candidates and candidates[0].stat().st_size > 0:
                matching_file = candidates[0]

        if matching_file is None:
            findings.append(f"No valid {expected_ext} file was created by the script.")
            attempt = CodeArtifactAttempt(
                attempt=attempt_index,
                code=code,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                timed_out=timed_out,
                generated_files=harvested_artifacts,
                verification_passed=False,
                findings=findings,
                error=f"No {expected_ext} file produced",
            )
            return attempt, None, tool_record

        # Build candidate Artifact contract
        candidate_artifact = artifact_from_path(
            matching_file,
            artifact_type=artifact_type,
            mime_type=mime_type,
            task_id=task_id,
            metadata={
                "generation_mode": "code",
                "file_size": matching_file.stat().st_size,
                "attempt": attempt_index,
            },
        )

        # Deep verification using existing validators
        valid, validation_findings = self._validate_artifact(
            candidate_artifact,
            norm_type=artifact_type,
            required_text=required_text,
        )

        if not valid:
            findings.extend(validation_findings)
            attempt = CodeArtifactAttempt(
                attempt=attempt_index,
                code=code,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                timed_out=timed_out,
                generated_files=[str(matching_file)],
                verification_passed=False,
                findings=findings,
                error="; ".join(validation_findings) if validation_findings else "Validation failed",
            )
            return attempt, None, tool_record

        # Verification passed!
        attempt = CodeArtifactAttempt(
            attempt=attempt_index,
            code=code,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            timed_out=timed_out,
            generated_files=[str(matching_file)],
            verification_passed=True,
            findings=[],
        )
        return attempt, candidate_artifact, tool_record

    def _validate_artifact(
        self,
        artifact: Artifact,
        *,
        norm_type: str,
        required_text: list[str] | None = None,
    ) -> tuple[bool, list[str]]:
        """Verify artifact readability and structure using the existing validators."""
        if norm_type == "pdf":
            validation = self.pdf_validator.validate(artifact, required_text=required_text)
            return validation.valid, validation.findings

        if norm_type in {"docx", "pptx", "document", "presentation", "xlsx", "spreadsheet"}:
            validation = self.office_validator.validate(
                artifact,
                required_text=required_text,
                render_preview=False,
            )
            return validation.valid, validation.findings

        # Fallback check for file existence and readability
        path = Path(artifact.storage_uri)
        if path.exists() and path.stat().st_size > 0:
            return True, []
        return False, ["Artifact file does not exist or is empty."]

    @staticmethod
    def _build_prompt(
        *,
        user_request: str,
        artifact_type: str,
        expected_ext: str,
        task_id: str,
        feedback: str,
        attempt: int,
    ) -> str:
        """Construct generation prompt tailored to the requested artifact type."""
        filename = f"artifact_{task_id[:8]}{expected_ext}"

        if artifact_type == "pdf":
            guidance = (
                "Use 'reportlab' to create a well-designed PDF document.\n"
                "- Recommended imports: SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle from reportlab.platypus, "
                "getSampleStyleSheet, ParagraphStyle from reportlab.lib.styles, and colors from reportlab.lib.\n"
                f"- Build and save the document to '{filename}' (or any '{expected_ext}' in the current working directory).\n"
                "- Include a professional title, headings, organized body paragraphs, and structured tables or lists.\n"
                "- Do NOT invent non-existent reportlab APIs. Keep styles standard.\n"
            )
        elif artifact_type in {"docx", "document"}:
            guidance = (
                "Use 'python-docx' (import docx / from docx import Document) to create a professional Word document.\n"
                f"- Save the document to '{filename}' (or any '{expected_ext}' in the current working directory).\n"
                "- Include a document title, structured headings (Heading 1, Heading 2), formatted paragraphs, and tables.\n"
            )
        elif artifact_type in {"pptx", "presentation"}:
            guidance = (
                "Use 'python-pptx' (from pptx import Presentation; from pptx.util import Inches, Pt) to create an editable presentation.\n"
                f"- Save the presentation to '{filename}' (or any '{expected_ext}' in the current working directory).\n"
                "- Create multiple distinct slides (e.g. title slide, overview, key points/findings, conclusion/next steps).\n"
                "- Add slide titles, bullet points, text boxes, and tables where appropriate.\n"
            )
        elif artifact_type in {"xlsx", "spreadsheet"}:
            guidance = (
                "Use 'openpyxl' (from openpyxl import Workbook; from openpyxl.styles import Font, PatternFill, Alignment, Border, Side) to create a styled Excel spreadsheet.\n"
                f"- Save the workbook to '{filename}' (or any '{expected_ext}' in the current working directory).\n"
                "- Create structured worksheets (e.g. Executive Summary, Data, Calculations).\n"
                "- Add formatted headers with background fills and bold text.\n"
                "- Include calculated summary formulas (=SUM, =AVERAGE, etc.) and auto-adjust column widths.\n"
            )
        else:
            guidance = f"Write a Python script to generate a valid {expected_ext} deliverable saved to '{filename}'.\n"

        repair_block = ""
        if feedback:
            repair_block = (
                f"\n--- PREVIOUS ATTEMPT FAILED ---\n"
                f"{feedback}\n"
                f"Please fix all errors and return the corrected Python script.\n"
                f"-------------------------------\n\n"
            )

        return (
            f"You are an expert Python engineer generating a professional {expected_ext.upper()} deliverable.\n\n"
            f"User Request:\n{user_request}\n\n"
            f"Technical Instructions:\n"
            f"{guidance}"
            f"- The code must be self-contained and run without user interaction.\n"
            f"- Never attempt external network connections; network is disabled in the sandbox.\n"
            f"- Output MUST be written to the local directory so the sandbox can harvest it.\n"
            f"- Return ONLY the executable Python script in a ```python ... ``` fenced code block.\n"
            f"{repair_block}"
            f"Attempt: {attempt}"
        )

    @staticmethod
    def _build_feedback(attempt: CodeArtifactAttempt) -> str:
        """Format execution feedback to steer the model toward repair."""
        parts = [
            f"exit_code={attempt.exit_code}",
            f"timed_out={attempt.timed_out}",
        ]
        if attempt.stderr.strip():
            parts.append(f"stderr:\n{attempt.stderr.strip()[-3000:]}")
        if attempt.stdout.strip():
            parts.append(f"stdout:\n{attempt.stdout.strip()[-1000:]}")
        if attempt.findings:
            parts.append("Validation findings:\n- " + "\n- ".join(attempt.findings))
        if attempt.error:
            parts.append(f"Error: {attempt.error}")
        return "\n".join(parts)

    @staticmethod
    def _normalize_artifact_type(raw_type: str) -> str:
        """Normalize artifact type aliases."""
        cleaned = raw_type.lower().strip()
        if "pdf" in cleaned:
            return "pdf"
        if "presentation" in cleaned or "pptx" in cleaned or "slide" in cleaned:
            return "pptx"
        if "spreadsheet" in cleaned or "excel" in cleaned or "xlsx" in cleaned or "workbook" in cleaned:
            return "xlsx"
        if "document" in cleaned or "docx" in cleaned or "word" in cleaned or "report" in cleaned:
            return "docx"
        return cleaned

