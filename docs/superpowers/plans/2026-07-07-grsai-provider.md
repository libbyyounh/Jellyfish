# Grsai Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `grsai` provider with 13 image generation models (nano-banana family + gpt-image-2 family) using async polling against the native `/v1/api/generate` + `/v1/api/result` endpoints, with the China node as default base URL.

**Architecture:** Follow the RunningHub async-polling pattern. The Grsai adapter submits a task with `replyType="async"`, receives a task ID, then polls `/v1/api/result?id=...` until terminal status. The adapter maps `ImageGenerationInput` → Grsai request body and Grsai response → `ImageGenerationResult`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy async, httpx, pytest, pytest-asyncio

## Global Constraints

- Provider key: `"grsai"` (lowercase)
- Default base URL: `https://grsai.dakka.com.cn` (China node)
- API authentication: `Authorization: Bearer {api_key}` header
- Image generation only (no text/video categories)
- 13 models total: 11 nano-banana family + 2 gpt-image-2 family
- Model identifier: `model.name` used directly as API model name (no `model_name` param)
- Async polling: `replyType="async"` for submit, poll `/v1/api/result?id=...` every 5s
- `imageSize` field only sent for nano-banana family models (omitted for gpt-image-2 family)
- Terminal statuses: `succeeded`, `failed`, `violation` (treated as failed)
- All tests use TDD: write failing test → verify failure → implement → verify pass → commit
- Test command: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/<test_file>::<test_name> -v`

---

### Task 1: Provider Key, Spec, and Alias Resolution

**Files:**
- Modify: `app/core/contracts/provider.py:8`
- Modify: `app/services/llm/provider_bootstrap.py:7-50`
- Modify: `app/services/llm/provider_registry.py:89-105`
- Test: `tests/test_task_registry.py`

**Interfaces:**
- Consumes: existing `ProviderSpec` dataclass, `register_many` function, `resolve_provider_key_from_name` function
- Produces: `"grsai"` added to `ProviderKey` Literal; `ProviderSpec(key="grsai", ...)` registered; `resolve_provider_key_from_name("grsai")` returns `"grsai"`

- [ ] **Step 1: Write the failing tests**

Add these tests to the end of `tests/test_task_registry.py`:

```python
def test_resolve_provider_key_for_grsai_aliases() -> None:
    from app.services.llm.provider_registry import resolve_provider_key_from_name
    from app.services.llm.provider_bootstrap import bootstrap_builtin_providers

    bootstrap_builtin_providers()
    assert resolve_provider_key_from_name("grsai") == "grsai"
    assert resolve_provider_key_from_name("Grsai") == "grsai"
    assert resolve_provider_key_from_name("GRSAI") == "grsai"


def test_grsai_provider_spec_registered() -> None:
    from app.services.llm.provider_registry import get_provider_spec
    from app.services.llm.provider_bootstrap import bootstrap_builtin_providers
    from app.models.llm import ModelCategoryKey

    bootstrap_builtin_providers()
    spec = get_provider_spec("grsai")
    assert spec.display_name == "Grsai"
    assert ModelCategoryKey.image in spec.supported_categories
    assert ModelCategoryKey.text not in spec.supported_categories
    assert ModelCategoryKey.video not in spec.supported_categories
    assert spec.default_base_url == "https://grsai.dakka.com.cn"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_task_registry.py::test_resolve_provider_key_for_grsai_aliases tests/test_task_registry.py::test_grsai_provider_spec_registered -v`
Expected: FAIL with "Unsupported provider key" or similar (grsai not yet registered)

- [ ] **Step 3: Add `"grsai"` to ProviderKey Literal**

In `app/core/contracts/provider.py`, change line 8:

```python
ProviderKey = Literal["openai", "volcengine", "runninghub", "runninghub-enterprise", "grsai"]
```

- [ ] **Step 4: Register Grsai ProviderSpec**

In `app/services/llm/provider_bootstrap.py`, add a new `ProviderSpec` entry inside the `register_many([...])` list, after the `runninghub-enterprise` entry:

```python
            ProviderSpec(
                key="grsai",
                display_name="Grsai",
                aliases=("grsai",),
                supported_categories=(ModelCategoryKey.image,),
                default_base_url="https://grsai.dakka.com.cn",
            ),
