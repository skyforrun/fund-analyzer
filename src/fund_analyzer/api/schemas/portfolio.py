"""Portfolio API 请求/响应模型。"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel


class BuyRequest(BaseModel):
    """买入请求。"""

    fund_code: str
    amount: float
    nav: float
    position_type: str = "satellite"


class SellRequest(BaseModel):
    """卖出请求。"""

    fund_code: str
    shares: float
    nav: float


class HoldingItem(BaseModel):
    """持仓明细。"""

    fund_code: str
    fund_name: str | None = None
    position_type: str | None = None
    shares: float
    cost_price: float
    buy_date: date | None = None


class DividendItem(BaseModel):
    """分红记录。"""

    fund_code: str
    ex_date: date
    dividend_per_unit: float | None = None
    dividend_type: str | None = None


class FeeRateItem(BaseModel):
    """赎回费率。"""

    fund_code: str
    holding_days: int
    fee_rate: float | None = None
