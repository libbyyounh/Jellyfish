# RunningHub 供应商接入 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 `runninghub` 第三方供应商，接入 RunningHub 个人消费版的异步工作流 API，提供 5 个图片模型 + 4 个视频模型。

**Architecture:** 在现有 provider/task adapter registry 体系上加一个 `runninghub` key。HTTP 适配器层封装 RunningHub 的 submit→poll→result 异步模式；图片 adapter 内部完成轮询（保持同步语义），视频 adapter 暴露 create+get 两阶段供 Task 层轮询。9 个 workflowId 的节点配置硬编码在 `node_configs.py`。启动时 DB bootstrap 自动 upsert provider 行 + 9 个 model 行。

**Tech Stack:** Python 3.x, FastAPI, SQLAlchemy (async), httpx, Pydantic, pytest

## Global Constraints

- `ProviderKey` Literal 扩展为 `Literal["openai", "volcengine", "runninghub"]`
- RunningHub base_url 默认 `https://www.runninghub.cn`
- 轮询间隔 5s，超时 600s（与参考 .ts 一致）
- API 认证：`Authorization: Bearer {api_key}`，仅用 `api_key`，不用 `api_secret`
- 不实现 text/TTS（RunningHub 不支持）
- 不改前端（UI 数据驱动）
- 所有新代码用 `from __future__ import annotations`
- 测试用 `httpx.MockTransport` 模拟 HTTP，不真打 RunningHub API
- 每个任务结束 commit，commit message 用 `feat:` / `test:` / `refactor:` 前缀

**Spec reference:** `docs/superpowers/specs/2026-07-06-runninghub-provider-design.md`

---

## File Structure

**新增文件：**
- `backend/app/core/integrations/runninghub/__init__.py` — 包初始化
- `backend/app/core/integrations/runninghub/client.py` — HTTP 底层（submit/query/upload/poll）
- `backend/app/core/integrations/runninghub/node_configs.py` — 9 个 workflowId 节点模板
- `backend/app/core/integrations/runninghub/images.py` — `RunningHubImageApiAdapter`
- `backend/app/core/integrations/runninghub/video.py` — `RunningHubVideoApiAdapter`
- `backend/app/core/integrations/runninghub/image_capabilities.py` — 图片能力声明
- `backend/app/core/integrations/runninghub/video_capabilities.py` — 视频能力声明
- `backend/app/services/llm/model_bootstrap.py` — DB 级 provider+model upsert
- `backend/tests/test_runninghub_client.py`
- `backend/tests/test_runninghub_node_configs.py`
- `backend/tests/test_runninghub_image_adapter.py`
- `backend/tests/test_runninghub_video_adapter.py`
- `backend/tests/test_runninghub_capabilities.py`
- `backend/tests/test_runninghub_model_bootstrap.py`
- `backend/tests/test_runninghub_model_identifier.py`

**修改文件：**
- `backend/app/core/contracts/provider.py` — ProviderKey 加 runninghub
- `backend/app/services/llm/provider_bootstrap.py` — 注册 runninghub ProviderSpec
- `backend/app/services/llm/provider_registry.py` — resolve 兜底加 runninghub
- `backend/app/core/integrations/image_capabilities.py` — resolve_* 加 runninghub 分支
- `backend/app/core/integrations/video_capabilities.py` — 同上
- `backend/app/core/tasks/image_generation_tasks.py` — 加 RunningHubImageGenerationTask
- `backend/app/core/tasks/video_generation_tasks.py` — 加 RunningHubVideoGenerationTask
- `backend/app/core/tasks/bootstrap.py` — TASK_ADAPTER_SPECS 加 2 行
- `backend/app/services/studio/image_task_runner.py` — workflow_id 透传
- `backend/app/services/film/generated_video.py` — 同上
- `backend/app/main.py` — lifespan 调用 DB bootstrap
- `backend/tests/test_task_registry.py` — 扩展 runninghub 用例

---

### Task 1: ProviderKey + ProviderSpec registration

**Files:**
- Modify: `backend/app/core/contracts/provider.py`
- Modify: `backend/app/services/llm/provider_bootstrap.py`
- Modify: `backend/app/services/llm/provider_registry.py`
- Test: `backend/tests/test_task_registry.py`（扩展）

**Interfaces:**
- Produces: `ProviderKey` Literal 包含 `"runninghub"`；`provider_registry.resolve_provider_key_from_name("runninghub")` 返回 `"runninghub"`；`list_registered_providers()` 包含 runninghub spec

- [ ] **Step 1: Write failing test**

在 `backend/tests/test_task_registry.py` 末尾追加：

```python
def test_resolve_provider_key_for_runninghub_aliases() -> None:
    from app.services.llm.provider_registry import resolve_provider_key_from_name
    from app.services.llm.provider_bootstrap import bootstrap_builtin_providers

    bootstrap_builtin_providers()
    assert resolve_provider_key_from_name("runninghub") == "runninghub"
    assert resolve_provider_key_from_name("RunningHub") == "runninghub"
    assert resolve_provider_key_from_name("rh") == "runninghub"
    assert resolve_provider_key_from_name("runninghub-personal") == "runninghub"


def test_runninghub_provider_spec_registered() -> None:
    from app.services.llm.provider_registry import get_provider_spec, list_registered_providers
    from app.services.llm.provider_bootstrap import bootstrap_builtin_providers
    from app.models.llm import ModelCategoryKey

    bootstrap_builtin_providers()
    spec = get_provider_spec("runninghub")
    assert spec.display_name == "RunningHub"
    assert ModelCategoryKey.image in spec.supported_categories
    assert ModelCategoryKey.video in spec.supported_categories
    assert ModelCategoryKey.text not in spec.supported_categories
    assert spec.default_base_url == "https://www.runninghub.cn"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_task_registry.py::test_resolve_provider_key_for_runninghub_aliases tests/test_task_registry.py::test_runninghub_provider_spec_registered -v
```
Expected: FAIL with "Unsupported provider name" / "Unsupported provider key"

- [ ] **Step 3: Modify `backend/app/core/contracts/provider.py`**

将第 8 行改为：

```python
ProviderKey = Literal["openai", "volcengine", "runninghub"]
```

- [ ] **Step 4: Modify `backend/app/services/llm/provider_bootstrap.py`**

在 `register_many` 的列表末尾（`aliyun_bailian` spec 之后）追加：

```python
            ProviderSpec(
                key="runninghub",
                display_name="RunningHub",
                aliases=("runninghub", "runninghub-personal", "rh"),
                supported_categories=(ModelCategoryKey.image, ModelCategoryKey.video),
                default_base_url="https://www.runninghub.cn",
            ),
```

- [ ] **Step 5: Modify `backend/app/services/llm/provider_registry.py`**

在 `resolve_provider_key_from_name` 函数中，`if "volc" in alias ...` 分支之后、`raise` 之前，加：

```python
    if "runninghub" in alias or alias == "rh":
        return "runninghub"
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_task_registry.py::test_resolve_provider_key_for_runninghub_aliases tests/test_task_registry.py::test_runninghub_provider_spec_registered -v
```
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/contracts/provider.py backend/app/services/llm/provider_bootstrap.py backend/app/services/llm/provider_registry.py backend/tests/test_task_registry.py
git commit -m "feat: register runninghub provider key and spec"
```

---

### Task 2: Capability modules

**Files:**
- Create: `backend/app/core/integrations/runninghub/__init__.py`
- Create: `backend/app/core/integrations/runninghub/image_capabilities.py`
- Create: `backend/app/core/integrations/runninghub/video_capabilities.py`
- Modify: `backend/app/core/integrations/image_capabilities.py`
- Modify: `backend/app/core/integrations/video_capabilities.py`
- Test: `backend/tests/test_runninghub_capabilities.py`

**Interfaces:**
- Consumes: `ProviderKey` from Task 1
- Produces: `resolve_runninghub_image_capability(model) -> ImageModelCapability`；`resolve_runninghub_video_capability(model) -> VideoModelCapability`；`image_capabilities.resolve_image_capability(provider="runninghub", ...)` 返回 runninghub 默认能力

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_runninghub_capabilities.py`:

