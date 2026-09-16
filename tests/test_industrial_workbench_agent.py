import asyncio
from pathlib import Path

from backend.agents.industrial_workbench import AGENT_ID, IndustrialWorkbenchAgent
from backend.agents.runtime import AgentRuntime
from backend.models.contracts import ModelDefinition, ModelResponse
from backend.models.providers import ModelProvider, ModelProviderRegistry
from backend.models.registry import ModelRegistry
from backend.models.router import ModelRouter
from backend.tools.contracts import Tool
from backend.tools.registry import ToolRegistry


class SuccessProvider(ModelProvider):
    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def generate(self, model: ModelDefinition, request) -> ModelResponse:
        self.prompts.append(request.prompt)
        return ModelResponse(content="complete", model_id=model.id)


class NamedTool(Tool):
    def __init__(self, name: str) -> None:
        self.name = name


def test_industrial_workbench_agent_is_created_from_config_and_sets_system_prompt(tmp_path: Path):
    models_config = tmp_path / "models.yaml"
    models_config.write_text(
        """models:
  - id: reasoning
    runtime: fake
    model: test
    capabilities: [reasoning]
    modalities: [text]
"""
    )
    provider = SuccessProvider()
    runtime = AgentRuntime(
        ModelRouter(ModelRegistry(models_config)),
        ModelProviderRegistry({"fake": provider}),
    )
    tools = ToolRegistry()
    for name in (
        "rag.search",
        "vision.analyze",
        "document.create",
        "spreadsheet.create",
        "presentation.create",
        "pdf.create",
        "artifact.validate",
    ):
        tools.register(NamedTool(name))

    config_path = Path("configs/agents.yaml")
    agent = IndustrialWorkbenchAgent.create(runtime, tools, config_path)
    state, _ = asyncio.run(agent.run("summarize the inspection", {"reasoning"}))

    assert agent.config.id == AGENT_ID
    assert agent.config.tools == frozenset(tools.names())
    assert state.status == "completed"
    assert "Industrial Workbench Agent" in provider.prompts[0]
    assert provider.prompts[0].endswith("summarize the inspection")
