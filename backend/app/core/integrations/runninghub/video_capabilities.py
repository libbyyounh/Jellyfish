"""RunningHub 视频能力声明。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.integrations.video_capabilities import VideoModelCapability

if TYPE_CHECKING:
    from app.core.contracts.video_generation import VideoGenerationInput

_RUNNINGHUB_DEFAULT = VideoModelCapability(
    supports_seed=False,
    supports_watermark=False,
    allowed_ratios={"16:9", "9:16"},
    default_ratio="16:9",
    min_seconds=5,
    max_seconds=10,
)

_RUNNINGHUB_MODEL_OVERRIDES: dict[str, VideoModelCapability] = {}


def register_runninghub_video_capability(*, model_prefix: str, capability: VideoModelCapability) -> None:
    prefix = model_prefix.strip().lower()
    if not prefix:
        raise ValueError("model_prefix must not be empty")
    _RUNNINGHUB_MODEL_OVERRIDES[prefix] = capability


def clear_runninghub_video_capability_overrides() -> None:
    _RUNNINGHUB_MODEL_OVERRIDES.clear()


def _pick_override(model: str | None) -> VideoModelCapability | None:
    if not model:
        return None
    value = model.strip().lower()
    if not value:
        return None
    for prefix, cap in sorted(_RUNNINGHUB_MODEL_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True):
        if value.startswith(prefix):
            return cap
    return None


def resolve_runninghub_video_capability(model: str | None) -> VideoModelCapability:
    return _pick_override(model) or _RUNNINGHUB_DEFAULT


def validate_runninghub_video_options(input_: VideoGenerationInput) -> None:
    from app.core.integrations.video_capabilities import validate_video_options

    assert isinstance(input_, VideoGenerationInput)
    validate_video_options(provider="runninghub", model=input_.model, input_=input_)