```

- [ ] **Step 5: Add alias resolution for Grsai**

In `app/services/llm/provider_registry.py`, in the `resolve_provider_key_from_name` function, add a Grsai check before the volcengine check (after the runninghub-enterprise check). The function should look like:

```python
def resolve_provider_key_from_name(name: str) -> str:
    alias = _norm(name)
    with _LOCK:
        key = _KEY_BY_ALIAS.get(alias)
    if key:
        return key
    # 兼容历史"包含式"命名（如 Doubao Video / bytedance-xxx）。
    if "runninghub-enterprise" in alias or "rh-enterprise" in alias:
        return "runninghub-enterprise"
    if "grsai" in alias:
        return "grsai"
    if "volc" in alias or "doubao" in alias or "bytedance" in alias:
        return "volcengine"
    if "runninghub" in alias or alias == "rh":
        return "runninghub"
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Unsupported provider name: {name!r}",
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_task_registry.py::test_resolve_provider_key_for_grsai_aliases tests/test_task_registry.py::test_grsai_provider_spec_registered -v`
Expected: PASS (both tests)

- [ ] **Step 7: Commit**

```bash
cd /Users/findhappylee/workspace/github/Jellyfish
git add backend/app/core/contracts/provider.py backend/app/services/llm/provider_bootstrap.py backend/app/services/llm/provider_registry.py backend/tests/test_task_registry.py
git commit -m "feat: register grsai provider key, spec, and alias resolution"
```

---

### Task 2: Image Capability Resolver

**Files:**
- Create: `app/core/integrations/grsai/__init__.py`
- Create: `app/core/integrations/grsai/image_capabilities.py`
- Modify: `app/core/integrations/image_capabilities.py:36-92`
- Test: `tests/test_grsai_image_capabilities.py`

**Interfaces:**
- Consumes: `ImageModelCapability` dataclass from `app.core.integrations.image_capabilities`
- Produces: `resolve_grsai_image_capability(model: str | None) -> ImageModelCapability`; `register_grsai_image_capability(*, model_prefix: str, capability: ImageModelCapability) -> None`; `clear_grsai_image_capability_overrides() -> None`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_grsai_image_capabilities.py`:

```python
from __future__ import annotations

from app.core.integrations.grsai.image_capabilities import (
    resolve_grsai_image_capability,
)


def test_nano_banana_family_returns_standard_ratios() -> None:
    for model in ("nano-banana", "nano-banana-fast", "nano-banana-pro", "nano-banana-pro-vt"):
        cap = resolve_grsai_image_capability(model)
        assert cap.supports_seed is False
        assert cap.supports_watermark is False
        assert "1:1" in cap.supported_ratios
        assert "16:9" in cap.supported_ratios
        assert "21:9" in cap.supported_ratios
        assert "1:4" not in cap.supported_ratios
        assert "8:1" not in cap.supported_ratios


def test_nano_banana_2_family_returns_extended_ratios() -> None:
    for model in (
        "nano-banana-2",
        "nano-banana-2-cl",
        "nano-banana-2-2k-cl",
        "nano-banana-2-4k-cl",
    ):
        cap = resolve_grsai_image_capability(model)
        assert "1:4" in cap.supported_ratios
        assert "4:1" in cap.supported_ratios
        assert "1:8" in cap.supported_ratios
        assert "8:1" in cap.supported_ratios
        assert "1:1" in cap.supported_ratios


def test_gpt_image_2_family_returns_standard_ratios() -> None:
    for model in ("gpt-image-2", "gpt-image-2-vip"):
        cap = resolve_grsai_image_capability(model)
        assert "1:1" in cap.supported_ratios
        assert "16:9" in cap.supported_ratios
        assert "1:4" not in cap.supported_ratios


def test_unknown_model_returns_default() -> None:
    cap = resolve_grsai_image_capability(None)
    assert cap.supports_seed is False
    assert cap.supports_watermark is False
    assert "1:1" in cap.supported_ratios
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_grsai_image_capabilities.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.integrations.grsai'`

- [ ] **Step 3: Create the grsai package**

Create `app/core/integrations/grsai/__init__.py`:

```python
"""Grsai 图片生成集成：HTTP client + adapter + 能力声明。"""
```

- [ ] **Step 4: Create the image_capabilities module**

Create `app/core/integrations/grsai/image_capabilities.py`:

