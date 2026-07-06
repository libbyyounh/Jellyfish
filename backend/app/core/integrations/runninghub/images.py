"""RunningHub 图片适配器：adapter 内部完成 submit → poll，对外同步语义。"""

from __future__ import annotations

from app.core.contracts.image_generation import (
    ImageGenerationInput,
    ImageGenerationResult,
    ImageItem,
)
from app.core.contracts.provider import ProviderConfig
from app.core.integrations.runninghub import client as rh_client
from app.core.integrations.runninghub.node_configs import IMAGE_NODE_CONFIGS


class RunningHubImageApiAdapter:
    """RunningHub 图片生成 HTTP；无状态。"""

    async def generate(
        self,
        *,
        cfg: ProviderConfig,
        inp: ImageGenerationInput,
        timeout_s: float,
    ) -> ImageGenerationResult:
        workflow_id = inp.model or ""
        config = IMAGE_NODE_CONFIGS.get(workflow_id)
        if config is None:
            raise ValueError(f"Unknown RunningHub image workflow: {workflow_id}")

        image_url: str | None = None
        if config.requires_image:
            image_url = _resolve_image_url(inp)
            if not image_url:
                raise ValueError("RunningHub 图片生成需要参考图片，但 InputImageRef 未提供 image_url")

        node_info_list = config.build_nodes(inp, image_url)

        base_url = cfg.base_url or "https://www.runninghub.cn"
        task_id = await rh_client.submit_ai_app_task(
            base_url, cfg.api_key, workflow_id, node_info_list, timeout_s=timeout_s
        )
        result_url = await rh_client.poll_until_done(
            base_url, cfg.api_key, task_id, interval=5.0, timeout=600.0
        )

        return ImageGenerationResult(
            images=[ImageItem(url=result_url)],
            provider="runninghub",
            provider_task_id=task_id,
            status="succeeded",
        )


def _resolve_image_url(inp: ImageGenerationInput) -> str | None:
    for ref in inp.images or []:
        if ref.image_url:
            return ref.image_url
    return None
