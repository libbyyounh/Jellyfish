# RunningHub 供应商接入设计

**日期**：2026-07-06
**状态**：待实现
**参考**：`~/Downloads/toonflow-runninghub-person.ts`（Toonflow RunningHub 个人消费版适配器）

## 背景与目标

Jellyfish 当前仅支持 `openai` / `volcengine` 两类供应商（外加 `aliyun_bailian` 仅文本）。需要新增第三方供应商 `runninghub`（RunningHub 个人消费版），接入其异步工作流 API，提供 5 个图片模型 + 4 个视频模型。

RunningHub 与现有供应商的关键差异：
- **异步工作流模式**：submit task → poll status → fetch result URL（图片也需要轮询，不同于 OpenAI 图片的同步接口）
- **每个模型（workflowId）有专属节点配置**：不同的 `nodeId` / `fieldName` 组合
- **参考图需要先上传**：base64 图片需通过 `/openapi/v2/media/upload/binary` 上传换取 URL
- **两个提交端点**：`/run/ai-app/{workflowId}`（大多数）与 `/run/workflow/{workflowId}`（4 帧 LTX 专用）

## 范围

**包含**：
- 新增 `runninghub` 供应商注册（image + video 类别）
- 9 个预置模型启动时自动 upsert
- HTTP client、节点配置、image/video adapter、Task 层接入
- Capability 声明与校验
- 单元测试

**不包含**：
- Text 模型（RunningHub 不支持）
- TTS（.ts 文件标注"暂未开放"）
- 前端改动（UI 数据驱动，新供应商会自动出现在下拉列表）
- OpenAPI 重新生成（接口签名不变）
- 集成测试（不真打 RunningHub API）

## 架构

### 文件布局

```
backend/app/
  core/
    contracts/provider.py                          # 修改: ProviderKey 加 "runninghub"
    integrations/
      runninghub/                                  # 新增目录
        __init__.py
        client.py                                  # HTTP 底层: submit/query/upload/poll
        node_configs.py                            # 9 个 workflowId → nodeInfoList 模板
        images.py                                  # RunningHubImageApiAdapter
        video.py                                   # RunningHubVideoApiAdapter
        image_capabilities.py                      # capability resolver
        video_capabilities.py                      # capability resolver
      image_capabilities.py                        # 修改: resolve_* 加 runninghub 分支
      video_capabilities.py                        # 修改: 同上
    tasks/
      image_generation_tasks.py                    # 修改: 加 RunningHubImageGenerationTask + _build_runninghub_impl
      video_generation_tasks.py                    # 修改: 加 RunningHubVideoGenerationTask + _build_runninghub_impl
      bootstrap.py                                 # 修改: TASK_ADAPTER_SPECS 加 2 行
  services/
    llm/
      provider_bootstrap.py                        # 修改: 注册 runninghub ProviderSpec
      provider_registry.py                         # 修改: resolve_provider_key_from_name 加 runninghub 兜底
      model_bootstrap.py                           # 新增: bootstrap_builtin_db_resources()
  bootstrap.py                                     # 不变（纯内存注册）
  main.py                                          # 修改: lifespan 加 await bootstrap_builtin_db_resources()
```

### 调用链

```
HTTP 请求 → Service 层（image_task_runner / generated_video）
         → ImageGenerationTask / VideoGenerationTask（按 provider 分派）
         → RunningHubImage/VideoGenerationTask
         → RunningHubImage/VideoApiAdapter
         → client.py（submit → poll → result URL）
         → ImageGenerationResult / VideoGenerationResult
```

## 数据模型

### Provider 行（id=`runninghub`）

| 字段 | 值 |
|------|-----|
| id | `runninghub` |
| name | `RunningHub` |
| base_url | `https://www.runninghub.cn` |
| image_base_url | `NULL` |
| video_base_url | `NULL` |
| api_key | `""`（用户在 UI 填） |
| api_secret | `""` |
| status | `testing` |
| description | `RunningHub 个人消费版：短剧图片模型 + WAN2.2/LTX2.3 视频模型` |

### Model 行（9 行，id 格式 `runninghub-{workflowId}`）

