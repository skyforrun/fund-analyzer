"""风险评估相关 API 数据模型。"""
from __future__ import annotations

from pydantic import BaseModel


class RiskSubmitRequest(BaseModel):
    """风险问卷提交请求体。"""

    answers: dict[str, int]


class RiskProfileResponse(BaseModel):
    """风险评估结果响应。"""

    id: int | None = None
    risk_level: int
    risk_label: str
    core_ratio: int
    satellite_ratio: int
    assessment_date: str
    answers: dict | None = None
