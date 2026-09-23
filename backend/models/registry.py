from pathlib import Path

import yaml

from backend.models.contracts import ModelDefinition


class ModelRegistry:
    def __init__(self, path: Path):
        content = yaml.safe_load(path.read_text()) or {}
        self.models = [
            ModelDefinition(
                id=item["id"],
                runtime=item["runtime"],
                model=item["model"],
                capabilities=set(item.get("capabilities", [])),
                modalities=set(item.get("modalities", ["text"])),
                priority=item.get("priority", 0),
                enabled=item.get("enabled", True),
            )
            for item in content.get("models", [])
        ]

    def candidates(self, capabilities: set[str], modality: str) -> list[ModelDefinition]:
        exact_matches = sorted(
            (
                model
                for model in self.models
                if model.enabled
                and capabilities <= model.capabilities
                and modality in model.modalities
            ),
            key=lambda model: model.priority,
            reverse=True,
        )
        if exact_matches:
            return exact_matches

        # Resilient fallback: match enabled models supporting the modality,
        # ranked by capability overlap and priority.
        scored_candidates = []
        for model in self.models:
            if not model.enabled:
                continue
            if modality in model.modalities:
                overlap = len(capabilities & model.capabilities)
                scored_candidates.append((overlap, model.priority, model))

        scored_candidates.sort(key=lambda item: (item[0], item[1]), reverse=True)
        return [item[2] for item in scored_candidates if item[0] > 0 or item[2].priority > 0]

