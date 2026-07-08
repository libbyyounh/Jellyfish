"""RunningHub 企业版视频适配器：create + get 两阶段，Task 层负责轮询节奏。"""

from __future__ import annotations

import base64
from typing import Any

from app.core.contracts.provider import ProviderConfig
from app.core.contracts.video_generation import VideoGenerationInput
from app.core.integrations.runninghub import client as rh_client
from app.core.integrations.runninghub.enterprise import client as ent_client
from app.core.integrations.runninghub.enterprise.request_builders import ENTERPRISE_VIDEO_BUILDERS, EnterpriseVideoBuildSpec


class RunningHubEnterpriseVideoApiAdapter:
    """RunningHub 企业版视频生成 HTTP；无状态。"""

    async def create_video(
        self,
        *,
        cfg: ProviderConfig,
        input_: VideoGenerationInput,
        timeout_s: float,
    ) -> str:
        model_name = input_.model or ""
        spec = ENTERPRISE_VIDEO_BUILDERS.get(model_name)
        if spec is None:
            raise ValueError(f"Unknown RunningHub enterprise video model: {model_name}")

        base_url = cfg.base_url or "https://www.runninghub.cn"
        image_urls = await _resolve_enterprise_image_urls(input_, spec, base_url, cfg.api_key, timeout_s)
        request_body = spec.build_request(input_, image_urls)

        return await ent_client.submit_enterprise_task(
            base_url, cfg.api_key, spec.endpoint_path, request_body, timeout_s=timeout_s
        )

    async def get_video(
        self,
        *,
        cfg: ProviderConfig,
        video_id: str,
        timeout_s: float,
    ) -> dict[str, Any]:
        base_url = cfg.base_url or "https://www.runninghub.cn"
        return await rh_client.query_task(base_url, cfg.api_key, video_id, timeout_s=timeout_s)


async def _resolve_enterprise_image_urls(
    input_: VideoGenerationInput,
    spec: EnterpriseVideoBuildSpec,
    base_url: str,
    api_key: str,
    timeout_s: float,
) -> list[str]:
    """按 spec.mode 收集 base64 帧 → 上传 → 返回 URL 列表。不补齐。

    text 模式无图（返回空列表）；multimodal 模式允许 0 张参考图（prompt-only）；
    其余模式至少需要一张参考图。
    """
    raw_frames: list[str] = []
    requires_image = True

    if spec.mode == "text":
        return []
    if spec.mode == "singleImage":
        if input_.first_frame_base64:
            raw_frames.append(input_.first_frame_base64)
    elif spec.mode == "startEndRequired":
        for raw in (input_.first_frame_base64, input_.last_frame_base64):
            if raw:
                raw_frames.append(raw)
    elif spec.mode == "imageReference:3":
        for raw in (input_.first_frame_base64, input_.last_frame_base64, input_.key_frame_base64):
            if raw:
                raw_frames.append(raw)
    elif spec.mode in ("imageReference:7", "imageReference:9"):
        max_n = 7 if spec.mode == "imageReference:7" else 9
        refs = input_.reference_frames_base64 or []
        for raw in refs[:max_n]:
            if raw:
                raw_frames.append(raw)
    elif spec.mode == "multimodal":
        requires_image = False
        refs = input_.reference_frames_base64 or []
        for raw in refs[:9]:
            if raw:
                raw_frames.append(raw)
    else:
        raise ValueError(f"Unsupported enterprise mode: {spec.mode}")

    if requires_image and not raw_frames:
        raise ValueError("RunningHub 企业版视频生成需要至少一张参考图")

    urls: list[str] = []
    for raw in raw_frames:
        mime, data = _split_data_url(raw)
        bytes_data = base64.b64decode(data)
        url = await rh_client.upload_media(base_url, api_key, mime, bytes_data, timeout_s=timeout_s)
        urls.append(url)
    return urls


def _split_data_url(raw: str) -> tuple[str, str]:
    """返回 (mime, base64_data)。支持纯 base64 与 data:image/...;base64,... 两种格式。"""
    s = raw.strip()
    if s.startswith("data:") and ";base64," in s:
        head, _, data = s.partition(";base64,")
        mime = head[5:] or "image/png"
        return mime, data
    return "image/png", s
