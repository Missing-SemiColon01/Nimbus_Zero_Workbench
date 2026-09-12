from contextlib import asynccontextmanager

from fastapi import FastAPI

from backend.agents.runtime import AgentRuntime
from backend.api.routes import router
from backend.core.config import get_settings
from backend.models.registry import ModelRegistry
from backend.models.providers import ModelProviderRegistry, OllamaProvider
from backend.models.router import ModelRouter


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.registry = ModelRegistry(settings.models_config)
    app.state.runtime = AgentRuntime(
        ModelRouter(app.state.registry),
        ModelProviderRegistry({"ollama": OllamaProvider(settings.ollama_base_url)}),
    )
    yield


app = FastAPI(title="Sovereign AI Workbench", version="0.1.0", lifespan=lifespan)
app.include_router(router, prefix="/api/v1")
