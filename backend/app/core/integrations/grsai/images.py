"""Grsai 图片适配器：adapter 内部完成 submit → poll，对外同步语义。"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.contracts.image_generation import (
    ImageGenerationInput,
    ImageGenerationResult,
    ImageItem,
)
from app.core.contracts.provider import ProviderConfig
from app.core.integrations.grsai import client as grsai_client

_GRSAI_DEFAULT_BASE_URL = "https://grsai.dakka.com.cn"
_GRSAI_POLL_INTERVAL_S = 5.0
_GRSAI_DEFAULT_IMAGE_SIZE = "1K"


class GrsaiImageApiAdapter:
    """Grsai 图片生成 HTTP；无状态。"""

    async def generate(
        self,
        *,
        cfg: ProviderConfig,
        inp: ImageGenerationInput,
        timeout_s: float,
    ) -> ImageGenerationResult:
        base_url = (cfg.base_url or _GRSAI_DEFAULT_BASE_URL).rstrip("/")
        request_body = _build_request_body(inp)

        task_id = await grsai_client.submit_grsai_task(
            base_url, cfg.api_key, request_body, timeout_s=timeout_s
        )

        data = await _poll_until_done(base_url, cfg.api_key, task_id, timeout_s)
        return _parse_result(data, task_id)


def _build_request_body(inp: ImageGenerationInput) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": inp.model or "",
        "prompt": inp.prompt,
        "images": _collect_image_strings(inp),
        "aspectRatio": inp.target_ratio or "1:1",
        "replyType": "async",
    }
    if _is_nano_banana_family(inp.model):
        body["imageSize"] = _resolve_image_size(inp)
    return body


def _is_nano_banana_family(model: str | None) -> bool:
    return (model or "").strip().lower().startswith("nano-banana")


def _resolve_image_size(inp: ImageGenerationInput) -> str:
    if inp.resolution_profile == "high":
        return "2K"
    return _GRSAI_DEFAULT_IMAGE_SIZE


def _collect_image_strings(inp: ImageGenerationInput) -> list[str]:
    images: list[str] = []
    for ref in inp.images or []:
        if ref.image_url:
            images.append(ref.image_url)
    return images


async def _poll_until_done(
    base_url: str,
    api_key: str,
    task_id: str,
    timeout_s: float,
    interval: float = _GRSAI_POLL_INTERVAL_S,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        data = await grsai_client.query_grsai_result(base_url, api_key, task_id, timeout_s=timeout_s)
        status = str(data.get("status") or "")
        if status == "succeeded":
            return data
        if status in ("failed", "violation"):
            error = str(data.get("error") or status)
            raise RuntimeError(f"Grsai 任务失败: {error}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Grsai 任务轮询超时: task_id={task_id}")
        await asyncio.sleep(interval)


def _parse_result(data: dict[str, Any], task_id: str) -> ImageGenerationResult:
    raw_items = data.get("results") or []
    images: list[ImageItem] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if url:
            images.append(ImageItem(url=url))
    if not images:
        raise RuntimeError(f"Grsai 任务完成但 no usable results: {data!r}")
    return ImageGenerationResult(
        images=images,
        provider="grsai",
        provider_task_id=task_id,
        status="succeeded",
    )
