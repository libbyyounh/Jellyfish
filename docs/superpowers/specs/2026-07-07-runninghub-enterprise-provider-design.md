# RunningHub 企业版供应商 — 设计规格

> 日期: 2026-07-07
> 分支: `feat/runninghub-enterprise-provider`
> 前置: `feat/runninghub-provider`（个人版，已合并到 `main`，commit `e31fb5c`）

## 目标

为 Jellyfish 增加第二个 RunningHub 供应商：`runninghub-enterprise`（企业版）。企业版走 RunningHub 官方加速通道，集成万相 2.7 / LTX2.3 / HappyHorse / 可灵 / 全能视频 系列视频模型。参考实现：`~/Downloads/toonflow-runninghub-enterprise.ts`。

## 与个人版的差异

| 维度 | 个人版 (`runninghub`) | 企业版 (`runninghub-enterprise`) |
|------|----------------------|-------------------------------|
| API 风格 | `/run/ai-app/{workflowId}` + `nodeInfoList`（ComfyUI 节点） | 直接 REST：`/openapi/v2/{vendor}/{model}/{action}` + JSON body |
| 模型数量 | 5 图 + 4 视频 = 9 | 14 视频（无图/文/TTS） |
| 模型标识 | 数字 `workflowId`（如 `"2052744677727715329"`） | 字符串 `modelName`（如 `"wan-2.7/image-to-video"`） |
| 多参考 | 仅 4 帧 LTX（imageReference:4，固定 4 张） | 1-9 张图片参考（imageReference:N，N=3/7/9） |
| 分辨率 | 固定（480P/720P） | 多选（480P/720P/1080P，部分 4K） |
| 音频 | 无 | 5 个可灵/HappyHorse 模型支持 `audio: optional` |
| 共享 | — | `upload_media` / `query_task` / `poll_until_done`（已在 `runninghub/client.py`） |

## 契约扩展：`VideoGenerationInput`

企业版模型需要 `VideoGenerationInput` 当前没有的 3 个字段。全部为 Optional + `None` 默认值，对现有供应商（openai / volcengine / runninghub 个人版）无影响。

```python
# app/core/contracts/video_generation.py
class VideoGenerationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # ... 现有字段不变 ...
    prompt: Optional[str] = ...
    first_frame_base64: Optional[str] = ...
    last_frame_base64: Optional[str] = ...
    key_frame_base64: Optional[str] = ...
    model: Optional[str] = ...
    ratio: VideoRatio = ...
    seconds: Optional[int] = ...
    seed: Optional[int] = ...
    watermark: Optional[bool] = ...

    # 新增 — 企业版多参考模型
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
```

### 模式到契约字段的映射

| 企业版 mode | 契约字段 | 说明 |
|-------------|---------|------|
| `singleImage` | `first_frame_base64` | 1 张图 |
| `startEndRequired` | `first_frame_base64` + `last_frame_base64` | 1-2 张图（`lastImageUrl` 允许 `None`） |
| `imageReference:3` | `first_frame_base64` + `last_frame_base64` + `key_frame_base64` | 1-3 张图（过滤 None，**不补齐**） |
| `imageReference:7` / `imageReference:9` | `reference_frames_base64[:N]` | 多图参考，**不补齐** — 发送实际数量（≤N）；需前端支持多参考上传 |

### 跳过的模型

`happyhorse-1.0/video-edit` 需要**视频**参考输入，Jellyfish 当前无视频输入契约。本规格不实现该模型（14/15）。如未来需要，再加 `reference_video_base64` 字段。

## 架构：独立子包（方案 A）

企业版逻辑放在独立子包 `app/core/integrations/runninghub/enterprise/`，与个人版模块并行。复用个人版 `client.py` 的 `upload_media` / `query_task` / `poll_until_done`，不重复实现。

### 新建文件

```
backend/app/core/integrations/runninghub/enterprise/
├── __init__.py
├── client.py              # submit_enterprise_task()
├── request_builders.py    # 14 个 per-model JSON body 构造器 + ENTERPRISE_VIDEO_BUILDERS dict
├── video.py               # RunningHubEnterpriseVideoApiAdapter (create + get)
└── video_capabilities.py  # resolve_runninghub_enterprise_video_capability(model)
```

