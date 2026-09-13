from pathlib import Path

import pytest

from backend.models.contracts import ModelRequest
from backend.models.registry import ModelRegistry
from backend.models.router import ModelRouter, NoCompatibleModelError


def router() -> ModelRouter:
    return ModelRouter(ModelRegistry(Path("configs/models.yaml")))


def test_routes_coding_to_coding_model():
    model = router().select(ModelRequest("write a test", {"coding"}))
    assert model.id == "coding"


def test_rejects_unavailable_capability():
    with pytest.raises(NoCompatibleModelError):
        router().select(ModelRequest("do something", {"audio"}))


def test_candidates_skip_disabled_models_and_sort_by_priority(tmp_path: Path):
    config = tmp_path / "models.yaml"
    config.write_text(
        """models:
  - id: disabled
    runtime: fake
    model: disabled
    capabilities: [coding]
    modalities: [text]
    priority: 100
    enabled: false
  - id: fallback
    runtime: fake
    model: fallback
    capabilities: [coding]
    modalities: [text]
    priority: 5
    enabled: true
  - id: preferred
    runtime: fake
    model: preferred
    capabilities: [coding]
    modalities: [text]
    priority: 10
    enabled: true
"""
    )

    selected = ModelRouter(ModelRegistry(config)).candidates(ModelRequest("write", {"coding"}))

    assert [model.id for model in selected] == ["preferred", "fallback"]
