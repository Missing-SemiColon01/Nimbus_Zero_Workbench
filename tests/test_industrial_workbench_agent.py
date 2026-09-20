import asyncio
from pathlib import Path

from backend.agents.industrial_workbench import AGENT_ID, IndustrialWorkbenchAgent
from backend.agents.runtime import AgentRuntime
from backend.models.contracts import ModelDefinition, ModelResponse, ToolCall
from backend.models.providers import ModelProvider, ModelProviderRegistry
from backend.models.registry import ModelRegistry
from backend.models.router import ModelRouter
from backend.tools.contracts import Tool, ToolResult
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


class SandboxToolStub(Tool):
    name = "sandbox.execute"
    description = "Execute Python in a sandbox."
    parameters = {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "required": ["code"],
    }

    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def execute(self, arguments: dict, context: dict) -> ToolResult:
        self.calls.append({"arguments": arguments, "context": context})
        return ToolResult(success=True, output={"stdout": "4\\n", "test_passed": True})


class SandboxCallingProvider(ModelProvider):
    def __init__(self) -> None:
        self.requests = []

    async def generate(self, model: ModelDefinition, request) -> ModelResponse:
        self.requests.append(request)
        if len(self.requests) == 1:
            return ModelResponse(
                content="I'll run the calculation.",
                model_id=model.id,
                tool_calls=[ToolCall(name="sandbox.execute", arguments={"code": "print(2 + 2)"})],
            )
        return ModelResponse(content="The sandbox returned 4.", model_id=model.id)


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
        "artifact.validate",
        "sandbox.execute",
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


def test_agent_discovers_executes_and_returns_registered_sandbox_tool_results(tmp_path: Path):
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
    config_path = tmp_path / "agents.yaml"
    config_path.write_text(
        """agents:
  industrial_workbench:
    tools: [sandbox.execute]
"""
    )
    provider = SandboxCallingProvider()
    runtime = AgentRuntime(
        ModelRouter(ModelRegistry(models_config)),
        ModelProviderRegistry({"fake": provider}),
    )
    tools = ToolRegistry()
    sandbox = SandboxToolStub()
    tools.register(sandbox)

    agent = IndustrialWorkbenchAgent.create(runtime, tools, config_path)
    state, response = asyncio.run(
        agent.run("Calculate 2 + 2", {"reasoning"}, approved_tools={"sandbox.execute"})
    )

    assert runtime.tools is tools
    assert provider.requests[0].tools == [
        {
            "name": "sandbox.execute",
            "description": "Execute Python in a sandbox.",
            "parameters": sandbox.parameters,
        }
    ]
    assert sandbox.calls[0]["arguments"] == {"code": "print(2 + 2)"}
    assert state.tool_results[0]["tool"] == "sandbox.execute"
    assert state.tool_results[0]["output"] == {"stdout": "4\\n", "test_passed": True}
    assert provider.requests[1].tool_results[0].output == {"stdout": "4\\n", "test_passed": True}
    assert response.content == "The sandbox returned 4."
