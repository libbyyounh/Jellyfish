from __future__ import annotations

import asyncio
import json
from typing import Any

import httpx
import pytest

from app.core.integrations.runninghub import client as rh_client


def _mock_transport(handler):
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_submit_ai_app_task_returns_task_id() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"taskId": "task-123"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        task_id = await rh_client.submit_ai_app_task(
            "https://www.runninghub.cn", "key-abc", "wf-1", [{"nodeId": "1", "fieldName": "text", "fieldValue": "hi"}]
        )
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    assert task_id == "task-123"
    assert captured["url"] == "https://www.runninghub.cn/openapi/v2/run/ai-app/wf-1"
    assert captured["headers"]["authorization"] == "Bearer key-abc"
    assert captured["body"]["nodeInfoList"] == [{"nodeId": "1", "fieldName": "text", "fieldValue": "hi"}]
    assert captured["body"]["instanceType"] == "default"
    assert captured["body"]["usePersonalQueue"] == "true"


@pytest.mark.asyncio
async def test_submit_ai_app_task_raises_without_task_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 1, "msg": "bad"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        with pytest.raises(RuntimeError, match="RunningHub 提交任务失败"):
            await rh_client.submit_ai_app_task("https://rh", "k", "wf", [])
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]


@pytest.mark.asyncio
async def test_submit_workflow_task_uses_workflow_endpoint() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"taskId": "task-wf"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        task_id = await rh_client.submit_workflow_task("https://rh", "k", "wf-4frame", [{"nodeId": "1"}])
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    assert task_id == "task-wf"
    assert captured["url"] == "https://rh/openapi/v2/run/workflow/wf-4frame"
    assert captured["body"]["addMetadata"] is True


@pytest.mark.asyncio
async def test_query_task_returns_response_dict() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"status": "PROCESSING", "taskId": "t1"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        data = await rh_client.query_task("https://rh", "k", "t1")
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    assert data == {"status": "PROCESSING", "taskId": "t1"}
    assert captured["body"] == {"taskId": "t1"}


@pytest.mark.asyncio
async def test_upload_media_returns_download_url() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "multipart/form-data" in request.headers.get("content-type", "")
        assert request.headers["authorization"] == "Bearer k"
        return httpx.Response(200, json={"code": 0, "data": {"download_url": "https://rh/dl/abc.png"}})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        url = await rh_client.upload_media("https://rh", "k", "image/png", b"\x89PNG\r\n\x1a\n")
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    assert url == "https://rh/dl/abc.png"


@pytest.mark.asyncio
async def test_upload_media_raises_on_bad_code() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"code": 1, "msg": "too large"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        with pytest.raises(RuntimeError, match="RunningHub 上传素材失败"):
            await rh_client.upload_media("https://rh", "k", "image/png", b"data")
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]


@pytest.mark.asyncio
async def test_poll_until_done_returns_url_on_success() -> None:
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return httpx.Response(200, json={"status": "PROCESSING"})
        return httpx.Response(200, json={"status": "SUCCESS", "results": [{"url": "https://rh/out.png"}]})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        url = await rh_client.poll_until_done("https://rh", "k", "t1", interval=0.01, timeout=5.0)
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]

    assert url == "https://rh/out.png"
    assert call_count == 2


@pytest.mark.asyncio
async def test_poll_until_done_raises_on_failed() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "FAILED", "errorMessage": "boom"})

    transport = _mock_transport(handler)
    original = httpx.AsyncClient
    httpx.AsyncClient = lambda *a, **kw: original(*a, transport=transport, **kw)  # type: ignore[misc]
    try:
        with pytest.raises(RuntimeError, match="boom"):
            await rh_client.poll_until_done("https://rh", "k", "t1", interval=0.01, timeout=5.0)
    finally:
        httpx.AsyncClient = original  # type: ignore[misc]