```python
from __future__ import annotations

from app.core.integrations.runninghub.image_capabilities import resolve_runninghub_image_capability
from app.core.integrations.runninghub.video_capabilities import resolve_runninghub_video_capability
from app.core.integrations.image_capabilities import resolve_image_capability
from app.core.integrations.video_capabilities import resolve_video_capability


def test_runninghub_image_capability_defaults() -> None:
    cap = resolve_runninghub_image_capability(None)
    assert cap.supports_seed is False
    assert cap.supports_watermark is False
    assert cap.allowed_sizes is None


def test_runninghub_video_capability_defaults() -> None:
    cap = resolve_runninghub_video_capability(None)
    assert cap.supports_seed is False
    assert cap.supports_watermark is False
    assert cap.allowed_ratios == {"16:9", "9:16"}
    assert cap.min_seconds == 5
    assert cap.max_seconds == 10


def test_resolve_image_capability_dispatches_to_runninghub() -> None:
    cap = resolve_image_capability(provider="runninghub", model=None)
    assert cap.supports_seed is False


def test_resolve_video_capability_dispatches_to_runninghub() -> None:
    cap = resolve_video_capability(provider="runninghub", model=None)
    assert cap.allowed_ratios == {"16:9", "9:16"}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_runninghub_capabilities.py -v
```
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Create `backend/app/core/integrations/runninghub/__init__.py`**

```python
"""RunningHub 个人消费版集成：异步工作流 API 适配。"""
```

- [ ] **Step 4: Create `backend/app/core/integrations/runninghub/image_capabilities.py`**

```python
"""RunningHub 图片能力声明。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.integrations.image_capabilities import ImageModelCapability

if TYPE_CHECKING:
    from app.core.contracts.image_generation import ImageGenerationInput

_RUNNINGHUB_DEFAULT = ImageModelCapability(
    supports_seed=False,
    supports_watermark=False,
    allowed_sizes=None,
    supported_ratios={"16:9", "9:16", "1:1", "4:3", "3:4", "3:2", "2:3"},
)

_RUNNINGHUB_MODEL_OVERRIDES: dict[str, ImageModelCapability] = {}


def register_runninghub_image_capability(*, model_prefix: str, capability: ImageModelCapability) -> None:
    prefix = model_prefix.strip().lower()
    if not prefix:
        raise ValueError("model_prefix must not be empty")
    _RUNNINGHUB_MODEL_OVERRIDES[prefix] = capability


def clear_runninghub_image_capability_overrides() -> None:
    _RUNNINGHUB_MODEL_OVERRIDES.clear()


def _pick_override(model: str | None) -> ImageModelCapability | None:
    if not model:
        return None
    value = model.strip().lower()
    if not value:
        return None
    for prefix, cap in sorted(_RUNNINGHUB_MODEL_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True):
        if value.startswith(prefix):
            return cap
    return None


def resolve_runninghub_image_capability(model: str | None) -> ImageModelCapability:
    return _pick_override(model) or _RUNNINGHUB_DEFAULT


def validate_runninghub_image_options(input_: ImageGenerationInput) -> None:
    from app.core.integrations.image_capabilities import validate_image_options

    assert isinstance(input_, ImageGenerationInput)
    validate_image_options(provider="runninghub", model=input_.model, input_=input_)
```

- [ ] **Step 5: Create `backend/app/core/integrations/runninghub/video_capabilities.py`**

```python
"""RunningHub 视频能力声明。"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.integrations.video_capabilities import VideoModelCapability

if TYPE_CHECKING:
    from app.core.contracts.video_generation import VideoGenerationInput

_RUNNINGHUB_DEFAULT = VideoModelCapability(
    supports_seed=False,
    supports_watermark=False,
    allowed_ratios={"16:9", "9:16"},
    default_ratio="16:9",
    min_seconds=5,
    max_seconds=10,
)

_RUNNINGHUB_MODEL_OVERRIDES: dict[str, VideoModelCapability] = {}


def register_runninghub_video_capability(*, model_prefix: str, capability: VideoModelCapability) -> None:
    prefix = model_prefix.strip().lower()
    if not prefix:
        raise ValueError("model_prefix must not be empty")
    _RUNNINGHUB_MODEL_OVERRIDES[prefix] = capability


def clear_runninghub_video_capability_overrides() -> None:
    _RUNNINGHUB_MODEL_OVERRIDES.clear()


def _pick_override(model: str | None) -> VideoModelCapability | None:
    if not model:
        return None
    value = model.strip().lower()
    if not value:
        return None
    for prefix, cap in sorted(_RUNNINGHUB_MODEL_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True):
        if value.startswith(prefix):
            return cap
    return None


def resolve_runninghub_video_capability(model: str | None) -> VideoModelCapability:
    return _pick_override(model) or _RUNNINGHUB_DEFAULT


def validate_runninghub_video_options(input_: VideoGenerationInput) -> None:
    from app.core.integrations.video_capabilities import validate_video_options

    assert isinstance(input_, VideoGenerationInput)
    validate_video_options(provider="runninghub", model=input_.model, input_=input_)
```

- [ ] **Step 6: Modify `backend/app/core/integrations/image_capabilities.py`**

在 `register_image_model_capability` 函数中，`if provider == "openai":` 分支之后加：

```python
    if provider == "runninghub":
        from app.core.integrations.runninghub.image_capabilities import register_runninghub_image_capability

        register_runninghub_image_capability(model_prefix=model_prefix, capability=capability)
        return
```

在 `clear_image_model_capability_overrides` 函数中，`if provider is None:` 分支加：

```python
        from app.core.integrations.runninghub.image_capabilities import clear_runninghub_image_capability_overrides
        clear_runninghub_image_capability_overrides()
```

并在 `if provider == "openai":` 之后加：

```python
    if provider == "runninghub":
        from app.core.integrations.runninghub.image_capabilities import clear_runninghub_image_capability_overrides
        clear_runninghub_image_capability_overrides()
        return
```

在 `resolve_image_capability` 函数中，`if provider == "openai":` 分支之后加：

```python
    if provider == "runninghub":
        from app.core.integrations.runninghub.image_capabilities import resolve_runninghub_image_capability

        return resolve_runninghub_image_capability(model)
```

- [ ] **Step 7: Modify `backend/app/core/integrations/video_capabilities.py`**

在 `register_video_model_capability`、`clear_video_model_capability_overrides`、`resolve_video_capability` 三个函数中，参照 Task 2 Step 6 的 image_capabilities 改法，在 openai 分支之后加 runninghub 分支，调用对应的 `register_runninghub_video_capability` / `clear_runninghub_video_capability_overrides` / `resolve_runninghub_video_capability`。

- [ ] **Step 8: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_runninghub_capabilities.py -v
```
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add backend/app/core/integrations/runninghub/__init__.py backend/app/core/integrations/runninghub/image_capabilities.py backend/app/core/integrations/runninghub/video_capabilities.py backend/app/core/integrations/image_capabilities.py backend/app/core/integrations/video_capabilities.py backend/tests/test_runninghub_capabilities.py
git commit -m "feat: add runninghub capability resolvers"
```

---

### Task 3: HTTP client

**Files:**
- Create: `backend/app/core/integrations/runninghub/client.py`
- Test: `backend/tests/test_runninghub_client.py`

**Interfaces:**
- Produces: `submit_ai_app_task(base_url, api_key, workflow_id, node_info_list) -> str`；`submit_workflow_task(...) -> str`；`query_task(base_url, api_key, task_id) -> dict`；`upload_media(base_url, api_key, mime, bytes_data) -> str`；`poll_until_done(base_url, api_key, task_id, interval, timeout) -> str`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_runninghub_client.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_runninghub_client.py -v
```
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Create `backend/app/core/integrations/runninghub/client.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_runninghub_client.py -v
```
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/integrations/runninghub/client.py backend/tests/test_runninghub_client.py
git commit -m "feat: add runninghub http client"
```

