"""RunningHub 9 个 workflowId 的 nodeInfoList 模板，硬编码（迁移自 toonflow .ts）。"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Literal

from app.core.contracts.image_generation import ImageGenerationInput
from app.core.contracts.video_generation import VideoGenerationInput


@dataclass(frozen=True, slots=True)
class ImageNodeConfig:
    endpoint: Literal["ai_app", "workflow"]
    build_nodes: Callable[[ImageGenerationInput, str | None], list[dict]]
    requires_image: bool


@dataclass(frozen=True, slots=True)
class VideoNodeConfig:
    endpoint: Literal["ai_app", "workflow"]
    build_nodes: Callable[[VideoGenerationInput, str | list[str]], list[dict]]
    image_count: int


def _parse_aspect_ratio(ratio: str | None) -> tuple[int, int]:
    if not ratio or "/" not in ratio and ":" not in ratio:
        return 1, 1
    sep = "/" if "/" in ratio else ":"
    parts = ratio.split(sep)
    if len(parts) != 2:
        return 1, 1
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return 1, 1


def _build_duanju_nodes(inp: ImageGenerationInput, image_url: str | None) -> list[dict]:
    rw, rh = _parse_aspect_ratio(inp.target_ratio)
    width = max(512, min(4096, round(rw * 96 / 8) * 8))
    height = max(512, min(4096, round(rh * 96 / 8) * 8))
    return [
        {"nodeId": "49", "fieldName": "text", "fieldValue": inp.prompt, "description": "提示词"},
        {"nodeId": "60", "fieldName": "value", "fieldValue": str(width), "description": "宽"},
        {"nodeId": "61", "fieldName": "value", "fieldValue": str(height), "description": "高"},
    ]


def _build_zimage_zhibao_nodes(inp: ImageGenerationInput, image_url: str | None) -> list[dict]:
    return [{"nodeId": "59", "fieldName": "value", "fieldValue": inp.prompt, "description": "提示词"}]


def _build_qwen_image_nodes(inp: ImageGenerationInput, image_url: str | None) -> list[dict]:
    ratio_map = {"3:2": "1", "2:3": "2", "16:9": "3", "9:16": "4", "4:3": "5", "3:4": "6", "1:1": "7"}
    ratio_select = ratio_map.get(inp.target_ratio or "", "7")
    seed = str(random.randint(0, 10**15 - 1))
    lora_name = "国潮面部插画qwen触发词gc.safetensors"
    return [
        {"nodeId": "932", "fieldName": "prompt", "fieldValue": inp.prompt, "description": "正向提示词"},
        {"nodeId": "931", "fieldName": "text", "fieldValue": "", "description": "反向提示词"},
        {"nodeId": "887", "fieldName": "select", "fieldValue": ratio_select, "description": "设置比例"},
        {"nodeId": "889", "fieldName": "batch_size", "fieldValue": "1", "description": "出图张数"},
        {"nodeId": "925", "fieldName": "lora_name", "fieldValue": lora_name, "description": "lora1_name"},
        {"nodeId": "925", "fieldName": "strength_model", "fieldValue": "0", "description": "lora1_strength"},
        {"nodeId": "925", "fieldName": "strength_clip", "fieldValue": "0", "description": "lora1_strength_clip"},
        {"nodeId": "933", "fieldName": "text1", "fieldValue": "", "description": "text1-lora触发词"},
        {"nodeId": "926", "fieldName": "lora_name", "fieldValue": lora_name, "description": "lora2_name"},
        {"nodeId": "926", "fieldName": "strength_model", "fieldValue": "0", "description": "lora2_strength"},
        {"nodeId": "926", "fieldName": "strength_clip", "fieldValue": "0", "description": "lora2_strength_clip"},
        {"nodeId": "933", "fieldName": "text2", "fieldValue": "", "description": "text2-lora触发词"},
        {"nodeId": "927", "fieldName": "lora_name", "fieldValue": lora_name, "description": "lora3_name"},
        {"nodeId": "927", "fieldName": "strength_model", "fieldValue": "0", "description": "lora3_strength"},
        {"nodeId": "927", "fieldName": "strength_clip", "fieldValue": "0", "description": "lora3_strength_clip"},
        {"nodeId": "933", "fieldName": "text3", "fieldValue": "", "description": "text3-lora触发词"},
        {"nodeId": "928", "fieldName": "lora_name", "fieldValue": lora_name, "description": "lora4_name"},
        {"nodeId": "928", "fieldName": "strength_model", "fieldValue": "0", "description": "lora4_strength"},
        {"nodeId": "928", "fieldName": "strength_clip", "fieldValue": "0", "description": "lora4_strength_clip"},
        {"nodeId": "933", "fieldName": "text4", "fieldValue": "", "description": "text4-lora触发词"},
        {"nodeId": "929", "fieldName": "lora_name", "fieldValue": lora_name, "description": "lora5_name"},
        {"nodeId": "929", "fieldName": "strength_model", "fieldValue": "0", "description": "lora5_strength"},
        {"nodeId": "929", "fieldName": "strength_clip", "fieldValue": "0", "description": "lora5_strength_clip"},
        {"nodeId": "933", "fieldName": "text5", "fieldValue": "", "description": "text5-lora触发词"},
        {"nodeId": "860", "fieldName": "seed", "fieldValue": seed, "description": "种子"},
        {"nodeId": "860", "fieldName": "steps", "fieldValue": "4", "description": "步数"},
        {"nodeId": "860", "fieldName": "sampler_name", "fieldValue": "euler", "description": "采样器"},
        {"nodeId": "860", "fieldName": "scheduler", "fieldValue": "simple", "description": "调度器"},
        {"nodeId": "938", "fieldName": "unet_name", "fieldValue": "qwen_image_fp8_e4m3fn.safetensors", "description": "unet_name"},
    ]


def _build_qwen_edit_nodes(inp: ImageGenerationInput, image_url: str | None) -> list[dict]:
    if not image_url:
        raise ValueError("Qwen Image Edit 图生图需要至少一张参考图片")
    return [
        {"nodeId": "41", "fieldName": "image", "fieldValue": image_url, "description": "image"},
        {"nodeId": "68", "fieldName": "prompt", "fieldValue": inp.prompt, "description": "prompt"},
    ]


def _build_zimage_8k_nodes(inp: ImageGenerationInput, image_url: str | None) -> list[dict]:
    return [{"nodeId": "163", "fieldName": "text", "fieldValue": inp.prompt, "description": "text"}]


def _video_dimensions(workflow_id: str, inp: VideoGenerationInput) -> tuple[int, int]:
    if workflow_id == "1956699246381469698":
        return 848, 480
    base_w, base_h = 1280, 720
    if inp.ratio == "9:16":
        return base_h, base_w
    return base_w, base_h


def _build_wan22_nodes(inp: VideoGenerationInput, image_urls: str | list[str]) -> list[dict]:
    url = image_urls[0] if isinstance(image_urls, list) else image_urls
    width, height = _video_dimensions("1956699246381469698", inp)
    duration = inp.seconds or 5
    return [
        {"nodeId": "790", "fieldName": "image", "fieldValue": url, "description": "输入图片"},
        {"nodeId": "809", "fieldName": "value", "fieldValue": inp.prompt or "", "description": "输入提示词"},
        {"nodeId": "789", "fieldName": "value", "fieldValue": str(duration), "description": "时长"},
        {"nodeId": "791", "fieldName": "max_width", "fieldValue": str(width), "description": "输入宽"},
        {"nodeId": "791", "fieldName": "max_height", "fieldValue": str(height), "description": "输入高"},
    ]


def _build_ltx23_standard_nodes(inp: VideoGenerationInput, image_urls: str | list[str]) -> list[dict]:
    url = image_urls[0] if isinstance(image_urls, list) else image_urls
    width, height = _video_dimensions("2029759632314474498", inp)
    duration = inp.seconds or 5
    return [
        {"nodeId": "98", "fieldName": "image", "fieldValue": url, "description": "上传图片"},
        {"nodeId": "185", "fieldName": "value", "fieldValue": str(round(duration * 24)), "description": "视频长度"},
        {"nodeId": "222", "fieldName": "value", "fieldValue": str(width), "description": "视频宽度"},
        {"nodeId": "223", "fieldName": "value", "fieldValue": str(height), "description": "视频高度"},
        {"nodeId": "224", "fieldName": "value", "fieldValue": inp.prompt or "", "description": "提示词"},
    ]


def _build_ltx23_multishot_nodes(inp: VideoGenerationInput, image_urls: str | list[str]) -> list[dict]:
    url = image_urls[0] if isinstance(image_urls, list) else image_urls
    prompt = inp.prompt or ""
    return [
        {"nodeId": "584", "fieldName": "image", "fieldValue": url, "description": "image"},
        {"nodeId": "620", "fieldName": "prompt", "fieldValue": prompt, "description": "prompt主提示词"},
        {"nodeId": "621", "fieldName": "prompt", "fieldValue": prompt, "description": "prompt分阶段提示词"},
    ]


def _build_ltx23_fourframe_nodes(inp: VideoGenerationInput, image_urls: str | list[str]) -> list[dict]:
    urls = list(image_urls) if isinstance(image_urls, list) else [image_urls]
    while len(urls) < 4:
        urls.append(urls[-1])
    return [
        {"nodeId": "1361", "fieldName": "image", "fieldValue": urls[0], "description": "参考图1"},
        {"nodeId": "1362", "fieldName": "image", "fieldValue": urls[1], "description": "参考图2"},
        {"nodeId": "1363", "fieldName": "image", "fieldValue": urls[2], "description": "参考图3"},
        {"nodeId": "1364", "fieldName": "image", "fieldValue": urls[3], "description": "参考图4"},
        {"nodeId": "1473", "fieldName": "text", "fieldValue": inp.prompt or "", "description": "自定义剧情提示词"},
    ]


IMAGE_NODE_CONFIGS: dict[str, ImageNodeConfig] = {
    "2052744677727715329": ImageNodeConfig("ai_app", _build_duanju_nodes, requires_image=False),
    "2003681895185563650": ImageNodeConfig("ai_app", _build_zimage_zhibao_nodes, requires_image=False),
    "1970396677775499266": ImageNodeConfig("ai_app", _build_qwen_image_nodes, requires_image=False),
    "2029488621429989377": ImageNodeConfig("ai_app", _build_qwen_edit_nodes, requires_image=True),
    "2058719340626796546": ImageNodeConfig("ai_app", _build_zimage_8k_nodes, requires_image=False),
}

VIDEO_NODE_CONFIGS: dict[str, VideoNodeConfig] = {
    "1956699246381469698": VideoNodeConfig("ai_app", _build_wan22_nodes, image_count=1),
    "2029759632314474498": VideoNodeConfig("ai_app", _build_ltx23_standard_nodes, image_count=1),
    "2055155307592077313": VideoNodeConfig("ai_app", _build_ltx23_multishot_nodes, image_count=1),
    "2054820963426021378": VideoNodeConfig("workflow", _build_ltx23_fourframe_nodes, image_count=4),
}
