from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.core.integrations.grsai import client as grsai_client


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_submit_grsai_task_posts_json_and_returns_task_id() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"id": "6-f671fc51-d5d7-4eff-a1c7-26e612fe08ab", "status": "running"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        task_id = await grsai_client.submit_grsai_task(
            "https://grsai.dakka.com.cn",
            "sk-test-key",
            {"model": "nano-banana-2", "prompt": "hi", "replyType": "async"},
        )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    assert task_id == "6-f671fc51-d5d7-4eff-a1c7-26e612fe08ab"
    assert captured["url"] == "https://grsai.dakka.com.cn/v1/api/generate"
    assert captured["headers"]["authorization"] == "Bearer sk-test-key"
    assert captured["headers"]["content-type"] == "application/json"
    assert captured["body"]["model"] == "nano-banana-2"
    assert captured["body"]["replyType"] == "async"


@pytest.mark.asyncio
async def test_submit_grsai_task_raises_without_task_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 1, "msg": "bad"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        with pytest.raises(RuntimeError, match="Grsai 提交任务失败"):
            await grsai_client.submit_grsai_task(
                "https://grsai.dakka.com.cn", "k", {"model": "nano-banana", "prompt": "x"}
            )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]


@pytest.mark.asyncio
async def test_submit_grsai_task_raises_on_non_2xx() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"code": 401, "msg": "unauthorized"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        with pytest.raises(httpx.HTTPStatusError):
            await grsai_client.submit_grsai_task(
                "https://grsai.dakka.com.cn", "k", {"model": "nano-banana", "prompt": "x"}
            )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]


@pytest.mark.asyncio
async def test_query_grsai_result_gets_with_id_query_param() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "id": "14-5f3cf761-a4bb-486a-8016-77f490998f80",
                "status": "succeeded",
                "progress": 100,
                "results": [{"url": "https://file1.aitohumanize.com/file/abc.png"}],
            },
        )

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        data = await grsai_client.query_grsai_result(
            "https://grsai.dakka.com.cn", "sk-test-key", "14-5f3cf761"
        )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    assert data["status"] == "succeeded"
    assert data["results"][0]["url"] == "https://file1.aitohumanize.com/file/abc.png"
    assert "id=14-5f3cf761" in captured["url"]
    assert captured["url"].startswith("https://grsai.dakka.com.cn/v1/api/result")
    assert captured["headers"]["authorization"] == "Bearer sk-test-key"
