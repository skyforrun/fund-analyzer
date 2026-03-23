"""Watchlist API 请求/响应模型。"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class WatchlistItem(BaseModel):
    """自选基金条目。"""

    id: int
    fund_code: str
    fund_name: str | None = None
    group_name: str
    notes: str | None = None
    added_at: datetime | None = None


class WatchlistCreateRequest(BaseModel):
    """添加自选请求。"""

    fund_code: str
    fund_name: str = ""
    group_name: str = "默认"
    notes: str = ""
