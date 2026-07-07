from __future__ import annotations

from typing import Any

import pytest

from app.core.contracts.provider import ProviderConfig
from app.core.contracts.video_generation import VideoGenerationInput
from app.core.integrations.runninghub.enterprise import video as ent_video
from app.core.integrations.runninghub.enterprise import client as ent_client
from app.core.integrations.runninghub import client as rh_client


@pytest.mark.asyncio
async def test_create_video_dispatches_to_correct_endpoint(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_upload(base_url, api_key, mime, bytes_data, timeout_s=120.0):
        return f"https://rh/dl/{mime.replace('/', '_')}"

    async def fake_submit(base_url, api_key, endpoint_path, request_body, *, timeout_s=60.0):
        captured["endpoint"] = endpoint_path
        captured["body"] = request_body
        return "ent-task-1"

    monkeypatch.setattr(rh_client, "upload_media", fake_upload)
    monkeypatch.setattr(ent_client, "submit_enterprise_task", fake_submit)

    adapter = ent_video.RunningHubEnterpriseVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub-enterprise", api_key="k", base_url="https://rh")
    inp = VideoGenerationInput(
        prompt="run", ratio="16:9", seconds=5, model="wan-2.7/image-to-video",
        first_frame_base64="data:image/png;base64,iVBORw0KGgo=",
    )
    task_id = await adapter.create_video(cfg=cfg, input_=inp, timeout_s=60.0)

    assert task_id == "ent-task-1"
    assert captured["endpoint"] == "/openapi/v2/alibaba/wan-2.7/image-to-video"
    assert captured["body"]["firstImageUrl"].startswith("https://rh/dl/")


@pytest.mark.asyncio
async def test_get_video_returns_query_response(monkeypatch) -> None:
    async def fake_query(base_url, api_key, task_id, timeout_s=60.0):
        return {"status": "PROCESSING", "taskId": task_id}

    monkeypatch.setattr(rh_client, "query_task", fake_query)

    adapter = ent_video.RunningHubEnterpriseVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub-enterprise", api_key="k", base_url="https://rh")
    data = await adapter.get_video(cfg=cfg, video_id="t1", timeout_s=60.0)
    assert data == {"status": "PROCESSING", "taskId": "t1"}


@pytest.mark.asyncio
async def test_create_video_unknown_model_raises(monkeypatch) -> None:
    adapter = ent_video.RunningHubEnterpriseVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub-enterprise", api_key="k", base_url="https://rh")
    inp = VideoGenerationInput(
        prompt="x", ratio="16:9", model="unknown/model",
        first_frame_base64="data:image/png;base64,iVBORw0KGgo=",
    )
    with pytest.raises(ValueError, match="Unknown RunningHub enterprise video model"):
        await adapter.create_video(cfg=cfg, input_=inp, timeout_s=60.0)


@pytest.mark.asyncio
async def test_create_video_singleimage_uploads_one_url(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_upload(base_url, api_key, mime, bytes_data, timeout_s=120.0):
        return "https://rh/dl/single.png"

    async def fake_submit(base_url, api_key, endpoint_path, request_body, *, timeout_s=60.0):
        captured["body"] = request_body
        return "ent-task-2"

    monkeypatch.setattr(rh_client, "upload_media", fake_upload)
    monkeypatch.setattr(ent_client, "submit_enterprise_task", fake_submit)

    adapter = ent_video.RunningHubEnterpriseVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub-enterprise", api_key="k", base_url="https://rh")
    inp = VideoGenerationInput(
        prompt="x", ratio="16:9", seconds=5, model="ltx-2.3/image-to-video", resolution="480P",
        first_frame_base64="data:image/png;base64,iVBORw0KGgo=",
    )
    await adapter.create_video(cfg=cfg, input_=inp, timeout_s=60.0)
    assert captured["body"]["imageUrl"] == "https://rh/dl/single.png"


@pytest.mark.asyncio
async def test_create_video_imagereference_9_no_padding(monkeypatch) -> None:
    """imageReference:9 sends actual count (3), not padded to 9."""
    captured: dict[str, Any] = {}

    async def fake_upload(base_url, api_key, mime, bytes_data, timeout_s=120.0):
        return f"https://rh/dl/{len(bytes_data)}.png"

    async def fake_submit(base_url, api_key, endpoint_path, request_body, *, timeout_s=60.0):
        captured["body"] = request_body
        return "ent-task-3"

    monkeypatch.setattr(rh_client, "upload_media", fake_upload)
    monkeypatch.setattr(ent_client, "submit_enterprise_task", fake_submit)

    adapter = ent_video.RunningHubEnterpriseVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub-enterprise", api_key="k", base_url="https://rh")
    inp = VideoGenerationInput(
        prompt="x", ratio="16:9", seconds=5, model="wan-2.7/reference-to-video",
        reference_frames_base64=[
            "data:image/png;base64,iVBORw0KGgo=",
            "data:image/png;base64,iVBORw0KGgo=",
            "data:image/png;base64,iVBORw0KGgo=",
        ],
    )
    await adapter.create_video(cfg=cfg, input_=inp, timeout_s=60.0)
    assert len(captured["body"]["imageUrls"]) == 3


@pytest.mark.asyncio
async def test_create_video_imagereference_3_uses_first_last_key(monkeypatch) -> None:
    """imageReference:3 uses first/last/key_frame_base64 (not reference_frames_base64)."""
    captured: dict[str, Any] = {}

    async def fake_upload(base_url, api_key, mime, bytes_data, timeout_s=120.0):
        return f"https://rh/dl/{mime.replace('/', '_')}"

    async def fake_submit(base_url, api_key, endpoint_path, request_body, *, timeout_s=60.0):
        captured["body"] = request_body
        return "ent-task-4"

    monkeypatch.setattr(rh_client, "upload_media", fake_upload)
    monkeypatch.setattr(ent_client, "submit_enterprise_task", fake_submit)

    adapter = ent_video.RunningHubEnterpriseVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub-enterprise", api_key="k", base_url="https://rh")
    inp = VideoGenerationInput(
        prompt="x", ratio="16:9", seconds=8, model="rhart-video-v3.1-fast/image-to-video",
        first_frame_base64="data:image/png;base64,iVBORw0KGgo=",
        last_frame_base64="data:image/png;base64,iVBORw0KGgo=",
        key_frame_base64="data:image/png;base64,iVBORw0KGgo=",
    )
    await adapter.create_video(cfg=cfg, input_=inp, timeout_s=60.0)
    assert len(captured["body"]["imageUrls"]) == 3
