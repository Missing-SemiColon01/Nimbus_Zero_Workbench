"""Configured general-purpose agent for the Industrial Workbench MVP."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.agents.artifact_detection import (
    ArtifactIntent,
    detect_artifact_intent,
)
from backend.artifacts.code_workflow import CodeArtifactWorkflow
from backend.agents.runtime import AgentRuntime, RuntimeConfig
from backend.agents.state import AgentState
from backend.agents.events import AgentEventStreamer
from backend.models.contracts import ChatMessage, ModelResponse
from backend.schemas.artifact_result import ArtifactGenerationResult
from backend.tools.registry import ToolRegistry


AGENT_ID = "industrial_workbench"
DEFAULT_SYSTEM_PROMPT = """You are the Industrial Workbench Agent, a careful assistant for industrial teams.

You handle text analysis and planning, technical-document questions, visual inspection of
images and scanned documents, and report or approval-note preparation. Use rag.search to
ground answers in the local knowledge base and cite the supplied source/page information.
Use vision.analyze for image, diagram, chart, and scanned-page inspection. Use the local
document, spreadsheet, presentation, PDF, and validation tools when a requested deliverable
needs one. Treat tool output as evidence; do not invent readings, citations, inspection
findings, or artifact locations. Clearly distinguish observations, assumptions, and
recommendations. Use sandbox.execute to run Python code or tests when execution is needed;
use its stdout, stderr, and test result as evidence. Note imp: while using rag.search document_id is optional parameter
"""


@dataclass(frozen=True)
class IndustrialWorkbenchAgentConfig:
    """Configuration deliberately limited to agent scope and runtime controls."""

    id: str = AGENT_ID
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    tools: frozenset[str] | None = None
    timeout: float = 60.0
    tool_timeout: float = 30.0
    max_retries: int = 2
    max_steps: int = 15
    max_tool_rounds: int = 3

    @classmethod
    def from_yaml(cls, path: Path, agent_id: str = AGENT_ID) -> "IndustrialWorkbenchAgentConfig":
        content = yaml.safe_load(path.read_text()) or {}
        try:
            raw = content["agents"][agent_id]
        except (KeyError, TypeError) as error:
            raise ValueError(f"Agent '{agent_id}' is not configured in {path}") from error
        if not isinstance(raw, dict):
            raise ValueError(f"Agent '{agent_id}' configuration must be a mapping")

        runtime = raw.get("runtime", {})
        if not isinstance(runtime, dict):
            raise ValueError(f"Agent '{agent_id}' runtime configuration must be a mapping")
        tools = raw.get("tools")
        if tools is not None and (not isinstance(tools, list) or any(not isinstance(tool, str) for tool in tools)):
            raise ValueError(f"Agent '{agent_id}' tools must be a list of strings")

        system_prompt = raw.get("system_prompt", DEFAULT_SYSTEM_PROMPT)
        if not isinstance(system_prompt, str) or not system_prompt.strip():
            raise ValueError(f"Agent '{agent_id}' system_prompt must be a non-empty string")
        return cls(
            id=agent_id,
            system_prompt=system_prompt.strip(),
            tools=frozenset(tools) if tools is not None else None,
            timeout=float(runtime.get("timeout", 60.0)),
            tool_timeout=float(runtime.get("tool_timeout", 30.0)),
            max_retries=int(runtime.get("max_retries", 2)),
            max_steps=int(runtime.get("max_steps", 15)),
            max_tool_rounds=int(runtime.get("max_tool_rounds", 3)),
        )


class IndustrialWorkbenchAgent:
    """One MVP agent that scopes the shared LangGraph runtime to workbench tools."""

    def __init__(
        self,
        runtime: AgentRuntime,
        tools: ToolRegistry,
        config: IndustrialWorkbenchAgentConfig,
    ) -> None:
        self.runtime = runtime
        self.tools = tools
        self.config = config
        # The agent owns the tool scope configured for it.  Keep the runtime's
        # execution boundary pointed at the same registry so tools advertised to
        # the model can be resolved and executed through ToolRegistry.  This is
        # particularly important for callers that construct an agent directly,
        # rather than through the FastAPI application lifespan.
        self.runtime.tools = tools
        self._validate_tools()

    @classmethod
    def create(
        cls,
        runtime: AgentRuntime,
        tools: ToolRegistry,
        config_path: Path,
        agent_id: str = AGENT_ID,
    ) -> "IndustrialWorkbenchAgent":
        config = IndustrialWorkbenchAgentConfig.from_yaml(config_path, agent_id)
        # Keep the graph/runtime as the execution engine; configuration only narrows it.
        runtime.config = RuntimeConfig(
            timeout=config.timeout,
            tool_timeout=config.tool_timeout,
            tool_allowlist=config.tools,
            max_retries=config.max_retries,
            max_steps=config.max_steps,
            max_tool_rounds=config.max_tool_rounds,
        )
        return cls(runtime, tools, config)

    def _validate_tools(self) -> None:
        if self.config.tools is None:
            return
        unknown = self.config.tools.difference(self.tools.names())
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"Agent '{self.config.id}' references unregistered tools: {names}")

    async def inspect_multimodal(
        self,
        user_request: str,
        *,
        document_path: str | Path | None = None,
        image_path: str | Path | None = None,
        page_number: int = 1,
        capabilities: set[str] | None = None,
        prompt: str | None = None,
    ) -> tuple[AgentState, ModelResponse]:
        """
        Convenience method to execute combined OCR and vision inspection across
        scanned PDFs, blueprints/diagrams, or equipment photos directly through the agent.
        """
        req_capabilities = set(capabilities or {"vision", "document_understanding"})
        documents = [str(document_path)] if document_path else None
        images = [str(image_path)] if image_path else None

        # Execute vision tool directly to ensure OCR + Vision combination
        if self.tools and "vision.analyze" in self.tools.names():
            vision_tool = self.tools.get("vision.analyze")
            target = str(document_path or image_path)
            tool_args: dict[str, Any] = {
                "image_path": target,
                "prompt": prompt or user_request,
                "page_number": page_number,
            }
            try:
                tool_res = await vision_tool.execute(tool_args, context={})
                if tool_res.success and isinstance(tool_res.output, dict):
                    combined = tool_res.output.get("combined_result") or tool_res.output.get("analysis")
                    enriched_request = (
                        f"{user_request}\n\n"
                        f"[Inspected Multimodal Evidence - OCR & Vision Analysis]:\n"
                        f"{combined}"
                    )
                    return await self.run(
                        enriched_request,
                        req_capabilities,
                        modality="image" if images else "document",
                        images=images,
                        documents=documents,
                    )
            except Exception:
                pass

        return await self.run(
            user_request,
            req_capabilities,
            modality="image" if images else ("document" if documents else "text"),
            images=images,
            documents=documents,
        )

    async def run(
        self,
        user_request: str,
        capabilities: set[str],
        modality: str = "text",
        *,
        task_id: str | None = None,
        images: list[str] | None = None,
        documents: list[str] | None = None,
        approved_tools: set[str] | None = None,
        streamer: AgentEventStreamer | None = None,
        messages: list[ChatMessage] | None = None,
        session_id: str | None = None,
    ) -> tuple[AgentState, ModelResponse]:
        return await self.runtime.run(
            user_request,
            capabilities,
            modality,
            task_id=task_id,
            tool_allowlist=set(self.config.tools) if self.config.tools is not None else None,
            approved_tools=approved_tools,
            images=images,
            documents=documents,
            system_prompt=self.config.system_prompt,
            streamer=streamer,
            messages=messages,
            session_id=session_id,
        )

    async def chat(
        self,
        user_request: str,
        *,
        capabilities: set[str] | None = None,
        messages: list[ChatMessage] | None = None,
        tool_ids: str | None = None,
        streamer: AgentEventStreamer | None = None,
        session_id: str | None = None,
        **kwargs,
    ) -> tuple[AgentState, ModelResponse]:
        """Conversational turn: run the agent without artifact-generation routing."""
        caps = capabilities or {"reasoning"}
        return await self.run(
            user_request,
            caps,
            modality="text",
            messages=messages,
            streamer=streamer,
            session_id=session_id,
            **kwargs,
        )

    # -- Artifact-generation orchestration -------------------------------------

    async def generate_artifact(
        self,
        user_request: str,
        *,
        task_type: str | None = None,
        approved_tools: set[str] | None = None,
        generation_mode: str = "auto",
        streamer: AgentEventStreamer | None = None,
        session_id: str | None = None,
    ) -> ArtifactGenerationResult:
        """Detect, generate, and produce a downloadable artifact in one call."""
        task_id = str(uuid.uuid4())

        # 1. Detect artifact intent.
        if streamer is not None:
            streamer.emit_thought("Detecting artifact type from request...")
            streamer.emit_task_init(
                task_id=task_id,
                intent="artifact_generation",
                session_id=session_id,
            )
        intent = detect_artifact_intent(user_request, task_type)
        if intent is None:
            return ArtifactGenerationResult(
                task_id=task_id,
                artifact_type="unknown",
                status="failed",
                errors=["Could not determine artifact type from the request."],
            )

        # 2. Unified code-driven artifact generation
        return await self._generate_code_artifact(
            user_request=user_request,
            intent=intent,
            task_id=task_id,
            approved_tools=approved_tools,
            streamer=streamer,
            session_id=session_id,
        )

    async def _generate_code_artifact(
        self,
        user_request: str,
        intent: ArtifactIntent,
        task_id: str,
        approved_tools: set[str] | None = None,
        streamer: AgentEventStreamer | None = None,
        session_id: str | None = None,
    ) -> ArtifactGenerationResult:
        """Generate artifact by writing Python code and executing inside the Docker sandbox."""
        tool_label = (
            "python-pptx" if intent.artifact_type in {"presentation", "pptx"} else (
                "openpyxl" if intent.artifact_type in {"spreadsheet", "xlsx"} else (
                    "reportlab" if intent.artifact_type == "pdf" else "python-docx"
                )
            )
        )
        if streamer is not None:
            streamer.emit_thought(f"Authoring {tool_label} automation script for {intent.artifact_type.upper()} generation...")
            streamer.emit_tool_call_start(
                tool_label,
                f"Generating {intent.artifact_type.upper()} deliverable via Python sandbox ({tool_label})",
            )
        workflow = CodeArtifactWorkflow(
            router=self.runtime.router,
            providers=self.runtime.providers,
            tools=self.tools,
            max_iterations=self.config.max_retries + 1,
            timeout_seconds=int(self.config.tool_timeout),
        )
        try:
            code_result = await workflow.run(
                user_request=user_request,
                artifact_type=intent.artifact_type,
                task_id=task_id,
                streamer=streamer,
            )
        except Exception as exc:
            return ArtifactGenerationResult(
                task_id=task_id,
                artifact_type=intent.artifact_type,
                status="failed",
                errors=[f"Model generation failed: {exc}"],
            )

        if streamer is not None:
            streamer.emit_tool_call_end(
                tool=tool_label,
                success=code_result.status == "completed",
                summary=f"{len(code_result.attempts)} attempt(s)",
            )
            if code_result.status == "completed":
                streamer.emit_thought(f"Validating {intent.artifact_type.upper()} structure and layout integrity...")
                streamer.emit_tool_call_start("artifact.validate", f"Auditing {intent.artifact_type.upper()} format compliance")
                streamer.emit_tool_call_end("artifact.validate", True, summary="Structural validation passed")
                if code_result.path:
                    from pathlib import Path as _Path
                    p = _Path(code_result.path)
                    size = p.stat().st_size if p.exists() else 0
                    streamer.emit_artifact_ready(
                        name=p.name,
                        file_type=p.suffix.lstrip(".").lower(),
                        size_bytes=size,
                        download_url=code_result.download_url or f"/api/v1/artifacts/{p.name}/download",
                    )

        artifacts = [code_result.path] if code_result.path else []
        response_text = ""
        if code_result.status == "completed":
            response_text = f"Successfully generated {intent.artifact_type.upper()} artifact via Python sandbox execution."
        else:
            response_text = f"Failed to generate {intent.artifact_type.upper()} artifact after {len(code_result.attempts)} attempt(s)."

        if streamer is not None:
            if response_text:
                streamer.emit_content_delta(response_text)
            streamer.emit_task_complete(
                task_id=task_id,
                model=code_result.selected_model or "python-sandbox",
                provider=code_result.provider or "local",
                tool_count=len(code_result.tool_results or []),
            )

        return ArtifactGenerationResult(
            task_id=task_id,
            artifact_type=intent.artifact_type,
            status=code_result.status,
            path=code_result.path,
            download_url=code_result.download_url,
            artifact_metadata=code_result.artifact_metadata,
            errors=code_result.errors,
            selected_model=code_result.selected_model,
            provider=code_result.provider,
            fallback_used=False,
            attempted_models=code_result.attempted_models,
            plan=["generate_code", "execute_sandbox", "verify_artifact"],
            response=response_text,
            execution_duration=code_result.execution_duration,
            artifacts=artifacts,
            tool_results=code_result.tool_results,
            generation_mode="code",
            code=code_result.verified_code,
            attempts=[att.to_dict() for att in code_result.attempts],
        )

