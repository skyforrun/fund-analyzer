"""Screening（基金筛选）相关的 Pydantic 模型定义。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class ScreenRequest(BaseModel):
    """筛选请求参数。

    Attributes
    ----------
    position_type : str
        仓位类型，"core" 或 "satellite"。
    top_n : int
        返回排名前 N 的基金。
    """

    position_type: str = "satellite"
    top_n: int = 10


class ScreenResultItem(BaseModel):
    """单只基金的筛选结果。"""

    fund_code: str
    fund_name: Optional[str] = None
    fund_type: Optional[str] = None
    score: float
    action: Optional[str] = None
    confidence: Optional[str] = None
    reason: Optional[str] = None


class FeeScheduleItem(BaseModel):
    """费率明细条目。"""

    fee_type: str
    min_holding_days: int
    max_holding_days: int
    fee_rate: float
    min_amount: float
    max_amount: Optional[float] = None
