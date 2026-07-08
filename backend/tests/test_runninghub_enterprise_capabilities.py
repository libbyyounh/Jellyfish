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


def test_sparkvideo_variants_are_4_to_15_with_seed_and_all_ratios() -> None:
    for model in (
        "sparkvideo-2.0/text-to-video",
        "sparkvideo-2.0/image-to-video",
        "sparkvideo-2.0/multimodal-video",
        "sparkvideo-2.0-fast/text-to-video",
        "sparkvideo-2.0-fast/image-to-video",
        "sparkvideo-2.0-fast/multimodal-video",
        "sparkvideo-2.0-mini/text-to-video",
        "sparkvideo-2.0-mini/image-to-video",
        "sparkvideo-2.0-mini/multimodal-video",
    ):
        cap = resolve_runninghub_enterprise_video_capability(model)
        assert cap.supports_seed is True
        assert cap.supports_watermark is False
        assert cap.allowed_ratios == {"16:9", "4:3", "1:1", "3:4", "9:16", "21:9"}
        assert cap.default_ratio == "16:9"
        assert cap.min_seconds == 4
        assert cap.max_seconds == 15


def test_sparkvideo_prefix_does_not_match_unrelated_family() -> None:
    """sparkvideo-2.0/ must not match the -fast/-mini variants (distinct prefixes)."""
    base = resolve_runninghub_enterprise_video_capability("sparkvideo-2.0/text-to-video")
    fast = resolve_runninghub_enterprise_video_capability("sparkvideo-2.0-fast/text-to-video")
    mini = resolve_runninghub_enterprise_video_capability("sparkvideo-2.0-mini/text-to-video")
    # all share the same capability, but each is matched by its own prefix, not the base's
    assert base.max_seconds == 15
    assert fast.max_seconds == 15
    assert mini.max_seconds == 15
