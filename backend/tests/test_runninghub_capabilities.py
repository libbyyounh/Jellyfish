from __future__ import annotations

from app.core.integrations.runninghub.image_capabilities import resolve_runninghub_image_capability
from app.core.integrations.runninghub.video_capabilities import resolve_runninghub_video_capability
from app.core.integrations.image_capabilities import resolve_image_capability
from app.core.integrations.video_capabilities import resolve_video_capability


def test_runninghub_image_capability_defaults() -> None:
    cap = resolve_runninghub_image_capability(None)
    assert cap.supports_seed is False
    assert cap.supports_watermark is False
    assert cap.allowed_sizes is None


def test_runninghub_video_capability_defaults() -> None:
    cap = resolve_runninghub_video_capability(None)
    assert cap.supports_seed is False
    assert cap.supports_watermark is False
    assert cap.allowed_ratios == {"16:9", "9:16"}
    assert cap.min_seconds == 5
    assert cap.max_seconds == 10


def test_resolve_image_capability_dispatches_to_runninghub() -> None:
    cap = resolve_image_capability(provider="runninghub", model=None)
    assert cap.supports_seed is False


def test_resolve_video_capability_dispatches_to_runninghub() -> None:
    cap = resolve_video_capability(provider="runninghub", model=None)
    assert cap.allowed_ratios == {"16:9", "9:16"}
