from backend.models.contracts import ModelDefinition, ModelRequest
from backend.models.registry import ModelRegistry


class NoCompatibleModelError(RuntimeError):
    pass


class ModelRouter:
    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def select(self, request: ModelRequest) -> ModelDefinition:
        candidates = self.registry.candidates(request.required_capabilities, request.required_modality)
        if not candidates:
            raise NoCompatibleModelError("No healthy local model satisfies this request")
        return candidates[0]
