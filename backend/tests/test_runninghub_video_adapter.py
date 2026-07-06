from __future__ import annotations

from typing import Any

import pytest

from app.core.contracts.provider import ProviderConfig
from app.core.contracts.video_generation import VideoGenerationInput
from app.core.integrations.runninghub import video as rh_video
from app.core.integrations.runninghub import client as rh_client


@pytest.mark.asyncio
async def test_create_video_ai_app_endpoint(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_upload(base_url, api_key, mime, bytes_data, timeout_s=120.0):
        return f"https://rh/dl/{mime.replace('/', '_')}"

    async def fake_submit_ai(base_url, api_key, workflow_id, node_info_list, timeout_s=60.0):
        captured["endpoint"] = "ai_app"
        captured["workflow_id"] = workflow_id
        return "task-wan22"

    async def fake_submit_wf(base_url, api_key, workflow_id, node_info_list, timeout_s=60.0):
        captured["endpoint"] = "workflow"
        return "task-4frame"

    monkeypatch.setattr(rh_client, "upload_media", fake_upload)
    monkeypatch.setattr(rh_client, "submit_ai_app_task", fake_submit_ai)
    monkeypatch.setattr(rh_client, "submit_workflow_task", fake_submit_wf)

    adapter = rh_video.RunningHubVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh")
    inp = VideoGenerationInput(
        prompt="run", ratio="16:9", seconds=5, model="1956699246381469698",
        first_frame_base64="data:image/png;base64,iVBORw0KGgo=",
    )

    task_id = await adapter.create_video(cfg=cfg, input_=inp, timeout_s=60.0)

    assert task_id == "task-wan22"
    assert captured["endpoint"] == "ai_app"
    assert captured["workflow_id"] == "1956699246381469698"


@pytest.mark.asyncio
async def test_create_video_workflow_endpoint_for_4frame(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_upload(base_url, api_key, mime, bytes_data, timeout_s=120.0):
        return "https://rh/dl/img.png"

    async def fake_submit_ai(base_url, api_key, workflow_id, node_info_list, timeout_s=60.0):
        captured["endpoint"] = "ai_app"
        return "task-ai"

    async def fake_submit_wf(base_url, api_key, workflow_id, node_info_list, timeout_s=60.0):
        captured["endpoint"] = "workflow"
        captured["workflow_id"] = workflow_id
        captured["node_count"] = len(node_info_list)
        return "task-4frame"

    monkeypatch.setattr(rh_client, "upload_media", fake_upload)
    monkeypatch.setattr(rh_client, "submit_ai_app_task", fake_submit_ai)
    monkeypatch.setattr(rh_client, "submit_workflow_task", fake_submit_wf)

    adapter = rh_video.RunningHubVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh")
    inp = VideoGenerationInput(
        prompt="flow", ratio="16:9", seconds=5, model="2054820963426021378",
        first_frame_base64="data:image/png;base64,iVBORw0KGgo=",
    )

    task_id = await adapter.create_video(cfg=cfg, input_=inp, timeout_s=60.0)

    assert task_id == "task-4frame"
    assert captured["endpoint"] == "workflow"
    assert captured["node_count"] == 5


@pytest.mark.asyncio
async def test_create_video_pads_4frame_when_only_one_frame(monkeypatch) -> None:
    captured: dict[str, Any] = {}

    async def fake_upload(base_url, api_key, mime, bytes_data, timeout_s=120.0):
        return "https://rh/dl/single.png"

    async def fake_submit_wf(base_url, api_key, workflow_id, node_info_list, timeout_s=60.0):
        captured["nodes"] = node_info_list
        return "task-4frame"

    async def fake_submit_ai(base_url, api_key, workflow_id, node_info_list, timeout_s=60.0):
        return "task-ai"

    monkeypatch.setattr(rh_client, "upload_media", fake_upload)
    monkeypatch.setattr(rh_client, "submit_workflow_task", fake_submit_wf)
    monkeypatch.setattr(rh_client, "submit_ai_app_task", fake_submit_ai)

    adapter = rh_video.RunningHubVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh")
    inp = VideoGenerationInput(
        prompt="flow", ratio="16:9", seconds=5, model="2054820963426021378",
        first_frame_base64="data:image/png;base64,iVBORw0KGgo=",
    )

    await adapter.create_video(cfg=cfg, input_=inp, timeout_s=60.0)

    by_node = {n["nodeId"]: n for n in captured["nodes"]}
    assert by_node["1361"]["fieldValue"] == "https://rh/dl/single.png"
    assert by_node["1364"]["fieldValue"] == "https://rh/dl/single.png"


@pytest.mark.asyncio
async def test_create_video_without_any_frame_raises(monkeypatch) -> None:
    adapter = rh_video.RunningHubVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh")
    inp = VideoGenerationInput(prompt="only prompt", ratio="16:9", model="1956699246381469698")

    with pytest.raises(ValueError, match="参考图"):
        await adapter.create_video(cfg=cfg, input_=inp, timeout_s=60.0)


@pytest.mark.asyncio
async def test_get_video_returns_query_response(monkeypatch) -> None:
    async def fake_query(base_url, api_key, task_id, timeout_s=60.0):
        return {"status": "PROCESSING", "taskId": task_id}

    monkeypatch.setattr(rh_client, "query_task", fake_query)

    adapter = rh_video.RunningHubVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh")
    data = await adapter.get_video(cfg=cfg, video_id="t1", timeout_s=60.0)

    assert data == {"status": "PROCESSING", "taskId": "t1"}


@pytest.mark.asyncio
async def test_create_video_unknown_workflow_raises(monkeypatch) -> None:
    adapter = rh_video.RunningHubVideoApiAdapter()
    cfg = ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh")
    inp = VideoGenerationInput(
        prompt="x", ratio="16:9", model="unknown-wf",
        first_frame_base64="data:image/png;base64,iVBORw0KGgo=",
    )

    with pytest.raises(ValueError, match="Unknown RunningHub video workflow"):
        await adapter.create_video(cfg=cfg, input_=inp, timeout_s=60.0)