---

### Task 4: Node configs

**Files:**
- Create: `backend/app/core/integrations/runninghub/node_configs.py`
- Test: `backend/tests/test_runninghub_node_configs.py`

**Interfaces:**
- Produces: `IMAGE_NODE_CONFIGS: dict[str, ImageNodeConfig]`；`VIDEO_NODE_CONFIGS: dict[str, VideoNodeConfig]`；`ImageNodeConfig`/`VideoNodeConfig` dataclass（含 `endpoint: str`、`build_nodes: Callable`、`requires_image: bool` / `image_count: int`）

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_runninghub_node_configs.py`:

```python
from __future__ import annotations

from app.core.contracts.image_generation import ImageGenerationInput
from app.core.contracts.video_generation import VideoGenerationInput
from app.core.integrations.runninghub.node_configs import (
    IMAGE_NODE_CONFIGS,
    VIDEO_NODE_CONFIGS,
    ImageNodeConfig,
    VideoNodeConfig,
)


def test_image_node_configs_cover_5_workflows() -> None:
    expected = {
        "2052744677727715329",
        "2003681895185563650",
        "1970396677775499266",
        "2029488621429989377",
        "2058719340626796546",
    }
    assert set(IMAGE_NODE_CONFIGS.keys()) == expected


def test_video_node_configs_cover_4_workflows() -> None:
    expected = {
        "1956699246381469698",
        "2029759632314474498",
        "2055155307592077313",
        "2054820963426021378",
    }
    assert set(VIDEO_NODE_CONFIGS.keys()) == expected


def test_duanju_image_nodes_have_width_height_and_prompt() -> None:
    cfg = IMAGE_NODE_CONFIGS["2052744677727715329"]
    inp = ImageGenerationInput(prompt="a cat", target_ratio="1:1")
    nodes = cfg.build_nodes(inp, None)
    by_node = {n["nodeId"]: n for n in nodes}
    assert by_node["49"]["fieldName"] == "text"
    assert by_node["49"]["fieldValue"] == "a cat"
    assert by_node["60"]["fieldName"] == "value"
    assert by_node["61"]["fieldName"] == "value"


def test_qwen_image_nodes_include_lora_params() -> None:
    cfg = IMAGE_NODE_CONFIGS["1970396677775499266"]
    inp = ImageGenerationInput(prompt="hero", target_ratio="16:9")
    nodes = cfg.build_nodes(inp, None)
    node_ids = {n["nodeId"] for n in nodes}
    assert {"925", "926", "927", "928", "929"}.issubset(node_ids)
    assert {"931", "932", "887", "860", "938"}.issubset(node_ids)


def test_qwen_edit_nodes_require_image_url() -> None:
    cfg = IMAGE_NODE_CONFIGS["2029488621429989377"]
    assert cfg.requires_image is True
    inp = ImageGenerationInput(prompt="edit this")
    nodes = cfg.build_nodes(inp, "https://rh/img.png")
    by_node = {n["nodeId"]: n for n in nodes}
    assert by_node["41"]["fieldValue"] == "https://rh/img.png"
    assert by_node["68"]["fieldValue"] == "edit this"


def test_wan22_video_nodes_have_image_prompt_duration_size() -> None:
    cfg = VIDEO_NODE_CONFIGS["1956699246381469698"]
    assert cfg.endpoint == "ai_app"
    assert cfg.image_count == 1
    inp = VideoGenerationInput(prompt="run", ratio="16:9", seconds=5)
    nodes = cfg.build_nodes(inp, "https://rh/img.png")
    by_node = {n["nodeId"]: n for n in nodes}
    assert by_node["790"]["fieldValue"] == "https://rh/img.png"
    assert by_node["809"]["fieldValue"] == "run"
    assert by_node["789"]["fieldValue"] == "5"
    assert by_node["791"]["fieldValue"] in ("848", "480")


def test_ltx23_standard_video_nodes_use_frames() -> None:
    cfg = VIDEO_NODE_CONFIGS["2029759632314474498"]
    inp = VideoGenerationInput(prompt="dance", ratio="16:9", seconds=5)
    nodes = cfg.build_nodes(inp, "https://rh/img.png")
    by_node = {n["nodeId"]: n for n in nodes}
    assert by_node["185"]["fieldValue"] == "120"
    assert by_node["224"]["fieldValue"] == "dance"


def test_ltx23_fourframe_uses_workflow_endpoint_and_4_images() -> None:
    cfg = VIDEO_NODE_CONFIGS["2054820963426021378"]
    assert cfg.endpoint == "workflow"
    assert cfg.image_count == 4
    inp = VideoGenerationInput(prompt="flow", ratio="16:9", seconds=5)
    urls = ["https://rh/a.png", "https://rh/b.png", "https://rh/c.png", "https://rh/d.png"]
    nodes = cfg.build_nodes(inp, urls)
    by_node = {n["nodeId"]: n for n in nodes}
    assert by_node["1361"]["fieldValue"] == "https://rh/a.png"
    assert by_node["1364"]["fieldValue"] == "https://rh/d.png"
    assert by_node["1473"]["fieldValue"] == "flow"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_runninghub_node_configs.py -v
