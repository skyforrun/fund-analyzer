"""定投相关 API 数据模型。"""
from __future__ import annotations

from pydantic import BaseModel


class DipPlanCreate(BaseModel):
    """创建定投计划请求体。"""

    fund_code: str
    amount: float
    frequency: str = "monthly"
    smart: bool = False


class DipPlanItem(BaseModel):
    """定投计划列表项。"""

    id: int
    fund_code: str
    amount: float
    frequency: str
    start_date: str | None = None
    status: str
    smart_dip: bool | None = None


class DipDueItem(BaseModel):
    """到期定投计划项。"""

    plan_id: int
    fund_code: str
    amount: float
    smart_dip: bool | None = None
