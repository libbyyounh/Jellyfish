# RunningHub 企业版供应商 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `runninghub-enterprise` as a second RunningHub provider with 14 enterprise video models, ported verbatim from `~/Downloads/toonflow-runninghub-enterprise.ts`.

**Architecture:** Separate subpackage `app/core/integrations/runninghub/enterprise/` with its own client, request builders, video adapter, and capability resolver. Reuses personal provider's `upload_media` / `query_task` / `poll_until_done` from `runninghub/client.py`. Enterprise API uses direct REST (`/openapi/v2/{vendor}/{model}/{action}` + JSON body) instead of personal ComfyUI nodeInfoList.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy async, httpx, pytest + pytest-asyncio, Pydantic v2.

## Global Constraints

- **ProviderKey**: `"runninghub-enterprise"` added to the `Literal` in `app/core/contracts/provider.py`.
- **Provider spec**: `key="runninghub-enterprise"`, `display_name="RunningHub 企业版"`, aliases `("runninghub-enterprise", "rh-enterprise", "RunningHub Enterprise")`, `supported_categories=(ModelCategoryKey.video,)` (no image/text), `default_base_url="https://www.runninghub.cn"`.
- **Alias resolution order**: `resolve_provider_key_from_name` MUST check `"runninghub-enterprise"` BEFORE the existing `if "runninghub" in alias` fallback (otherwise `"runninghub-enterprise"` gets caught by the personal fallback).
- **Contract extension**: `VideoGenerationInput` gets 3 new Optional fields (`reference_frames_base64: Optional[list[str]]`, `resolution: Optional[str]`, `audio: Optional[bool]`), all default `None`. The `require_prompt_or_any_reference` validator MUST also check `reference_frames_base64` as a valid reference.
- **Model ID scheme**: `runninghub-enterprise-{modelName with / replaced by -}` (e.g. `wan-2.7/image-to-video` → `runninghub-enterprise-wan-2.7-image-to-video`).
- **Request body field names**: Ported verbatim from .ts — do NOT "improve" casing. Notably: `firstImageUrl`/`lastImageUrl` for wan-2.7 and kling, but `firstFrameUrl`/`lastFrameUrl` for rhart-video-v3.1-fast.
- **Duration field**: Some builders send `str(duration)`, some send `int(duration)`. Match .ts exactly per model.
- **Resolution field**: Some builders keep `"720P"`, some lowercase to `"720p"` via `.replace("P", "p")`. Match .ts exactly per model.
- **Audio field**: Kling builders use `sound: inp.audio is not False` (None → True). Other models either omit the field or handle it differently. Match .ts exactly.
- **Multi-reference NO padding**: Enterprise `imageReference:N` modes send the actual number of images (≤N), unlike personal 4-frame LTX which pads. Filter `None` values, do NOT pad.
- **`imageReference:3` field source**: Uses existing `first_frame_base64` + `last_frame_base64` + `key_frame_base64` (backward compatible with frontend). Only `imageReference:7` / `imageReference:9` use the new `reference_frames_base64` field.
- **Capability resolver**: Takes `model: str | None` (NOT a `Model` object) — must hardcode per-model-prefix overrides, same pattern as personal provider. `VideoModelCapability` has NO `allowed_durations`/`allowed_resolutions` fields; use `min_seconds`/`max_seconds` only.
- **Skipping `happyhorse-1.0/video-edit`**: Needs video reference input; Jellyfish has no video input contract. 14/15 models implemented.
- **DB bootstrap idempotent**: Provider row preserves user `api_key`/`base_url`/`status`; model rows refresh `name`/`params`/`description`.
- **Test pattern**: Use `httpx.MockTransport` for HTTP tests (see `test_runninghub_client.py`); use `monkeypatch` for adapter tests (see `test_runninghub_video_adapter.py`); use in-memory SQLite + `pytest_asyncio.fixture` for DB tests (see `test_runninghub_model_bootstrap.py`).

---

## File Structure

### New files

```
backend/app/core/integrations/runninghub/enterprise/
├── __init__.py              # docstring only
├── client.py                # submit_enterprise_task()
├── request_builders.py      # EnterpriseVideoBuildSpec dataclass + 14 builders + ENTERPRISE_VIDEO_BUILDERS dict
├── video.py                 # RunningHubEnterpriseVideoApiAdapter + _resolve_enterprise_image_urls
└── video_capabilities.py    # resolve_runninghub_enterprise_video_capability(model)
```

### New test files

```
backend/tests/
├── test_runninghub_enterprise_client.py            # 3 tests
├── test_runninghub_enterprise_request_builders.py  # 14 tests (one per model)
├── test_runninghub_enterprise_video_adapter.py     # 6 tests
└── test_runninghub_enterprise_capabilities.py      # 4 tests
```

### Modified files

| File | Change |
|------|--------|
| `app/core/contracts/provider.py` | `ProviderKey` Literal += `"runninghub-enterprise"` |
| `app/core/contracts/video_generation.py` | += `reference_frames_base64` / `resolution` / `audio`; update validator |
| `app/services/llm/provider_bootstrap.py` | += enterprise `ProviderSpec` |
| `app/services/llm/provider_registry.py` | += enterprise check in `resolve_provider_key_from_name` BEFORE personal fallback |
| `app/core/integrations/video_capabilities.py` | += enterprise branch in `register_video_model_capability` / `clear_video_model_capability_overrides` / `resolve_video_capability` |
| `app/core/tasks/video_generation_tasks.py` | += `_build_runninghub_enterprise_impl` static method + import |
| `app/core/tasks/bootstrap.py` | `TASK_ADAPTER_SPECS` += enterprise entry |
| `app/services/llm/model_identifier.py` | += enterprise branch returning `params["model_name"]` |
| `app/services/llm/model_bootstrap.py` | += enterprise provider + 14 model rows |
| `backend/tests/test_task_registry.py` | += 2 enterprise tests |
| `backend/tests/test_runninghub_model_bootstrap.py` | += 3 enterprise tests |
| `backend/tests/test_runninghub_model_identifier.py` | += 2 enterprise tests |

---

## Task 1: ProviderKey + ProviderSpec + alias resolution

**Files:**
- Modify: `backend/app/core/contracts/provider.py`
- Modify: `backend/app/services/llm/provider_bootstrap.py`
- Modify: `backend/app/services/llm/provider_registry.py`
- Test: `backend/tests/test_task_registry.py` (extend)

**Interfaces:**
- Consumes: `ModelCategoryKey` from `app.models.llm`
- Produces: `ProviderKey` Literal now includes `"runninghub-enterprise"`; `ProviderSpec` registered with key `"runninghub-enterprise"`; `resolve_provider_key_from_name("runninghub-enterprise")` returns `"runninghub-enterprise"` (not caught by personal fallback).

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_task_registry.py` (append before EOF):

```python
def test_resolve_provider_key_for_runninghub_enterprise_aliases() -> None:
    from app.services.llm.provider_registry import resolve_provider_key_from_name
    from app.services.llm.provider_bootstrap import bootstrap_builtin_providers

    bootstrap_builtin_providers()
    assert resolve_provider_key_from_name("runninghub-enterprise") == "runninghub-enterprise"
    assert resolve_provider_key_from_name("RunningHub Enterprise") == "runninghub-enterprise"
    assert resolve_provider_key_from_name("rh-enterprise") == "runninghub-enterprise"


def test_runninghub_enterprise_provider_spec_registered() -> None:
    from app.services.llm.provider_registry import get_provider_spec
    from app.services.llm.provider_bootstrap import bootstrap_builtin_providers
    from app.models.llm import ModelCategoryKey

    bootstrap_builtin_providers()
    spec = get_provider_spec("runninghub-enterprise")
    assert spec.display_name == "RunningHub 企业版"
    assert ModelCategoryKey.video in spec.supported_categories
    assert ModelCategoryKey.image not in spec.supported_categories
    assert ModelCategoryKey.text not in spec.supported_categories
    assert spec.default_base_url == "https://www.runninghub.cn"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_task_registry.py::test_resolve_provider_key_for_runninghub_enterprise_aliases tests/test_task_registry.py::test_runninghub_enterprise_provider_spec_registered -v`
Expected: FAIL — `runninghub-enterprise` not registered, alias resolution returns `"runninghub"` (caught by personal fallback).

- [ ] **Step 3: Add `"runninghub-enterprise"` to ProviderKey**

Edit `backend/app/core/contracts/provider.py`:

```python
ProviderKey = Literal["openai", "volcengine", "runninghub", "runninghub-enterprise"]
```

- [ ] **Step 4: Register enterprise ProviderSpec**

Edit `backend/app/services/llm/provider_bootstrap.py` — add a new `ProviderSpec` to the `register_many` list inside `bootstrap_builtin_providers()`:

```python
            ProviderSpec(
                key="runninghub-enterprise",
                display_name="RunningHub 企业版",
                aliases=("runninghub-enterprise", "rh-enterprise", "RunningHub Enterprise"),
                supported_categories=(ModelCategoryKey.video,),
                default_base_url="https://www.runninghub.cn",
            ),
