"""Grsai HTTP 底层：submit / query。"""

from __future__ import annotations

import json
from typing import Any


async def submit_grsai_task(
    base_url: str,
    api_key: str,
    request_body: dict[str, Any],
    *,
    timeout_s: float = 60.0,
) -> str:
    """POST {base_url}/v1/api/generate with JSON body. Returns Grsai task id.

    Raises:
        httpx.HTTPStatusError: 非 2xx 响应
        RuntimeError: 响应缺少 id
    """
    import httpx

    url = f"{base_url.rstrip('/')}/v1/api/generate"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(url, headers=headers, json=request_body)
        r.raise_for_status()
        data = r.json()

    task_id = str(data.get("id") or "")
    if not task_id:
        raise RuntimeError(f"Grsai 提交任务失败: {json.dumps(data, ensure_ascii=False)}")
    return task_id


async def query_grsai_result(
    base_url: str,
    api_key: str,
    task_id: str,
    *,
    timeout_s: float = 60.0,
) -> dict[str, Any]:
    """GET {base_url}/v1/api/result?id={task_id}. Returns raw response dict.

    Raises:
        httpx.HTTPStatusError: 非 2xx 响应
    """
    import httpx

    url = f"{base_url.rstrip('/')}/v1/api/result"
    headers = {"Authorization": f"Bearer {api_key}"}
    params = {"id": task_id}
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        return r.json()
