# Grsai Provider Design

**Date:** 2026-07-07
**Status:** Approved (pending spec review)
**Scope:** Add a `grsai` provider for image generation only

## Goal

Add a new `grsai` provider to the Jellyfish backend, supporting 13 image generation models via Grsai's native `/v1/api/generate` + `/v1/api/result` async polling endpoints. The China node (`https://grsai.dakka.com.cn`) is the default base URL.

## Background

Grsai exposes two API modes:
- **Native mode** (`/v1/api/generate` + `/v1/api/result`): 13 image models (nano-banana family + gpt-image-2 family), supports async polling, aspect ratios, image sizes
- **OpenAI-compatible mode** (`/v1/chat/completions` + `/v1/images/generations`): standard OpenAI interface for text chat and image generation

This design uses the **native mode** for image generation. Text generation is out of scope (the Grsai docs don't list specific text models — only mentions "supports all models" with a `gemini-3.1-pro` example).

## Key Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Scope | Image generation only | Text models not documented; video not supported by Grsai |
| API mode | Async polling (`replyType=async`) | Matches RunningHub pattern; robust for long-running generations |
| Default base URL | `https://grsai.dakka.com.cn` (China node) | User preference for China-based deployment |
| Model identifier | `model.name` used directly | API model names (e.g., `nano-banana-2`) are already human-readable; matches OpenAI/Volcengine pattern |
| Model count | All 13 documented models | User said "related models" — register all |

## Architecture

The Grsai adapter follows the RunningHub async-polling pattern:

1. **Submit** — `POST {base_url}/v1/api/generate` with `replyType="async"`, returns `{"id": "...", "status": "running"}`
2. **Poll** — `GET {base_url}/v1/api/result?id={task_id}` every 5s until terminal status
3. **Map** — terminal response → `ImageGenerationResult`

**Provider key:** `"grsai"` added to `ProviderKey` Literal, registered with `supported_categories=(ModelCategoryKey.image,)`.

## Components

### New files (4)

- `app/core/integrations/grsai/__init__.py` — package docstring only
- `app/core/integrations/grsai/client.py` — `submit_grsai_task(base_url, api_key, request_body, *, timeout_s) -> str` and `query_grsai_result(base_url, api_key, task_id, *, timeout_s) -> dict`. Thin functions over `httpx.AsyncClient`.
- `app/core/integrations/grsai/images.py` — `GrsaiImageApiAdapter` with `async def generate(*, cfg, inp, timeout_s) -> ImageGenerationResult`. Builds request body, submits, polls, maps result.
- `app/core/integrations/grsai/image_capabilities.py` — `resolve_grsai_image_capability(model: str | None)` returning ratio/size constraints per model family.

### Modified files (7)

- `app/core/contracts/provider.py` — add `"grsai"` to `ProviderKey` Literal
- `app/services/llm/provider_bootstrap.py` — register `ProviderSpec(key="grsai", display_name="Grsai", aliases=("grsai",), supported_categories=(image,), default_base_url="https://grsai.dakka.com.cn")`
- `app/services/llm/provider_registry.py` — add `if "grsai" in alias: return "grsai"` to `resolve_provider_key_from_name` (placed before generic fallbacks, after volcengine check)
- `app/core/integrations/image_capabilities.py` — add `grsai` branch to `register_image_model_capability`, `clear_image_model_capability_overrides`, `resolve_image_capability`
- `app/core/tasks/image_generation_tasks.py` — add `GrsaiImageGenerationTask` class + `_build_grsai_impl` static method on `ImageGenerationTask`
- `app/core/tasks/bootstrap.py` — add `("image_generation", "grsai", ImageGenerationTask._build_grsai_impl)` to `TASK_ADAPTER_SPECS`
- `app/services/llm/model_bootstrap.py` — add `_GRSAI_PROVIDER_DEFAULTS` + `_GRSAI_MODELS` (13 models), extend `bootstrap_builtin_db_resources`

### No changes needed

- `app/services/llm/model_identifier.py` — Grsai uses `model.name` directly, falls through to default behavior
- `app/core/contracts/image_generation.py` — existing contract has all needed fields

## Data Flow

### Submit request

`POST {base_url}/v1/api/generate`

Headers:
```
Authorization: Bearer {api_key}
Content-Type: application/json
```

Body:
```json
{
  "model": "nano-banana-2",
  "prompt": "一只边牧在直播间带货",
  "images": ["https://example.com/ref.png"],
  "aspectRatio": "1:1",
  "imageSize": "1K",
  "replyType": "async"
}
```

Field mapping from `ImageGenerationInput`:
- `model` ← `inp.model`
- `prompt` ← `inp.prompt`
- `images` ← `inp.images` (list of `InputImageRef` → list of strings, using `image_url` or data-URI from `file_id`)
- `aspectRatio` ← `inp.target_ratio` (default `"1:1"`)
- `imageSize` ← derived from `inp.resolution_profile` or default `"1K"`; **only sent for nano-banana family** (omitted for gpt-image-2 family)
- `replyType` ← always `"async"`

### Submit response (200)

```json
{"id": "6-f671fc51-d5d7-4eff-a1c7-26e612fe08ab", "status": "running"}
```

### Poll

`GET {base_url}/v1/api/result?id={task_id}` with same auth header, every 5s, until terminal status.

### Poll response (terminal)

```json
{
  "id": "14-5f3cf761-a4bb-486a-8016-77f490998f80",
  "status": "succeeded",
  "progress": 100,
  "results": [{"url": "https://file1.aitohumanize.com/file/abc.png"}],
  "error": ""
}
```

### Mapping to `ImageGenerationResult`

- `images` ← `[ImageItem(url=r["url"]) for r in results]`
- `provider` ← `"grsai"`
- `provider_task_id` ← the task `id`
- `status` ← `"succeeded"` if status=="succeeded", else `"failed"`

## Model List (13 Image Models)

All 13 models registered via `model_bootstrap.py`. Model ID scheme: `grsai-{api_model_name}`.

### nano-banana family (11 models)

| ID | Name | Extra ratios |
|---|---|---|
| `grsai-nano-banana` | `nano-banana` | standard |
| `grsai-nano-banana-fast` | `nano-banana-fast` | standard |
| `grsai-nano-banana-2` | `nano-banana-2` | +1:4, 4:1, 1:8, 8:1 |
| `grsai-nano-banana-2-cl` | `nano-banana-2-cl` | +1:4, 4:1, 1:8, 8:1 |
| `grsai-nano-banana-2-2k-cl` | `nano-banana-2-2k-cl` | +1:4, 4:1, 1:8, 8:1 |
| `grsai-nano-banana-2-4k-cl` | `nano-banana-2-4k-cl` | +1:4, 4:1, 1:8, 8:1 |
| `grsai-nano-banana-pro` | `nano-banana-pro` | standard |
| `grsai-nano-banana-pro-vt` | `nano-banana-pro-vt` | standard |
| `grsai-nano-banana-pro-cl` | `nano-banana-pro-cl` | standard |
| `grsai-nano-banana-pro-vip` | `nano-banana-pro-vip` | standard |
| `grsai-nano-banana-pro-4k-vip` | `nano-banana-pro-4k-vip` | standard |

### gpt-image-2 family (2 models)

| ID | Name | Notes |
|---|---|---|
| `grsai-gpt-image-2` | `gpt-image-2` | supports ratios or "1024x1024" pixel values |
| `grsai-gpt-image-2-vip` | `gpt-image-2-vip` | 1K-4K pixel values only, no ratios |

### Standard ratios (all models)

`auto`, `1:1`, `16:9`, `9:16`, `4:3`, `3:4`, `3:2`, `2:3`, `5:4`, `4:5`, `21:9`

### `params` field per model

`{"family": "nano-banana" | "gpt-image-2"}` — used by the adapter to decide whether to send `imageSize` and by the capability resolver to determine allowed ratios.

## Error Handling

### HTTP errors
- Non-2xx from `/v1/api/generate` or `/v1/api/result` → raise `RuntimeError` with status code + response body (same pattern as RunningHub client)
- Network/timeout errors from `httpx` → propagated as-is, caught by the task layer

### Status mapping
- `succeeded` → `ImageGenerationResult(status="succeeded")`
- `failed` → `ImageGenerationResult(status="failed")` with empty images list; error message logged
- `violation` → treated as `failed`
- `running` → keep polling

### Polling timeout
- Total timeout bounded by `timeout_s` (default 600s, matching RunningHub image timeout)
- If timeout exceeded while status is `running` → raise `TimeoutError` with task ID
- Poll interval: 5s

### Empty results edge case
- If `status=="succeeded"` but `results` is empty/missing → raise `RuntimeError` (same as OpenAI adapter's "no usable data" check)

### Validation
- `prompt` required by existing contract validator
- `model` — if None, let the API reject it (matches OpenAI adapter behavior)

## Testing Strategy

TDD throughout — write failing test first, verify failure, implement, verify pass, commit.

### New test files (4)

1. **`tests/test_grsai_client.py`** — HTTP client tests using `httpx.MockTransport`:
   - `submit_grsai_task` posts to `/v1/api/generate` with correct body + Bearer header
   - `submit_grsai_task` raises on non-2xx with response body in message
   - `query_grsai_result` GETs `/v1/api/result?id=...` with correct query param

2. **`tests/test_grsai_image_adapter.py`** — adapter tests using `monkeypatch` on `grsai.client` module:
   - Submits with `replyType="async"`, polls until `succeeded`, returns correct `ImageGenerationResult`
   - Returns `failed` status when API returns `failed`
   - Raises on empty results despite `succeeded` status
   - Sends `imageSize` for nano-banana family, omits for gpt-image-2 family
   - Maps `target_ratio` → `aspectRatio` correctly
   - Maps `images` (`InputImageRef` list) → string list

3. **`tests/test_grsai_image_capabilities.py`** — capability resolver tests:
   - nano-banana family returns standard 11 ratios
   - nano-banana-2 family returns 15 ratios (standard + 4 extra)
   - gpt-image-2 family returns standard ratios
   - Unknown model returns default ratios

4. **`tests/test_grsai_model_bootstrap.py`** — DB bootstrap tests using in-memory SQLite + `pytest_asyncio.fixture`:
   - Creates provider + 13 models idempotently
   - Preserves user-configured api_key/base_url on re-bootstrap
   - All models have `family` in params

### Extended existing test files (2)

5. **`tests/test_task_registry.py`** — +3 tests:
   - `test_resolve_provider_key_for_grsai_aliases` — "grsai"/"Grsai"/"GRSAI" all resolve to "grsai"
   - `test_grsai_provider_spec_registered` — spec has correct display_name, categories, base_url
   - `test_grsai_image_task_builds_adapter_impl` — `ImageGenerationTask._build_grsai_impl` returns `GrsaiImageGenerationTask`

6. **`tests/test_runninghub_model_identifier.py`** — +1 test:
   - `test_grsai_returns_model_name` — `resolve_model_identifier(model, "grsai")` returns `model.name` directly

**Total new tests:** ~20 across 4 new files + 2 extended files.