| id | name | category | params | description |
|----|------|----------|--------|-------------|
| `runninghub-2052744677727715329` | 短剧专用图片模型 | image | `{"workflow_id":"2052744677727715329","mode":"text"}` | 短剧场景专用，支持自定义宽高 |
| `runninghub-2003681895185563650` | Z-image 超真实感短剧定妆照 | image | `{"workflow_id":"2003681895185563650","mode":"text"}` | 超真实感定妆照文生图 |
| `runninghub-1970396677775499266` | Qwen-image 文生图 | image | `{"workflow_id":"1970396677775499266","mode":"text"}` | 支持正反向提示词与多比例 |
| `runninghub-2029488621429989377` | Qwen Image Edit 2511图生图 | image | `{"workflow_id":"2029488621429989377","mode":"singleImage"}` | 图生图，参考图+提示词 |
| `runninghub-2058719340626796546` | Z-Image在线8K直出 | image | `{"workflow_id":"2058719340626796546","mode":"text"}` | 8K 直出文生图 |
| `runninghub-1956699246381469698` | WAN2.2 官方加速 | video | `{"workflow_id":"1956699246381469698","mode":"singleImage","duration":[5],"resolution":["480P"]}` | 图生视频，5s 480P |
| `runninghub-2029759632314474498` | LTX2.3 图生视频 | video | `{"workflow_id":"2029759632314474498","mode":"singleImage","duration":[5,10],"resolution":["720P"]}` | 5/10s 720P |
| `runninghub-2055155307592077313` | LTX2.3 图生长视频多镜头分段 | video | `{"workflow_id":"2055155307592077313","mode":"singleImage","duration":[10],"resolution":["720P"]}` | 多镜头分段 |
| `runninghub-2054820963426021378` | LTX2.3 四帧丝滑流转 | video | `{"workflow_id":"2054820963426021378","mode":"imageReference:4","duration":[5],"resolution":["720P"]}` | 4 张参考图 |

### Bootstrap 时机

- **`bootstrap_all_registries()`**（纯内存）：保持不变，只往 provider/task registry 里加 runninghub 注册。会在启动时和惰性路径（如 `ImageGenerationTask.__init__`）被调用，必须幂等且不碰 DB。
- **`bootstrap_builtin_db_resources()`**（新增，DB 级）：只在 `lifespan` 启动时调用一次。幂等 upsert provider 行 + 9 个 model 行。

### 幂等策略

- **Provider**：按 `id='runninghub'` 查。存在则跳过（**不覆盖**用户已填的 `api_key` / `base_url` / `status`）；不存在则插入默认行。
- **Model**：按 `id` 查。存在则更新 `name` / `params` / `description`（保持版本最新）；不存在则插入。不触碰 `created_by`。

## HTTP Client（`client.py`）

无状态工具函数，镜像 .ts 文件的 4 个 HTTP 操作。统一用 `httpx.AsyncClient`，header `Authorization: Bearer {api_key}`，复用 `http_logging.py` 日志辅助。

```python
async def submit_ai_app_task(base_url, api_key, workflow_id, node_info_list) -> str
    # POST {base_url}/openapi/v2/run/ai-app/{workflow_id}
    # body: {"nodeInfoList":..., "instanceType":"default", "usePersonalQueue":"true"}
    # 返回 task_id；响应缺 task_id 时 raise

async def submit_workflow_task(base_url, api_key, workflow_id, node_info_list) -> str
    # POST {base_url}/openapi/v2/run/workflow/{workflow_id}  (4帧LTX专用)
    # body: {"addMetadata":true, "nodeInfoList":..., "instanceType":"default", "usePersonalQueue":"true"}

async def query_task(base_url, api_key, task_id) -> dict
    # POST {base_url}/openapi/v2/query  body: {"taskId":...}
    # 返回原始响应 dict（含 status / results / errorMessage）

async def upload_media(base_url, api_key, mime: str, bytes_data: bytes) -> str
    # POST {base_url}/openapi/v2/media/upload/binary  (multipart/form-data，手工拼 boundary)
    # 返回 download_url；code != 0 时 raise

async def poll_until_done(base_url, api_key, task_id, interval=5.0, timeout=600.0) -> str
    # 循环 query_task：
    #   SUCCESS → 返回 results[0].url
    #   FAILED/ERROR → raise（含 errorMessage / errorCode）
    #   其他 → sleep(interval) 继续
    # 超时 raise
```

## 节点配置（`node_configs.py`）

按 workflowId 硬编码。每个条目包含端点类型与 `build_nodes` 函数：

