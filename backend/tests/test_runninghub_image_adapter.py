from __future__ import annotations

from typing import Any

import pytest

from app.core.contracts.image_generation import ImageGenerationInput, InputImageRef
from app.core.contracts.provider import ProviderConfig
from app.core.integrations.runninghub import images as rh_images
from app.core.integrations.runninghub import client as rh_client


@pytest.mark.asyncio
async def test_image_adapter_text_mode_submits_and_polls(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_submit(base_url, api_key, workflow_id, node_info_list, timeout_s=60.0):
        captured["workflow_id"] = workflow_id
        captured["node_info_list"] = node_info_list
        return "task-xyz"

    async def fake_poll(base_url, api_key, task_id, interval=5.0, timeout=600.0):
        captured["task_id"] = task_id
        return "https://rh/out.png"

    monkeypatch.setattr(rh_client, "submit_ai_app_task", fake_submit)
    monkeypatch.setattr(rh_client, "poll_until_done", fake_poll)

    adapter = rh_images.RunningHubImageApiAdapter()
    cfg = ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh")
    inp = ImageGenerationInput(prompt="hero", target_ratio="1:1", model="2052744677727715329")

    result = await adapter.generate(cfg=cfg, inp=inp, timeout_s=60.0)

    assert result.provider == "runninghub"
    assert result.provider_task_id == "task-xyz"
    assert result.images[0].url == "https://rh/out.png"
    assert captured["workflow_id"] == "2052744677727715329"
    assert any(n["nodeId"] == "49" for n in captured["node_info_list"])


@pytest.mark.asyncio
async def test_image_adapter_qwen_edit_resolves_image_url(monkeypatch) -> None:
    async def fake_submit(base_url, api_key, workflow_id, node_info_list, timeout_s=60.0):
        return "task-edit"

    async def fake_poll(base_url, api_key, task_id, interval=5.0, timeout=600.0):
        return "https://rh/out-edit.png"

    monkeypatch.setattr(rh_client, "submit_ai_app_task", fake_submit)
    monkeypatch.setattr(rh_client, "poll_until_done", fake_poll)

    adapter = rh_images.RunningHubImageApiAdapter()
    cfg = ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh")
    inp = ImageGenerationInput(
        prompt="edit",
        target_ratio="1:1",
        model="2029488621429989377",
        images=[InputImageRef(image_url="https://rh/ref.png")],
    )

    result = await adapter.generate(cfg=cfg, inp=inp, timeout_s=60.0)

    assert result.images[0].url == "https://rh/out-edit.png"


@pytest.mark.asyncio
async def test_image_adapter_unknown_workflow_raises(monkeypatch) -> None:
    adapter = rh_images.RunningHubImageApiAdapter()
    cfg = ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh")
    inp = ImageGenerationInput(prompt="x", model="unknown-wf")

    with pytest.raises(ValueError, match="Unknown RunningHub image workflow"):
        await adapter.generate(cfg=cfg, inp=inp, timeout_s=60.0)


@pytest.mark.asyncio
async def test_image_adapter_qwen_edit_without_image_raises(monkeypatch) -> None:
    adapter = rh_images.RunningHubImageApiAdapter()
    cfg = ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh")
    inp = ImageGenerationInput(prompt="x", model="2029488621429989377")

    with pytest.raises(ValueError, match="参考图片"):
        await adapter.generate(cfg=cfg, inp=inp, timeout_s=60.0)
