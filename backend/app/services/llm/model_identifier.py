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