```python
@dataclass
class ImageNodeConfig:
    endpoint: Literal["ai_app", "workflow"]   # image 全部走 ai_app
    build_nodes: Callable[[ImageGenerationInput, str | None], list[dict]]
    requires_image: bool                       # True = singleImage 模式

@dataclass
class VideoNodeConfig:
    endpoint: Literal["ai_app", "workflow"]   # 4帧LTX 走 workflow
    build_nodes: Callable[[VideoGenerationInput, str | list[str]], list[dict]]
    image_count: int                           # 1 或 4

IMAGE_NODE_CONFIGS: dict[str, ImageNodeConfig] = {
    "2052744677727715329": ImageNodeConfig("ai_app", _build_duanju_nodes,      requires_image=False),
    "2003681895185563650": ImageNodeConfig("ai_app", _build_zimage_zhibao_nodes, requires_image=False),
    "1970396677775499266": ImageNodeConfig("ai_app", _build_qwen_image_nodes,  requires_image=False),
    "2029488621429989377": ImageNodeConfig("ai_app", _build_qwen_edit_nodes,   requires_image=True),
    "2058719340626796546": ImageNodeConfig("ai_app", _build_zimage_8k_nodes,   requires_image=False),
}

VIDEO_NODE_CONFIGS: dict[str, VideoNodeConfig] = {
    "1956699246381469698": VideoNodeConfig("ai_app",   _build_wan22_nodes,           image_count=1),
    "2029759632314474498": VideoNodeConfig("ai_app",   _build_ltx23_standard_nodes,  image_count=1),
    "2055155307592077313": VideoNodeConfig("ai_app",   _build_ltx23_multishot_nodes, image_count=1),
    "2054820963426021378": VideoNodeConfig("workflow", _build_ltx23_fourframe_nodes, image_count=4),
}
```

每个 `build_nodes` 函数完整迁移 .ts 文件中对应的 `nodeInfoList` 构造逻辑，包括：
- 短剧专用：text + width + height 三节点
- Z-image 定妆照：仅 value 节点
- Qwen-image 文生图：正向/反向提示词 + 比例映射 + 5 组 lora 参数 + seed/steps/sampler/scheduler + unet_name
- Qwen Image Edit：image + prompt 两节点
- Z-Image 8K：仅 text 节点
- WAN2.2：image(790) + prompt(809) + duration(789) + max_width/max_height(791)
- LTX2.3 标准：image(98) + video_length(185,=duration*24) + width(222) + height(223) + prompt(224)
- LTX2.3 多镜头：image(584) + prompt(620) + prompt分段(621)
- LTX2.3 四帧：4 张参考图(1361-1364) + 提示词(1473)

## Adapter 层

### `images.py` — `RunningHubImageApiAdapter`

```python
class RunningHubImageApiAdapter:
    async def generate(self, *, cfg, inp, timeout_s) -> ImageGenerationResult:
        workflow_id = inp.model  # service 层把 workflow_id 透传到 inp.model
        config = IMAGE_NODE_CONFIGS.get(workflow_id)
        if not config:
            raise ValueError(f"Unknown RunningHub image workflow: {workflow_id}")

        image_url = None
        if config.requires_image:
            image_url = await _resolve_image_url(inp.images, cfg, timeout_s)

        node_info_list = config.build_nodes(inp, image_url)
        task_id = await client.submit_ai_app_task(cfg.base_url, cfg.api_key, workflow_id, node_info_list)
        result_url = await client.poll_until_done(cfg.base_url, cfg.api_key, task_id)

        return ImageGenerationResult(
            images=[ImageItem(url=result_url)],
            provider="runninghub",
            provider_task_id=task_id,
            status="succeeded",
        )
```

**轮询在 adapter 内部完成**，对外保持同步语义（与现有 `OpenAIImageApiAdapter` 一致，Task 层无需改动基类）。

### `video.py` — `RunningHubVideoApiAdapter`

```python
class RunningHubVideoApiAdapter:
    async def create_video(self, *, cfg, input_, timeout_s) -> str:
        """提交任务，返回 task_id（供 Task 层轮询）"""
        workflow_id = input_.model
        config = VIDEO_NODE_CONFIGS.get(workflow_id)
        if not config:
            raise ValueError(f"Unknown RunningHub video workflow: {workflow_id}")
        image_urls = await _upload_references(input_, config.image_count, cfg, timeout_s)
        node_info_list = config.build_nodes(input_, image_urls)
        if config.endpoint == "workflow":
            return await client.submit_workflow_task(cfg.base_url, cfg.api_key, workflow_id, node_info_list)
        return await client.submit_ai_app_task(cfg.base_url, cfg.api_key, workflow_id, node_info_list)

    async def get_video(self, *, cfg, video_id, timeout_s) -> dict:
        """供 Task 层轮询调用，返回原始响应 dict"""
        return await client.query_task(cfg.base_url, cfg.api_key, video_id)
```

### 参考图 URL 解析策略

