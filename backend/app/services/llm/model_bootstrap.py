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
