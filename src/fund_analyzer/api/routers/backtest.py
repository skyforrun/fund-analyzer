"""Backtest（回测分析）路由模块。

提供回测运行端点。
"""
from __future__ import annotations

import logging
from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends

from fund_analyzer.api.deps import get_repo, get_composite, get_settings
from fund_analyzer.api.schemas.backtest import (
    BacktestMetrics,
    BacktestRequest,
    BacktestResult,
    SeriesData,
)
from fund_analyzer.api.schemas.common import ApiResponse
from fund_analyzer.backtest.engine import BacktestEngine
from fund_analyzer.config import Settings
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.composite import CompositeStrategy

logger = logging.getLogger(__name__)

router = APIRouter()


def _series_to_data(s: pd.Series) -> SeriesData:
    """将 pd.Series 转换为 JSON 可序列化的 SeriesData。"""
    return SeriesData(
        dates=[d.isoformat() if hasattr(d, "isoformat") else str(d) for d in s.index],
        values=[
            float(v) if not (isinstance(v, float) and v != v) else 0.0
            for v in s.values
        ],
    )


@router.post("/run", response_model=ApiResponse[BacktestResult])
def backtest_run(
    req: BacktestRequest,
    repo: FundRepository = Depends(get_repo),
    composite: CompositeStrategy = Depends(get_composite),
    settings: Settings = Depends(get_settings),
) -> ApiResponse[BacktestResult]:
    """运行回测分析。

    根据请求参数构建回测引擎，对符合条件的基金池执行回测，
    返回收益曲线、基准对比及各项绩效指标。
    """
    try:
        pool_cfg = settings.data.fund_pool
        as_of = date.today()

        # 获取符合条件的基金池
        eligible = repo.get_eligible_funds(
            min_inception_years=pool_cfg.min_inception_years,
            min_size_billion=pool_cfg.min_size_billion,
            exclude_types=pool_cfg.exclude_types,
            as_of=as_of,
        )
        fund_universe = [f.fund_code for f in eligible]

        if not fund_universe:
            return ApiResponse(code=400, message="无符合条件的基金，无法运行回测")

        # 解析日期
        start = date.fromisoformat(req.start_date)
        end = date.fromisoformat(req.end_date) if req.end_date else date.today()

        # 计算仓位比例
        core_ratio = req.core_ratio / 100
        satellite_ratio = 1.0 - core_ratio

        # 创建回测引擎（覆盖默认参数）
        freq_map = {"quarterly": 3, "monthly": 1, "weekly": 1}
        engine = BacktestEngine(
            repo=repo,
            composite=composite,
            initial_capital=req.initial_capital,
            core_ratio=core_ratio,
            satellite_ratio=satellite_ratio,
            core_top_n=settings.backtest.core_top_n,
            satellite_top_n=settings.backtest.satellite_top_n,
            buy_fee=settings.backtest.buy_fee_rate,
            sell_fee=settings.backtest.sell_fee_rate,
            core_rebalance_months=freq_map.get(settings.backtest.core_rebalance_freq, 3),
            satellite_rebalance_months=freq_map.get(
                settings.backtest.satellite_rebalance_freq, 1
            ),
        )

        # 运行回测
        raw = engine.run(fund_universe, start, end, req.benchmark_code)

        # 处理 metrics 中的 NaN
        raw_metrics = raw["metrics"]
        metrics = BacktestMetrics(
            annualized_return=_safe_float(raw_metrics.get("annualized_return", 0)),
            annualized_volatility=_safe_float(
                raw_metrics.get("annualized_volatility", 0)
            ),
            max_drawdown=_safe_float(raw_metrics.get("max_drawdown", 0)),
            sharpe_ratio=_safe_float(raw_metrics.get("sharpe_ratio", 0)),
            sortino_ratio=_safe_float(raw_metrics.get("sortino_ratio", 0)),
            calmar_ratio=_safe_float(raw_metrics.get("calmar_ratio", 0)),
            monthly_win_rate=_safe_float(raw_metrics.get("monthly_win_rate", 0)),
            information_ratio=_safe_float_or_none(
                raw_metrics.get("information_ratio")
            ),
            alpha=_safe_float_or_none(raw_metrics.get("alpha")),
        )

        result = BacktestResult(
            portfolio_returns=_series_to_data(raw["portfolio_returns"]),
            benchmark_returns=_series_to_data(raw["benchmark_returns"]),
            portfolio_values=_series_to_data(raw["portfolio_values"]),
            metrics=metrics,
            total_fees_paid=_safe_float(raw.get("total_fees_paid", 0)),
            final_value=_safe_float(raw.get("final_value", 0)),
            initial_capital=_safe_float(raw.get("initial_capital", 0)),
        )

        return ApiResponse(data=result)

    except Exception as exc:
        logger.exception("回测运行失败")
        return ApiResponse(code=500, message=f"回测运行失败: {exc}")


def _safe_float(val) -> float:
    """安全转换为 float，NaN 替换为 0.0。"""
    if val is None:
        return 0.0
    f = float(val)
    if f != f:  # NaN check
        return 0.0
    return f


def _safe_float_or_none(val):
    """安全转换为 float 或 None，NaN 替换为 None。"""
    if val is None:
        return None
    f = float(val)
    if f != f:  # NaN check
        return None
    return f
