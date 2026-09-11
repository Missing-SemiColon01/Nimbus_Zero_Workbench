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
