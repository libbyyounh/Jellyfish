from __future__ import annotations

from app.core.integrations.runninghub.enterprise.video_capabilities import (
    resolve_runninghub_enterprise_video_capability,
)


def test_default_for_unknown_model() -> None:
    cap = resolve_runninghub_enterprise_video_capability(None)
    assert cap.supports_seed is False
    assert cap.supports_watermark is False
    assert cap.allowed_ratios == {"16:9", "9:16"}
    assert cap.default_ratio == "16:9"
    assert cap.min_seconds == 5
    assert cap.max_seconds == 5


def test_wan27_models_are_5_to_5() -> None:
    for model in ("wan-2.7/image-to-video", "wan-2.7/reference-to-video"):
        cap = resolve_runninghub_enterprise_video_capability(model)
        assert cap.min_seconds == 5
        assert cap.max_seconds == 5


def test_kling_v3_models_are_5_to_10() -> None:
    for model in (
        "kling-video-o3-pro/image-to-video",
        "kling-video-o3-std/image-to-video",
        "kling-v3.0-pro/image-to-video",
        "kling-v3.0-std/image-to-video",
    ):
        cap = resolve_runninghub_enterprise_video_capability(model)
        assert cap.min_seconds == 5
        assert cap.max_seconds == 10


def test_rhart_g_is_6_to_30() -> None:
    cap = resolve_runninghub_enterprise_video_capability("rhart-video-g/image-to-video")
    assert cap.min_seconds == 6
    assert cap.max_seconds == 30


def test_rhart_v31_fast_is_8_to_8() -> None:
    for model in (
        "rhart-video-v3.1-fast/start-end-to-video",
        "rhart-video-v3.1-fast/image-to-video",
    ):
        cap = resolve_runninghub_enterprise_video_capability(model)
        assert cap.min_seconds == 8
        assert cap.max_seconds == 8