```

- [ ] **Step 5: Fix alias resolution order**

Edit `backend/app/services/llm/provider_registry.py` — in `resolve_provider_key_from_name`, add enterprise check BEFORE the personal `if "runninghub" in alias` fallback:

```python
def resolve_provider_key_from_name(name: str) -> str:
    alias = _norm(name)
    with _LOCK:
        key = _KEY_BY_ALIAS.get(alias)
    if key:
        return key
    # 兼容历史"包含式"命名。
    if "runninghub-enterprise" in alias or "rh-enterprise" in alias:
        return "runninghub-enterprise"
    if "volc" in alias or "doubao" in alias or "bytedance" in alias:
        return "volcengine"
    if "runninghub" in alias or alias == "rh":
        return "runninghub"
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Unsupported provider name: {name!r}",
    )
```

- [ ] **Step 6: Run tests to verify pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_task_registry.py::test_resolve_provider_key_for_runninghub_enterprise_aliases tests/test_task_registry.py::test_runninghub_enterprise_provider_spec_registered tests/test_task_registry.py::test_resolve_provider_key_for_runninghub_aliases -v`
Expected: PASS — all 3 tests pass (including existing personal alias test, confirming no regression).

- [ ] **Step 7: Commit**

```bash
git add backend/app/core/contracts/provider.py backend/app/services/llm/provider_bootstrap.py backend/app/services/llm/provider_registry.py backend/tests/test_task_registry.py
git commit -m "feat: register runninghub-enterprise provider key and aliases"
```

---

## Task 2: VideoGenerationInput contract extension

**Files:**
- Modify: `backend/app/core/contracts/video_generation.py`
- Test: `backend/tests/test_video_generation_input.py` (new)

**Interfaces:**
- Consumes: nothing new
- Produces: `VideoGenerationInput.reference_frames_base64: Optional[list[str]]`, `VideoGenerationInput.resolution: Optional[str]`, `VideoGenerationInput.audio: Optional[bool]` — all default `None`. Validator `require_prompt_or_any_reference` now also accepts `reference_frames_base64` as a valid reference.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_video_generation_input.py`:

```python
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.contracts.video_generation import VideoGenerationInput


def test_accepts_new_optional_fields() -> None:
    inp = VideoGenerationInput(
        prompt="run",
        ratio="16:9",
        reference_frames_base64=["data:image/png;base64,iVBORw0KGgo=", "data:image/png;base64,iVBORw0KGgo="],
        resolution="720P",
        audio=True,
    )
    assert inp.reference_frames_base64 == ["data:image/png;base64,iVBORw0KGgo=", "data:image/png;base64,iVBORw0KGgo="]
    assert inp.resolution == "720P"
    assert inp.audio is True


def test_new_fields_default_none() -> None:
    inp = VideoGenerationInput(prompt="run", ratio="16:9")
    assert inp.reference_frames_base64 is None
    assert inp.resolution is None
    assert inp.audio is None


def test_reference_frames_base64_rejects_non_string_items() -> None:
    with pytest.raises(ValidationError):
        VideoGenerationInput(prompt="run", ratio="16:9", reference_frames_base64=["ok", 123])


def test_reference_frames_base64_counts_as_reference_for_validator() -> None:
    inp = VideoGenerationInput(
        ratio="16:9",
        reference_frames_base64=["data:image/png;base64,iVBORw0KGgo="],
    )
    assert inp.reference_frames_base64 == ["data:image/png;base64,iVBORw0KGgo="]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_video_generation_input.py -v`
Expected: FAIL — `reference_frames_base64` / `resolution` / `audio` not yet fields; `extra="forbid"` rejects them.

- [ ] **Step 3: Extend VideoGenerationInput**

Edit `backend/app/core/contracts/video_generation.py` — add 3 fields after `watermark` and before the `@model_validator`, and update `require_prompt_or_any_reference` to check `reference_frames_base64`:

```python
class VideoGenerationInput(BaseModel):
    """视频生成输入：支持文本提示词 + 可选的多种帧参考图（纯 base64 或 data URL）。"""

    model_config = ConfigDict(extra="forbid")

    prompt: Optional[str] = Field(None, description="文本提示词；可与参考图二选一或同时存在")

    first_frame_base64: Optional[str] = Field(None, description="首帧图：纯 base64 或 data:image/...;base64,...")
    last_frame_base64: Optional[str] = Field(None, description="尾帧图：纯 base64 或 data URL")
    key_frame_base64: Optional[str] = Field(None, description="关键帧图：纯 base64 或 data URL")

    model: Optional[str] = Field(None, description="视频模型名称（可选，供应商透传）")
    ratio: VideoRatio = Field(..., description="视频宽高比，业务层唯一主参数")
    seconds: Optional[int] = Field(None, description="时长（秒）（可选，供应商透传）")
    seed: Optional[int] = Field(
        None,
        ge=-1,
        le=4294967295,
        description="随机种子，-1 或 [0, 2^32-1]，供应商/模型可能有差异",
    )
    watermark: Optional[bool] = Field(None, description="是否包含水印，供应商/模型可能有差异")

    reference_frames_base64: Optional[list[str]] = Field(
        None,
        description="额外参考帧 base64 列表（多图参考模型，如 wan-2.7 reference-to-video 最多 9 张）",
    )
    resolution: Optional[str] = Field(
        None,
        description="分辨率标识（'480P' / '720P' / '1080P' / '4K'），供应商/模型可能有差异",
    )
    audio: Optional[bool] = Field(
        None,
        description="是否生成音频，仅部分模型支持；None 时按 .ts 行为处理（kling 系列默认 True，其他默认 False）",
    )

    @model_validator(mode="after")
    def require_prompt_or_any_reference(self) -> "VideoGenerationInput":
        has_prompt = bool((self.prompt or "").strip())
        has_ref = any(
            [
                _strip_optional_b64(self.first_frame_base64),
                _strip_optional_b64(self.last_frame_base64),
                _strip_optional_b64(self.key_frame_base64),
                bool(self.reference_frames_base64 and any(self.reference_frames_base64)),
            ]
        )
        if not has_prompt and not has_ref:
            raise ValueError("Require prompt or at least one reference frame (base64)")
        return self
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_video_generation_input.py -v`
Expected: PASS — all 4 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/contracts/video_generation.py backend/tests/test_video_generation_input.py
git commit -m "feat: extend VideoGenerationInput with reference_frames_base64, resolution, audio"
```

---

## Task 3: Enterprise HTTP client

**Files:**
- Create: `backend/app/core/integrations/runninghub/enterprise/__init__.py`
- Create: `backend/app/core/integrations/runninghub/enterprise/client.py`
- Test: `backend/tests/test_runninghub_enterprise_client.py` (new)

**Interfaces:**
- Consumes: `httpx`, `json` (stdlib)
- Produces: `submit_enterprise_task(base_url, api_key, endpoint_path, request_body, *, timeout_s=60.0) -> str` — POSTs JSON to `{base_url}{endpoint_path}`, returns `taskId` from response. Raises `RuntimeError` if response lacks `taskId`. Raises `httpx.HTTPStatusError` on non-2xx.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_runninghub_enterprise_client.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_enterprise_client.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.integrations.runninghub.enterprise'`.

- [ ] **Step 3: Create enterprise package __init__.py**

Create `backend/app/core/integrations/runninghub/enterprise/__init__.py`:

```python
"""RunningHub 企业版集成：直接 REST API 适配（万相 / LTX / HappyHorse / 可灵 / 全能视频）。"""
```

- [ ] **Step 4: Create enterprise client**

Create `backend/app/core/integrations/runninghub/enterprise/client.py`:

```python
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
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_enterprise_client.py -v`
Expected: PASS — all 3 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/integrations/runninghub/enterprise/__init__.py backend/app/core/integrations/runninghub/enterprise/client.py backend/tests/test_runninghub_enterprise_client.py
git commit -m "feat: add runninghub enterprise HTTP client"
```

---

## Task 4: Enterprise request builders (14 models)

**Files:**
- Create: `backend/app/core/integrations/runninghub/enterprise/request_builders.py`
- Test: `backend/tests/test_runninghub_enterprise_request_builders.py` (new)

**Interfaces:**
- Consumes: `VideoGenerationInput` from `app.core.contracts.video_generation`
- Produces: `EnterpriseVideoBuildSpec` dataclass with `endpoint_path: str`, `mode: str`, `build_request: Callable[[VideoGenerationInput, list[str]], dict]`. `ENTERPRISE_VIDEO_BUILDERS: dict[str, EnterpriseVideoBuildSpec]` keyed by modelName (14 entries).

**Mode → field mapping (from spec):**
- `singleImage` → `first_frame_base64` → 1 URL
- `startEndRequired` → `first_frame_base64` + `last_frame_base64` (filter None) → 1-2 URLs
- `imageReference:3` → `first/last/key_frame_base64` (filter None) → 1-3 URLs, NO padding
- `imageReference:7` → `reference_frames_base64[:7]` → 1-7 URLs, NO padding
- `imageReference:9` → `reference_frames_base64[:9]` → 1-9 URLs, NO padding

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_runninghub_enterprise_request_builders.py`:

