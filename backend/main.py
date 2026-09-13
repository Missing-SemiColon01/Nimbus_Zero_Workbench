from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.agents.runtime import AgentRuntime
from backend.api.routes import router
from backend.core.config import get_settings
from backend.models.providers import ModelProviderRegistry, OllamaProvider
from backend.models.registry import ModelRegistry
from backend.models.router import ModelRouter
from backend.tools.setup import build_tool_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.registry = ModelRegistry(settings.models_config)
    providers = ModelProviderRegistry({"ollama": OllamaProvider(settings.ollama_base_url)})
    app.state.runtime = AgentRuntime(
        ModelRouter(app.state.registry),
        providers,
    )
    app.state.tools = build_tool_registry(
        settings=settings,
        model_registry=app.state.registry,
        provider_registry=providers,
    )
    yield


app = FastAPI(title="Sovereign AI Workbench", version="0.1.0", lifespan=lifespan)
app.include_router(router, prefix="/api/v1")
