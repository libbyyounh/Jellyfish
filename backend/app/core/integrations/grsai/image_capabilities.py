"""Grsai 图片能力声明。"""

from __future__ import annotations

from app.core.integrations.image_capabilities import ImageModelCapability

_GRSAI_STANDARD_RATIOS: set[str] = {
    "auto",
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "5:4",
    "4:5",
    "21:9",
}

_GRSAI_EXTENDED_RATIOS: set[str] = _GRSAI_STANDARD_RATIOS | {
    "1:4",
    "4:1",
    "1:8",
    "8:1",
}

_GRSAI_DEFAULT = ImageModelCapability(
    supports_seed=False,
    supports_watermark=False,
    allowed_sizes=None,
    supported_ratios=_GRSAI_STANDARD_RATIOS,
)

_GRSAI_MODEL_OVERRIDES: dict[str, ImageModelCapability] = {
    "nano-banana-2": ImageModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_sizes=None,
        supported_ratios=_GRSAI_EXTENDED_RATIOS,
    ),
    "nano-banana-2-cl": ImageModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_sizes=None,
        supported_ratios=_GRSAI_EXTENDED_RATIOS,
    ),
    "nano-banana-2-2k-cl": ImageModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_sizes=None,
        supported_ratios=_GRSAI_EXTENDED_RATIOS,
    ),
    "nano-banana-2-4k-cl": ImageModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_sizes=None,
        supported_ratios=_GRSAI_EXTENDED_RATIOS,
    ),
}


def register_grsai_image_capability(*, model_prefix: str, capability: ImageModelCapability) -> None:
    prefix = model_prefix.strip().lower()
    if not prefix:
        raise ValueError("model_prefix must not be empty")
    _GRSAI_MODEL_OVERRIDES[prefix] = capability


def clear_grsai_image_capability_overrides() -> None:
    _GRSAI_MODEL_OVERRIDES.clear()


def _pick_override(model: str | None) -> ImageModelCapability | None:
    if not model:
        return None
    value = model.strip().lower()
    if not value:
        return None
    if value in _GRSAI_MODEL_OVERRIDES:
        return _GRSAI_MODEL_OVERRIDES[value]
    for prefix, cap in sorted(_GRSAI_MODEL_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True):
        if value.startswith(prefix):
            return cap
    return None


def resolve_grsai_image_capability(model: str | None) -> ImageModelCapability:
    return _pick_override(model) or _GRSAI_DEFAULT
