"""调仓建议相关 API 数据模型。"""
from __future__ import annotations

from pydantic import BaseModel


class ActionItem(BaseModel):
    """调仓行动项。"""

    fund_code: str
    position_type: str
    action: str
    reason: str


class RebalanceResult(BaseModel):
    """调仓建议结果。"""

    as_of: str
    actions: list[ActionItem]
    core_picks: list[list]
    satellite_picks: list[list]