```python
"""Grsai 图片能力声明。"""

from __future__ import annotations

from app.core.integrations.image_capabilities import ImageModelCapability

_GRSAI_STANDARD_RATIOS: set[str] = {
    "auto",
    "1:1",
    "16:9",
    "9:16",
    "4:3",
    "3:4",
    "3:2",
    "2:3",
    "5:4",
    "4:5",
    "21:9",
}

_GRSAI_EXTENDED_RATIOS: set[str] = _GRSAI_STANDARD_RATIOS | {
    "1:4",
    "4:1",
    "1:8",
    "8:1",
}

_GRSAI_DEFAULT = ImageModelCapability(
    supports_seed=False,
    supports_watermark=False,
    allowed_sizes=None,
    supported_ratios=_GRSAI_STANDARD_RATIOS,
)

_GRSAI_MODEL_OVERRIDES: dict[str, ImageModelCapability] = {
    "nano-banana-2": ImageModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_sizes=None,
        supported_ratios=_GRSAI_EXTENDED_RATIOS,
    ),
    "nano-banana-2-cl": ImageModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_sizes=None,
        supported_ratios=_GRSAI_EXTENDED_RATIOS,
    ),
    "nano-banana-2-2k-cl": ImageModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_sizes=None,
        supported_ratios=_GRSAI_EXTENDED_RATIOS,
    ),
    "nano-banana-2-4k-cl": ImageModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_sizes=None,
        supported_ratios=_GRSAI_EXTENDED_RATIOS,
    ),
}


def register_grsai_image_capability(*, model_prefix: str, capability: ImageModelCapability) -> None:
    prefix = model_prefix.strip().lower()
    if not prefix:
        raise ValueError("model_prefix must not be empty")
    _GRSAI_MODEL_OVERRIDES[prefix] = capability


def clear_grsai_image_capability_overrides() -> None:
    _GRSAI_MODEL_OVERRIDES.clear()


def _pick_override(model: str | None) -> ImageModelCapability | None:
    if not model:
        return None
    value = model.strip().lower()
    if not value:
        return None
    if value in _GRSAI_MODEL_OVERRIDES:
        return _GRSAI_MODEL_OVERRIDES[value]
    for prefix, cap in sorted(_GRSAI_MODEL_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True):
        if value.startswith(prefix):
            return cap
    return None


def resolve_grsai_image_capability(model: str | None) -> ImageModelCapability:
    return _pick_override(model) or _GRSAI_DEFAULT
```

- [ ] **Step 5: Wire grsai into the dispatch functions**

In `app/core/integrations/image_capabilities.py`, modify three functions:

In `register_image_model_capability`, add a `grsai` branch before the final `volcengine` fallback:

```python
def register_image_model_capability(
    *,
    provider: ProviderKey,
    model_prefix: str,
    capability: ImageModelCapability,
) -> None:
    """兼容入口：注册模型能力覆盖（按前缀匹配，大小写不敏感）。"""
    if provider == "openai":
        from app.core.integrations.openai.image_capabilities import register_openai_image_capability

        register_openai_image_capability(model_prefix=model_prefix, capability=capability)
        return
    if provider == "runninghub":
        from app.core.integrations.runninghub.image_capabilities import register_runninghub_image_capability

        register_runninghub_image_capability(model_prefix=model_prefix, capability=capability)
        return
    if provider == "grsai":
        from app.core.integrations.grsai.image_capabilities import register_grsai_image_capability

        register_grsai_image_capability(model_prefix=model_prefix, capability=capability)
        return
    from app.core.integrations.volcengine.image_capabilities import register_volcengine_image_capability

    register_volcengine_image_capability(model_prefix=model_prefix, capability=capability)
```

In `clear_image_model_capability_overrides`, add grsai to both the `provider is None` branch and as an explicit branch:

```python
def clear_image_model_capability_overrides(*, provider: ProviderKey | None = None) -> None:
    """兼容入口：清空能力覆盖；供测试或重置场景使用。"""
    from app.core.integrations.openai.image_capabilities import clear_openai_image_capability_overrides
    from app.core.integrations.volcengine.image_capabilities import clear_volcengine_image_capability_overrides

    if provider is None:
        from app.core.integrations.runninghub.image_capabilities import clear_runninghub_image_capability_overrides
        from app.core.integrations.grsai.image_capabilities import clear_grsai_image_capability_overrides

        clear_openai_image_capability_overrides()
        clear_volcengine_image_capability_overrides()
        clear_runninghub_image_capability_overrides()
        clear_grsai_image_capability_overrides()
        return
    if provider == "openai":
        clear_openai_image_capability_overrides()
        return
    if provider == "runninghub":
        from app.core.integrations.runninghub.image_capabilities import clear_runninghub_image_capability_overrides

        clear_runninghub_image_capability_overrides()
        return
    if provider == "grsai":
        from app.core.integrations.grsai.image_capabilities import clear_grsai_image_capability_overrides

        clear_grsai_image_capability_overrides()
        return
    clear_volcengine_image_capability_overrides()
```

In `resolve_image_capability`, add a `grsai` branch before the `volcengine` fallback:

```python
def resolve_image_capability(*, provider: ProviderKey, model: str | None) -> ImageModelCapability:
    if provider == "openai":
        from app.core.integrations.openai.image_capabilities import resolve_openai_image_capability

        return resolve_openai_image_capability(model)
    if provider == "runninghub":
        from app.core.integrations.runninghub.image_capabilities import resolve_runninghub_image_capability

        return resolve_runninghub_image_capability(model)
    if provider == "grsai":
        from app.core.integrations.grsai.image_capabilities import resolve_grsai_image_capability

        return resolve_grsai_image_capability(model)
    from app.core.integrations.volcengine.image_capabilities import resolve_volcengine_image_capability

    return resolve_volcengine_image_capability(model)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_grsai_image_capabilities.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 7: Commit**

```bash
cd /Users/findhappylee/workspace/github/Jellyfish
git add backend/app/core/integrations/grsai/__init__.py backend/app/core/integrations/grsai/image_capabilities.py backend/app/core/integrations/image_capabilities.py backend/tests/test_grsai_image_capabilities.py
git commit -m "feat: add grsai image capability resolver with ratio overrides"
```

---

### Task 3: HTTP Client

**Files:**
- Create: `app/core/integrations/grsai/client.py`
- Test: `tests/test_grsai_client.py`

**Interfaces:**
- Consumes: `httpx.AsyncClient`
- Produces: `submit_grsai_task(base_url: str, api_key: str, request_body: dict[str, Any], *, timeout_s: float = 60.0) -> str` — returns task ID; `query_grsai_result(base_url: str, api_key: str, task_id: str, *, timeout_s: float = 60.0) -> dict[str, Any]` — returns raw response dict

- [ ] **Step 1: Write the failing tests**

Create `tests/test_grsai_client.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_grsai_client.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.integrations.grsai.client'`

- [ ] **Step 3: Create the client module**

Create `app/core/integrations/grsai/client.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_grsai_client.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/findhappylee/workspace/github/Jellyfish
git add backend/app/core/integrations/grsai/client.py backend/tests/test_grsai_client.py
git commit -m "feat: add grsai http client for submit and query endpoints"
```

---

### Task 4: Image Adapter

**Files:**
- Create: `app/core/integrations/grsai/images.py`
- Test: `tests/test_grsai_image_adapter.py`

**Interfaces:**
- Consumes: `ProviderConfig` from `app.core.contracts.provider`; `ImageGenerationInput`, `ImageGenerationResult`, `ImageItem` from `app.core.contracts.image_generation`; `submit_grsai_task`, `query_grsai_result` from `app.core.integrations.grsai.client`
- Produces: `GrsaiImageApiAdapter` class with `async def generate(*, cfg: ProviderConfig, inp: ImageGenerationInput, timeout_s: float) -> ImageGenerationResult`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_grsai_image_adapter.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_grsai_image_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.core.integrations.grsai.images'`

- [ ] **Step 3: Create the adapter module**

Create `app/core/integrations/grsai/images.py`:

```python
"""Grsai 图片适配器：adapter 内部完成 submit → poll，对外同步语义。"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from app.core.contracts.image_generation import (
    ImageGenerationInput,
    ImageGenerationResult,
    ImageItem,
)
from app.core.contracts.provider import ProviderConfig
from app.core.integrations.grsai import client as grsai_client

_GRSAI_DEFAULT_BASE_URL = "https://grsai.dakka.com.cn"
_GRSAI_POLL_INTERVAL_S = 5.0
_GRSAI_DEFAULT_IMAGE_SIZE = "1K"


class GrsaiImageApiAdapter:
    """Grsai 图片生成 HTTP；无状态。"""

    async def generate(
        self,
        *,
        cfg: ProviderConfig,
        inp: ImageGenerationInput,
        timeout_s: float,
    ) -> ImageGenerationResult:
        base_url = (cfg.base_url or _GRSAI_DEFAULT_BASE_URL).rstrip("/")
        request_body = _build_request_body(inp)

        task_id = await grsai_client.submit_grsai_task(
            base_url, cfg.api_key, request_body, timeout_s=timeout_s
        )

        data = await _poll_until_done(base_url, cfg.api_key, task_id, timeout_s)
        return _parse_result(data, task_id)


def _build_request_body(inp: ImageGenerationInput) -> dict[str, Any]:
    body: dict[str, Any] = {
        "model": inp.model or "",
        "prompt": inp.prompt,
        "images": _collect_image_strings(inp),
        "aspectRatio": inp.target_ratio or "1:1",
        "replyType": "async",
    }
    if _is_nano_banana_family(inp.model):
        body["imageSize"] = _resolve_image_size(inp)
    return body


def _is_nano_banana_family(model: str | None) -> bool:
    return (model or "").strip().lower().startswith("nano-banana")


def _resolve_image_size(inp: ImageGenerationInput) -> str:
    if inp.resolution_profile == "high":
        return "2K"
    return _GRSAI_DEFAULT_IMAGE_SIZE


def _collect_image_strings(inp: ImageGenerationInput) -> list[str]:
    images: list[str] = []
    for ref in inp.images or []:
        if ref.image_url:
            images.append(ref.image_url)
    return images


async def _poll_until_done(
    base_url: str,
    api_key: str,
    task_id: str,
    timeout_s: float,
    interval: float = _GRSAI_POLL_INTERVAL_S,
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout_s
    while True:
        data = await grsai_client.query_grsai_result(base_url, api_key, task_id, timeout_s=timeout_s)
        status = str(data.get("status") or "")
        if status == "succeeded":
            return data
        if status in ("failed", "violation"):
            error = str(data.get("error") or status)
            raise RuntimeError(f"Grsai 任务失败: {error}")
        if time.monotonic() >= deadline:
            raise TimeoutError(f"Grsai 任务轮询超时: task_id={task_id}")
        await asyncio.sleep(interval)


def _parse_result(data: dict[str, Any], task_id: str) -> ImageGenerationResult:
    raw_items = data.get("results") or []
    images: list[ImageItem] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if url:
            images.append(ImageItem(url=url))
    if not images:
        raise RuntimeError(f"Grsai 任务完成但无可用结果: {data!r}")
    return ImageGenerationResult(
        images=images,
        provider="grsai",
        provider_task_id=task_id,
        status="succeeded",
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_grsai_image_adapter.py -v`
Expected: PASS (all 6 tests)