### 修改文件

| 文件 | 改动 |
|------|------|
| `app/core/contracts/provider.py` | `ProviderKey` Literal 加 `"runninghub-enterprise"` |
| `app/core/contracts/video_generation.py` | 加 `reference_frames_base64` / `resolution` / `audio` 字段 |
| `app/services/llm/provider_bootstrap.py` | 注册企业版 `ProviderSpec`（仅 video，base_url 同个人版） |
| `app/services/llm/provider_registry.py` | 别名解析：`runninghub-enterprise` / `rh-enterprise` / `RunningHub Enterprise` |
| `app/core/integrations/video_capabilities.py` | `register_video_model_capability` / `resolve_video_capability` 加 enterprise 分支 |
| `app/core/tasks/video_generation_tasks.py` | `VideoGenerationTask._build_runninghub_enterprise_impl` 静态方法 |
| `app/core/tasks/bootstrap.py` | `TASK_ADAPTER_SPECS` 加 `("video_generation", "runninghub-enterprise", ...)` |
| `app/services/llm/model_identifier.py` | `runninghub-enterprise` 返回 `params["model_name"]` |
| `app/services/llm/model_bootstrap.py` | 企业版 provider 行 + 14 个 model 行（幂等 upsert） |

## 模块详细设计

### `enterprise/client.py`

```python
async def submit_enterprise_task(
    base_url: str,
    api_key: str,
    endpoint_path: str,         # "/openapi/v2/alibaba/wan-2.7/image-to-video"
    request_body: dict,
    *,
    timeout_s: float = 60.0,
) -> str:
    """POST {base_url}{endpoint_path} with JSON body. Returns RunningHub task id.

    Raises:
        httpx.HTTPStatusError: 非 2xx 响应
        RuntimeError: 响应缺少 taskId
    """
```

`upload_media` 和 `query_task` 从 `app.core.integrations.runninghub.client` 导入 — 端点与响应结构完全一致。

### `enterprise/request_builders.py`

```python
@dataclass(frozen=True, slots=True)
class EnterpriseVideoBuildSpec:
    endpoint_path: str
    image_count: int            # 最少需要的图片数（1 / 2 / N）
    mode: str                   # "singleImage" | "startEndRequired" | "imageReference:N"
    build_request: Callable[[VideoGenerationInput, list[str]], dict]

ENTERPRISE_VIDEO_BUILDERS: dict[str, EnterpriseVideoBuildSpec] = {
    "wan-2.7/image-to-video": ...,
    "wan-2.7/reference-to-video": ...,
    "ltx-2.3/image-to-video": ...,
    "ltx-2.3/image-to-video-lora": ...,
    "happyhorse-1.0/image-to-video": ...,
    "happyhorse-1.0/reference-to-video": ...,
    # happyhorse-1.0/video-edit 跳过（需要视频输入）
    "kling-video-o3-pro/image-to-video": ...,
    "kling-video-o3-std/image-to-video": ...,
    "kling-v3.0-pro/image-to-video": ...,
    "kling-v3.0-std/image-to-video": ...,
    "rhart-video-g-official/reference-to-video": ...,
    "rhart-video-g/image-to-video": ...,
    "rhart-video-v3.1-fast/start-end-to-video": ...,
    "rhart-video-v3.1-fast/image-to-video": ...,
}
```

每个 `build_request` 函数接收 `VideoGenerationInput` + 已上传的图片 URL 列表，返回 JSON body dict。body 的字段名、magic string、`cfgScale` 值等**逐字移植**自 .ts，不"改进"。

#### 关键 builder 示例

