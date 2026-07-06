"""RunningHub 图片能力声明。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.integrations.image_capabilities import ImageModelCapability

if TYPE_CHECKING:
    from app.core.contracts.image_generation import ImageGenerationInput

_RUNNINGHUB_DEFAULT = ImageModelCapability(
    supports_seed=False,
    supports_watermark=False,
    allowed_sizes=None,
    supported_ratios={"16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"},
)

_RUNNINGHUB_MODEL_OVERRIDES: dict[str, ImageModelCapability] = {}


def register_runninghub_image_capability(*, model_prefix: str, capability: ImageModelCapability) -> None:
    prefix = model_prefix.strip().lower()
    if not prefix:
        raise ValueError("model_prefix must not be empty")
    _RUNNINGHUB_MODEL_OVERRIDES[prefix] = capability


def clear_runninghub_image_capability_overrides() -> None:
    _RUNNINGHUB_MODEL_OVERRIDES.clear()


def _pick_override(model: str | None) -> ImageModelCapability | None:
    if not model:
        return None
    value = model.strip().lower()
    if not value:
        return None
    for prefix, cap in sorted(_RUNNINGHUB_MODEL_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True):
        if value.startswith(prefix):
            return cap
    return None


def resolve_runninghub_image_capability(model: str | None) -> ImageModelCapability:
    return _pick_override(model) or _RUNNINGHUB_DEFAULT


def validate_runninghub_image_options(input_: ImageGenerationInput) -> None:
    from app.core.integrations.image_capabilities import validate_image_options

    assert isinstance(input_, ImageGenerationInput)
    validate_image_options(provider="runninghub", model=input_.model, input_=input_)
