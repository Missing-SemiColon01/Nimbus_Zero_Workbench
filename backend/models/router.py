from backend.models.contracts import ModelDefinition, ModelRequest
from backend.models.registry import ModelRegistry


class NoCompatibleModelError(RuntimeError):
    pass


class ModelRouter:
    def __init__(self, registry: ModelRegistry):
        self.registry = registry

    def select(self, request: ModelRequest) -> ModelDefinition:
        candidates = self.candidates(request)
        if not candidates:
            required = ", ".join(sorted(request.required_capabilities)) or "none"
            raise NoCompatibleModelError(
                "No compatible model exists for "
                f"modality '{request.required_modality}' with capabilities: {required}"
            )
        return candidates[0]

    def candidates(self, request: ModelRequest) -> list[ModelDefinition]:
        """Return enabled compatible models in preference order."""
        return self.registry.candidates(request.required_capabilities, request.required_modality)