- **Image（Qwen Edit）**：`InputImageRef.image_url` 有值直接用；只有 `file_id` 时通过文件服务取 URL；都没有则报错。
- **Video**：`first_frame_base64` / `key_frame_base64` 是 base64，必须先 `upload_media` 上传到 RunningHub 拿 URL（与 .ts 一致）。4 帧模型需要 4 张，不足则按 .ts 逻辑用最后一张补齐。

### workflow_id 传递

- Model 行 `params.workflow_id` 存 workflowId
- Service 层（`image_task_runner.py` / `generated_video.py`）在构造 `run_args["input"]` 字典时，从 Model 行的 `params.workflow_id` 读取，写入 `input["model"]`
- `ImageGenerationInput.model` / `VideoGenerationInput.model` 字段即承载 workflow_id
- Adapter 从 `inp.model` 读 workflow_id，查 `IMAGE_NODE_CONFIGS` / `VIDEO_NODE_CONFIGS`

**实现位置**：需要在 service 层构造 `run_args` 的上游（如 `image_task_runner.py` 中构建 `run_args["input"]` 的位置，以及 `generated_video.py` 中类似位置）增加一段：当 `provider == "runninghub"` 时，把 model 行的 `params.workflow_id` 取出来放进 `input["model"]`。具体落点在实现计划中定位。

### 4 帧模型参考图来源

Jellyfish 的 `VideoGenerationInput` 只有 3 个 frame 字段（`first_frame_base64` / `last_frame_base64` / `key_frame_base64`），但 RunningHub 4 帧 LTX 模型需要 4 张图。处理策略（镜像 .ts 文件的补齐逻辑）：

1. 按顺序收集 `first_frame_base64` → `last_frame_base64` → `key_frame_base64` 中非空的 base64
2. 依次上传到 RunningHub 拿 URL
3. 不足 4 张时，用最后一张补齐到 4 张（与 .ts `while (imageUrls.length < 4) imageUrls.push(imageUrls[imageUrls.length - 1])` 一致）
4. 至少需要 1 张图，否则报错

**已知局限**：Jellyfish 当前 UI 未必暴露 3 个 frame 上传入口。若实际只能传 1 张，则 4 帧全部用同一张图——功能可用但效果退化。这是 Jellyfish 输入侧的限制，不在本次接入范围内解决。

## Task 层

### Image — `RunningHubImageGenerationTask`

跟随 `OpenAIImageGenerationTask` 模式（adapter 内部轮询，Task 层不轮询）：

```python
class RunningHubImageGenerationTask(AbstractImageGenerationTask):
    def __init__(self, *, adapter=None, provider_config, input_, timeout_s=600.0):
        super().__init__(provider_config=provider_config, input_=input_, timeout_s=timeout_s)
        self._adapter = adapter or RunningHubImageApiAdapter()
        self._deferred = None

    async def _create_task(self):
        self._deferred = await self._adapter.generate(
            cfg=self._cfg, inp=self._input, timeout_s=self._timeout_s)

    async def _poll_and_get_result(self):
        assert self._deferred is not None
        return self._deferred
```

`timeout_s` 默认 600s（RunningHub 任务最长 10 分钟，与 .ts 一致）。

在 `ImageGenerationTask` 类上加静态方法 `_build_runninghub_impl`。

### Video — `RunningHubVideoGenerationTask`

跟随 `VolcengineVideoGenerationTask` 模式（Task 层轮询）：

```python
class RunningHubVideoGenerationTask(AbstractVideoGenerationTask):
    def __init__(self, *, adapter=None, provider_config, input_,
                 poll_interval_s=5.0, timeout_s=600.0):
        super().__init__(provider_config=provider_config, input_=input_,
                         poll_interval_s=poll_interval_s, timeout_s=timeout_s)
        self._adapter = adapter or RunningHubVideoApiAdapter()

    async def _create_task(self):
        self._provider_task_id = await self._adapter.create_video(
            cfg=self._cfg, input_=self._input, timeout_s=self._timeout_s)

    async def _poll_and_get_result(self):
        task_id = self._provider_task_id or ""
        if not task_id:
            raise RuntimeError("RunningHub poll missing task id")
        while True:
            meta = await self._adapter.get_video(
                cfg=self._cfg, video_id=task_id, timeout_s=self._timeout_s)
            status_val = str(meta.get("status") or "")
            if status_val == "SUCCESS":
                results = meta.get("results") or []
                url = results[0].get("url") if results else None
                if not url:
                    raise RuntimeError("RunningHub SUCCESS but no result url")
                break
            if status_val in ("FAILED", "ERROR"):
                raise RuntimeError(
                    f"RunningHub task failed: "
                    f"{meta.get('errorMessage') or meta.get('errorCode') or status_val}")
            await self._sleep_poll()
        return VideoGenerationResult(
            url=url, file_id=None, provider_task_id=task_id,
            provider="runninghub", status="succeeded",
        )
```