```python
from __future__ import annotations

import pytest

from app.core.contracts.video_generation import VideoGenerationInput
from app.core.integrations.runninghub.enterprise.request_builders import ENTERPRISE_VIDEO_BUILDERS


def _inp(**kw) -> VideoGenerationInput:
    defaults = {"ratio": "16:9", "prompt": "a cat runs"}
    defaults.update(kw)
    return VideoGenerationInput(**defaults)


# ---- wan-2.7/image-to-video (startEndRequired) ----
def test_wan27_image_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["wan-2.7/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/alibaba/wan-2.7/image-to-video"
    assert spec.mode == "startEndRequired"
    body = spec.build_request(_inp(seconds=5, resolution="720P"), ["https://rh/first.png", "https://rh/last.png"])
    assert body == {
        "prompt": "a cat runs",
        "firstImageUrl": "https://rh/first.png",
        "lastImageUrl": "https://rh/last.png",
        "resolution": "720P",
        "duration": "5",
        "promptExtend": True,
        "seed": None,
    }


def test_wan27_image_to_video_single_frame_last_is_none() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["wan-2.7/image-to-video"]
    body = spec.build_request(_inp(seconds=5), ["https://rh/first.png"])
    assert body["lastImageUrl"] is None


# ---- wan-2.7/reference-to-video (imageReference:9) ----
def test_wan27_reference_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["wan-2.7/reference-to-video"]
    assert spec.mode == "imageReference:9"
    urls = ["https://rh/a.png", "https://rh/b.png", "https://rh/c.png"]
    body = spec.build_request(_inp(seconds=5, resolution="1080P"), urls)
    assert body == {
        "prompt": "a cat runs",
        "videoUrls": [],
        "imageUrls": urls,
        "resolution": "1080P",
        "duration": "5",
        "aspectRatio": "16:9",
        "promptExtend": True,
        "seed": None,
    }


# ---- ltx-2.3/image-to-video (singleImage) ----
def test_ltx23_image_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["ltx-2.3/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video/ltx-2.3/image-to-video"
    assert spec.mode == "singleImage"
    body = spec.build_request(_inp(seconds=5, resolution="480P"), ["https://rh/img.png"])
    assert body == {
        "imageUrl": "https://rh/img.png",
        "prompt": "a cat runs",
        "resolution": "480p",
        "aspectRatio": "16:9",
        "duration": 5,
    }


# ---- ltx-2.3/image-to-video-lora (singleImage) ----
def test_ltx23_image_to_video_lora_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["ltx-2.3/image-to-video-lora"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video/ltx-2.3/image-to-video-lora"
    body = spec.build_request(_inp(seconds=5, resolution="480P"), ["https://rh/img.png"])
    assert body == {
        "imageUrl": "https://rh/img.png",
        "resolution": "480p",
        "aspectRatio": "16:9",
        "duration": 5,
        "lora1": "framee_4000.safetensors",
        "lora1_strength_model": 0,
        "lora2": "framee_4000.safetensors",
        "lora2_strength_model": 0,
        "lora3": "framee_4000.safetensors",
        "lora3_strength_model": 0,
        "prompt": "a cat runs",
    }


# ---- happyhorse-1.0/image-to-video (singleImage) ----
def test_happyhorse_image_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["happyhorse-1.0/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/alibaba/happyhorse-1.0/image-to-video"
    body = spec.build_request(_inp(seconds=5, resolution="720P"), ["https://rh/img.png"])
    assert body == {
        "imageUrl": "https://rh/img.png",
        "prompt": "a cat runs",
        "resolution": "720p",
        "duration": "5",
        "seed": None,
    }


# ---- happyhorse-1.0/reference-to-video (imageReference:9) ----
def test_happyhorse_reference_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["happyhorse-1.0/reference-to-video"]
    assert spec.mode == "imageReference:9"
    urls = ["https://rh/a.png", "https://rh/b.png"]
    body = spec.build_request(_inp(seconds=5, resolution="1080P"), urls)
    assert body == {
        "prompt": "a cat runs",
        "imageUrls": urls,
        "resolution": "1080p",
        "aspectRatio": "16:9",
        "duration": "5",
        "seed": None,
    }


# ---- kling-video-o3-pro/image-to-video (startEndRequired, sound=True, duration=int) ----
def test_kling_o3_pro_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["kling-video-o3-pro/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/kling-video-o3-pro/image-to-video"
    assert spec.mode == "startEndRequired"
    body = spec.build_request(_inp(seconds=10, audio=None), ["https://rh/first.png", "https://rh/last.png"])
    assert body == {
        "prompt": "a cat runs",
        "firstImageUrl": "https://rh/first.png",
        "lastImageUrl": "https://rh/last.png",
        "duration": 10,
        "sound": True,
        "multiShot": False,
        "shotType": "customize",
    }


def test_kling_o3_pro_audio_false_sets_sound_false() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["kling-video-o3-pro/image-to-video"]
    body = spec.build_request(_inp(audio=False), ["https://rh/first.png"])
    assert body["sound"] is False


# ---- kling-video-o3-std/image-to-video ----
def test_kling_o3_std_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["kling-video-o3-std/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/kling-video-o3-std/image-to-video"
    body = spec.build_request(_inp(seconds=5), ["https://rh/first.png"])
    assert body["duration"] == 5
    assert body["sound"] is True


# ---- kling-v3.0-pro/image-to-video (cfgScale=0.5, duration=str) ----
def test_kling_v3_pro_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["kling-v3.0-pro/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/kling-v3.0-pro/image-to-video"
    body = spec.build_request(_inp(seconds=10), ["https://rh/first.png", "https://rh/last.png"])
    assert body == {
        "prompt": "a cat runs",
        "firstImageUrl": "https://rh/first.png",
        "lastImageUrl": "https://rh/last.png",
        "duration": "10",
        "sound": True,
        "multiShot": False,
        "shotType": "customize",
        "negativePrompt": None,
        "cfgScale": 0.5,
    }


# ---- kling-v3.0-std/image-to-video (cfgScale=0.8) ----
def test_kling_v3_std_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["kling-v3.0-std/image-to-video"]
    body = spec.build_request(_inp(seconds=5), ["https://rh/first.png"])
    assert body["cfgScale"] == 0.8
    assert body["duration"] == "5"


# ---- rhart-video-g-official/reference-to-video (imageReference:9) ----
def test_rhart_g_official_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["rhart-video-g-official/reference-to-video"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video-g-official/reference-to-video"
    assert spec.mode == "imageReference:9"
    urls = ["https://rh/a.png", "https://rh/b.png"]
    body = spec.build_request(_inp(seconds=8, resolution="720P"), urls)
    assert body == {
        "imageUrls": urls,
        "prompt": "a cat runs",
        "duration": "8",
        "resolution": "720p",
    }


# ---- rhart-video-g/image-to-video (imageReference:7, clamped duration) ----
def test_rhart_g_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["rhart-video-g/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video-g/image-to-video"
    assert spec.mode == "imageReference:7"
    urls = ["https://rh/a.png", "https://rh/b.png"]
    body = spec.build_request(_inp(seconds=30, resolution="720P"), urls)
    assert body == {
        "prompt": "a cat runs",
        "aspectRatio": "16:9",
        "imageUrls": urls,
        "resolution": "720p",
        "duration": 30,
    }


def test_rhart_g_clamps_duration_to_min_6() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["rhart-video-g/image-to-video"]
    body = spec.build_request(_inp(seconds=3), ["https://rh/a.png"])
    assert body["duration"] == 6


# ---- rhart-video-v3.1-fast/start-end-to-video (startEndRequired, firstFrameUrl casing) ----
def test_rhart_v31_start_end_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["rhart-video-v3.1-fast/start-end-to-video"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video-v3.1-fast/start-end-to-video"
    assert spec.mode == "startEndRequired"
    body = spec.build_request(_inp(seconds=8, resolution="1080P"), ["https://rh/first.png", "https://rh/last.png"])
    assert body == {
        "prompt": "a cat runs",
        "firstFrameUrl": "https://rh/first.png",
        "lastFrameUrl": "https://rh/last.png",
        "aspectRatio": "16:9",
        "duration": "8",
        "resolution": "1080p",
    }


# ---- rhart-video-v3.1-fast/image-to-video (imageReference:3) ----
def test_rhart_v31_image_to_video_body() -> None:
    spec = ENTERPRISE_VIDEO_BUILDERS["rhart-video-v3.1-fast/image-to-video"]
    assert spec.endpoint_path == "/openapi/v2/rhart-video-v3.1-fast/image-to-video"
    assert spec.mode == "imageReference:3"
    urls = ["https://rh/a.png", "https://rh/b.png", "https://rh/c.png"]
    body = spec.build_request(_inp(seconds=8, resolution="720P"), urls)
    assert body == {
        "prompt": "a cat runs",
        "aspectRatio": "16:9",
        "imageUrls": urls,
        "duration": "8",
        "resolution": "720p",
    }


def test_enterprise_builders_has_14_entries() -> None:
    assert len(ENTERPRISE_VIDEO_BUILDERS) == 14
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_enterprise_request_builders.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.integrations.runninghub.enterprise.request_builders'`.

