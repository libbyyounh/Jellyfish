"""RunningHub HTTP 底层：submit / query / upload / poll。"""

from __future__ import annotations

import asyncio
import json
import time
from typing import Any


async def _post_json(url: str, headers: dict[str, str], body: dict[str, Any], timeout_s: float) -> dict[str, Any]:
    import httpx

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(url, headers=headers, json=body)
        r.raise_for_status()
        return r.json()


async def submit_ai_app_task(
    base_url: str, api_key: str, workflow_id: str, node_info_list: list[dict[str, Any]], timeout_s: float = 60.0
) -> str:
    """POST /openapi/v2/run/ai-app/{workflow_id}，返回 task_id。"""
    url = f"{base_url.rstrip('/')}/openapi/v2/run/ai-app/{workflow_id}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "nodeInfoList": node_info_list,
        "instanceType": "default",
        "usePersonalQueue": "true",
    }
    data = await _post_json(url, headers, body, timeout_s)
    task_id = str(data.get("taskId") or "")
    if not task_id:
        raise RuntimeError(f"RunningHub 提交任务失败: {json.dumps(data, ensure_ascii=False)}")
    return task_id


async def submit_workflow_task(
    base_url: str, api_key: str, workflow_id: str, node_info_list: list[dict[str, Any]], timeout_s: float = 60.0
) -> str:
    """POST /openapi/v2/run/workflow/{workflow_id}（4帧LTX专用），返回 task_id。"""
    url = f"{base_url.rstrip('/')}/openapi/v2/run/workflow/{workflow_id}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "addMetadata": True,
        "nodeInfoList": node_info_list,
        "instanceType": "default",
        "usePersonalQueue": "true",
    }
    data = await _post_json(url, headers, body, timeout_s)
    task_id = str(data.get("taskId") or "")
    if not task_id:
        raise RuntimeError(f"RunningHub 提交任务失败: {json.dumps(data, ensure_ascii=False)}")
    return task_id


async def query_task(base_url: str, api_key: str, task_id: str, timeout_s: float = 60.0) -> dict[str, Any]:
    """POST /openapi/v2/query，返回原始响应。"""
    url = f"{base_url.rstrip('/')}/openapi/v2/query"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {"taskId": task_id}
    return await _post_json(url, headers, body, timeout_s)


async def upload_media(base_url: str, api_key: str, mime: str, bytes_data: bytes, timeout_s: float = 120.0) -> str:
    """POST /openapi/v2/media/upload/binary（multipart），返回 download_url。"""
    import httpx

    ext = "png"
    if "jpeg" in mime or "jpg" in mime:
        ext = "jpg"
    elif "webp" in mime:
        ext = "webp"
    elif "mp4" in mime:
        ext = "mp4"
    elif "mp3" in mime:
        ext = "mp3"

    boundary = f"----RHBoundary{int(time.time() * 1000):x}"
    header = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="upload_{int(time.time() * 1000)}.{ext}"\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode()
    footer = f"\r\n--{boundary}--\r\n".encode()
    payload = header + bytes_data + footer

    url = f"{base_url.rstrip('/')}/openapi/v2/media/upload/binary"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(url, headers=headers, content=payload)
        r.raise_for_status()
        data = r.json()

    if data.get("code") != 0 or not (data.get("data") or {}).get("download_url"):
        raise RuntimeError(f"RunningHub 上传素材失败: {json.dumps(data, ensure_ascii=False)}")
    return str(data["data"]["download_url"])


async def poll_until_done(
    base_url: str,
    api_key: str,
    task_id: str,
    interval: float = 5.0,
    timeout: float = 600.0,
) -> str:
    """轮询 query_task，SUCCESS 返回 results[0].url，FAILED/ERROR 抛错，超时抛 TimeoutError。"""
    deadline = time.monotonic() + timeout
    while True:
        data = await query_task(base_url, api_key, task_id)
        status = str(data.get("status") or "")
        if status == "SUCCESS":
            results = data.get("results") or []
            url = results[0].get("url") if results else None
            if not url:
                raise RuntimeError("RunningHub 任务完成但未返回结果 URL")
            return str(url)
        if status in ("FAILED", "ERROR"):
            raise RuntimeError(
                f"RunningHub 任务失败: {data.get('errorMessage') or data.get('errorCode') or status}"
            )
        if time.monotonic() >= deadline:
            raise TimeoutError(f"RunningHub 任务轮询超时: task_id={task_id}")
        await asyncio.sleep(interval)
