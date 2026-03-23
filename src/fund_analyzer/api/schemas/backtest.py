"""Backtest（回测分析）相关的 Pydantic 模型定义。"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class BacktestRequest(BaseModel):
    """回测请求参数。

    Attributes
    ----------
    start_date : str
        回测起始日期（ISO 格式），默认 "2020-01-01"。
    end_date : str | None
        回测结束日期，None 表示今天。
    initial_capital : float
        初始资金，默认 100000。
    core_ratio : int
        核心仓位占比（百分比 0-100），默认 30。
    benchmark_code : str
        基准指数代码，默认 "000688"。
    """

    start_date: str = "2020-01-01"
    end_date: Optional[str] = None
    initial_capital: float = 100000
    core_ratio: int = 30
    benchmark_code: str = "000688"


class SeriesData(BaseModel):
    """pd.Series 的 JSON 序列化格式。"""

    dates: list[str]
    values: list[float]


class BacktestMetrics(BaseModel):
    """回测绩效指标。"""

    annualized_return: float
    annualized_volatility: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    monthly_win_rate: float
    information_ratio: Optional[float] = None
    alpha: Optional[float] = None


class BacktestResult(BaseModel):
    """回测结果。"""

    portfolio_returns: SeriesData
    benchmark_returns: SeriesData
    portfolio_values: SeriesData
    metrics: BacktestMetrics
    total_fees_paid: float
    final_value: float
    initial_capital: float