```
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Create `backend/app/core/integrations/runninghub/node_configs.py`**

```python
"""RunningHub 9 个 workflowId 的 nodeInfoList 模板，硬编码（迁移自 toonflow .ts）。"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Callable, Literal

from app.core.contracts.image_generation import ImageGenerationInput
from app.core.contracts.video_generation import VideoGenerationInput


@dataclass(frozen=True, slots=True)
class ImageNodeConfig:
    endpoint: Literal["ai_app", "workflow"]
    build_nodes: Callable[[ImageGenerationInput, str | None], list[dict]]
    requires_image: bool


@dataclass(frozen=True, slots=True)
class VideoNodeConfig:
    endpoint: Literal["ai_app", "workflow"]
    build_nodes: Callable[[VideoGenerationInput, str | list[str]], list[dict]]
    image_count: int


def _parse_aspect_ratio(ratio: str | None) -> tuple[int, int]:
    if not ratio or "/" not in ratio and ":" not in ratio:
        return 1, 1
    sep = "/" if "/" in ratio else ":"
    parts = ratio.split(sep)
    if len(parts) != 2:
        return 1, 1
    try:
        return int(parts[0]), int(parts[1])
    except ValueError:
        return 1, 1


def _build_duanju_nodes(inp: ImageGenerationInput, image_url: str | None) -> list[dict]:
    rw, rh = _parse_aspect_ratio(inp.target_ratio)
    width = max(512, min(4096, round(rw * 96 / 8) * 8))
    height = max(512, min(4096, round(rh * 96 / 8) * 8))
    return [
        {"nodeId": "49", "fieldName": "text", "fieldValue": inp.prompt, "description": "提示词"},
        {"nodeId": "60", "fieldName": "value", "fieldValue": str(width), "description": "宽"},
        {"nodeId": "61", "fieldName": "value", "fieldValue": str(height), "description": "高"},
    ]


def _build_zimage_zhibao_nodes(inp: ImageGenerationInput, image_url: str | None) -> list[dict]:
    return [{"nodeId": "59", "fieldName": "value", "fieldValue": inp.prompt, "description": "提示词"}]


def _build_qwen_image_nodes(inp: ImageGenerationInput, image_url: str | None) -> list[dict]:
    ratio_map = {"3:2": "1", "2:3": "2", "16:9": "3", "9:16": "4", "4:3": "5", "3:4": "6", "1:1": "7"}
    ratio_select = ratio_map.get(inp.target_ratio or "", "7")
    seed = str(random.randint(0, 10**15 - 1))
    lora_name = "国潮面部插画qwen触发词gc.safetensors"
    return [
        {"nodeId": "932", "fieldName": "prompt", "fieldValue": inp.prompt, "description": "正向提示词"},
        {"nodeId": "931", "fieldName": "text", "fieldValue": "", "description": "反向提示词"},
        {"nodeId": "887", "fieldName": "select", "fieldValue": ratio_select, "description": "设置比例"},
        {"nodeId": "889", "fieldName": "batch_size", "fieldValue": "1", "description": "出图张数"},
        {"nodeId": "925", "fieldName": "lora_name", "fieldValue": lora_name, "description": "lora1_name"},
        {"nodeId": "925", "fieldName": "strength_model", "fieldValue": "0", "description": "lora1_strength"},
        {"nodeId": "925", "fieldName": "strength_clip", "fieldValue": "0", "description": "lora1_strength_clip"},
        {"nodeId": "933", "fieldName": "text1", "fieldValue": "", "description": "text1-lora触发词"},
        {"nodeId": "926", "fieldName": "lora_name", "fieldValue": lora_name, "description": "lora2_name"},
        {"nodeId": "926", "fieldName": "strength_model", "fieldValue": "0", "description": "lora2_strength"},
        {"nodeId": "926", "fieldName": "strength_clip", "fieldValue": "0", "description": "lora2_strength_clip"},
        {"nodeId": "933", "fieldName": "text2", "fieldValue": "", "description": "text2-lora触发词"},
        {"nodeId": "927", "fieldName": "lora_name", "fieldValue": lora_name, "description": "lora3_name"},
        {"nodeId": "927", "fieldName": "strength_model", "fieldValue": "0", "description": "lora3_strength"},
        {"nodeId": "927", "fieldName": "strength_clip", "fieldValue": "0", "description": "lora3_strength_clip"},
        {"nodeId": "933", "fieldName": "text3", "fieldValue": "", "description": "text3-lora触发词"},
        {"nodeId": "928", "fieldName": "lora_name", "fieldValue": lora_name, "description": "lora4_name"},
        {"nodeId": "928", "fieldName": "strength_model", "fieldValue": "0", "description": "lora4_strength"},
        {"nodeId": "928", "fieldName": "strength_clip", "fieldValue": "0", "description": "lora4_strength_clip"},
        {"nodeId": "933", "fieldName": "text4", "fieldValue": "", "description": "text4-lora触发词"},
        {"nodeId": "929", "fieldName": "lora_name", "fieldValue": lora_name, "description": "lora5_name"},
        {"nodeId": "929", "fieldName": "strength_model", "fieldValue": "0", "description": "lora5_strength"},
        {"nodeId": "929", "fieldName": "strength_clip", "fieldValue": "0", "description": "lora5_strength_clip"},
        {"nodeId": "933", "fieldName": "text5", "fieldValue": "", "description": "text5-lora触发词"},
        {"nodeId": "860", "fieldName": "seed", "fieldValue": seed, "description": "种子"},
        {"nodeId": "860", "fieldName": "steps", "fieldValue": "4", "description": "步数"},
        {"nodeId": "860", "fieldName": "sampler_name", "fieldValue": "euler", "description": "采样器"},
        {"nodeId": "860", "fieldName": "scheduler", "fieldValue": "simple", "description": "调度器"},
        {"nodeId": "938", "fieldName": "unet_name", "fieldValue": "qwen_image_fp8_e4m3fn.safetensors", "description": "unet_name"},
    ]


def _build_qwen_edit_nodes(inp: ImageGenerationInput, image_url: str | None) -> list[dict]:
    if not image_url:
        raise ValueError("Qwen Image Edit 图生图需要至少一张参考图片")
    return [
        {"nodeId": "41", "fieldName": "image", "fieldValue": image_url, "description": "image"},
        {"nodeId": "68", "fieldName": "prompt", "fieldValue": inp.prompt, "description": "prompt"},
    ]


def _build_zimage_8k_nodes(inp: ImageGenerationInput, image_url: str | None) -> list[dict]:
    return [{"nodeId": "163", "fieldName": "text", "fieldValue": inp.prompt, "description": "text"}]


def _video_dimensions(workflow_id: str, inp: VideoGenerationInput) -> tuple[int, int]:
    if workflow_id == "1956699246381469698":
        return 848, 480
    res = "720P"
    base_w, base_h = 1280, 720
    if "1080" in res:
        base_w, base_h = 1920, 1080
    elif "720" not in res:
        base_w, base_h = 854, 480
    if inp.ratio == "9:16":
        return base_h, base_w
    return base_w, base_h


def _build_wan22_nodes(inp: VideoGenerationInput, image_urls: str | list[str]) -> list[dict]:
    url = image_urls[0] if isinstance(image_urls, list) else image_urls
    width, height = _video_dimensions("1956699246381469698", inp)
    duration = inp.seconds or 5
    return [
        {"nodeId": "790", "fieldName": "image", "fieldValue": url, "description": "输入图片"},
        {"nodeId": "809", "fieldName": "value", "fieldValue": inp.prompt or "", "description": "输入提示词"},
        {"nodeId": "789", "fieldName": "value", "fieldValue": str(duration), "description": "时长"},
        {"nodeId": "791", "fieldName": "max_width", "fieldValue": str(width), "description": "输入宽"},
        {"nodeId": "791", "fieldName": "max_height", "fieldValue": str(height), "description": "输入高"},
    ]


def _build_ltx23_standard_nodes(inp: VideoGenerationInput, image_urls: str | list[str]) -> list[dict]:
    url = image_urls[0] if isinstance(image_urls, list) else image_urls
    width, height = _video_dimensions("2029759632314474498", inp)
    duration = inp.seconds or 5
    return [
        {"nodeId": "98", "fieldName": "image", "fieldValue": url, "description": "上传图片"},
        {"nodeId": "185", "fieldName": "value", "fieldValue": str(round(duration * 24)), "description": "视频长度"},
        {"nodeId": "222", "fieldName": "value", "fieldValue": str(width), "description": "视频宽度"},
        {"nodeId": "223", "fieldName": "value", "fieldValue": str(height), "description": "视频高度"},
        {"nodeId": "224", "fieldName": "value", "fieldValue": inp.prompt or "", "description": "提示词"},
    ]


def _build_ltx23_multishot_nodes(inp: VideoGenerationInput, image_urls: str | list[str]) -> list[dict]:
    url = image_urls[0] if isinstance(image_urls, list) else image_urls
    prompt = inp.prompt or ""
    return [
        {"nodeId": "584", "fieldName": "image", "fieldValue": url, "description": "image"},
        {"nodeId": "620", "fieldName": "prompt", "fieldValue": prompt, "description": "prompt主提示词"},
        {"nodeId": "621", "fieldName": "prompt", "fieldValue": prompt, "description": "prompt分阶段提示词"},
    ]


def _build_ltx23_fourframe_nodes(inp: VideoGenerationInput, image_urls: str | list[str]) -> list[dict]:
    urls = image_urls if isinstance(image_urls, list) else [image_urls]
    while len(urls) < 4:
        urls.append(urls[-1])
    return [
        {"nodeId": "1361", "fieldName": "image", "fieldValue": urls[0], "description": "参考图1"},
        {"nodeId": "1362", "fieldName": "image", "fieldValue": urls[1], "description": "参考图2"},
        {"nodeId": "1363", "fieldName": "image", "fieldValue": urls[2], "description": "参考图3"},
        {"nodeId": "1364", "fieldName": "image", "fieldValue": urls[3], "description": "参考图4"},
        {"nodeId": "1473", "fieldName": "text", "fieldValue": inp.prompt or "", "description": "自定义剧情提示词"},
    ]


IMAGE_NODE_CONFIGS: dict[str, ImageNodeConfig] = {
    "2052744677727715329": ImageNodeConfig("ai_app", _build_duanju_nodes, requires_image=False),
    "2003681895185563650": ImageNodeConfig("ai_app", _build_zimage_zhibao_nodes, requires_image=False),
    "1970396677775499266": ImageNodeConfig("ai_app", _build_qwen_image_nodes, requires_image=False),
    "2029488621429989377": ImageNodeConfig("ai_app", _build_qwen_edit_nodes, requires_image=True),
    "2058719340626796546": ImageNodeConfig("ai_app", _build_zimage_8k_nodes, requires_image=False),
}

VIDEO_NODE_CONFIGS: dict[str, VideoNodeConfig] = {
    "1956699246381469698": VideoNodeConfig("ai_app", _build_wan22_nodes, image_count=1),
    "2029759632314474498": VideoNodeConfig("ai_app", _build_ltx23_standard_nodes, image_count=1),
    "2055155307592077313": VideoNodeConfig("ai_app", _build_ltx23_multishot_nodes, image_count=1),
    "2054820963426021378": VideoNodeConfig("workflow", _build_ltx23_fourframe_nodes, image_count=4),
}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_runninghub_node_configs.py -v
```
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/integrations/runninghub/node_configs.py backend/tests/test_runninghub_node_configs.py
git commit -m "feat: add runninghub node config templates for 9 workflows"
```

---

### Task 5: Image adapter

**Files:**
- Create: `backend/app/core/integrations/runninghub/images.py`
- Test: `backend/tests/test_runninghub_image_adapter.py`

**Interfaces:**
- Consumes: `client.poll_until_done`, `client.submit_ai_app_task`, `IMAGE_NODE_CONFIGS` (Task 4)
- Produces: `RunningHubImageApiAdapter.generate(cfg, inp, timeout_s) -> ImageGenerationResult`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_runninghub_image_adapter.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_runninghub_image_adapter.py -v
```
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Create `backend/app/core/integrations/runninghub/images.py`**

```python
"""RunningHub 图片适配器：adapter 内部完成 submit → poll，对外同步语义。"""

from __future__ import annotations

from app.core.contracts.image_generation import (
    ImageGenerationInput,
    ImageGenerationResult,
    ImageItem,
)
from app.core.contracts.provider import ProviderConfig
from app.core.integrations.runninghub import client as rh_client
from app.core.integrations.runninghub.node_configs import IMAGE_NODE_CONFIGS


class RunningHubImageApiAdapter:
    """RunningHub 图片生成 HTTP；无状态。"""

    async def generate(
        self,
        *,
        cfg: ProviderConfig,
        inp: ImageGenerationInput,
        timeout_s: float,
    ) -> ImageGenerationResult:
        workflow_id = inp.model or ""
        config = IMAGE_NODE_CONFIGS.get(workflow_id)
        if config is None:
            raise ValueError(f"Unknown RunningHub image workflow: {workflow_id}")

        image_url: str | None = None
        if config.requires_image:
            image_url = _resolve_image_url(inp)
            if not image_url:
                raise ValueError("RunningHub 图片生成需要参考图片，但 InputImageRef 未提供 image_url")

        node_info_list = config.build_nodes(inp, image_url)

        base_url = cfg.base_url or "https://www.runninghub.cn"
        task_id = await rh_client.submit_ai_app_task(
            base_url, cfg.api_key, workflow_id, node_info_list, timeout_s=timeout_s
        )
        result_url = await rh_client.poll_until_done(
            base_url, cfg.api_key, task_id, interval=5.0, timeout=600.0
        )

        return ImageGenerationResult(
            images=[ImageItem(url=result_url)],
            provider="runninghub",
            provider_task_id=task_id,
            status="succeeded",
        )


def _resolve_image_url(inp: ImageGenerationInput) -> str | None:
    for ref in inp.images or []:
        if ref.image_url:
            return ref.image_url
    return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_runninghub_image_adapter.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/integrations/runninghub/images.py backend/tests/test_runninghub_image_adapter.py
git commit -m "feat: add runninghub image adapter with internal polling"
```

---

### Task 6: Video adapter

**Files:**
- Create: `backend/app/core/integrations/runninghub/video.py`
- Test: `backend/tests/test_runninghub_video_adapter.py`

**Interfaces:**
- Consumes: `client.submit_ai_app_task`, `client.submit_workflow_task`, `client.query_task`, `client.upload_media`, `VIDEO_NODE_CONFIGS` (Task 4)
- Produces: `RunningHubVideoApiAdapter.create_video(cfg, input_, timeout_s) -> str`；`get_video(cfg, video_id, timeout_s) -> dict`

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_runninghub_video_adapter.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_runninghub_video_adapter.py -v
```
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Create `backend/app/core/integrations/runninghub/video.py`**

```python
"""RunningHub 视频适配器：create + get 两阶段，Task 层负责轮询节奏。"""

from __future__ import annotations

import base64
from typing import Any

from app.core.contracts.provider import ProviderConfig
from app.core.contracts.video_generation import VideoGenerationInput
from app.core.integrations.runninghub import client as rh_client
from app.core.integrations.runninghub.node_configs import VIDEO_NODE_CONFIGS


class RunningHubVideoApiAdapter:
    """RunningHub 视频生成 HTTP；无状态。"""

    async def create_video(
        self,
        *,
        cfg: ProviderConfig,
        input_: VideoGenerationInput,
        timeout_s: float,
    ) -> str:
        workflow_id = input_.model or ""
        config = VIDEO_NODE_CONFIGS.get(workflow_id)
        if config is None:
            raise ValueError(f"Unknown RunningHub video workflow: {workflow_id}")

        base_url = cfg.base_url or "https://www.runninghub.cn"
        image_urls = await _resolve_frame_urls(input_, config.image_count, cfg, timeout_s)

        node_info_list = config.build_nodes(input_, image_urls)

        if config.endpoint == "workflow":
            return await rh_client.submit_workflow_task(
                base_url, cfg.api_key, workflow_id, node_info_list, timeout_s=timeout_s
            )
        return await rh_client.submit_ai_app_task(
            base_url, cfg.api_key, workflow_id, node_info_list, timeout_s=timeout_s
        )

    async def get_video(
        self,
        *,
        cfg: ProviderConfig,
        video_id: str,
        timeout_s: float,
    ) -> dict[str, Any]:
        base_url = cfg.base_url or "https://www.runninghub.cn"
        return await rh_client.query_task(base_url, cfg.api_key, video_id, timeout_s=timeout_s)


async def _resolve_frame_urls(
    input_: VideoGenerationInput,
    image_count: int,
    cfg: ProviderConfig,
    timeout_s: float,
) -> list[str]:
    base64_frames: list[tuple[str, str]] = []
    for label, raw in (
        ("first", input_.first_frame_base64),
        ("last", input_.last_frame_base64),
        ("key", input_.key_frame_base64),
    ):
        if raw:
            mime, data = _split_data_url(raw)
            base64_frames.append((mime, data))

    if not base64_frames:
        raise ValueError("RunningHub 视频生成需要至少一张参考图（first/last/key_frame_base64）")

    base_url = cfg.base_url or "https://www.runninghub.cn"
    urls: list[str] = []
    for mime, data in base64_frames:
        bytes_data = base64.b64decode(data)
        url = await rh_client.upload_media(base_url, cfg.api_key, mime, bytes_data, timeout_s=timeout_s)
        urls.append(url)

    while len(urls) < image_count:
        urls.append(urls[-1])
    return urls


def _split_data_url(raw: str) -> tuple[str, str]:
    """返回 (mime, base64_data)。支持纯 base64 与 data:image/...;base64,... 两种格式。"""
    s = raw.strip()
    if s.startswith("data:") and ";base64," in s:
        head, _, data = s.partition(";base64,")
        mime = head[5:] or "image/png"
        return mime, data
    return "image/png", s
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_runninghub_video_adapter.py -v
```
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/integrations/runninghub/video.py backend/tests/test_runninghub_video_adapter.py
git commit -m "feat: add runninghub video adapter with create+get two-phase"
```

---

### Task 7: Task layer + bootstrap registration

**Files:**
- Modify: `backend/app/core/tasks/image_generation_tasks.py`
- Modify: `backend/app/core/tasks/video_generation_tasks.py`
- Modify: `backend/app/core/tasks/bootstrap.py`
- Test: `backend/tests/test_task_registry.py`（扩展）

**Interfaces:**
- Consumes: `RunningHubImageApiAdapter` (Task 5), `RunningHubVideoApiAdapter` (Task 6), `ProviderKey="runninghub"` (Task 1)
- Produces: `RunningHubImageGenerationTask`, `RunningHubVideoGenerationTask` 类；`ImageGenerationTask._build_runninghub_impl`、`VideoGenerationTask._build_runninghub_impl` 静态方法；task adapter registry 注册 `(image_generation, runninghub)` 与 `(video_generation, runninghub)`

- [ ] **Step 1: Write failing test**

在 `backend/tests/test_task_registry.py` 末尾追加：

```python
def test_runninghub_task_adapters_registered() -> None:
    from app.core.tasks.bootstrap import bootstrap_task_adapters
    from app.core.tasks.registry import resolve_task_adapter

    bootstrap_task_adapters()
    image_factory = resolve_task_adapter("image_generation", "runninghub")
    video_factory = resolve_task_adapter("video_generation", "runninghub")
    assert image_factory is not None
    assert video_factory is not None


def test_runninghub_image_task_builds_adapter_impl() -> None:
    from app.core.tasks.image_generation_tasks import ImageGenerationTask, RunningHubImageGenerationTask
    from app.core.contracts.image_generation import ImageGenerationInput
    from app.core.contracts.provider import ProviderConfig

    impl = ImageGenerationTask._build_runninghub_impl(
        provider_config=ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh"),
        input_=ImageGenerationInput(prompt="x", model="2052744677727715329"),
        timeout_s=60.0,
    )
    assert isinstance(impl, RunningHubImageGenerationTask)


def test_runninghub_video_task_builds_adapter_impl() -> None:
    from app.core.tasks.video_generation_tasks import VideoGenerationTask, RunningHubVideoGenerationTask
    from app.core.contracts.video_generation import VideoGenerationInput
    from app.core.contracts.provider import ProviderConfig

    impl = VideoGenerationTask._build_runninghub_impl(
        provider_config=ProviderConfig(provider="runninghub", api_key="k", base_url="https://rh"),
        input_=VideoGenerationInput(prompt="x", ratio="16:9", model="1956699246381469698"),
        poll_interval_s=5.0,
        timeout_s=600.0,
    )
    assert isinstance(impl, RunningHubVideoGenerationTask)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_task_registry.py::test_runninghub_task_adapters_registered tests/test_task_registry.py::test_runninghub_image_task_builds_adapter_impl tests/test_task_registry.py::test_runninghub_video_task_builds_adapter_impl -v
```
Expected: FAIL with AttributeError (no `_build_runninghub_impl`) / ValueError (adapter not registered)

- [ ] **Step 3: Modify `backend/app/core/tasks/image_generation_tasks.py`**

在文件顶部 import 区加：

```python
from app.core.integrations.runninghub.images import RunningHubImageApiAdapter
```

在 `VolcengineImageGenerationTask` 类定义之后、`ImageGenerationTask` 类定义之前，加新类：

```python
class RunningHubImageGenerationTask(AbstractImageGenerationTask):
    """RunningHub 图片：adapter 内部完成 submit→poll，Task 层不轮询。"""

    def __init__(
        self,
        *,
        adapter: RunningHubImageApiAdapter | None = None,
        provider_config: ProviderConfig,
        input_: ImageGenerationInput,
        timeout_s: float = 600.0,
    ) -> None:
        super().__init__(provider_config=provider_config, input_=input_, timeout_s=timeout_s)
        self._adapter = adapter or RunningHubImageApiAdapter()
        self._deferred: ImageGenerationResult | None = None

    async def _create_task(self) -> None:
        self._deferred = await self._adapter.generate(
            cfg=self._cfg,
            inp=self._input,
            timeout_s=self._timeout_s,
        )

    async def _poll_and_get_result(self) -> ImageGenerationResult:
        assert self._deferred is not None
        return self._deferred
```

在 `ImageGenerationTask` 类内部，`_build_volcengine_impl` 静态方法之后，加：

```python
    @staticmethod
    def _build_runninghub_impl(
        *,
        provider_config: ProviderConfig,
        input_: ImageGenerationInput,
        timeout_s: float = 600.0,
    ) -> AbstractImageGenerationTask:
        return RunningHubImageGenerationTask(
            provider_config=provider_config,
            input_=input_,
            timeout_s=timeout_s,
        )
```

同时把 `__all__` 列表里加上 `"RunningHubImageGenerationTask"`。

- [ ] **Step 4: Modify `backend/app/core/tasks/video_generation_tasks.py`**

在文件顶部 import 区加：

```python
from app.core.integrations.runninghub.video import RunningHubVideoApiAdapter
```

在 `VolcengineVideoGenerationTask` 类之后、`VideoGenerationTask` 类之前，加：

```python
class RunningHubVideoGenerationTask(AbstractVideoGenerationTask):
    """RunningHub 视频：adapter create+get，Task 层轮询。"""

    def __init__(
        self,
        *,
        adapter: RunningHubVideoApiAdapter | None = None,
        provider_config: ProviderConfig,
        input_: VideoGenerationInput,
        poll_interval_s: float = 5.0,
        timeout_s: float = 600.0,
    ) -> None:
        super().__init__(
            provider_config=provider_config,
            input_=input_,
            poll_interval_s=poll_interval_s,
            timeout_s=timeout_s,
        )
        self._adapter = adapter or RunningHubVideoApiAdapter()

    async def _create_task(self) -> None:
        self._provider_task_id = await self._adapter.create_video(
            cfg=self._cfg,
            input_=self._input,
            timeout_s=self._timeout_s,
        )

    async def _poll_and_get_result(self) -> VideoGenerationResult:
        task_id = self._provider_task_id or ""
        if not task_id:
            raise RuntimeError("RunningHub poll missing task id")
        video_url: str | None = None
        status_val = ""
        while True:
            meta = await self._adapter.get_video(
                cfg=self._cfg,
                video_id=task_id,
                timeout_s=self._timeout_s,
            )
            status_val = str(meta.get("status") or "")
            if status_val == "SUCCESS":
                results = meta.get("results") or []
                video_url = results[0].get("url") if results else None
                if not video_url:
                    raise RuntimeError("RunningHub SUCCESS but no result url")
                break
            if status_val in ("FAILED", "ERROR"):
                raise RuntimeError(
                    f"RunningHub task failed: "
                    f"{meta.get('errorMessage') or meta.get('errorCode') or status_val}"
                )
            await self._sleep_poll()

        return VideoGenerationResult(
            url=video_url,
            file_id=None,
            provider_task_id=task_id,
            provider="runninghub",
            status=status_val or "succeeded",
        )
```

在 `VideoGenerationTask` 类内部，`_build_volcengine_impl` 静态方法之后，加：

```python
    @staticmethod
    def _build_runninghub_impl(
        *,
        provider_config: ProviderConfig,
        input_: VideoGenerationInput,
        poll_interval_s: float = 5.0,
        timeout_s: float = 600.0,
    ) -> AbstractVideoGenerationTask:
        return RunningHubVideoGenerationTask(
            provider_config=provider_config,
            input_=input_,
            poll_interval_s=poll_interval_s,
            timeout_s=timeout_s,
        )
```

同时把 `__all__` 列表里加上 `"RunningHubVideoGenerationTask"`。

- [ ] **Step 5: Modify `backend/app/core/tasks/bootstrap.py`**

将 `TASK_ADAPTER_SPECS` 元组替换为：

```python
TASK_ADAPTER_SPECS = (
    ("image_generation", "openai", ImageGenerationTask._build_openai_impl),
    ("image_generation", "volcengine", ImageGenerationTask._build_volcengine_impl),
    ("image_generation", "runninghub", ImageGenerationTask._build_runninghub_impl),
    ("video_generation", "openai", VideoGenerationTask._build_openai_impl),
    ("video_generation", "volcengine", VideoGenerationTask._build_volcengine_impl),
    ("video_generation", "runninghub", VideoGenerationTask._build_runninghub_impl),
)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_task_registry.py -v
```
Expected: PASS (all tests including new 3)

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/tasks/image_generation_tasks.py backend/app/core/tasks/video_generation_tasks.py backend/app/core/tasks/bootstrap.py backend/tests/test_task_registry.py
git commit -m "feat: register runninghub image/video generation tasks"
```

---

### Task 8: Model bootstrap (DB)

**Files:**
- Create: `backend/app/services/llm/model_bootstrap.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_runninghub_model_bootstrap.py`

**Interfaces:**
- Consumes: `Provider`、`Model` ORM models；`ModelCategoryKey` enum；`provider_registry`（确认 runninghub key 已注册）
- Produces: `bootstrap_builtin_db_resources(session) -> None`（幂等 upsert provider 行 + 9 个 model 行）

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_runninghub_model_bootstrap.py`:

```python
from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.db import Base
from app.models.llm import Model, ModelCategoryKey, Provider, ProviderStatus
from app.services.llm.model_bootstrap import bootstrap_builtin_db_resources


async def _build_session() -> tuple[AsyncSession, object]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    session_local = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return session_local(), engine


@pytest.fixture
async def db():
    session, engine = await _build_session()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


async def test_bootstrap_creates_provider_and_9_models(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    provider = (await db.execute(select(Provider).where(Provider.id == "runninghub"))).scalar_one()
    assert provider.name == "RunningHub"
    assert provider.base_url == "https://www.runninghub.cn"
    assert provider.status == ProviderStatus.testing

    models = (await db.execute(select(Model).where(Model.provider_id == "runninghub"))).scalars().all()
    assert len(models) == 9
    image_count = sum(1 for m in models if m.category == ModelCategoryKey.image)
    video_count = sum(1 for m in models if m.category == ModelCategoryKey.video)
    assert image_count == 5
    assert video_count == 4


async def test_bootstrap_is_idempotent(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    models = (await db.execute(select(Model).where(Model.provider_id == "runninghub"))).scalars().all()
    assert len(models) == 9


async def test_bootstrap_preserves_user_api_key(db: AsyncSession) -> None:
    db.add(Provider(
        id="runninghub",
        name="Old Name",
        base_url="https://custom.rh",
        api_key="user-secret-key",
        api_secret="",
        description="",
        status=ProviderStatus.active,
        created_by="user",
    ))
    await db.commit()

    await bootstrap_builtin_db_resources(db)
    await db.commit()

    provider = (await db.execute(select(Provider).where(Provider.id == "runninghub"))).scalar_one()
    assert provider.api_key == "user-secret-key"
    assert provider.base_url == "https://custom.rh"
    assert provider.status == ProviderStatus.active


async def test_bootstrap_model_has_workflow_id_in_params(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    model = (await db.execute(
        select(Model).where(Model.id == "runninghub-2052744677727715329")
    )).scalar_one()
    assert model.params["workflow_id"] == "2052744677727715329"
    assert model.params["mode"] == "text"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_runninghub_model_bootstrap.py -v
```
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Create `backend/app/services/llm/model_bootstrap.py`**

```python
"""DB 级幂等 upsert：runninghub provider 行 + 9 个预置 model 行。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llm import Model, ModelCategoryKey, Provider, ProviderStatus