- [ ] **Step 5: Commit**

```bash
cd /Users/findhappylee/workspace/github/Jellyfish
git add backend/app/core/integrations/grsai/images.py backend/tests/test_grsai_image_adapter.py
git commit -m "feat: add grsai image adapter with async polling"
```

---

### Task 5: Task Layer Wiring

**Files:**
- Modify: `app/core/tasks/image_generation_tasks.py:11-37,148-173,221-232`
- Modify: `app/core/tasks/bootstrap.py:10-18`
- Test: `tests/test_task_registry.py`

**Interfaces:**
- Consumes: `GrsaiImageApiAdapter` from `app.core.integrations.grsai.images`; existing `AbstractImageGenerationTask` base class
- Produces: `GrsaiImageGenerationTask` class; `ImageGenerationTask._build_grsai_impl` static method; `("image_generation", "grsai", ...)` in `TASK_ADAPTER_SPECS`

- [ ] **Step 1: Write the failing test**

Add this test to the end of `tests/test_task_registry.py`:

```python
def test_grsai_image_task_builds_adapter_impl() -> None:
    from app.core.tasks.image_generation_tasks import ImageGenerationTask, GrsaiImageGenerationTask
    from app.core.contracts.image_generation import ImageGenerationInput
    from app.core.contracts.provider import ProviderConfig

    impl = ImageGenerationTask._build_grsai_impl(
        provider_config=ProviderConfig(provider="grsai", api_key="k", base_url="https://grsai.dakka.com.cn"),
        input_=ImageGenerationInput(prompt="x", model="nano-banana-2"),
        timeout_s=60.0,
    )
    assert isinstance(impl, GrsaiImageGenerationTask)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_task_registry.py::test_grsai_image_task_builds_adapter_impl -v`
Expected: FAIL with `AttributeError: type object 'ImageGenerationTask' has no attribute '_build_grsai_impl'`

- [ ] **Step 3: Add GrsaiImageGenerationTask and _build_grsai_impl**

In `app/core/tasks/image_generation_tasks.py`:

Add the import for `GrsaiImageApiAdapter` after line 13 (`from app.core.integrations.runninghub.images import RunningHubImageApiAdapter`):

```python
from app.core.integrations.grsai.images import GrsaiImageApiAdapter
```

Add `"GrsaiImageGenerationTask"` to the `__all__` list (after `"RunningHubImageGenerationTask"`):

```python
__all__ = [
    "ImageGenerationInput",
    "ImageGenerationResult",
    "ImageItem",
    "InputImageRef",
    "ResponseFormat",
    "AbstractImageGenerationTask",
    "OpenAIImageGenerationTask",
    "VolcengineImageGenerationTask",
    "RunningHubImageGenerationTask",
    "GrsaiImageGenerationTask",
    "ImageGenerationTask",
]
```

Add the `GrsaiImageGenerationTask` class after `RunningHubImageGenerationTask` (before `ImageGenerationTask`):

```python
class GrsaiImageGenerationTask(AbstractImageGenerationTask):
    """Grsai 图片：adapter 内部完成 submit→poll，Task 层不轮询。"""

    def __init__(
        self,
        *,
        adapter: GrsaiImageApiAdapter | None = None,
        provider_config: ProviderConfig,
        input_: ImageGenerationInput,
        timeout_s: float = 600.0,
    ) -> None:
        super().__init__(provider_config=provider_config, input_=input_, timeout_s=timeout_s)
        self._adapter = adapter or GrsaiImageApiAdapter()
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

Add the `_build_grsai_impl` static method to `ImageGenerationTask` (after `_build_runninghub_impl`):

```python
    @staticmethod
    def _build_grsai_impl(
        *,
        provider_config: ProviderConfig,
        input_: ImageGenerationInput,
        timeout_s: float = 600.0,
    ) -> AbstractImageGenerationTask:
        return GrsaiImageGenerationTask(
            provider_config=provider_config,
            input_=input_,
            timeout_s=timeout_s,
        )
