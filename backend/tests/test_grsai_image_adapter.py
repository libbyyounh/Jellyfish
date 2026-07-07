from __future__ import annotations

from typing import Any

import pytest

from app.core.contracts.image_generation import ImageGenerationInput, InputImageRef
from app.core.contracts.provider import ProviderConfig
from app.core.integrations.grsai import client as grsai_client
from app.core.integrations.grsai import images as grsai_images


@pytest.mark.asyncio
async def test_generate_submits_with_async_and_polls_until_succeeded(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_submit(base_url, api_key, request_body, *, timeout_s=60.0):
        captured["base_url"] = base_url
        captured["body"] = request_body
        return "6-f671fc51-d5d7-4eff-a1c7-26e612fe08ab"

    async def fake_query(base_url, api_key, task_id, *, timeout_s=60.0):
        return {
            "id": task_id,
            "status": "succeeded",
            "progress": 100,
            "results": [{"url": "https://file1.aitohumanize.com/file/abc.png"}],
        }

    monkeypatch.setattr(grsai_client, "submit_grsai_task", fake_submit)
    monkeypatch.setattr(grsai_client, "query_grsai_result", fake_query)

    adapter = grsai_images.GrsaiImageApiAdapter()
    cfg = ProviderConfig(provider="grsai", api_key="sk-test", base_url="https://grsai.dakka.com.cn")
    inp = ImageGenerationInput(prompt="a border collie", model="nano-banana-2")
    result = await adapter.generate(cfg=cfg, inp=inp, timeout_s=60.0)

    assert result.provider == "grsai"
    assert result.provider_task_id == "6-f671fc51-d5d7-4eff-a1c7-26e612fe08ab"
    assert result.status == "succeeded"
    assert result.images[0].url == "https://file1.aitohumanize.com/file/abc.png"
    assert captured["body"]["replyType"] == "async"
    assert captured["body"]["model"] == "nano-banana-2"


@pytest.mark.asyncio
async def test_generate_sends_image_size_for_nano_banana_family(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_submit(base_url, api_key, request_body, *, timeout_s=60.0):
        captured["body"] = request_body
        return "task-1"

    async def fake_query(base_url, api_key, task_id, *, timeout_s=60.0):
        return {"id": task_id, "status": "succeeded", "results": [{"url": "https://x/a.png"}]}

    monkeypatch.setattr(grsai_client, "submit_grsai_task", fake_submit)
    monkeypatch.setattr(grsai_client, "query_grsai_result", fake_query)

    adapter = grsai_images.GrsaiImageApiAdapter()
    cfg = ProviderConfig(provider="grsai", api_key="k", base_url="https://grsai.dakka.com.cn")
    inp = ImageGenerationInput(prompt="x", model="nano-banana-pro", target_ratio="16:9")
    await adapter.generate(cfg=cfg, inp=inp, timeout_s=60.0)

    assert captured["body"]["imageSize"] == "1K"
    assert captured["body"]["aspectRatio"] == "16:9"


@pytest.mark.asyncio
async def test_generate_omits_image_size_for_gpt_image_2_family(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_submit(base_url, api_key, request_body, *, timeout_s=60.0):
        captured["body"] = request_body
        return "task-2"

    async def fake_query(base_url, api_key, task_id, *, timeout_s=60.0):
        return {"id": task_id, "status": "succeeded", "results": [{"url": "https://x/b.png"}]}

    monkeypatch.setattr(grsai_client, "submit_grsai_task", fake_submit)
    monkeypatch.setattr(grsai_client, "query_grsai_result", fake_query)

    adapter = grsai_images.GrsaiImageApiAdapter()
    cfg = ProviderConfig(provider="grsai", api_key="k", base_url="https://grsai.dakka.com.cn")
    inp = ImageGenerationInput(prompt="x", model="gpt-image-2")
    await adapter.generate(cfg=cfg, inp=inp, timeout_s=60.0)

    assert "imageSize" not in captured["body"]


@pytest.mark.asyncio
async def test_generate_raises_on_failed_status(monkeypatch) -> None:
    async def fake_submit(base_url, api_key, request_body, *, timeout_s=60.0):
        return "task-fail"

    async def fake_query(base_url, api_key, task_id, *, timeout_s=60.0):
        return {"id": task_id, "status": "failed", "error": "generate failed"}

    monkeypatch.setattr(grsai_client, "submit_grsai_task", fake_submit)
    monkeypatch.setattr(grsai_client, "query_grsai_result", fake_query)

    adapter = grsai_images.GrsaiImageApiAdapter()
    cfg = ProviderConfig(provider="grsai", api_key="k", base_url="https://grsai.dakka.com.cn")
    inp = ImageGenerationInput(prompt="x", model="nano-banana")
    with pytest.raises(RuntimeError, match="generate failed"):
        await adapter.generate(cfg=cfg, inp=inp, timeout_s=60.0)


@pytest.mark.asyncio
async def test_generate_raises_on_empty_results(monkeypatch) -> None:
    async def fake_submit(base_url, api_key, request_body, *, timeout_s=60.0):
        return "task-empty"

    async def fake_query(base_url, api_key, task_id, *, timeout_s=60.0):
        return {"id": task_id, "status": "succeeded", "results": []}

    monkeypatch.setattr(grsai_client, "submit_grsai_task", fake_submit)
    monkeypatch.setattr(grsai_client, "query_grsai_result", fake_query)

    adapter = grsai_images.GrsaiImageApiAdapter()
    cfg = ProviderConfig(provider="grsai", api_key="k", base_url="https://grsai.dakka.com.cn")
    inp = ImageGenerationInput(prompt="x", model="nano-banana")
    with pytest.raises(RuntimeError, match="no usable results"):
        await adapter.generate(cfg=cfg, inp=inp, timeout_s=60.0)


@pytest.mark.asyncio
async def test_generate_maps_images_to_string_list(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_submit(base_url, api_key, request_body, *, timeout_s=60.0):
        captured["body"] = request_body
        return "task-img"

    async def fake_query(base_url, api_key, task_id, *, timeout_s=60.0):
        return {"id": task_id, "status": "succeeded", "results": [{"url": "https://x/c.png"}]}

    monkeypatch.setattr(grsai_client, "submit_grsai_task", fake_submit)
    monkeypatch.setattr(grsai_client, "query_grsai_result", fake_query)

    adapter = grsai_images.GrsaiImageApiAdapter()
    cfg = ProviderConfig(provider="grsai", api_key="k", base_url="https://grsai.dakka.com.cn")
    inp = ImageGenerationInput(
        prompt="x",
        model="nano-banana",
        images=[
            InputImageRef(image_url="https://example.com/ref1.png"),
            InputImageRef(image_url="https://example.com/ref2.png"),
        ],
    )
    await adapter.generate(cfg=cfg, inp=inp, timeout_s=60.0)

    assert captured["body"]["images"] == [
        "https://example.com/ref1.png",
        "https://example.com/ref2.png",
    ]