_RUNNINGHUB_PROVIDER_DEFAULTS = {
    "id": "runninghub",
    "name": "RunningHub",
    "base_url": "https://www.runninghub.cn",
    "image_base_url": None,
    "video_base_url": None,
    "api_secret": "",
    "description": "RunningHub 个人消费版：短剧图片模型 + WAN2.2/LTX2.3 视频模型",
    "status": ProviderStatus.testing,
    "created_by": "system",
}

_RUNNINGHUB_MODELS: list[dict] = [
    {
        "id": "runninghub-2052744677727715329",
        "name": "短剧专用图片模型",
        "category": ModelCategoryKey.image,
        "params": {"workflow_id": "2052744677727715329", "mode": "text"},
        "description": "短剧场景专用，支持自定义宽高",
    },
    {
        "id": "runninghub-2003681895185563650",
        "name": "Z-image 超真实感短剧定妆照",
        "category": ModelCategoryKey.image,
        "params": {"workflow_id": "2003681895185563650", "mode": "text"},
        "description": "超真实感 AI 短剧定妆照文生图",
    },
    {
        "id": "runninghub-1970396677775499266",
        "name": "Qwen-image 文生图",
        "category": ModelCategoryKey.image,
        "params": {"workflow_id": "1970396677775499266", "mode": "text"},
        "description": "支持正反向提示词与多比例输出",
    },
    {
        "id": "runninghub-2029488621429989377",
        "name": "Qwen Image Edit 2511图生图",
        "category": ModelCategoryKey.image,
        "params": {"workflow_id": "2029488621429989377", "mode": "singleImage"},
        "description": "图生图，输入参考图+提示词即可编辑生成",
    },
    {
        "id": "runninghub-2058719340626796546",
        "name": "Z-Image在线8K直出",
        "category": ModelCategoryKey.image,
        "params": {"workflow_id": "2058719340626796546", "mode": "text"},
        "description": "Z-Image 在线 8K 直出文生图",
    },
    {
        "id": "runninghub-1956699246381469698",
        "name": "WAN2.2 官方加速",
        "category": ModelCategoryKey.video,
        "params": {"workflow_id": "1956699246381469698", "mode": "singleImage", "duration": [5], "resolution": ["480P"]},
        "description": "WAN2.2 图生视频，5s 480P",
    },
    {
        "id": "runninghub-2029759632314474498",
        "name": "LTX2.3 图生视频",
        "category": ModelCategoryKey.video,
        "params": {"workflow_id": "2029759632314474498", "mode": "singleImage", "duration": [5, 10], "resolution": ["720P"]},
        "description": "LTX2.3 图生视频，支持 5/10s 720P",
    },
    {
        "id": "runninghub-2055155307592077313",
        "name": "LTX2.3 图生长视频多镜头分段",
        "category": ModelCategoryKey.video,
        "params": {"workflow_id": "2055155307592077313", "mode": "singleImage", "duration": [10], "resolution": ["720P"]},
        "description": "LTX2.3 多镜头时间分段提示词控制",
    },
    {
        "id": "runninghub-2054820963426021378",
        "name": "LTX2.3 四帧丝滑流转与全自动动态编排",
        "category": ModelCategoryKey.video,
        "params": {"workflow_id": "2054820963426021378", "mode": "imageReference:4", "duration": [5], "resolution": ["720P"]},
        "description": "LTX2.3 四帧丝滑流转，4 张参考图自动编排",
    },
]


