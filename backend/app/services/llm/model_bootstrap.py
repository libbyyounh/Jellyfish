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


_RUNNINGHUB_ENTERPRISE_PROVIDER_DEFAULTS = {
    "id": "runninghub-enterprise",
    "name": "RunningHub 企业版",
    "base_url": "https://www.runninghub.cn",
    "image_base_url": None,
    "video_base_url": None,
    "api_secret": "",
    "description": "RunningHub 企业版：万相 2.7 / LTX2.3 / HappyHorse / 可灵 / 全能视频 / Seedance 2.0 系列视频模型",
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
    # ---- seedance 2.0 / Fast / Mini（sparkvideo-2.0[-fast|-mini]）----
    {
        "id": "runninghub-enterprise-sparkvideo-2.0-text-to-video",
        "name": "Seedance 2.0 文生视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "sparkvideo-2.0/text-to-video",
            "mode": "text",
            "duration_resolution_map": [{"duration": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], "resolution": ["480P", "720P", "1080P", "2K", "4K"]}],
            "audio": "optional",
        },
        "description": "Seedance 2.0 文生视频，纯提示词生成，支持 4-15s、多比例与可选音频。",
    },
    {
        "id": "runninghub-enterprise-sparkvideo-2.0-image-to-video",
        "name": "Seedance 2.0 图生视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "sparkvideo-2.0/image-to-video",
            "mode": "startEndRequired",
            "duration_resolution_map": [{"duration": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], "resolution": ["480P", "720P", "1080P", "2K", "4K"]}],
            "audio": "optional",
        },
        "description": "Seedance 2.0 图生视频，首帧（可选尾帧）控制，支持 4-15s 与可选音频。",
    },
    {
        "id": "runninghub-enterprise-sparkvideo-2.0-multimodal-video",
        "name": "Seedance 2.0 多模态视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "sparkvideo-2.0/multimodal-video",
            "mode": "multimodal",
            "duration_resolution_map": [{"duration": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], "resolution": ["480P", "720P", "1080P", "2K", "4K"]}],
            "audio": "optional",
        },
        "description": "Seedance 2.0 多模态视频，支持多图参考（最多 9 张）+ 提示词生成。",
    },
    {
        "id": "runninghub-enterprise-sparkvideo-2.0-fast-text-to-video",
        "name": "Seedance 2.0-Fast 文生视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "sparkvideo-2.0-fast/text-to-video",
            "mode": "text",
            "duration_resolution_map": [{"duration": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], "resolution": ["480P", "720P", "1080P", "2K", "4K"]}],
            "audio": "optional",
        },
        "description": "Seedance 2.0-Fast 文生视频，快速生成版本，支持 4-15s 与可选音频。",
    },
    {
        "id": "runninghub-enterprise-sparkvideo-2.0-fast-image-to-video",
        "name": "Seedance 2.0-Fast 图生视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "sparkvideo-2.0-fast/image-to-video",
            "mode": "startEndRequired",
            "duration_resolution_map": [{"duration": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], "resolution": ["480P", "720P", "1080P", "2K", "4K"]}],
            "audio": "optional",
        },
        "description": "Seedance 2.0-Fast 图生视频，首帧（可选尾帧）控制，快速生成版本。",
    },
    {
        "id": "runninghub-enterprise-sparkvideo-2.0-fast-multimodal-video",
        "name": "Seedance 2.0-Fast 多模态视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "sparkvideo-2.0-fast/multimodal-video",
            "mode": "multimodal",
            "duration_resolution_map": [{"duration": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], "resolution": ["480P", "720P", "1080P", "2K", "4K"]}],
            "audio": "optional",
        },
        "description": "Seedance 2.0-Fast 多模态视频，多图参考 + 提示词，快速生成版本。",
    },
    {
        "id": "runninghub-enterprise-sparkvideo-2.0-mini-text-to-video",
        "name": "Seedance 2.0-Mini 文生视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "sparkvideo-2.0-mini/text-to-video",
            "mode": "text",
            "duration_resolution_map": [{"duration": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], "resolution": ["480P", "720P", "1080P", "2K", "4K"]}],
            "audio": "optional",
        },
        "description": "Seedance 2.0-Mini 文生视频，轻量版本，1080p/2k/4k 由 720p 超分补帧。",
    },
    {
        "id": "runninghub-enterprise-sparkvideo-2.0-mini-image-to-video",
        "name": "Seedance 2.0-Mini 图生视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "sparkvideo-2.0-mini/image-to-video",
            "mode": "startEndRequired",
            "duration_resolution_map": [{"duration": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], "resolution": ["480P", "720P", "1080P", "2K", "4K"]}],
            "audio": "optional",
        },
        "description": "Seedance 2.0-Mini 图生视频，首帧（可选尾帧）控制，轻量版本。",
    },
    {
        "id": "runninghub-enterprise-sparkvideo-2.0-mini-multimodal-video",
        "name": "Seedance 2.0-Mini 多模态视频",
        "category": ModelCategoryKey.video,
        "params": {
            "model_name": "sparkvideo-2.0-mini/multimodal-video",
            "mode": "multimodal",
            "duration_resolution_map": [{"duration": [4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15], "resolution": ["480P", "720P", "1080P", "2K", "4K"]}],
            "audio": "optional",
        },
        "description": "Seedance 2.0-Mini 多模态视频，多图参考 + 提示词，轻量版本。",
    },
]


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


async def bootstrap_builtin_db_resources(session: AsyncSession) -> None:
    """幂等 upsert runninghub + runninghub-enterprise + grsai provider 行 + 9 + 23 + 13 个 model 行。

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
    # 已存在则不覆盖用户字段

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