```

- [ ] **Step 4: Register the task adapter in bootstrap**

In `app/core/tasks/bootstrap.py`, add the grsai entry to `TASK_ADAPTER_SPECS` (after the runninghub image entry):

```python
TASK_ADAPTER_SPECS = (
    ("image_generation", "openai", ImageGenerationTask._build_openai_impl),
    ("image_generation", "volcengine", ImageGenerationTask._build_volcengine_impl),
    ("image_generation", "runninghub", ImageGenerationTask._build_runninghub_impl),
    ("image_generation", "grsai", ImageGenerationTask._build_grsai_impl),
    ("video_generation", "openai", VideoGenerationTask._build_openai_impl),
    ("video_generation", "volcengine", VideoGenerationTask._build_volcengine_impl),
    ("video_generation", "runninghub", VideoGenerationTask._build_runninghub_impl),
    ("video_generation", "runninghub-enterprise", VideoGenerationTask._build_runninghub_enterprise_impl),
)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_task_registry.py::test_grsai_image_task_builds_adapter_impl -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd /Users/findhappylee/workspace/github/Jellyfish
git add backend/app/core/tasks/image_generation_tasks.py backend/app/core/tasks/bootstrap.py backend/tests/test_task_registry.py
git commit -m "feat: wire grsai image generation task adapter"
```

---

### Task 6: DB Bootstrap for Provider and 13 Models

**Files:**
- Modify: `app/services/llm/model_bootstrap.py:8-9,273-367`
- Test: `tests/test_grsai_model_bootstrap.py`

**Interfaces:**
- Consumes: `Model`, `ModelCategoryKey`, `Provider`, `ProviderStatus` from `app.models.llm`; existing `bootstrap_builtin_db_resources` function
- Produces: `_GRSAI_PROVIDER_DEFAULTS` dict; `_GRSAI_MODELS` list (13 model dicts); extended `bootstrap_builtin_db_resources` that upserts Grsai provider + 13 models

- [ ] **Step 1: Write the failing tests**

Create `tests/test_grsai_model_bootstrap.py`:

```python
from __future__ import annotations

import pytest
import pytest_asyncio
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


@pytest_asyncio.fixture
async def db():
    session, engine = await _build_session()
    try:
        yield session
    finally:
        await session.close()
        await engine.dispose()