- [ ] **Step 3: Create request_builders.py**

Create `backend/app/core/integrations/runninghub/enterprise/request_builders.py`:

```python
"""RunningHub 企业版 14 个视频模型的 JSON body 构造器。

字段名、magic string、duration 类型（str/int）、resolution 大小写、cfgScale 值等
逐字移植自 ~/Downloads/toonflow-runninghub-enterprise.ts，不"改进"。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from app.core.contracts.video_generation import VideoGenerationInput


@dataclass(frozen=True, slots=True)
class EnterpriseVideoBuildSpec:
    endpoint_path: str
    mode: str  # "singleImage" | "startEndRequired" | "imageReference:3" | "imageReference:7" | "imageReference:9"
    build_request: Callable[[VideoGenerationInput, list[str]], dict]


def _wan27_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "resolution": inp.resolution or "720P",
        "duration": str(inp.seconds or 5),
        "promptExtend": True,
        "seed": None,
    }


def _wan27_reference_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "videoUrls": [],
        "imageUrls": urls,
        "resolution": inp.resolution or "720P",
        "duration": str(inp.seconds or 5),
        "aspectRatio": inp.ratio,
        "promptExtend": True,
        "seed": None,
    }


def _ltx23_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "imageUrl": urls[0],
        "prompt": inp.prompt or "",
        "resolution": (inp.resolution or "480P").replace("P", "p"),
        "aspectRatio": inp.ratio,
        "duration": inp.seconds or 5,
    }


def _ltx23_image_to_video_lora(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "imageUrl": urls[0],
        "resolution": (inp.resolution or "480P").replace("P", "p"),
        "aspectRatio": inp.ratio,
        "duration": inp.seconds or 5,
        "lora1": "framee_4000.safetensors",
        "lora1_strength_model": 0,
        "lora2": "framee_4000.safetensors",
        "lora2_strength_model": 0,
        "lora3": "framee_4000.safetensors",
        "lora3_strength_model": 0,
        "prompt": inp.prompt or "",
    }


def _happyhorse_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "imageUrl": urls[0],
        "prompt": inp.prompt or "",
        "resolution": (inp.resolution or "720P").replace("P", "p"),
        "duration": str(inp.seconds or 5),
        "seed": None,
    }


def _happyhorse_reference_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "imageUrls": urls,
        "resolution": (inp.resolution or "720P").replace("P", "p"),
        "aspectRatio": inp.ratio,
        "duration": str(inp.seconds or 5),
        "seed": None,
    }


def _kling_o3_pro(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "duration": inp.seconds or 5,
        "sound": inp.audio is not False,
        "multiShot": False,
        "shotType": "customize",
    }


def _kling_o3_std(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "duration": inp.seconds or 5,
        "sound": inp.audio is not False,
        "multiShot": False,
        "shotType": "customize",
    }


def _kling_v3_pro(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "duration": str(inp.seconds or 5),
        "sound": inp.audio is not False,
        "multiShot": False,
        "shotType": "customize",
        "negativePrompt": None,
        "cfgScale": 0.5,
    }


def _kling_v3_std(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "duration": str(inp.seconds or 5),
        "sound": inp.audio is not False,
        "multiShot": False,
        "shotType": "customize",
        "negativePrompt": None,
        "cfgScale": 0.8,
    }


def _rhart_g_official_reference_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "imageUrls": urls,
        "prompt": inp.prompt or "",
        "duration": str(inp.seconds or 6),
        "resolution": (inp.resolution or "720P").replace("P", "p"),
    }


def _rhart_g_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "aspectRatio": inp.ratio,
        "imageUrls": urls,
        "resolution": (inp.resolution or "480P").replace("P", "p"),
        "duration": max(6, min(30, inp.seconds or 6)),
    }


def _rhart_v31_start_end_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstFrameUrl": urls[0],
        "lastFrameUrl": urls[1] if len(urls) >= 2 else None,
        "aspectRatio": inp.ratio,
        "duration": str(inp.seconds or 8),
        "resolution": (inp.resolution or "720P").replace("P", "p"),
    }


def _rhart_v31_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "aspectRatio": inp.ratio,
        "imageUrls": urls,
        "duration": str(inp.seconds or 8),
        "resolution": (inp.resolution or "720P").replace("P", "p"),
    }


ENTERPRISE_VIDEO_BUILDERS: dict[str, EnterpriseVideoBuildSpec] = {
    "wan-2.7/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/alibaba/wan-2.7/image-to-video",
        mode="startEndRequired",
        build_request=_wan27_image_to_video,
    ),
    "wan-2.7/reference-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/alibaba/wan-2.7/reference-to-video",
        mode="imageReference:9",
        build_request=_wan27_reference_to_video,
    ),
    "ltx-2.3/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/ltx-2.3/image-to-video",
        mode="singleImage",
        build_request=_ltx23_image_to_video,
    ),
    "ltx-2.3/image-to-video-lora": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video/ltx-2.3/image-to-video-lora",
        mode="singleImage",
        build_request=_ltx23_image_to_video_lora,
    ),
    "happyhorse-1.0/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/alibaba/happyhorse-1.0/image-to-video",
        mode="singleImage",
        build_request=_happyhorse_image_to_video,
    ),
    "happyhorse-1.0/reference-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/alibaba/happyhorse-1.0/reference-to-video",
        mode="imageReference:9",
        build_request=_happyhorse_reference_to_video,
    ),
    "kling-video-o3-pro/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/kling-video-o3-pro/image-to-video",
        mode="startEndRequired",
        build_request=_kling_o3_pro,
    ),
    "kling-video-o3-std/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/kling-video-o3-std/image-to-video",
        mode="startEndRequired",
        build_request=_kling_o3_std,
    ),
    "kling-v3.0-pro/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/kling-v3.0-pro/image-to-video",
        mode="startEndRequired",
        build_request=_kling_v3_pro,
    ),
    "kling-v3.0-std/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/kling-v3.0-std/image-to-video",
        mode="startEndRequired",
        build_request=_kling_v3_std,
    ),
    "rhart-video-g-official/reference-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video-g-official/reference-to-video",
        mode="imageReference:9",
        build_request=_rhart_g_official_reference_to_video,
    ),
    "rhart-video-g/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video-g/image-to-video",
        mode="imageReference:7",
        build_request=_rhart_g_image_to_video,
    ),
    "rhart-video-v3.1-fast/start-end-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video-v3.1-fast/start-end-to-video",
        mode="startEndRequired",
        build_request=_rhart_v31_start_end_to_video,
    ),
    "rhart-video-v3.1-fast/image-to-video": EnterpriseVideoBuildSpec(
        endpoint_path="/openapi/v2/rhart-video-v3.1-fast/image-to-video",
        mode="imageReference:3",
        build_request=_rhart_v31_image_to_video,
    ),
}
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_enterprise_request_builders.py -v`
Expected: PASS — all 18 tests pass (14 model tests + 4 edge case tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/integrations/runninghub/enterprise/request_builders.py backend/tests/test_runninghub_enterprise_request_builders.py
git commit -m "feat: add 14 enterprise video request builders ported from .ts reference"
```

---

## Task 5: Enterprise video adapter

**Files:**
- Create: `backend/app/core/integrations/runninghub/enterprise/video.py`
- Test: `backend/tests/test_runninghub_enterprise_video_adapter.py` (new)

**Interfaces:**
- Consumes: `ProviderConfig`, `VideoGenerationInput`, `ENTERPRISE_VIDEO_BUILDERS`, `submit_enterprise_task` (Task 3), `upload_media` + `query_task` from `runninghub.client` (existing)
- Produces: `RunningHubEnterpriseVideoApiAdapter` with `create_video(*, cfg, input_, timeout_s) -> str` and `get_video(*, cfg, video_id, timeout_s) -> dict`. Helper `_resolve_enterprise_image_urls(input_, spec, cfg, timeout_s) -> list[str]` dispatches by `spec.mode`.

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_runninghub_enterprise_video_adapter.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_enterprise_video_adapter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.integrations.runninghub.enterprise.video'`.

- [ ] **Step 3: Create enterprise video adapter**

Create `backend/app/core/integrations/runninghub/enterprise/video.py`:

```python
"""RunningHub 企业版视频适配器：create + get 两阶段，Task 层负责轮询节奏。"""

from __future__ import annotations

import base64
from typing import Any

from app.core.contracts.provider import ProviderConfig
from app.core.contracts.video_generation import VideoGenerationInput
from app.core.integrations.runninghub import client as rh_client
from app.core.integrations.runninghub.enterprise.client import submit_enterprise_task
from app.core.integrations.runninghub.enterprise.request_builders import ENTERPRISE_VIDEO_BUILDERS, EnterpriseVideoBuildSpec


class RunningHubEnterpriseVideoApiAdapter:
    """RunningHub 企业版视频生成 HTTP；无状态。"""

    async def create_video(
        self,
        *,
        cfg: ProviderConfig,
        input_: VideoGenerationInput,
        timeout_s: float,
    ) -> str:
        model_name = input_.model or ""
        spec = ENTERPRISE_VIDEO_BUILDERS.get(model_name)
        if spec is None:
            raise ValueError(f"Unknown RunningHub enterprise video model: {model_name}")

        base_url = cfg.base_url or "https://www.runninghub.cn"
        image_urls = await _resolve_enterprise_image_urls(input_, spec, base_url, cfg.api_key, timeout_s)
        request_body = spec.build_request(input_, image_urls)

        return await submit_enterprise_task(
            base_url, cfg.api_key, spec.endpoint_path, request_body, timeout_s=timeout_s
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


async def _resolve_enterprise_image_urls(
    input_: VideoGenerationInput,
    spec: EnterpriseVideoBuildSpec,
    base_url: str,
    api_key: str,
    timeout_s: float,
) -> list[str]:
    """按 spec.mode 收集 base64 帧 → 上传 → 返回 URL 列表。不补齐。"""
    raw_frames: list[str] = []

    if spec.mode == "singleImage":
        if input_.first_frame_base64:
            raw_frames.append(input_.first_frame_base64)
    elif spec.mode == "startEndRequired":
        for raw in (input_.first_frame_base64, input_.last_frame_base64):
            if raw:
                raw_frames.append(raw)
    elif spec.mode == "imageReference:3":
        for raw in (input_.first_frame_base64, input_.last_frame_base64, input_.key_frame_base64):
            if raw:
                raw_frames.append(raw)
    elif spec.mode in ("imageReference:7", "imageReference:9"):
        max_n = 7 if spec.mode == "imageReference:7" else 9
        refs = input_.reference_frames_base64 or []
        for raw in refs[:max_n]:
            if raw:
                raw_frames.append(raw)
    else:
        raise ValueError(f"Unsupported enterprise mode: {spec.mode}")

    if not raw_frames:
        raise ValueError("RunningHub 企业版视频生成需要至少一张参考图")

    urls: list[str] = []
    for raw in raw_frames:
        mime, data = _split_data_url(raw)
        bytes_data = base64.b64decode(data)
        url = await rh_client.upload_media(base_url, api_key, mime, bytes_data, timeout_s=timeout_s)
        urls.append(url)
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

- [ ] **Step 4: Run tests to verify pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_enterprise_video_adapter.py -v`
Expected: PASS — all 6 tests pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/core/integrations/runninghub/enterprise/video.py backend/tests/test_runninghub_enterprise_video_adapter.py
git commit -m "feat: add runninghub enterprise video adapter with multi-reference support"
```

---

## Task 6: Enterprise capability resolver

**Files:**
- Create: `backend/app/core/integrations/runninghub/enterprise/video_capabilities.py`
- Modify: `backend/app/core/integrations/video_capabilities.py`
- Test: `backend/tests/test_runninghub_enterprise_capabilities.py` (new)

**Interfaces:**
- Consumes: `VideoModelCapability` from `app.core.integrations.video_capabilities`, `ProviderKey` (Task 1)
- Produces: `resolve_runninghub_enterprise_video_capability(model: str | None) -> VideoModelCapability`. Takes `model: str | None` (NOT `Model` object) — hardcodes per-model-prefix overrides. All enterprise models: `supports_seed=False`, `supports_watermark=False`, `allowed_ratios={"16:9", "9:16"}`, `default_ratio="16:9"`. Per-model `min_seconds`/`max_seconds` from .ts `durationResolutionMap`.

**Hardcoded duration ranges (from .ts):**
- `wan-2.7/*`: [5] → 5-5
- `ltx-2.3/*`: [5] → 5-5
- `happyhorse-1.0/*`: [5] → 5-5
- `kling-video-o3-*`: [5, 10] → 5-10
- `kling-v3.0-*`: [5, 10] → 5-10
- `rhart-video-g-official/*`: [6, 8] → 6-8
- `rhart-video-g/*`: [6, 10, 15, 20, 30] → 6-30
- `rhart-video-v3.1-fast/*`: [8] → 8-8

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_runninghub_enterprise_capabilities.py`:

```python
from __future__ import annotations

from app.core.integrations.runninghub.enterprise.video_capabilities import (
    resolve_runninghub_enterprise_video_capability,
)


def test_default_for_unknown_model() -> None:
    cap = resolve_runninghub_enterprise_video_capability(None)
    assert cap.supports_seed is False
    assert cap.supports_watermark is False
    assert cap.allowed_ratios == {"16:9", "9:16"}
    assert cap.default_ratio == "16:9"
    assert cap.min_seconds == 5
    assert cap.max_seconds == 5


def test_wan27_models_are_5_to_5() -> None:
    for model in ("wan-2.7/image-to-video", "wan-2.7/reference-to-video"):
        cap = resolve_runninghub_enterprise_video_capability(model)
        assert cap.min_seconds == 5
        assert cap.max_seconds == 5


def test_kling_v3_models_are_5_to_10() -> None:
    for model in (
        "kling-video-o3-pro/image-to-video",
        "kling-video-o3-std/image-to-video",
        "kling-v3.0-pro/image-to-video",
        "kling-v3.0-std/image-to-video",
    ):
        cap = resolve_runninghub_enterprise_video_capability(model)
        assert cap.min_seconds == 5
        assert cap.max_seconds == 10


def test_rhart_g_is_6_to_30() -> None:
    cap = resolve_runninghub_enterprise_video_capability("rhart-video-g/image-to-video")
    assert cap.min_seconds == 6
    assert cap.max_seconds == 30


def test_rhart_v31_fast_is_8_to_8() -> None:
    for model in (
        "rhart-video-v3.1-fast/start-end-to-video",
        "rhart-video-v3.1-fast/image-to-video",
    ):
        cap = resolve_runninghub_enterprise_video_capability(model)
        assert cap.min_seconds == 8
        assert cap.max_seconds == 8
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_enterprise_capabilities.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.core.integrations.runninghub.enterprise.video_capabilities'`.

- [ ] **Step 3: Create enterprise capability resolver**

Create `backend/app/core/integrations/runninghub/enterprise/video_capabilities.py`:

```python
"""RunningHub 企业版视频能力声明。

能力按模型名前缀硬编码（与个人版模式一致），因为 resolve_video_capability
接收 model: str | None，无法读取 Model.params。duration 范围源自 .ts 的
durationResolutionMap。
"""

from __future__ import annotations

from app.core.integrations.video_capabilities import VideoModelCapability

_ENTERPRISE_DEFAULT = VideoModelCapability(
    supports_seed=False,
    supports_watermark=False,
    allowed_ratios={"16:9", "9:16"},
    default_ratio="16:9",
    min_seconds=5,
    max_seconds=5,
)

# 按模型名前缀匹配（大小写不敏感）。最长前缀优先。
_ENTERPRISE_PREFIX_OVERRIDES: dict[str, VideoModelCapability] = {
    "wan-2.7/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=5,
        max_seconds=5,
    ),
    "ltx-2.3/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=5,
        max_seconds=5,
    ),
    "happyhorse-1.0/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=5,
        max_seconds=5,
    ),
    "kling-video-o3-": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=5,
        max_seconds=10,
    ),
    "kling-v3.0-": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=5,
        max_seconds=10,
    ),
    "rhart-video-g-official/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=6,
        max_seconds=8,
    ),
    "rhart-video-g/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=6,
        max_seconds=30,
    ),
    "rhart-video-v3.1-fast/": VideoModelCapability(
        supports_seed=False,
        supports_watermark=False,
        allowed_ratios={"16:9", "9:16"},
        default_ratio="16:9",
        min_seconds=8,
        max_seconds=8,
    ),
}


def register_runninghub_enterprise_video_capability(*, model_prefix: str, capability: VideoModelCapability) -> None:
    prefix = model_prefix.strip().lower()
    if not prefix:
        raise ValueError("model_prefix must not be empty")
    _ENTERPRISE_PREFIX_OVERRIDES[prefix] = capability


def clear_runninghub_enterprise_video_capability_overrides() -> None:
    _ENTERPRISE_PREFIX_OVERRIDES.clear()


def _pick_override(model: str | None) -> VideoModelCapability | None:
    if not model:
        return None
    value = model.strip().lower()
    if not value:
        return None
    for prefix, cap in sorted(_ENTERPRISE_PREFIX_OVERRIDES.items(), key=lambda item: len(item[0]), reverse=True):
        if value.startswith(prefix):
            return cap
    return None


def resolve_runninghub_enterprise_video_capability(model: str | None) -> VideoModelCapability:
    return _pick_override(model) or _ENTERPRISE_DEFAULT
```

- [ ] **Step 4: Wire enterprise branch into shared video_capabilities.py**

Edit `backend/app/core/integrations/video_capabilities.py` — add enterprise branches to `register_video_model_capability`, `clear_video_model_capability_overrides`, and `resolve_video_capability`:

```python
def register_video_model_capability(
    *,
    provider: ProviderKey,
    model_prefix: str,
    capability: VideoModelCapability,
) -> None:
    """兼容入口：注册模型能力覆盖（按前缀匹配，大小写不敏感）。"""
    if provider == "openai":
        from app.core.integrations.openai.video_capabilities import register_openai_video_capability

        register_openai_video_capability(model_prefix=model_prefix, capability=capability)
        return
    if provider == "runninghub":
        from app.core.integrations.runninghub.video_capabilities import register_runninghub_video_capability

        register_runninghub_video_capability(model_prefix=model_prefix, capability=capability)
        return
    if provider == "runninghub-enterprise":
        from app.core.integrations.runninghub.enterprise.video_capabilities import (
            register_runninghub_enterprise_video_capability,
        )

        register_runninghub_enterprise_video_capability(model_prefix=model_prefix, capability=capability)
        return
    from app.core.integrations.volcengine.video_capabilities import register_volcengine_video_capability

    register_volcengine_video_capability(model_prefix=model_prefix, capability=capability)


def clear_video_model_capability_overrides(*, provider: ProviderKey | None = None) -> None:
    """兼容入口：清空能力覆盖；供测试或重置场景使用。"""
    from app.core.integrations.openai.video_capabilities import clear_openai_video_capability_overrides
    from app.core.integrations.volcengine.video_capabilities import clear_volcengine_video_capability_overrides

    if provider is None:
        from app.core.integrations.runninghub.video_capabilities import clear_runninghub_video_capability_overrides
        from app.core.integrations.runninghub.enterprise.video_capabilities import (
            clear_runninghub_enterprise_video_capability_overrides,
        )

        clear_openai_video_capability_overrides()
        clear_volcengine_video_capability_overrides()
        clear_runninghub_video_capability_overrides()
        clear_runninghub_enterprise_video_capability_overrides()
        return
    if provider == "openai":
        clear_openai_video_capability_overrides()
        return
    if provider == "runninghub":
        from app.core.integrations.runninghub.video_capabilities import clear_runninghub_video_capability_overrides

        clear_runninghub_video_capability_overrides()
        return
    if provider == "runninghub-enterprise":
        from app.core.integrations.runninghub.enterprise.video_capabilities import (
            clear_runninghub_enterprise_video_capability_overrides,
        )

        clear_runninghub_enterprise_video_capability_overrides()
        return
    clear_volcengine_video_capability_overrides()


def resolve_video_capability(*, provider: ProviderKey, model: str | None) -> VideoModelCapability:
    if provider == "openai":
        from app.core.integrations.openai.video_capabilities import resolve_openai_video_capability

        return resolve_openai_video_capability(model)
    if provider == "runninghub":
        from app.core.integrations.runninghub.video_capabilities import resolve_runninghub_video_capability

        return resolve_runninghub_video_capability(model)
    if provider == "runninghub-enterprise":
        from app.core.integrations.runninghub.enterprise.video_capabilities import (
            resolve_runninghub_enterprise_video_capability,
        )

        return resolve_runninghub_enterprise_video_capability(model)
    from app.core.integrations.volcengine.video_capabilities import resolve_volcengine_video_capability

    return resolve_volcengine_video_capability(model)
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_enterprise_capabilities.py -v`
Expected: PASS — all 5 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/integrations/runninghub/enterprise/video_capabilities.py backend/app/core/integrations/video_capabilities.py backend/tests/test_runninghub_enterprise_capabilities.py
git commit -m "feat: add runninghub enterprise video capability resolver"
```

---

## Task 7: Task layer + bootstrap registration

**Files:**
- Modify: `backend/app/core/tasks/video_generation_tasks.py`
- Modify: `backend/app/core/tasks/bootstrap.py`
- Test: `backend/tests/test_task_registry.py` (extend)

**Interfaces:**
- Consumes: `RunningHubEnterpriseVideoApiAdapter` (Task 5), `ProviderKey` (Task 1)
- Produces: `VideoGenerationTask._build_runninghub_enterprise_impl` static method; `TASK_ADAPTER_SPECS` includes `("video_generation", "runninghub-enterprise", VideoGenerationTask._build_runninghub_enterprise_impl)`.

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_task_registry.py` (append before EOF):

```python
def test_runninghub_enterprise_task_adapters_registered() -> None:
    from app.core.tasks.bootstrap import bootstrap_task_adapters
    from app.core.tasks.registry import resolve_task_adapter

    bootstrap_task_adapters()
    video_factory = resolve_task_adapter("video_generation", "runninghub-enterprise")
    assert video_factory is not None


def test_runninghub_enterprise_video_task_builds_adapter_impl() -> None:
    from app.core.tasks.video_generation_tasks import VideoGenerationTask, RunningHubVideoGenerationTask
    from app.core.contracts.video_generation import VideoGenerationInput
    from app.core.contracts.provider import ProviderConfig

    impl = VideoGenerationTask._build_runninghub_enterprise_impl(
        provider_config=ProviderConfig(provider="runninghub-enterprise", api_key="k", base_url="https://rh"),
        input_=VideoGenerationInput(prompt="x", ratio="16:9", model="wan-2.7/image-to-video"),
        poll_interval_s=5.0,
        timeout_s=600.0,
    )
    assert isinstance(impl, RunningHubVideoGenerationTask)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_task_registry.py::test_runninghub_enterprise_task_adapters_registered tests/test_task_registry.py::test_runninghub_enterprise_video_task_builds_adapter_impl -v`
Expected: FAIL — `_build_runninghub_enterprise_impl` not defined; adapter not registered.

- [ ] **Step 3: Add enterprise import + static method to video_generation_tasks.py**

Edit `backend/app/core/tasks/video_generation_tasks.py` — add import after the existing runninghub import (line 14):

```python
from app.core.integrations.runninghub.enterprise.video import RunningHubEnterpriseVideoApiAdapter
```

Add `__all__` is unchanged. After the existing `_build_runninghub_impl` static method (inside `VideoGenerationTask` class, before `async def run`), add:

```python
    @staticmethod
    def _build_runninghub_enterprise_impl(
        *,
        provider_config: ProviderConfig,
        input_: VideoGenerationInput,
        poll_interval_s: float = 5.0,
        timeout_s: float = 600.0,
    ) -> AbstractVideoGenerationTask:
        return RunningHubVideoGenerationTask(
            adapter=RunningHubEnterpriseVideoApiAdapter(),
            provider_config=provider_config,
            input_=input_,
            poll_interval_s=poll_interval_s,
            timeout_s=timeout_s,
        )
```

- [ ] **Step 4: Register in bootstrap.py**

Edit `backend/app/core/tasks/bootstrap.py` — add enterprise entry to `TASK_ADAPTER_SPECS`:

```python
TASK_ADAPTER_SPECS = (
    ("image_generation", "openai", ImageGenerationTask._build_openai_impl),
    ("image_generation", "volcengine", ImageGenerationTask._build_volcengine_impl),
    ("image_generation", "runninghub", ImageGenerationTask._build_runninghub_impl),
    ("video_generation", "openai", VideoGenerationTask._build_openai_impl),
    ("video_generation", "volcengine", VideoGenerationTask._build_volcengine_impl),
    ("video_generation", "runninghub", VideoGenerationTask._build_runninghub_impl),
    ("video_generation", "runninghub-enterprise", VideoGenerationTask._build_runninghub_enterprise_impl),
)
```

- [ ] **Step 5: Run tests to verify pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_task_registry.py -v`
Expected: PASS — all tests pass including the 2 new enterprise tests.

- [ ] **Step 6: Commit**

```bash
git add backend/app/core/tasks/video_generation_tasks.py backend/app/core/tasks/bootstrap.py backend/tests/test_task_registry.py
git commit -m "feat: register runninghub-enterprise video generation task adapter"
```

---

## Task 8: DB model bootstrap (enterprise provider + 14 models)

**Files:**
- Modify: `backend/app/services/llm/model_bootstrap.py`
- Test: `backend/tests/test_runninghub_model_bootstrap.py` (extend)

**Interfaces:**
- Consumes: `Model`, `Provider`, `ModelCategoryKey`, `ProviderStatus` from `app.models.llm`; existing `bootstrap_builtin_db_resources` function
- Produces: `bootstrap_builtin_db_resources(session)` now upserts enterprise provider row + 14 enterprise model rows (in addition to existing personal provider + 9 models). Enterprise provider: `id="runninghub-enterprise"`, `name="RunningHub 企业版"`, `base_url="https://www.runninghub.cn"`, `status=ProviderStatus.testing`. Enterprise models: 14 rows with `params` containing `model_name`, `mode`, `duration_resolution_map`, `audio`.

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_runninghub_model_bootstrap.py` (append before EOF):

```python
@pytest.mark.asyncio
async def test_bootstrap_creates_enterprise_provider_and_14_models(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    provider = (await db.execute(select(Provider).where(Provider.id == "runninghub-enterprise"))).scalar_one()
    assert provider.name == "RunningHub 企业版"
    assert provider.base_url == "https://www.runninghub.cn"
    assert provider.status == ProviderStatus.testing

    models = (
        await db.execute(select(Model).where(Model.provider_id == "runninghub-enterprise"))
    ).scalars().all()
    assert len(models) == 14
    for m in models:
        assert m.category == ModelCategoryKey.video
        assert "model_name" in m.params
        assert "mode" in m.params
        assert "duration_resolution_map" in m.params


@pytest.mark.asyncio
async def test_bootstrap_enterprise_is_idempotent(db: AsyncSession) -> None:
    await bootstrap_builtin_db_resources(db)
    await db.commit()
    await bootstrap_builtin_db_resources(db)
    await db.commit()

    models = (
        await db.execute(select(Model).where(Model.provider_id == "runninghub-enterprise"))
    ).scalars().all()
    assert len(models) == 14


@pytest.mark.asyncio
async def test_bootstrap_preserves_enterprise_user_api_key(db: AsyncSession) -> None:
    db.add(Provider(
        id="runninghub-enterprise",
        name="Old Enterprise",
        base_url="https://custom.rh-ent",
        api_key="user-ent-key",
        api_secret="",
        description="",
        status=ProviderStatus.active,
        created_by="user",
    ))
    await db.commit()

    await bootstrap_builtin_db_resources(db)
    await db.commit()

    provider = (await db.execute(select(Provider).where(Provider.id == "runninghub-enterprise"))).scalar_one()
    assert provider.api_key == "user-ent-key"
    assert provider.base_url == "https://custom.rh-ent"
    assert provider.status == ProviderStatus.active
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_model_bootstrap.py::test_bootstrap_creates_enterprise_provider_and_14_models -v`
Expected: FAIL — enterprise provider not created; 0 models found.

- [ ] **Step 3: Add enterprise provider + 14 models to model_bootstrap.py**

Edit `backend/app/services/llm/model_bootstrap.py` — add enterprise constants after the personal `_RUNNINGHUB_MODELS` list and extend `bootstrap_builtin_db_resources`:

```python
_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS = {
    "id": "runninghub-enterprise",
    "name": "RunningHub 企业版",
    "base_url": "https://www.runninghub.cn",
    "image_base_url": None,
    "video_base_url": None,
    "api_secret": "",
    "description": "RunningHub 企业版：万相 2.7 / LTX2.3 / HappyHorse / 可灵 / 全能视频 系列视频模型",
    "status": ProviderStatus.testing,
    "created_by": "system",
}

_RUNNINGHUB_ENTERPRISE_MODELS: list[dict] = [
    {
        "id": "runninghub-enterprise-wan-2.7-image-to-video",
        "name": "万相 2.7 图生视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "wan-2.7/image-to-video",
            "mode": "startEndRequired",
            "duration_resolution_map": [{"duration": [5], "resolution": ["720P"]}],
            "audio": False,
        },
        "description": "万相 2.7 官方图生视频，支持首尾帧控制、提示词引导与智能扩展。",
    },
    {
        "id": "runninghub-enterprise-wan-2.7-reference-to-video",
        "name": "万相 2.7 参考生视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "wan-2.7/reference-to-video",
            "mode": "imageReference:9",
            "duration_resolution_map": [{"duration": [5], "resolution": ["720P", "1080P"]}],
            "audio": False,
        },
        "description": "万相 2.7 官方参考生视频，支持多图/多视频参考混合生成，角色一致性高。",
    },
    {
        "id": "runninghub-enterprise-ltx-2.3-image-to-video",
        "name": "LTX2.3 图生视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "ltx-2.3/image-to-video",
            "mode": "singleImage",
            "duration_resolution_map": [{"duration": [5], "resolution": ["480P"]}],
            "audio": False,
        },
        "description": "LTX2.3 图生视频，支持自定义分辨率、宽高比与时长。",
    },
    {
        "id": "runninghub-enterprise-ltx-2.3-image-to-video-lora",
        "name": "LTX2.3 图生视频 LoRA",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "ltx-2.3/image-to-video-lora",
            "mode": "singleImage",
            "duration_resolution_map": [{"duration": [5], "resolution": ["480P"]}],
            "audio": False,
        },
        "description": "LTX2.3 图生视频 LoRA 版，支持 3 组 LoRA 叠加与强度调节，风格可控性更强。",
    },
    {
        "id": "runninghub-enterprise-happyhorse-1.0-image-to-video",
        "name": "HappyHorse 图生视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "happyhorse-1.0/image-to-video",
            "mode": "singleImage",
            "duration_resolution_map": [{"duration": [5], "resolution": ["720P", "1080P"]}],
            "audio": False,
        },
        "description": "HappyHorse 1.0 图生视频，东方美学风格，画质精细。",
    },
    {
        "id": "runninghub-enterprise-happyhorse-1.0-reference-to-video",
        "name": "HappyHorse 参考生视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "happyhorse-1.0/reference-to-video",
            "mode": "imageReference:9",
            "duration_resolution_map": [{"duration": [5], "resolution": ["720P", "1080P"]}],
            "audio": False,
        },
        "description": "HappyHorse 1.0 多图参考生视频，支持多图融合生成风格统一的视频。",
    },
    {
        "id": "runninghub-enterprise-kling-video-o3-pro-image-to-video",
        "name": "可灵图生视频 o3-pro",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "kling-video-o3-pro/image-to-video",
            "mode": "startEndRequired",
            "duration_resolution_map": [{"duration": [5, 10], "resolution": ["720P", "1080P"]}],
            "audio": "optional",
        },
        "description": "可灵 o3-pro 图生视频，顶级画质，支持首尾帧控制与音频生成。",
    },
    {
        "id": "runninghub-enterprise-kling-video-o3-std-image-to-video",
        "name": "可灵图生视频 o3-std",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "kling-video-o3-std/image-to-video",
            "mode": "startEndRequired",
            "duration_resolution_map": [{"duration": [5, 10], "resolution": ["720P", "1080P"]}],
            "audio": "optional",
        },
        "description": "可灵 o3-std 图生视频，高性价比，支持首尾帧控制与音频生成。",
    },
    {
        "id": "runninghub-enterprise-kling-v3.0-pro-image-to-video",
        "name": "可灵图生视频 3.0-pro",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "kling-v3.0-pro/image-to-video",
            "mode": "startEndRequired",
            "duration_resolution_map": [{"duration": [5, 10], "resolution": ["720P", "1080P"]}],
            "audio": "optional",
        },
        "description": "可灵 3.0-pro 图生视频，支持首尾帧、反向提示词与 cfgScale 精细调控。",
    },
    {
        "id": "runninghub-enterprise-kling-v3.0-std-image-to-video",
        "name": "可灵图生视频 3.0-std",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "kling-v3.0-std/image-to-video",
            "mode": "startEndRequired",
            "duration_resolution_map": [{"duration": [5, 10], "resolution": ["720P", "1080P"]}],
            "audio": "optional",
        },
        "description": "可灵 3.0-std 图生视频，支持首尾帧、反向提示词与 cfgScale 精细调控。",
    },
    {
        "id": "runninghub-enterprise-rhart-video-g-official-reference-to-video",
        "name": "全能视频X 多图参考生视频 官方稳定版",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "rhart-video-g-official/reference-to-video",
            "mode": "imageReference:9",
            "duration_resolution_map": [{"duration": [6, 8], "resolution": ["720P"]}],
            "audio": False,
        },
        "description": "全能视频X 官方稳定版，多图参考生视频，支持自定义时长与分辨率。",
    },
    {
        "id": "runninghub-enterprise-rhart-video-g-image-to-video",
        "name": "全能视频X 图生视频 低价渠道版",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "rhart-video-g/image-to-video",
            "mode": "imageReference:7",
            "duration_resolution_map": [{"duration": [6, 10, 15, 20, 30], "resolution": ["480P", "720P"]}],
            "audio": False,
        },
        "description": "全能视频X 低价渠道版，支持 1-7 张图片参考，时长 6-30 秒，性价比高。",
    },
    {
        "id": "runninghub-enterprise-rhart-video-v3.1-fast-start-end-to-video",
        "name": "全能视频V3.1-fast 首尾帧生视频 低价渠道版",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "rhart-video-v3.1-fast/start-end-to-video",
            "mode": "startEndRequired",
            "duration_resolution_map": [{"duration": [8], "resolution": ["720P", "1080P"]}],
            "audio": False,
        },
        "description": "全能视频 V3.1-fast 首尾帧生视频，低价渠道，支持 720p/1080p/4k 输出。",
    },
    {
        "id": "runninghub-enterprise-rhart-video-v3.1-fast-image-to-video",
        "name": "全能视频V3.1-fast 图生视频 低价渠道版",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "rhart-video-v3.1-fast/image-to-video",
            "mode": "imageReference:3",
            "duration_resolution_map": [{"duration": [8], "resolution": ["720P", "1080P"]}],
            "audio": False,
        },
        "description": "全能视频 V3.1-fast 图生视频，低价渠道，最多 3 张图参考，支持 720p/1080p/4k。",
    },
]
```

Then extend `bootstrap_builtin_db_resources` — after the personal provider upsert and before the personal models loop, add the enterprise provider upsert; after the personal models loop, add the enterprise models loop:

```python
async def bootstrap_builtin_db_resources(session: AsyncSession) -> None:
    """幂等 upsert runninghub + runninghub-enterprise provider 行 + 9 + 14 个 model 行。

    - Provider 存在时：不覆盖 api_key / base_url / status / created_by（保留用户配置）
    - Provider 不存在时：用默认值插入（api_key 为空，用户在 UI 填）
    - Model 存在时：更新 name / params / description（保持版本最新）
    - Model 不存在时：插入
    """
    # --- 个人版 provider ---
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

    # --- 企业版 provider ---
    ent_provider = (
        await session.execute(select(Provider).where(Provider.id == "runninghub-enterprise"))
    ).scalar_one_or_none()

    if ent_provider is None:
        ent_provider = Provider(
            id=_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS["id"],
            name=_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS["name"],
            base_url=_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS["base_url"],
            image_base_url=_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS["image_base_url"],
            video_base_url=_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS["video_base_url"],
            api_key="",
            api_secret=_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS["api_secret"],
            description=_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS["description"],
            status=_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS["status"],
            created_by=_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS["created_by"],
        )
        session.add(ent_provider)

    # --- 个人版 models ---
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

    # --- 企业版 models ---
    for spec in _RUNNINGHUB_ENTERPRISE_MODELS:
        model = (
            await session.execute(select(Model).where(Model.id == spec["id"]))
        ).scalar_one_or_none()
        if model is None:
            model = Model(
                id=spec["id"],
                name=spec["name"],
                category=spec["category"],
                provider_id="runninghub-enterprise",
                params=spec["params"],
                description=spec["description"],
                created_by="system",
            )
            session.add(model)
        else:
            model.name = spec["name"]
            model.category = spec["category"]
            model.provider_id = "runninghub-enterprise"
            model.params = spec["params"]
            model.description = spec["description"]
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_model_bootstrap.py -v`
Expected: PASS — all 7 tests pass (4 existing personal + 3 new enterprise).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/model_bootstrap.py backend/tests/test_runninghub_model_bootstrap.py
git commit -m "feat: add db bootstrap for runninghub-enterprise provider and 14 video models"
```

---

## Task 9: Service-layer model_name wiring

**Files:**
- Modify: `backend/app/services/llm/model_identifier.py`
- Test: `backend/tests/test_runninghub_model_identifier.py` (extend)

**Interfaces:**
- Consumes: `Model` from `app.models.llm`; `provider_key` string
- Produces: `resolve_model_identifier(model, "runninghub-enterprise")` returns `model.params["model_name"]` if present, else `model.name`.

- [ ] **Step 1: Write failing tests**

Add to `backend/tests/test_runninghub_model_identifier.py` (append before EOF):

```python
def test_runninghub_enterprise_returns_model_name_from_params() -> None:
    model = _make_model(
        name="万相 2.7 图生视频",
        params={"model_name": "wan-2.7/image-to-video"},
    )
    assert resolve_model_identifier(model, "runninghub-enterprise") == "wan-2.7/image-to-video"


def test_runninghub_enterprise_without_model_name_falls_back_to_name() -> None:
    model = _make_model(name="万相 2.7 图生视频", params={})
    assert resolve_model_identifier(model, "runninghub-enterprise") == "万相 2.7 图生视频"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_model_identifier.py::test_runninghub_enterprise_returns_model_name_from_params tests/test_runninghub_model_identifier.py::test_runninghub_enterprise_without_model_name_falls_back_to_name -v`
Expected: FAIL — enterprise branch not implemented; returns `model.name` instead of `params["model_name"]`.

- [ ] **Step 3: Add enterprise branch to resolve_model_identifier**

Edit `backend/app/services/llm/model_identifier.py`:

```python
"""根据供应商类型解析最终传给 adapter 的 model 标识符。

RunningHub 个人版用 params.workflow_id；企业版用 params.model_name；其他供应商沿用 model.name。
"""

from __future__ import annotations

from app.models.llm import Model


def resolve_model_identifier(model: Model, provider_key: str) -> str:
    """返回 adapter 层 inp.model 应当使用的标识符。"""
    if provider_key == "runninghub":
        workflow_id = (model.params or {}).get("workflow_id")
        if workflow_id:
            return str(workflow_id)
    if provider_key == "runninghub-enterprise":
        model_name = (model.params or {}).get("model_name")
        if model_name:
            return str(model_name)
    return model.name
```

- [ ] **Step 4: Run tests to verify pass**

Run: `cd /Users/findhappylee/workspace/github/Jellyfish/backend && python -m pytest tests/test_runninghub_model_identifier.py -v`
Expected: PASS — all 6 tests pass (4 existing + 2 new).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/llm/model_identifier.py backend/tests/test_runninghub_model_identifier.py
git commit -m "feat: resolve model_name from params for runninghub-enterprise provider"
```

---

## Self-Review

**1. Spec coverage:**
- ProviderKey + ProviderSpec + aliases → Task 1 ✓
- VideoGenerationInput extension (3 fields) → Task 2 ✓
- Enterprise HTTP client → Task 3 ✓
- 14 request builders → Task 4 ✓
- Enterprise video adapter → Task 5 ✓
- Enterprise capability resolver → Task 6 ✓
- Task layer + bootstrap → Task 7 ✓
- DB model bootstrap (14 models) → Task 8 ✓
- Service-layer model_name wiring → Task 9 ✓
- `happyhorse-1.0/video-edit` skipped (14/15) → Global Constraints ✓

**2. Placeholder scan:** No TBD/TODO. All code blocks contain complete implementations. All test code is complete with assertions.

**3. Type consistency:**
- `submit_enterprise_task(base_url, api_key, endpoint_path, request_body, *, timeout_s)` — same signature in client (Task 3), adapter (Task 5), and tests.
- `EnterpriseVideoBuildSpec(endpoint_path, mode, build_request)` — same in request_builders (Task 4) and video adapter (Task 5).
- `RunningHubEnterpriseVideoApiAdapter.create_video(*, cfg, input_, timeout_s)` and `get_video(*, cfg, video_id, timeout_s)` — same in adapter (Task 5) and task layer (Task 7).
- `resolve_runninghub_enterprise_video_capability(model: str | None)` — same in resolver (Task 6) and video_capabilities dispatcher (Task 6).
- Model IDs: `runninghub-enterprise-{modelName with / → -}` — consistent between bootstrap (Task 8) and tests.

**4. Corrections from spec (noted in plan):**
- Capability resolver hardcodes per-prefix overrides (NOT reads from `Model.params`) — `VideoModelCapability` has no `allowed_durations`/`allowed_resolutions` fields, and the resolver takes `model: str | None` not `Model`. This matches the personal provider pattern.
- Alias resolution: enterprise check (`"runninghub-enterprise" in alias`) added BEFORE the personal `if "runninghub" in alias` fallback — otherwise enterprise gets caught by personal.
- `imageReference:3` uses existing `first/last/key_frame_base64` (backward compatible); only `imageReference:7/9` uses new `reference_frames_base64` field.
