from pathlib import Path

import yaml

from backend.models.contracts import ModelDefinition


class ModelRegistry:
    def __init__(self, path: Path):
        content = yaml.safe_load(path.read_text()) or {}
        self.models = [ModelDefinition(id=item["id"], runtime=item["runtime"], model=item["model"], capabilities=set(item.get("capabilities", [])), modalities=set(item.get("modalities", ["text"])), priority=item.get("priority", 0)) for item in content.get("models", [])]

    def candidates(self, capabilities: set[str], modality: str) -> list[ModelDefinition]:
        return sorted((model for model in self.models if capabilities <= model.capabilities and modality in model.modalities), key=lambda model: model.priority, reverse=True)
