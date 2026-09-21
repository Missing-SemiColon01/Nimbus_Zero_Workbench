from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.agents.industrial_workbench import IndustrialWorkbenchAgent
from backend.agents.runtime import AgentRuntime
from backend.api.routes import router
from backend.api.auth import router as auth_router
from backend.core.config import get_settings
from backend.core.database import close_mongo, init_mongo
from backend.knowledge.retriever import reset_retriever
from backend.models.providers import ModelProviderRegistry, OllamaProvider
from backend.models.registry import ModelRegistry
from backend.models.router import ModelRouter
from backend.security.audit import AuditLogger
from backend.tools.setup import build_tool_registry


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    app.state.settings = settings
    app.state.audit = AuditLogger(settings.data_dir)
    app.state.registry = ModelRegistry(settings.models_config)
    providers = ModelProviderRegistry({"ollama": OllamaProvider(settings.ollama_base_url)})
    app.state.tools = build_tool_registry(
        settings=settings,
        model_registry=app.state.registry,
        provider_registry=providers,
    )
    app.state.runtime = AgentRuntime(
        ModelRouter(app.state.registry),
        providers,
        tools=app.state.tools,
    )
    app.state.agent = IndustrialWorkbenchAgent.create(
        app.state.runtime,
        app.state.tools,
        settings.agents_config,
    )
    # Initialize MongoDB connection pool (if MONGODB_URI is provided)
    await init_mongo(settings)
    try:
        yield
    finally:
        await close_mongo()
        reset_retriever()


app = FastAPI(title="Sovereign AI Workbench", version="0.1.0", lifespan=lifespan)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins if hasattr(settings, 'cors_origins') else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1/auth", tags=["auth"])
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
