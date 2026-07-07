from __future__ import annotations

import pytest

from app.core.contracts.video_generation import VideoGenerationInput
from app.core.integrations.runninghub.enterprise.request_builders import ENTERPRISE_VIDEO_BUILDERS


def _inp(**kw) -> VideoGenerationInput:
    defaults = {"ratio": "16:9", "prompt": "a cat runs"}
    defaults.update(kw)
    return VideoGenerationInput(**defaults)


# ---- wan-2.7/image-to-video (startEndRequired) ----
def test_wan27_image_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["wan-2.7/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/alibaba/wan-2.7/image-to-video"
    assert spec.mode == "startEndRequired"
    body = spec.build_request(_inp(seconds=5, resolution="720P"), ["https://rh/first.png", "https://rh/last.png"])
    assert body == {
        "prompt": "a cat runs",
        "firstImageUrl": "https://rh/first.png",
        "lastImageUrl": "https://rh/last.png",
        "resolution": "720P",
        "duration": "5",
        "promptExtend": True,
        "seed": None,
    }


def test_wan27_image_to_video_single_frame_last_is_none() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["wan-2.7/image-to-video"]
    body = spec.build_request(_inp(seconds=5), ["https://rh/first.png"])
    assert body["lastImageUrl"] is None


# ---- wan-2.7/reference-to-video (imageReference:9) ----
def test_wan27_reference_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["wan-2.7/reference-to-video"]
    assert spec.mode == "imageReference:9"
    urls = ["https://rh/a.png", "https://rh/b.png", "https://rh/c.png"]
    body = spec.build_request(_inp(seconds=5, resolution="1080P"), urls)
    assert body == {
        "prompt": "a cat runs",
        "videoUrls": [],
        "imageUrls": urls,
        "resolution": "1080P",
        "duration": "5",
        "aspectRatio": "16:9",
        "promptExtend": True,
        "seed": None,
    }


# ---- ltx-2.3/image-to-video (singleImage) ----
def test_ltx23_image_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["ltx-2.3/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video/ltx-2.3/image-to-video"
    assert spec.mode == "singleImage"
    body = spec.build_request(_inp(seconds=5, resolution="480P"), ["https://rh/img.png"])
    assert body == {
        "imageUrl": "https://rh/img.png",
        "prompt": "a cat runs",
        "resolution": "480p",
        "aspectRatio": "16:9",
        "duration": 5,
    }


# ---- ltx-2.3/image-to-video-lora (singleImage) ----
def test_ltx23_image_to_video_lora_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["ltx-2.3/image-to-video-lora"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video/ltx-2.3/image-to-video-lora"
    body = spec.build_request(_inp(seconds=5, resolution="480P"), ["https://rh/img.png"])
    assert body == {
        "imageUrl": "https://rh/img.png",
        "resolution": "480p",
        "aspectRatio": "16:9",
        "duration": 5,
        "lora1": "framee_4000.safetensors",
        "lora1_strength_model": 0,
        "lora2": "framee_4000.safetensors",
        "lora2_strength_model": 0,
        "lora3": "framee_4000.safetensors",
        "lora3_strength_model": 0,
        "prompt": "a cat runs",
    }


# ---- happyhorse-1.0/image-to-video (singleImage) ----
def test_happyhorse_image_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["happyhorse-1.0/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/alibaba/happyhorse-1.0/image-to-video"
    body = spec.build_request(_inp(seconds=5, resolution="720P"), ["https://rh/img.png"])
    assert body == {
        "imageUrl": "https://rh/img.png",
        "prompt": "a cat runs",
        "resolution": "720p",
        "duration": "5",
        "seed": None,
    }


# ---- happyhorse-1.0/reference-to-video (imageReference:9) ----
def test_happyhorse_reference_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["happyhorse-1.0/reference-to-video"]
    assert spec.mode == "imageReference:9"
    urls = ["https://rh/a.png", "https://rh/b.png"]
    body = spec.build_request(_inp(seconds=5, resolution="1080P"), urls)
    assert body == {
        "prompt": "a cat runs",
        "imageUrls": urls,
        "resolution": "1080p",
        "aspectRatio": "16:9",
        "duration": "5",
        "seed": None,
    }


# ---- kling-video-o3-pro/image-to-video (startEndRequired, sound=True, duration=int) ----
def test_kling_o3_pro_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["kling-video-o3-pro/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/kling-video-o3-pro/image-to-video"
    assert spec.mode == "startEndRequired"
    body = spec.build_request(_inp(seconds=10, audio=None), ["https://rh/first.png", "https://rh/last.png"])
    assert body == {
        "prompt": "a cat runs",
        "firstImageUrl": "https://rh/first.png",
        "lastImageUrl": "https://rh/last.png",
        "duration": 10,
        "sound": True,
        "multiShot": False,
        "shotType": "customize",
    }


def test_kling_o3_pro_audio_false_sets_sound_false() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["kling-video-o3-pro/image-to-video"]
    body = spec.build_request(_inp(audio=False), ["https://rh/first.png"])
    assert body["sound"] is False


# ---- kling-video-o3-std/image-to-video ----
def test_kling_o3_std_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["kling-video-o3-std/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/kling-video-o3-std/image-to-video"
    body = spec.build_request(_inp(seconds=5), ["https://rh/first.png"])
    assert body["duration"] == 5
    assert body["sound"] is True


# ---- kling-v3.0-pro/image-to-video (cfgScale=0.5, duration=str) ----
def test_kling_v3_pro_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["kling-v3.0-pro/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/kling-v3.0-pro/image-to-video"
    body = spec.build_request(_inp(seconds=10), ["https://rh/first.png", "https://rh/last.png"])
    assert body == {
        "prompt": "a cat runs",
        "firstImageUrl": "https://rh/first.png",
        "lastImageUrl": "https://rh/last.png",
        "duration": "10",
        "sound": True,
        "multiShot": False,
        "shotType": "customize",
        "negativePrompt": None,
        "cfgScale": 0.5,
    }


# ---- kling-v3.0-std/image-to-video (cfgScale=0.8) ----
def test_kling_v3_std_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["kling-v3.0-std/image-to-video"]
    body = spec.build_request(_inp(seconds=5), ["https://rh/first.png"])
    assert body["cfgScale"] == 0.8
    assert body["duration"] == "5"


# ---- rhart-video-g-official/reference-to-video (imageReference:9) ----
def test_rhart_g_official_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["rhart-video-g-official/reference-to-video"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video-g-official/reference-to-video"
    assert spec.mode == "imageReference:9"
    urls = ["https://rh/a.png", "https://rh/b.png"]
    body = spec.build_request(_inp(seconds=8, resolution="720P"), urls)
    assert body == {
        "imageUrls": urls,
        "prompt": "a cat runs",
        "duration": "8",
        "resolution": "720p",
    }


# ---- rhart-video-g/image-to-video (imageReference:7, clamped duration) ----
def test_rhart_g_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["rhart-video-g/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video-g/image-to-video"
    assert spec.mode == "imageReference:7"
    urls = ["https://rh/a.png", "https://rh/b.png"]
    body = spec.build_request(_inp(seconds=30, resolution="720P"), urls)
    assert body == {
        "prompt": "a cat runs",
        "aspectRatio": "16:9",
        "imageUrls": urls,
        "resolution": "720p",
        "duration": 30,
    }


def test_rhart_g_clamps_duration_to_min_6() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["rhart-video-g/image-to-video"]
    body = spec.build_request(_inp(seconds=3), ["https://rh/a.png"])
    assert body["duration"] == 6


# ---- rhart-video-v3.1-fast/start-end-to-video (startEndRequired, firstFrameUrl casing) ----
def test_rhart_v31_start_end_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["rhart-video-v3.1-fast/start-end-to-video"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video-v3.1-fast/start-end-to-video"
    assert spec.mode == "startEndRequired"
    body = spec.build_request(_inp(seconds=8, resolution="1080P"), ["https://rh/first.png", "https://rh/last.png"])
    assert body == {
        "prompt": "a cat runs",
        "firstFrameUrl": "https://rh/first.png",
        "lastFrameUrl": "https://rh/last.png",
        "aspectRatio": "16:9",
        "duration": "8",
        "resolution": "1080p",
    }


# ---- rhart-video-v3.1-fast/image-to-video (imageReference:3) ----
def test_rhart_v31_image_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["rhart-video-v3.1-fast/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video-v3.1-fast/image-to-video"
    assert spec.mode == "imageReference:3"
    urls = ["https://rh/a.png", "https://rh/b.png", "https://rh/c.png"]
    body = spec.build_request(_inp(seconds=8, resolution="720P"), urls)
    assert body == {
        "prompt": "a cat runs",
        "aspectRatio": "16:9",
        "imageUrls": urls,
        "duration": "8",
        "resolution": "720p",
    }


def test_enterprise_builders_has_14_entries() -> None:
    assert len(ENTERPRISE_VIDEO_BUILDERS) == 14