async def bootstrap_builtin_db_resources(session: AsyncSession) -> None:
    """幂等 upsert runninghub provider 行 + 9 个 model 行。

    - Provider 存在时：不覆盖 api_key / base_url / status / created_by（保留用户配置）
    - Provider 不存在时：用默认值插入（api_key 为空，用户在 UI 填）
    - Model 存在时：更新 name / params / description（保持版本最新）
    - Model 不存在时：插入
    """
    provider = (
        await session.execute(select(Provider).where(Provider.id == "runninghub"))
    ).scalar_one_or_none()

    if provider is None:
        provider = Provider(
            id=_RUNNINGHUB_PROVIDER_DEFAULTS["id"],
            name=_RUNNINGHUB_PROVIDER_DEFAULTS["name"],
            base_url=_RUNNINGHUB_PROVIDER_DEFAULTS["base_url"],
            image_base_url=_RUNNINGHUB_PROVIDER_DEFAULTS["image_base_url"],
            video_base_url=_RUNNINGHUB_PROVIDER_DEFAULTS["video_base_url"],
            api_key="",
            api_secret=_RUNNINGHUB_PROVIDER_DEFAULTS["api_secret"],
            description=_RUNNINGHUB_PROVIDER_DEFAULTS["description"],
            status=_RUNNINGHUB_PROVIDER_DEFAULTS["status"],
            created_by=_RUNNINGHUB_PROVIDER_DEFAULTS["created_by"],
        )
        session.add(provider)
    # 已存在则不覆盖用户字段

    for spec in _RUNNINGHUB_MODELS:
        model = (
            await session.execute(select(Model).where(Model.id == spec["id"]))
        ).scalar_one_or_none()
        if model is None:
            model = Model(
                id=spec["id"],
                name=spec["name"],
                category=spec["category"],
                provider_id="runninghub",
                params=spec["params"],
                description=spec["description"],
                created_by="system",
            )
            session.add(model)
        else:
            model.name = spec["name"]
            model.category = spec["category"]
            model.provider_id = "runninghub"
            model.params = spec["params"]
            model.description = spec["description"]
