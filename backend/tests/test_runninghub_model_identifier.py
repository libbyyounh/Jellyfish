from __future__ import annotations

from app.models.llm import Model, ModelCategoryKey
from app.services.llm.model_identifier import resolve_model_identifier


def _make_model(*, name: str, params: dict | None = None) -> Model:
    return Model(
        id="m1",
        name=name,
        category=ModelCategoryKey.image,
        provider_id="p1",
        params=params or {},
        description="",
        created_by="",
    )


def test_runninghub_returns_workflow_id_from_params() -> None:
    model = _make_model(name="短剧专用图片模型", params={"workflow_id": "2052744677727715329"})
    assert resolve_model_identifier(model, "runninghub") == "2052744677727715329"


def test_runninghub_without_workflow_id_falls_back_to_name() -> None:
    model = _make_model(name="短剧专用图片模型", params={})
    assert resolve_model_identifier(model, "runninghub") == "短剧专用图片模型"


def test_openai_returns_model_name() -> None:
    model = _make_model(name="gpt-image-1.5")
    assert resolve_model_identifier(model, "openai") == "gpt-image-1.5"


def test_volcengine_returns_model_name() -> None:
    model = _make_model(name="doubao-seedream-3.0")
    assert resolve_model_identifier(model, "volcengine") == "doubao-seedream-3.0"