`poll_interval_s=5.0`（与 .ts 一致），`timeout_s=600.0`。

在 `VideoGenerationTask` 类上加静态方法 `_build_runninghub_impl`。

## Capability

### `runninghub/image_capabilities.py`

- 默认：`supports_seed=False`, `supports_watermark=False`, `allowed_sizes=None`（由节点配置内部处理宽高）
- `supported_ratios={"16:9","9:16","1:1","4:3","3:4","3:2","2:3"}`（Qwen-image 比例映射子集）

### `runninghub/video_capabilities.py`

- `supports_seed=False`, `supports_watermark=False`
- `allowed_ratios={"16:9","9:16"}`（.ts 中 `VideoConfig.aspectRatio` 仅这两项）
- `min_seconds=5`, `max_seconds=10`（按 `durationResolutionMap` 约束）

### 修改 `image_capabilities.py` / `video_capabilities.py`

在 `resolve_image_capability` / `resolve_video_capability` / `register_image_model_capability` / `clear_image_model_capability_overrides` 等函数里加 `elif provider == "runninghub"` 分支，import 对应模块。

## 注册改动清单

| 文件 | 改动 |
|------|------|
| `core/contracts/provider.py` | `ProviderKey = Literal["openai", "volcengine", "runninghub"]` |
| `services/llm/provider_bootstrap.py` | 加 `ProviderSpec(key="runninghub", display_name="RunningHub", aliases=("runninghub","runninghub-personal","rh"), supported_categories=(image,video), default_base_url="https://www.runninghub.cn")` |
| `services/llm/provider_registry.py` | `resolve_provider_key_from_name` 加 `if "runninghub" in alias or alias == "rh": return "runninghub"` 兜底 |
| `core/tasks/bootstrap.py` | `TASK_ADAPTER_SPECS` 加 2 行 |
| `core/integrations/image_capabilities.py` | `resolve_*` 函数加 runninghub 分支 |
| `core/integrations/video_capabilities.py` | 同上 |
| `services/llm/model_bootstrap.py`（新增） | `bootstrap_builtin_db_resources()` |
| `main.py` | `lifespan` 加 `await bootstrap_builtin_db_resources()` |

## 测试策略

| 测试文件 | 覆盖内容 |
|---------|---------|
| `tests/test_task_registry.py`（扩展） | runninghub adapter 注册/解析幂等 |
| `tests/test_runninghub_client.py`（新增） | client.py 4 个 HTTP 函数，用 `httpx.MockTransport` 模拟响应；校验 URL/header/body |
| `tests/test_runninghub_node_configs.py`（新增） | 9 个 workflowId 的 `build_nodes` 输出结构正确；Qwen-image 的 lora 参数完整；LTX 分辨率计算正确 |
| `tests/test_runninghub_image_adapter.py`（新增） | `generate()` 全流程：mock client，校验 task_id → poll → `ImageGenerationResult`；Qwen Edit 路径需要参考图 |
| `tests/test_runninghub_video_adapter.py`（新增） | `create_video` + `get_video`；4 帧 LTX 走 workflow 端点；base64 上传 mock |
| `tests/test_runninghub_capabilities.py`（新增） | capability resolver 返回正确默认值；runninghub 分支生效 |
| `tests/test_model_bootstrap.py`（新增） | upsert 幂等：首次创建 9 模型 + provider；第二次不重复；不覆盖用户 api_key |

不写集成测试（不真打 RunningHub API）。

## 风险与边界

- **api_key 为空时**：adapter 调用会在 RunningHub 端返回 401；由上层 task 错误处理兜底。不在 adapter 层做空值校验（与现有 OpenAI/volcengine 一致）。
- **未知 workflowId**：adapter 抛 `ValueError`，task 层捕获后写入 task error。
- **轮询超时**：`poll_until_done` 超过 600s 抛 `TimeoutError`，task 层捕获。
- **4 帧模型参考图不足**：按 .ts 逻辑用最后一张补齐，不报错。
- **DB bootstrap 失败**：`bootstrap_builtin_db_resources` 异常应记录日志但不阻断启动（供应商注册仍在内存中生效，用户可手动添加）。