```python
def _build_wan27_image_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "resolution": inp.resolution or "720P",
        "duration": str(inp.seconds or 5),
        "promptExtend": True,
        "seed": None,
    }

def _build_kling_v3_pro(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "firstImageUrl": urls[0],
        "lastImageUrl": urls[1] if len(urls) >= 2 else None,
        "duration": str(inp.seconds or 5),
        "sound": inp.audio is not False,   # None → True（匹配 .ts 的 config.audio !== false）
        "multiShot": False,
        "shotType": "customize",
        "negativePrompt": None,
        "cfgScale": 0.5,                    # pro 变体
    }

def _build_wan27_reference_to_video(inp: VideoGenerationInput, urls: list[str]) -> dict:
    return {
        "prompt": inp.prompt or "",
        "imageUrls": urls,                  # 不补齐 — 发送实际数量
        "videoUrls": [],
        "resolution": inp.resolution or "720P",
        "duration": str(inp.seconds or 5),
        "aspectRatio": inp.ratio,
        "promptExtend": True,
        "seed": None,
    }
```

#### 14 个模型的端点与模式

| modelName | endpoint_path | mode | image_count | duration | resolution |
|-----------|---------------|------|-------------|----------|------------|
| `wan-2.7/image-to-video` | `/openapi/v2/alibaba/wan-2.7/image-to-video` | `startEndRequired` | 1 | [5] | [720P] |
| `wan-2.7/reference-to-video` | `/openapi/v2/alibaba/wan-2.7/reference-to-video` | `imageReference:9` | 1 | [5] | [720P, 1080P] |
| `ltx-2.3/image-to-video` | `/openapi/v2/rhart-video/ltx-2.3/image-to-video` | `singleImage` | 1 | [5] | [480P] |
| `ltx-2.3/image-to-video-lora` | `/openapi/v2/rhart-video/ltx-2.3/image-to-video-lora` | `singleImage` | 1 | [5] | [480P] |
| `happyhorse-1.0/image-to-video` | `/openapi/v2/alibaba/happyhorse-1.0/image-to-video` | `singleImage` | 1 | [5] | [720P, 1080P] |
| `happyhorse-1.0/reference-to-video` | `/openapi/v2/alibaba/happyhorse-1.0/reference-to-video` | `imageReference:9` | 1 | [5] | [720P, 1080P] |
| `kling-video-o3-pro/image-to-video` | `/openapi/v2/kling-video-o3-pro/image-to-video` | `startEndRequired` | 1 | [5, 10] | [720P, 1080P] |
| `kling-video-o3-std/image-to-video` | `/openapi/v2/kling-video-o3-std/image-to-video` | `startEndRequired` | 1 | [5, 10] | [720P, 1080P] |
| `kling-v3.0-pro/image-to-video` | `/openapi/v2/kling-v3.0-pro/image-to-video` | `startEndRequired` | 1 | [5, 10] | [720P, 1080P] |
| `kling-v3.0-std/image-to-video` | `/openapi/v2/kling-v3.0-std/image-to-video` | `startEndRequired` | 1 | [5, 10] | [720P, 1080P] |
| `rhart-video-g-official/reference-to-video` | `/openapi/v2/rhart-video-g-official/reference-to-video` | `imageReference:9` | 1 | [6, 8] | [720P] |
| `rhart-video-g/image-to-video` | `/openapi/v2/rhart-video-g/image-to-video` | `imageReference:7` | 1 | [6, 10, 15, 20, 30] | [480P, 720P] |
| `rhart-video-v3.1-fast/start-end-to-video` | `/openapi/v2/rhart-video-v3.1-fast/start-end-to-video` | `startEndRequired` | 1 | [8] | [720P, 1080P] |
| `rhart-video-v3.1-fast/image-to-video` | `/openapi/v2/rhart-video-v3.1-fast/image-to-video` | `imageReference:3` | 1 | [8] | [720P, 1080P] |

### `enterprise/video.py`

```python
class RunningHubEnterpriseVideoApiAdapter:
    """RunningHub 企业版视频适配器：create + get 两阶段，Task 层轮询。"""

    async def create_video(self, *, cfg, input_, timeout_s) -> str:
        model_name = input_.model or ""
        spec = ENTERPRISE_VIDEO_BUILDERS.get(model_name)
        if spec is None:
            raise ValueError(f"Unknown RunningHub enterprise video model: {model_name}")

        image_urls = await _resolve_enterprise_image_urls(input_, spec, cfg, timeout_s)
        request_body = spec.build_request(input_, image_urls)

        base_url = cfg.base_url or "https://www.runninghub.cn"
        return await submit_enterprise_task(
            base_url, cfg.api_key, spec.endpoint_path, request_body, timeout_s=timeout_s
        )

    async def get_video(self, *, cfg, video_id, timeout_s) -> dict[str, Any]:
        base_url = cfg.base_url or "https://www.runninghub.cn"
        return await query_task(base_url, cfg.api_key, video_id, timeout_s=timeout_s)
```

