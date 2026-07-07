"""RunningHub 企业版 HTTP 底层：submit / query / upload 复用个人版 client。"""

from __future__ import annotations

import json
from typing import Any


async def submit_enterprise_task(
    base_url: str,
    api_key: str,
    endpoint_path: str,
    request_body: dict[str, Any],
    *,
    timeout_s: float = 60.0,
) -> str:
    """POST {base_url}{endpoint_path} with JSON body. Returns RunningHub task id.

    Raises:
        httpx.HTTPStatusError: 非 2xx 响应
        RuntimeError: 响应缺少 taskId
    """
    import httpx

    url = f"{base_url.rstrip('/')}{endpoint_path}"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        r = await client.post(url, headers=headers, json=request_body)
        r.raise_for_status()
        data = r.json()

    task_id = str(data.get("taskId") or "")
    if not task_id:
        raise RuntimeError(f"RunningHub 企业版提交任务失败: {json.dumps(data, ensure_ascii=False)}")
    return task_id
