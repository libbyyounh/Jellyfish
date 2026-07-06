"""RunningHub 视频适配器：create + get 两阶段，Task 层负责轮询节奏。"""

from __future__ import annotations

import base64
from typing import Any

from app.core.contracts.provider import ProviderConfig
from app.core.contracts.video_generation import VideoGenerationInput
from app.core.integrations.runninghub import client as rh_client
from app.core.integrations.runninghub.node_configs import VIDEO_NODE_CONFIGS


class RunningHubVideoApiAdapter:
    """RunningHub 视频生成 HTTP；无状态。"""

    async def create_video(
        self,
        *,
        cfg: ProviderConfig,
        input_: VideoGenerationInput,
        timeout_s: float,
    ) -> str:
        workflow_id = input_.model or ""
        config = VIDEO_NODE_CONFIGS.get(workflow_id)
        if config is None:
            raise ValueError(f"Unknown RunningHub video workflow: {workflow_id}")

        base_url = cfg.base_url or "https://www.runninghub.cn"
        image_urls = await _resolve_frame_urls(input_, config.image_count, cfg, timeout_s)

        node_info_list = config.build_nodes(input_, image_urls)

        if config.endpoint == "workflow":
            return await rh_client.submit_workflow_task(
                base_url, cfg.api_key, workflow_id, node_info_list, timeout_s=timeout_s
            )
        return await rh_client.submit_ai_app_task(
            base_url, cfg.api_key, workflow_id, node_info_list, timeout_s=timeout_s
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


async def _resolve_frame_urls(
    input_: VideoGenerationInput,
    image_count: int,
    cfg: ProviderConfig,
    timeout_s: float,
) -> list[str]:
    base64_frames: list[tuple[str, str]] = []
    for label, raw in (
        ("first", input_.first_frame_base64),
        ("last", input_.last_frame_base64),
        ("key", input_.key_frame_base64),
    ):
        if raw:
            mime, data = _split_data_url(raw)
            base64_frames.append((mime, data))

    if not base64_frames:
        raise ValueError("RunningHub 视频生成需要至少一张参考图（first/last/key_frame_base64）")

    base_url = cfg.base_url or "https://www.runninghub.cn"
    urls: list[str] = []
    for mime, data in base64_frames:
        bytes_data = base64.b64decode(data)
        url = await rh_client.upload_media(base_url, cfg.api_key, mime, bytes_data, timeout_s=timeout_s)
        urls.append(url)

    while len(urls) < image_count:
        urls.append(urls[-1])
    return urls


def _split_data_url(raw: str) -> tuple[str, str]:
    """返回 (mime, base64_data)。支持纯 base64 与 data:image/...;base64,... 两种格式。"""
    s = raw.strip()
    if s.startswith("data:") and ";base64," in s:
        head, _, data = s.partition(";base64,")
        mime = head[5:] or "image/png"
        return mime, data
    return "image/png", s