`_resolve_enterprise_image_urls` 按 `spec.mode` 分发：
- `singleImage` → 上传 `first_frame_base64` → 1 URL
- `startEndRequired` → 上传 `first_frame_base64` + `last_frame_base64`（尾帧可为 None → 过滤）
- `imageReference:3` → 上传 `first/last/key_frame_base64`（过滤 None），**不补齐**（与个人版 4 帧 LTX 的补齐逻辑不同 — 企业版多参考模型接受 1-N 张，不要求固定数量）
- `imageReference:7` / `imageReference:9` → 上传 `reference_frames_base64[:N]`，**不补齐**

### `enterprise/video_capabilities.py`

```python
def resolve_runninghub_enterprise_video_capability(model: Model) -> VideoModelCapability:
    """从 Model.params['duration_resolution_map'] 派生能力。"""
    params = model.params or {}
    drm = params.get("duration_resolution_map") or []
    durations: set[int] = set()
    resolutions: set[str] = set()
    for entry in drm:
        durations.update(entry.get("duration") or [])
        resolutions.update(entry.get("resolution") or [])
    return VideoModelCapability(
        allowed_ratios={"16:9", "9:16"},
        allowed_durations=durations or {5},
        allowed_resolutions=resolutions or {"720P"},
        min_seconds=min(durations) if durations else 5,
        max_seconds=max(durations) if durations else 5,
    )
```

数据源单一：DB 中的 `Model.params`（由 `model_bootstrap.py` 写入）。不重复硬编码。

## Task 层 + DB bootstrap + 服务层

### Task 层（最小改动）

现有 `RunningHubVideoGenerationTask` 已接受 `adapter` 参数（个人版 Task 7 加的）。企业版只需一个新静态方法：

```python
# app/core/tasks/video_generation_tasks.py
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

轮询循环 `RunningHubVideoGenerationTask._poll_and_get_result` 原样复用 — 个人版与企业版都用 `query_task` → `results[0].url`。

`bootstrap.py` 注册：
```python
TASK_ADAPTER_SPECS = (
    # ... 现有 6 项 ...
    ("video_generation", "runninghub-enterprise", VideoGenerationTask._build_runninghub_enterprise_impl),
)
```

无 image task adapter — 企业版无图片模型。

### DB bootstrap — 14 个 model 行

`model_bootstrap.py` 扩展第二个 provider + model 集合。幂等 upsert，同个人版：

```python
_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS = {
    "id": "runninghub-enterprise",
    "name": "RunningHub 企业版",
    "base_url": "https://www.runninghub.cn",
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
    # ... 13 more ...
]
```

Model ID 方案：`runninghub-enterprise-{modelName 中 / 替换为 -}`。例：`wan-2.7/image-to-video` → `runninghub-enterprise-wan-2.7-image-to-video`。

`bootstrap_builtin_db_resources(session)` 扩展为 upsert 两个 provider + 两组 model。同样幂等：provider 行保留用户 `api_key` / `base_url` / `status`；model 行刷新 `name` / `params` / `description`。

### 服务层 wiring

`resolve_model_identifier` 加企业版分支：

```python
def resolve_model_identifier(model: Model, provider_key: str) -> str:
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

服务层（`image_task_runner.py` / `generated_video.py`）已调用 `resolve_model_identifier(model, provider_cfg.provider)` — 无需改动。企业版 `inp.model` 将是 `modelName` 字符串（如 `"wan-2.7/image-to-video"`），企业版 adapter 用它查 `ENTERPRISE_VIDEO_BUILDERS`。

## 测试计划

### 新建测试文件（5 个）

