"""Dashboard 相关的 Pydantic 模型定义。"""
from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class HoldingItem(BaseModel):
    """单笔持仓明细。"""

    fund_code: str
    position_type: str
    shares: float
    cost_price: float
    current_nav: Optional[float] = None
    market_value: float
    cost: float
    pnl: float
    return_pct: Optional[float] = None
    buy_date: Optional[date] = None
    holding_days: int = 0


class TypeSummary(BaseModel):
    """按持仓类型分组的汇总信息。"""

    market_value: float
    cost: float
    pnl: float
    return_pct: Optional[float] = None


class DashboardSummary(BaseModel):
    """仪表盘总览数据。"""

    as_of: date
    total_market_value: float
    total_cost: float
    total_pnl: float
    total_return_pct: Optional[float] = None
    by_type: dict[str, TypeSummary] = {}
    holdings: list[HoldingItem] = []


class EstimateItem(BaseModel):
    """基金盘中估值条目。"""

    fund_code: str
    estimate_date: date
    estimate_nav: Optional[float] = None
    estimate_return: Optional[float] = None
    estimate_time: Optional[str] = None
    source: Optional[str] = None