@pytest.mark.asyncio
async def test_bootstrap_creates_grsai_provider_and_13_models(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    provider = (await db.execute(select(Provider).where(Provider.id == "grsai"))).scalar_one()
    assert provider.name == "Grsai"
    assert provider.base_url == "https://grsai.dakka.com.cn"
    assert provider.status == ProviderStatus.testing

    models = (await db.execute(select(Model).where(Model.provider_id == "grsai"))).scalars().all()
    assert len(models) == 13
    nano_count = sum(1 for m in models if m.params.get("family") == "nano-banana")
    gpt_count = sum(1 for m in models if m.params.get("family") == "gpt-image-2")
    assert nano_count == 11
    assert gpt_count == 2
    for m in models:
        assert m.category == ModelCategoryKey.image


@pytest.mark.asyncio
async def test_bootstrap_grsai_is_idempotent(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    models = (await db.execute(select(Model).where(Model.provider_id == "grsai"))).scalars().all()
    assert len(models) == 13


@pytest.mark.asyncio
async def test_bootstrap_preserves_grsai_user_api_key(db: AsyncSession) -> None:
    db.add(Provider(
        id="grsai",
        name="Old Name",
        base_url="https://custom.grsai",
        api_key="user-secret-key",
        api_secret="",
        description="",
        status=ProviderStatus.active,
        created_by="user",
    ))
    await db.commit()

    await bootstrap_builtin_db_resources(db)
    await db.commit()

    provider = (await db.execute(select(Provider).where(Provider.id == "grsai"))).scalar_one()
    assert provider.api_key == "user-secret-key"
    assert provider.base_url == "https://custom.grsai"
    assert provider.status == ProviderStatus.active


@pytest.mark.asyncio
async def test_bootstrap_grsai_models_have_family_param(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    nano = (await db.execute(select(Model).where(Model.id == "grsai-nano-banana-2"))).scalar_one()
    assert nano.params["family"] == "nano-banana"
    assert nano.name == "nano-banana-2"

    gpt = (await db.execute(select(Model).where(Model.id == "grsai-gpt-image-2-vip"))).scalar_one()
    assert gpt.params["family"] == "gpt-image-2"
    assert gpt.name == "gpt-image-2-vip"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_grsai_model_bootstrap.py -v`
Expected: FAIL with provider "grsai" not found or model count mismatch

- [ ] **Step 3: Add Grsai provider defaults and model list**

In `app/services/llm/model_bootstrap.py`, add after the `_RUNNINGHUB_ENTERPRISE_MODELS` list (before `bootstrap_builtin_db_resources`):

```python
_GRSAI_PROVIDER_DEFAULTS = {
    "id": "grsai",
    "name": "Grsai",
    "base_url": "https://grsai.dakka.com.cn",
    "image_base_url": None,
    "video_base_url": None,
    "api_secret": "",
    "description": "Grsai 图片生成：nano-banana 系列 + gpt-image-2 系列",
    "status": ProviderStatus.testing,
    "created_by": "system",
}

_GRSAI_MODELS: list[dict] = [
    {
        "id": "grsai-nano-banana",
        "name": "nano-banana",
        "category": ModelCategoryKey.image,
        "params": {"family": "nano-banana"},
        "description": "Nano Banana 基础模型，支持多比例与 1K/2K/4K 输出",
    },
    {
        "id": "grsai-nano-banana-fast",
        "name": "nano-banana-fast",
        "category": ModelCategoryKey.image,
        "params": {"family": "nano-banana"},
        "description": "Nano Banana Fast，快速生成版本",
    },
    {
        "id": "grsai-nano-banana-2",
        "name": "nano-banana-2",
        "category": ModelCategoryKey.image,
        "params": {"family": "nano-banana"},
        "description": "Nano Banana 2，额外支持 1:4/4:1/1:8/8:1 比例",
    },
    {
        "id": "grsai-nano-banana-2-cl",
        "name": "nano-banana-2-cl",
        "category": ModelCategoryKey.image,
        "params": {"family": "nano-banana"},
        "description": "Nano Banana 2 CL 版本",
    },
    {
        "id": "grsai-nano-banana-2-2k-cl",
        "name": "nano-banana-2-2k-cl",
        "category": ModelCategoryKey.image,
        "params": {"family": "nano-banana"},
        "description": "Nano Banana 2 2K CL 版本",
    },
    {
        "id": "grsai-nano-banana-2-4k-cl",
        "name": "nano-banana-2-4k-cl",
        "category": ModelCategoryKey.image,
        "params": {"family": "nano-banana"},
        "description": "Nano Banana 2 4K CL 版本",
    },
    {
        "id": "grsai-nano-banana-pro",
        "name": "nano-banana-pro",
        "category": ModelCategoryKey.image,
        "params": {"family": "nano-banana"},
        "description": "Nano Banana Pro，高质量版本",
    },
    {
        "id": "grsai-nano-banana-pro-vt",
        "name": "nano-banana-pro-vt",
        "category": ModelCategoryKey.image,
        "params": {"family": "nano-banana"},
        "description": "Nano Banana Pro VT 版本",
    },
    {
        "id": "grsai-nano-banana-pro-cl",
        "name": "nano-banana-pro-cl",
        "category": ModelCategoryKey.image,
        "params": {"family": "nano-banana"},
        "description": "Nano Banana Pro CL 版本",
    },
    {
        "id": "grsai-nano-banana-pro-vip",
        "name": "nano-banana-pro-vip",
        "category": ModelCategoryKey.image,
        "params": {"family": "nano-banana"},
        "description": "Nano Banana Pro VIP 版本",
    },
    {
        "id": "grsai-nano-banana-pro-4k-vip",
        "name": "nano-banana-pro-4k-vip",
        "category": ModelCategoryKey.image,
        "params": {"family": "nano-banana"},
        "description": "Nano Banana Pro 4K VIP 版本",
    },
    {
        "id": "grsai-gpt-image-2",
        "name": "gpt-image-2",
        "category": ModelCategoryKey.image,
        "params": {"family": "gpt-image-2"},
        "description": "GPT Image 2，支持比例或像素值",
    },
    {
        "id": "grsai-gpt-image-2-vip",
        "name": "gpt-image-2-vip",
        "category": ModelCategoryKey.image,
        "params": {"family": "gpt-image-2"},
        "description": "GPT Image 2 VIP，支持 1K-4K 像素值",
    },
]
```

- [ ] **Step 4: Extend bootstrap_builtin_db_resources to upsert Grsai**

In `app/services/llm/model_bootstrap.py`, inside `bootstrap_builtin_db_resources`, after the enterprise provider block (before the personal models loop), add the Grsai provider upsert:

```python
    # --- Grsai provider ---
    grsai_provider = (
        await session.execute(select(Provider).where(Provider.id == "grsai"))
    ).scalar_one_or_none()

    if grsai_provider is None:
        grsai_provider = Provider(
            id=_GRSAI_PROVIDER_DEFAULTS["id"],
            name=_GRSAI_PROVIDER_DEFAULTS["name"],
            base_url=_GRSAI_PROVIDER_DEFAULTS["base_url"],
            image_base_url=_GRSAI_PROVIDER_DEFAULTS["image_base_url"],
            video_base_url=_GRSAI_PROVIDER_DEFAULTS["video_base_url"],
            api_key="",
            api_secret=_GRSAI_PROVIDER_DEFAULTS["api_secret"],
            description=_GRSAI_PROVIDER_DEFAULTS["description"],
            status=_GRSAI_PROVIDER_DEFAULTS["status"],
            created_by=_GRSAI_PROVIDER_DEFAULTS["created_by"],
        )
        session.add(grsai_provider)
    # 已存在则不覆盖用户字段
```

After the enterprise models loop (at the end of the function), add the Grsai models upsert:

```python
    # --- Grsai models ---
    for spec in _GRSAI_MODELS:
        model = (
            await session.execute(select(Model).where(Model.id == spec["id"]))
        ).scalar_one_or_none()
        if model is None:
            model = Model(
                id=spec["id"],
                name=spec["name"],
                category=spec["category"],
                provider_id="grsai",
                params=spec["params"],
                description=spec["description"],
                created_by="system",
            )
            session.add(model)
        else:
            model.name = spec["name"]
            model.category = spec["category"]
            model.provider_id = "grsai"
            model.params = spec["params"]
            model.description = spec["description"]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_grsai_model_bootstrap.py -v`
Expected: PASS (all 4 tests)

- [ ] **Step 6: Commit**

```bash
cd /Users/findhappylee/workspace/github/Jellyfish
git add backend/app/services/llm/model_bootstrap.py backend/tests/test_grsai_model_bootstrap.py
git commit -m "feat: add db bootstrap for grsai provider and 13 image models"
```

---

### Task 7: Model Identifier Verification

**Files:**
- Modify: `tests/test_runninghub_model_identifier.py` (add test only, no implementation change)

**Interfaces:**
- Consumes: `resolve_model_identifier` from `app.services.llm.model_identifier` (existing, falls through to `return model.name` for unknown providers)
- Produces: test confirming `resolve_model_identifier(model, "grsai")` returns `model.name` directly

- [ ] **Step 1: Write the failing test**

Add this test to the end of `tests/test_runninghub_model_identifier.py`:

```python
def test_grsai_returns_model_name() -> None:
    model = _make_model(name="nano-banana-2")
    assert resolve_model_identifier(model, "grsai") == "nano-banana-2"
```

- [ ] **Step 2: Run test to verify it fails (or passes if fallthrough already works)**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && .venv/bin/python -m pytest tests/test_runninghub_model_identifier.py::test_grsai_returns_model_name -v`
Expected: PASS (the existing `resolve_model_identifier` falls through to `return model.name` for any provider without a special branch, so this test should pass immediately)

Note: If the test passes on the first run, that's expected — the goal is to verify and lock in the behavior with a test. No implementation change is needed.

- [ ] **Step 3: Commit**

```bash
cd /Users/findhappylee/workspace/github/Jellyfish
git add backend/tests/test_runninghub_model_identifier.py
git commit -m "test: verify grsai model identifier falls through to model.name"
```

---

## Self-Review Notes

**Spec coverage:**
- ✅ Provider key + spec + alias resolution → Task 1
- ✅ Image capability resolver → Task 2
- ✅ HTTP client (submit + query) → Task 3
- ✅ Image adapter with async polling → Task 4
- ✅ Task layer wiring → Task 5
- ✅ DB bootstrap (provider + 13 models) → Task 6
- ✅ Model identifier verification → Task 7
- ✅ All 13 models registered (11 nano-banana + 2 gpt-image-2) → Task 6
- ✅ `imageSize` only for nano-banana family → Task 4 (`_is_nano_banana_family` check)
- ✅ `replyType="async"` → Task 4 (`_build_request_body`)
- ✅ Polling with 5s interval, 600s timeout → Task 4 (`_poll_until_done`)
- ✅ Terminal status handling (succeeded/failed/violation) → Task 4
- ✅ Empty results edge case → Task 4 (`_parse_result` raises)
- ✅ China node default base URL → Tasks 1, 4, 6
- ✅ `model.name` used as API model name → Task 7 verifies

**Type consistency:**
- `submit_grsai_task(base_url, api_key, request_body, *, timeout_s=60.0) -> str` — consistent across Task 3 (definition) and Task 4 (usage)
- `query_grsai_result(base_url, api_key, task_id, *, timeout_s=60.0) -> dict[str, Any]` — consistent across Task 3 (definition) and Task 4 (usage)
- `GrsaiImageApiAdapter.generate(*, cfg, inp, timeout_s) -> ImageGenerationResult` — consistent across Task 4 (definition) and Task 5 (usage)
- `GrsaiImageGenerationTask` class name — consistent across Task 5 (definition) and test
- `_build_grsai_impl` static method — consistent across Task 5 (definition) and bootstrap.py registration
- Model IDs `grsai-{model_name}` — consistent across Task 6 (definition) and tests
