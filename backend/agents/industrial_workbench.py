"""Configured general-purpose agent for the Industrial Workbench MVP."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from backend.agents.runtime import AgentRuntime, RuntimeConfig
from backend.agents.state import AgentState
from backend.models.contracts import ModelResponse
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
