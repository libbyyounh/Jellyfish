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
