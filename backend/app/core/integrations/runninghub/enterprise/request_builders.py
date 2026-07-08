"""RunningHub 企业版 23 个视频模型的 JSON body 构造器。

字段名、magic string、duration 类型（str/int）、resolution 大小写、cfgScale 值等
逐字移植自 ~/Downloads/toonflow-runninghub-enterprise.ts，不"改进"。
seedance 2.0 / Fast / Mini 三档（API 路径 sparkvideo-2.0[-fast|-mini]）的
text-to-video / image-to-video / multimodal-video 九个模型逐字移植自
~/Downloads/provider/seedance2.0*.md。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.core.contracts.video_generation import VideoGenerationInput


@dataclass(frozen=True, slots=True)
class EnterpriseVideoBuildSpec:
    endpoint_path: str
    mode: str  # "text" | "singleImage" | "startEndRequired" | "imageReference:3" | "imageReference:7" | "imageReference:9" | "multimodal"
    build_request: Callable[[VideoGenerationInput, list[str]], dict]


def _wan27_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "resolution": inp.resolution or "720P",
        "duration": str(inp.seconds or 5),
        "promptExtend": True,
        "seed": None,
    }


def _wan27_reference_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "videoUrls": [],
        "imageUrls": urls,
        "resolution": inp.resolution or "720P",
        "duration": str(inp.seconds or 5),
        "aspectRatio": inp.ratio,
        "promptExtend": True,
        "seed": None,
    }


def _ltx23_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "imageUrl": urls[0],
        "prompt": inp.prompt or "",
        "resolution": (inp.resolution or "480P").replace("P", "p"),
        "aspectRatio": inp.ratio,
        "duration": inp.seconds or 5,
    }


def _ltx23_image_to_video_lora(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "imageUrl": urls[0],
        "resolution": (inp.resolution or "480P").replace("P", "p"),
        "aspectRatio": inp.ratio,
        "duration": inp.seconds or 5,
        "lora1": "framee_4000.safetensors",
        "lora1_strength_model": 0,
        "lora2": "framee_4000.safetensors",
        "lora2_strength_model": 0,
        "lora3": "framee_4000.safetensors",
        "lora3_strength_model": 0,
        "prompt": inp.prompt or "",
    }


def _happyhorse_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "imageUrl": urls[0],
        "prompt": inp.prompt or "",
        "resolution": (inp.resolution or "720P").replace("P", "p"),
        "duration": str(inp.seconds or 5),
        "seed": None,
    }


def _happyhorse_reference_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "imageUrls": urls,
        "resolution": (inp.resolution or "720P").replace("P", "p"),
        "aspectRatio": inp.ratio,
        "duration": str(inp.seconds or 5),
        "seed": None,
    }


def _kling_o3_pro(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "duration": inp.seconds or 5,
        "sound": inp.audio is not False,
        "multiShot": False,
        "shotType": "customize",
    }


def _kling_o3_std(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "duration": inp.seconds or 5,
        "sound": inp.audio is not False,
        "multiShot": False,
        "shotType": "customize",
    }


def _kling_v3_pro(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "duration": str(inp.seconds or 5),
        "sound": inp.audio is not False,
        "multiShot": False,
        "shotType": "customize",
        "negativePrompt": None,
        "cfgScale": 0.5,
    }


def _kling_v3_std(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "duration": str(inp.seconds or 5),
        "sound": inp.audio is not False,
        "multiShot": False,
        "shotType": "customize",
        "negativePrompt": None,
        "cfgScale": 0.8,
    }


def _rhart_g_official_reference_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "imageUrls": urls,
        "prompt": inp.prompt or "",
        "duration": str(inp.seconds or 6),
        "resolution": (inp.resolution or "720P").replace("P", "p"),
    }


def _rhart_g_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "aspectRatio": inp.ratio,
        "imageUrls": urls,
        "resolution": (inp.resolution or "480P").replace("P", "p"),
        "duration": max(6, min(30, inp.seconds or 6)),
    }


def _rhart_v31_start_end_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstFrameUrl": urls[0],
        "lastFrameUrl": urls[1] if len(urls) >= 2 else None,
        "aspectRatio": inp.ratio,
        "duration": str(inp.seconds or 8),
        "resolution": (inp.resolution or "720P").replace("P", "p"),
    }


def _rhart_v31_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "aspectRatio": inp.ratio,
        "imageUrls": urls,
        "duration": str(inp.seconds or 8),
        "resolution": (inp.resolution or "720P").replace("P", "p"),
    }


# ---- seedance 2.0 / Fast / Mini（sparkvideo-2.0[-fast|-mini]）----
# 三档 body 形状一致，仅 endpoint_path 不同，故共用三个构造函数。

def _sparkvideo_resolution(inp: VideoGenerationInput) -> str:
    """seedance 分辨率：API 接受小写枚举 480p/720p/1080p/2k/4k（基座另支持 native1080p/native4k）。
    契约 resolution 为 '480P'/'720P'/'1080P'/'2K'/'4K'，统一转小写。"""
    return (inp.resolution or "720P").lower()


def _sparkvideo_seed(inp: VideoGenerationInput) -> int:
    return inp.seed if inp.seed is not None else -1


def _sparkvideo_text_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "resolution": _sparkvideo_resolution(inp),
        "duration": str(inp.seconds or 5),
        "generateAudio": inp.audio is not False,
        "ratio": inp.ratio,
        "webSearch": False,
        "returnLastFrame": False,
        "seed": _sparkvideo_seed(inp),
    }


def _sparkvideo_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or None,
        "resolution": _sparkvideo_resolution(inp),
        "duration": str(inp.seconds or 5),
        "firstFrameUrl": urls[0],
        "lastFrameUrl": urls[1] if len(urls) >= 2 else None,
        "generateAudio": inp.audio is not False,
        "ratio": inp.ratio,
        "realPersonMode": True,
        "conversionSlots": ["all"],
        "returnLastFrame": False,
        "seed": _sparkvideo_seed(inp),
    }


def _sparkvideo_multimodal_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "resolution": _sparkvideo_resolution(inp),
        "duration": str(inp.seconds or 5),
        "imageUrls": urls,
        "videoUrls": [],
        "audioUrls": [],
        "generateAudio": inp.audio is not False,
        "ratio": inp.ratio,
        "realPersonMode": True,
        "conversionSlots": ["all"],
        "returnLastFrame": False,
        "seed": _sparkvideo_seed(inp),
    }


ENTERPRISE_VIDEO_BUILDERS: dict[str, EnterpriseVideoBuildSpec] = {
    "wan-2.7/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/alibaba/wan-2.7/image-to-video",
        mode="startEndRequired",
        build_request=_wan27_image_to_video,
    ),
    "wan-2.7/reference-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/alibaba/wan-2.7/reference-to-video",
        mode="imageReference:9",
        build_request=_wan27_reference_to_video,
    ),
    "ltx-2.3/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/ltx-2.3/image-to-video",
        mode="singleImage",
        build_request=_ltx23_image_to_video,
    ),
    "ltx-2.3/image-to-video-lora": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/ltx-2.3/image-to-video-lora",
        mode="singleImage",
        build_request=_ltx23_image_to_video_lora,
    ),
    "happyhorse-1.0/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/alibaba/happyhorse-1.0/image-to-video",
        mode="singleImage",
        build_request=_happyhorse_image_to_video,
    ),
    "happyhorse-1.0/reference-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/alibaba/happyhorse-1.0/reference-to-video",
        mode="imageReference:9",
        build_request=_happyhorse_reference_to_video,
    ),
    "kling-video-o3-pro/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/kling-video-o3-pro/image-to-video",
        mode="startEndRequired",
        build_request=_kling_o3_pro,
    ),
    "kling-video-o3-std/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/kling-video-o3-std/image-to-video",
        mode="startEndRequired",
        build_request=_kling_o3_std,
    ),
    "kling-v3.0-pro/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/kling-v3.0-pro/image-to-video",
        mode="startEndRequired",
        build_request=_kling_v3_pro,
    ),
    "kling-v3.0-std/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/kling-v3.0-std/image-to-video",
        mode="startEndRequired",
        build_request=_kling_v3_std,
    ),
    "rhart-video-g-official/reference-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video-g-official/reference-to-video",
        mode="imageReference:9",
        build_request=_rhart_g_official_reference_to_video,
    ),
    "rhart-video-g/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video-g/image-to-video",
        mode="imageReference:7",
        build_request=_rhart_g_image_to_video,
    ),
    "rhart-video-v3.1-fast/start-end-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video-v3.1-fast/start-end-to-video",
        mode="startEndRequired",
        build_request=_rhart_v31_start_end_to_video,
    ),
    "rhart-video-v3.1-fast/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video-v3.1-fast/image-to-video",
        mode="imageReference:3",
        build_request=_rhart_v31_image_to_video,
    ),
    # ---- seedance 2.0 / Fast / Mini（sparkvideo-2.0[-fast|-mini]）----
    "sparkvideo-2.0/text-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/sparkvideo-2.0/text-to-video",
        mode="text",
        build_request=_sparkvideo_text_to_video,
    ),
    "sparkvideo-2.0/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/sparkvideo-2.0/image-to-video",
        mode="startEndRequired",
        build_request=_sparkvideo_image_to_video,
    ),
    "sparkvideo-2.0/multimodal-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/sparkvideo-2.0/multimodal-video",
        mode="multimodal",
        build_request=_sparkvideo_multimodal_video,
    ),
    "sparkvideo-2.0-fast/text-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/sparkvideo-2.0-fast/text-to-video",
        mode="text",
        build_request=_sparkvideo_text_to_video,
    ),
    "sparkvideo-2.0-fast/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/sparkvideo-2.0-fast/image-to-video",
        mode="startEndRequired",
        build_request=_sparkvideo_image_to_video,
    ),
    "sparkvideo-2.0-fast/multimodal-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/sparkvideo-2.0-fast/multimodal-video",
        mode="multimodal",
        build_request=_sparkvideo_multimodal_video,
    ),
    "sparkvideo-2.0-mini/text-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/sparkvideo-2.0-mini/text-to-video",
        mode="text",
        build_request=_sparkvideo_text_to_video,
    ),
    "sparkvideo-2.0-mini/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/sparkvideo-2.0-mini/image-to-video",
        mode="startEndRequired",
        build_request=_sparkvideo_image_to_video,
    ),
    "sparkvideo-2.0-mini/multimodal-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/sparkvideo-2.0-mini/multimodal-video",
        mode="multimodal",
        build_request=_sparkvideo_multimodal_video,
    ),
}
