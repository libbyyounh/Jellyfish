from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.core.integrations.runninghub.enterprise import client as ent_client


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_submit_enterprise_task_posts_json_and_returns_task_id() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"taskId": "ent-task-1"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        task_id = await ent_client.submit_enterprise_task(
            "https://www.runninghub.cn",
            "key-ent",
            "/openapi/v2/alibaba/wan-2.7/image-to-video",
            {"prompt": "hi", "firstImageUrl": "https://rh/img.png"},
        )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    assert task_id == "ent-task-1"
    assert captured["url"] == "https://www.runninghub.cn/openapi/v2/alibaba/wan-2.7/image-to-video"
    assert captured["headers"]["authorization"] == "Bearer key-ent"
    assert captured["headers"]["content-type"] == "application/json"
    assert captured["body"]["prompt"] == "hi"
    assert captured["body"]["firstImageUrl"] == "https://rh/img.png"


@pytest.mark.asyncio
async def test_submit_enterprise_task_raises_without_task_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 1, "msg": "bad"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        with pytest.raises(RuntimeError, match="RunningHub 企业版提交任务失败"):
            await ent_client.submit_enterprise_task(
                "https://rh", "k", "/openapi/v2/alibaba/wan-2.7/image-to-video", {"prompt": "x"}
            )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]


@pytest.mark.asyncio
async def test_submit_enterprise_task_raises_on_non_2xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": 401, "msg": "unauthorized"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await ent_client.submit_enterprise_task(
                "https://rh", "k", "/openapi/v2/alibaba/wan-2.7/image-to-video", {"prompt": "x"}
            )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]