```

- [ ] **Step 4: Modify `backend/app/main.py`**

在 `lifespan` 函数中，`bootstrap_all_registries()` 之后、`yield` 之前，加 DB bootstrap：

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期：启动时初始化，关闭时清理。"""
    bootstrap_all_registries()
    # DB 级幂等 upsert：runninghub provider + 9 个预置模型
    from app.services.llm.model_bootstrap import bootstrap_builtin_db_resources
    from app.core.db import async_session_maker
    try:
        async with async_session_maker() as session:
            await bootstrap_builtin_db_resources(session)
            await session.commit()
    except Exception as e:  # noqa: BLE001
        import logging
        logging.getLogger("app.bootstrap").warning(f"RunningHub DB bootstrap skipped: {e}")
    yield
    pass
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_runninghub_model_bootstrap.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add backend/app/services/llm/model_bootstrap.py backend/app/main.py backend/tests/test_runninghub_model_bootstrap.py
git commit -m "feat: add db bootstrap for runninghub provider and 9 preset models"
```

---

### Task 9: Service-layer workflow_id wiring

**Files:**
- Modify: `backend/app/services/studio/image_task_runner.py:267-269`
- Modify: `backend/app/services/film/generated_video.py:182-188`
- Create: `backend/app/services/llm/model_identifier.py`
- Test: `backend/tests/test_runninghub_model_identifier.py`