| 文件 | 测试数 | 验证内容 |
|------|--------|---------|
| `test_runninghub_enterprise_client.py` | 3 | `submit_enterprise_task` POST 正确 JSON 到正确 path；缺 taskId 抛错；非 2xx 抛错。用 `httpx.MockTransport`。 |
| `test_runninghub_enterprise_request_builders.py` | 14 | 每个模型一个测试 — 验证 JSON body 精确结构（字段名、值、`None` 处理）。将 .ts 的 request body 作为期望输出 fixture。 |
| `test_runninghub_enterprise_video_adapter.py` | 6 | `create_video` 分发到正确 endpoint；`get_video` 查询；未知 model 抛错；缺图抛错；多参考上传 + 发送 N 个 URL（不补齐）；`singleImage` 模式上传 1 个 URL。 |
| `test_runninghub_enterprise_capabilities.py` | 4 | resolver 从 `Model.params['duration_resolution_map']` 派生正确的 `allowed_ratios` / `allowed_durations` / `allowed_resolutions`。 |
| `test_video_generation_input.py` | 3 | 新字段接受合法输入；拒绝非法（如 `reference_frames_base64` 含非字符串）；默认 `None`。 |

### 扩展现有测试文件（3 个）

| 文件 | 新增测试 | 验证内容 |
|------|---------|---------|
| `test_task_registry.py` | +2 | 企业版 adapter 已注册；`_build_runninghub_enterprise_impl` 返回 `RunningHubVideoGenerationTask`（企业版 adapter）。 |
| `test_runninghub_model_bootstrap.py` | +3 | 企业版 provider + 14 model 创建；二次调用幂等；保留用户 `api_key`。 |
| `test_runninghub_model_identifier.py` | +2 | 企业版返回 `model_name`；params 缺失时回退 `model.name`。 |

### 关键边界用例

1. **多参考不补齐** — 企业版 `imageReference:N` 发送实际数量（≤N），不像个人版 4 帧补齐到固定 4。测试：传 3 张图给 `imageReference:9` → body 的 `imageUrls` 长度为 3。

2. **`startEndRequired` 单图** — `lastImageUrl` 为 `None`（不省略字段）。.ts 允许此行为。测试：只传 `first_frame_base64` → body 有 `lastImageUrl: None`。

3. **分辨率默认** — `inp.resolution` 为 `None` 时，builder 用 model 第一个允许分辨率。测试：传 `resolution=None` → body 用默认。

4. **音频默认** — `inp.audio` 为 `None` 时，kling builder 设 `sound: True`（匹配 .ts 的 `config.audio !== false`）。测试：`audio=None` → `sound: True`；`audio=False` → `sound: False`。

5. **`cfgScale` pro vs std** — v3.0-pro 用 `0.5`，v3.0-std 用 `0.8`。测试分别验证。

### 不在范围

- 集成测试（真实 API 调用）— 与个人版规格一致，超出范围。
- `happyhorse-1.0/video-edit` 模型 — 需要视频输入契约，本规格不实现。
- 前端改动 — 新字段全为 Optional + 默认值，前端可忽略；若要暴露多参考上传/分辨率选择，属独立前端任务。
- OpenAPI 重新生成 — 接口签名不变（`VideoGenerationInput` 是内部契约，非 API 入参）。

## 已知问题（沿用个人版）

- `backend/tests/core/integrations/test_video_capabilities.py` collection error（`infer_ratio_from_size` 从未定义）— `main` 上已存在，与本特性无关。
- 13 个预存在测试失败（12 API envelope shape + 1 mock DB）— `main` 上已存在，与本特性无关。

## 验收标准

1. `runninghub-enterprise` provider 在 UI 中可见（DB bootstrap 后），用户可填 API key。
2. 14 个企业版视频模型在 UI 中可选。
3. 每个模型的请求 body 与 .ts 参考实现逐字一致（测试 fixture 验证）。
4. 多参考模型接受 1-N 张图，不补齐。
5. `startEndRequired` 模型接受 1-2 张图（尾帧可选）。
6. 分辨率/音频字段通过 `VideoGenerationInput` 透传，默认值合理。
7. 企业版与个人版共存，互不干扰（两个 provider 行，两组 model 行，两个 task adapter）。
8. 所有新测试通过；现有测试无新增失败。
