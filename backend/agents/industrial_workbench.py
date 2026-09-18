"""Configured general-purpose agent for the Industrial Workbench MVP."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.agents.artifact_detection import ArtifactIntent, detect_artifact_intent
from backend.agents.runtime import AgentRuntime, RuntimeConfig
from backend.agents.state import AgentState
from backend.models.contracts import ModelResponse
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
recommendations. Artifact-creating tools require human approval before they run.
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
        images: list[str] | None = None,
        documents: list[str] | None = None,
        approved_tools: set[str] | None = None,
    ) -> tuple[AgentState, ModelResponse]:
        return await self.runtime.run(
            user_request,
            capabilities,
            modality,
            tool_allowlist=set(self.config.tools) if self.config.tools is not None else None,
            approved_tools=approved_tools,
            images=images,
            documents=documents,
            system_prompt=self.config.system_prompt,
        )

    # -- Artifact-generation orchestration -------------------------------------

    async def generate_artifact(
        self,
        user_request: str,
        *,
        task_type: str | None = None,
        approved_tools: set[str] | None = None,
    ) -> ArtifactGenerationResult:
        """Detect, generate, and produce a downloadable artifact in one call.

        Orchestration flow
        ------------------
        1. Detect intent   → identify artifact type and target tool.
        2. Generate content → ask the model for structured JSON matching the tool schema.
        3. Extract result   → check if the runtime already called the tool, or parse JSON.
        4. Execute tool     → call the artifact tool if not already executed.
        5. Validate result  → verify success and build the typed response.

        Parameters
        ----------
        user_request:
            The raw natural-language request from the user.
        task_type:
            Optional explicit task type (``"report"``, ``"artifact"``, etc.).
        approved_tools:
            Tool names explicitly pre-approved by a human for this run.
        """
        task_id = str(uuid.uuid4())

        # 1. Detect artifact intent.
        intent = detect_artifact_intent(user_request, task_type)
        if intent is None:
            return ArtifactGenerationResult(
                task_id=task_id,
                artifact_type="unknown",
                status="failed",
                errors=["Could not determine artifact type from the request."],
            )

        # 2. Verify the target tool is registered and allowed.
        error = self._check_tool_available(intent)
        if error is not None:
            return ArtifactGenerationResult(
                task_id=task_id,
                artifact_type=intent.artifact_type,
                status="failed",
                errors=[error],
            )

        # 3. Generate content through the model (may trigger tool calls via runtime).
        tool_schema = self._tool_parameter_schema(intent.tool_name)
        generation_prompt = self._artifact_generation_prompt(user_request, intent, tool_schema)

        # Ensure the target tool is approved so the runtime can call it.
        effective_approved = set(approved_tools or ())
        effective_approved.add(intent.tool_name)

        try:
            state, model_response = await self.run(
                generation_prompt,
                {"reasoning"},
                approved_tools=effective_approved,
            )
        except Exception as exc:
            return ArtifactGenerationResult(
                task_id=task_id,
                artifact_type=intent.artifact_type,
                status="failed",
                errors=[f"Model generation failed: {exc}"],
            )

        if state.status == "failed":
            return ArtifactGenerationResult(
                task_id=task_id,
                artifact_type=intent.artifact_type,
                status="failed",
                errors=state.errors or ["Model generation failed."],
            )

        # 4. Check if the runtime already executed the artifact tool.
        tool_result = self._find_tool_result(state, intent.tool_name)

        if tool_result is None:
            # The model returned content but didn't call the tool — parse and call manually.
            tool_result = await self._parse_and_execute_tool(
                model_response, intent, task_id,
            )

        # 5. Build the typed response.
        return self._build_result(task_id, intent, tool_result)

    # -- Private helpers -------------------------------------------------------

    def _check_tool_available(self, intent: ArtifactIntent) -> str | None:
        """Return an error string if the target tool is unavailable, else ``None``."""
        if self.tools is None:
            return f"No tool registry configured; cannot call '{intent.tool_name}'."
        try:
            self.tools.get(intent.tool_name)
        except KeyError:
            return f"Tool '{intent.tool_name}' is not registered."
        if self.config.tools is not None and intent.tool_name not in self.config.tools:
            return f"Tool '{intent.tool_name}' is not in the agent's allowed tool set."
        return None

    def _tool_parameter_schema(self, tool_name: str) -> dict[str, Any]:
        """Retrieve the JSON-Schema ``parameters`` block for a registered tool."""
        try:
            tool = self.tools.get(tool_name)
            return getattr(tool, "parameters", {})
        except (KeyError, AttributeError):
            return {}

    @staticmethod
    def _artifact_generation_prompt(
        user_request: str,
        intent: ArtifactIntent,
        tool_schema: dict[str, Any],
    ) -> str:
        """Build a prompt that steers the model toward calling the artifact tool."""
        schema_hint = json.dumps(tool_schema, indent=2) if tool_schema else "{}"
        return (
            f"{user_request}\n\n"
            f"--- Artifact Generation Instructions ---\n"
            f"You MUST produce a structured JSON tool call for the tool '{intent.tool_name}' "
            f"to create a {intent.artifact_type} artifact.\n"
            f"The tool accepts the following JSON schema for its arguments:\n"
            f"```json\n{schema_hint}\n```\n"
            f"Call the tool with well-formed arguments derived from the user's request. "
            f"Do NOT output the artifact content as plain text; use the tool call."
        )

    @staticmethod
    def _find_tool_result(
        state: AgentState,
        tool_name: str,
    ) -> dict[str, Any] | None:
        """Extract the first successful tool result for *tool_name* from the agent state."""
        for result in state.tool_results:
            if isinstance(result, dict) and result.get("tool") == tool_name and result.get("success"):
                return result
        return None

    async def _parse_and_execute_tool(
        self,
        model_response: ModelResponse,
        intent: ArtifactIntent,
        task_id: str,
    ) -> dict[str, Any]:
        """Parse JSON arguments from model output and execute the artifact tool."""
        arguments = self._extract_tool_arguments(model_response, intent.tool_name)
        if arguments is None:
            return {
                "tool": intent.tool_name,
                "success": False,
                "output": None,
                "error": "Model did not produce valid tool-call arguments for the artifact tool.",
                "artifacts": [],
            }

        try:
            tool = self.tools.get(intent.tool_name)
            result = await tool.execute(arguments, context={"task_id": task_id})
        except Exception as exc:
            return {
                "tool": intent.tool_name,
                "success": False,
                "output": None,
                "error": f"Tool execution failed: {exc}",
                "artifacts": [],
            }

        return {
            "tool": intent.tool_name,
            "success": result.success,
            "output": result.output,
            "error": result.error,
            "artifacts": result.artifacts,
        }

    @staticmethod
    def _extract_tool_arguments(
        model_response: ModelResponse,
        tool_name: str,
    ) -> dict[str, Any] | None:
        """Best-effort extraction of tool-call arguments from model output.

        Checks, in order:
        1. Structured ``tool_calls`` on the response.
        2. ``tool_calls`` key inside ``response.raw``.
        3. JSON block in ``response.content``.
        """
        # 1. Structured tool_calls on ModelResponse.
        for tc in model_response.tool_calls:
            if tc.name == tool_name:
                return tc.arguments

        # 2. raw dict may carry tool_calls from the provider.
        raw_calls = model_response.raw.get("tool_calls")
        if isinstance(raw_calls, list):
            for item in raw_calls:
                if isinstance(item, dict):
                    name = item.get("name") or item.get("tool")
                    if name == tool_name:
                        args = item.get("arguments") or item.get("args") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                continue
                        if isinstance(args, dict):
                            return args

        # 3. Try parsing the content as JSON.
        content = model_response.content.strip()
        if not content:
            return None
        try:
            payload = json.loads(content)
        except json.JSONDecodeError:
            return None
        if isinstance(payload, dict):
            # Direct argument object.
            if "tool_calls" in payload and isinstance(payload["tool_calls"], list):
                for item in payload["tool_calls"]:
                    if isinstance(item, dict):
                        name = item.get("name") or item.get("tool")
                        if name == tool_name:
                            args = item.get("arguments") or item.get("args") or {}
                            return args if isinstance(args, dict) else None
            # Could be the arguments themselves.
            return payload
        return None

    @staticmethod
    def _build_result(
        task_id: str,
        intent: ArtifactIntent,
        tool_result: dict[str, Any],
    ) -> ArtifactGenerationResult:
        """Convert a raw tool-result dict into the typed orchestration response."""
        success = bool(tool_result.get("success"))
        output = tool_result.get("output")
        artifacts = tool_result.get("artifacts", [])
        error = tool_result.get("error")

        path: str | None = None
        download_url: str | None = None
        artifact_metadata: dict[str, Any] = {}

        if success and isinstance(output, dict):
            artifact_metadata = output
            path = output.get("storage_uri") or (artifacts[0] if artifacts else None)
            filename = output.get("filename")
            if filename:
                download_url = f"/api/v1/artifacts/{filename}/download"

        status = "completed" if success else "failed"
        errors: list[str] = []
        if error:
            errors.append(error)

        return ArtifactGenerationResult(
            task_id=task_id,
            artifact_type=intent.artifact_type,
            status=status,
            path=path,
            download_url=download_url,
            artifact_metadata=artifact_metadata,
            errors=errors,
        )

