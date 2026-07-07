"""RunningHub 企业版视频能力声明。

能力按模型名前缀硬编码（与个人版模式一致），因为 resolve_video_capability
接收 model: str | None，无法读取 Model.params。duration 范围源自 .ts 的
durationResolutionMap。
"""

from __future__ import annotations

from app.core.integrations.video_capabilities import VideoModelCapability

_ENTERPRISE_DEFAULT = VideoModelCapability(
    supports_seed=False,
    supports_watermark=False,
    allowed_ratios={"16:9", "9:16"},
    default_ratio="16:9",
    min_seconds=5,
    max_seconds=5,
)

# 按模型名前缀匹配（大小写不敏感）。最长前缀优先。
_ENTERPRISE_PREFIX_OVERRIDES: dict[str, VideoModelCapability] = {
    "wan-2.7/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=5,
        max_seconds=5,
    ),
    "ltx-2.3/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=5,
        max_seconds=5,
    ),
    "happyhorse-1.0/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=5,
        max_seconds=5,
    ),
    "kling-video-o3-": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=5,
        max_seconds=10,
    ),
    "kling-v3.0-": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=5,
        max_seconds=10,
    ),
    "rhart-video-g-official/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=6,
        max_seconds=8,
    ),
    "rhart-video-g/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=6,
        max_seconds=30,
    ),
    "rhart-video-v3.1-fast/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=8,
        max_seconds=8,
    ),
}


def register_runninghub_enterprise_video_capability(*, model_prefix: str, capability: VideoModelCapability) -> None:
    prefix = model_prefix.strip().lower()
    if not prefix:
        raise ValueError("model_prefix must not be empty")
    _ENTERPRISE_PREFIX_OVERRIDES[prefix] = capability


def clear_runninghub_enterprise_video_capability_overrides() -> None:
    _ENTERPRISE_PREFIX_OVERRIDES.clear()


def _pick_override(model: str | None) -> VideoModelCapability | None:
    if not model:
        return None
    value = model.strip().lower()
    if not value:
        return None
    for prefix, cap in sorted(_ENTERPRISE_PREFIX_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True):
        if value.startswith(prefix):
            return cap
    return None


def resolve_runninghub_enterprise_video_capability(model: str | None) -> VideoModelCapability:
    return _pick_override(model) or _ENTERPRISE_DEFAULT