**Interfaces:**
- Consumes: `Model.params["workflow_id"]`（Task 8 写入）；`provider_cfg.provider`
- Produces: `resolve_model_identifier(model: Model, provider_key: str) -> str`（runninghub 返回 `params.workflow_id`，其他返回 `model.name`）

- [ ] **Step 1: Write failing test**

Create `backend/tests/test_runninghub_model_identifier.py`:

```python
from __future__ import annotations

from app.models.llm import Model, ModelCategoryKey
from app.services.llm.model_identifier import resolve_model_identifier


def _make_model(*, name: str, params: dict | None = None) -> Model:
    return Model(
        id="m1",
        name=name,
        category=ModelCategoryKey.image,
        provider_id="p1",
        params=params or {},
        description="",
        created_by="",
    )


def test_runninghub_returns_workflow_id_from_params() -> None:
    model = _make_model(name="短剧专用图片模型", params={"workflow_id": "2052744677727715329"})
    assert resolve_model_identifier(model, "runninghub") == "2052744677727715329"


def test_runninghub_without_workflow_id_falls_back_to_name() -> None:
    model = _make_model(name="短剧专用图片模型", params={})
    assert resolve_model_identifier(model, "runninghub") == "短剧专用图片模型"


def test_openai_returns_model_name() -> None:
    model = _make_model(name="gpt-image-1.5")
    assert resolve_model_identifier(model, "openai") == "gpt-image-1.5"


def test_volcengine_returns_model_name() -> None:
    model = _make_model(name="doubao-seedream-3.0")
    assert resolve_model_identifier(model, "volcengine") == "doubao-seedream-3.0"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd backend && uv run pytest tests/test_runninghub_model_identifier.py -v
```
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Create `backend/app/services/llm/model_identifier.py`**

```python
"""根据供应商类型解析最终传给 adapter 的 model 标识符。

RunningHub 用 params.workflow_id（即 workflowId）；其他供应商沿用 model.name。
"""

from __future__ import annotations

from app.models.llm import Model


def resolve_model_identifier(model: Model, provider_key: str) -> str:
    """返回 adapter 层 inp.model 应当使用的标识符。"""
    if provider_key == "runninghub":
        workflow_id = (model.params or {}).get("workflow_id")
        if workflow_id:
            return str(workflow_id)
    return model.name
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd backend && uv run pytest tests/test_runninghub_model_identifier.py -v
```
Expected: PASS (4 tests)

- [ ] **Step 5: Modify `backend/app/services/studio/image_task_runner.py`**

在文件顶部 import 区加：

```python
from app.services.llm.model_identifier import resolve_model_identifier
```

将 `create_image_task_and_link` 函数中 `run_args` 构造里的 `"model": model.name,` 改为：

```python
            "model": resolve_model_identifier(model, provider_cfg.provider),
```

注意：`provider_cfg` 是 `ProviderConfig`，其 `.provider` 字段即 provider key。

- [ ] **Step 6: Modify `backend/app/services/film/generated_video.py`**

在文件顶部 import 区加：

```python
from app.services.llm.model_identifier import resolve_model_identifier
```

将 `run_args` 构造里的 `"model": model.name,` 改为：

```python
            "model": resolve_model_identifier(model, provider_cfg.provider),
```

- [ ] **Step 7: Run full test suite to verify no regression**

```bash
cd backend && uv run pytest tests/ -x --tb=short -q
```
Expected: PASS (no regressions)

- [ ] **Step 8: Commit**

```bash
git add backend/app/services/llm/model_identifier.py backend/app/services/studio/image_task_runner.py backend/app/services/film/generated_video.py backend/tests/test_runninghub_model_identifier.py
git commit -m "feat: wire workflow_id through service layer for runninghub"
```

---

## Self-Review

**1. Spec coverage:**
- ✅ ProviderKey + ProviderSpec registration → Task 1
- ✅ Capability modules → Task 2
- ✅ HTTP client (submit/query/upload/poll) → Task 3
- ✅ 9 个 workflowId 节点配置 → Task 4
- ✅ Image adapter (内部轮询) → Task 5
- ✅ Video adapter (create+get 两阶段) → Task 6
- ✅ Task 层 + bootstrap 注册 → Task 7
- ✅ DB model bootstrap (provider 行 + 9 model 行) → Task 8
- ✅ Service 层 workflow_id 透传 → Task 9
- ✅ 前端无需改动（UI 数据驱动）
- ✅ 无 text/TTS

**2. Placeholder scan:**
- 无 TBD/TODO
- 每个步骤都有完整代码
- 测试代码完整可运行

**3. Type consistency:**
- `ProviderKey` Literal 在 Task 1 加 `"runninghub"`，所有下游 task 使用一致
- `ImageNodeConfig` / `VideoNodeConfig` dataclass 在 Task 4 定义，Task 5/6 引用一致
- `RunningHubImageApiAdapter.generate` 签名在 Task 5 定义，Task 7 调用一致
- `RunningHubVideoApiAdapter.create_video` / `get_video` 签名在 Task 6 定义，Task 7 调用一致
- `bootstrap_builtin_db_resources(session)` 签名在 Task 8 定义，main.py 调用一致
- `resolve_model_identifier(model, provider_key)` 在 Task 9 定义，service 层调用一致

**4. Known gaps:**
- 集成测试不在范围（按 spec 要求）
- 前端无改动（UI 数据驱动，已确认）
- OpenAPI 重新生成不需要（接口签名不变）
