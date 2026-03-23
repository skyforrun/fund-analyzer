"""Dashboard 路由模块。

提供仪表盘总览和盘中估值两个端点。
"""
from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends

from fund_analyzer.api.deps import get_repo, get_tracker
from fund_analyzer.api.schemas.common import ApiResponse
from fund_analyzer.api.schemas.dashboard import (
    DashboardSummary,
    EstimateItem,
    HoldingItem,
    TypeSummary,
)
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.portfolio.tracker import PortfolioTracker

logger = logging.getLogger(__name__)

router = APIRouter()


def _dec2float(val: Decimal | float | int | None) -> float | None:
    """将 Decimal 转为 float，None 保持 None。"""
    if val is None:
        return None
    return float(val)


@router.get("/summary", response_model=ApiResponse[DashboardSummary])
def dashboard_summary(
    tracker: PortfolioTracker = Depends(get_tracker),
) -> ApiResponse[DashboardSummary]:
    """获取仪表盘总览数据。

    返回当前组合市值、成本、盈亏、收益率，以及按类型分组的汇总和持仓明细。
    """
    try:
        raw = tracker.summary()

        # 转换 holdings
        holdings = []
        for h in raw.get("holdings", []):
            holdings.append(HoldingItem(
                fund_code=h["fund_code"],
                position_type=h["position_type"],
                shares=_dec2float(h["shares"]) or 0.0,
                cost_price=_dec2float(h["cost_price"]) or 0.0,
                current_nav=_dec2float(h.get("current_nav")),
                market_value=_dec2float(h["market_value"]) or 0.0,
                cost=_dec2float(h["cost"]) or 0.0,
                pnl=_dec2float(h["pnl"]) or 0.0,
                return_pct=_dec2float(h.get("return_pct")),
                buy_date=h.get("buy_date"),
                holding_days=h.get("holding_days", 0),
            ))

        # 转换 by_type
        by_type = {}
        for type_name, type_data in raw.get("by_type", {}).items():
            by_type[type_name] = TypeSummary(
                market_value=_dec2float(type_data["market_value"]) or 0.0,
                cost=_dec2float(type_data["cost"]) or 0.0,
                pnl=_dec2float(type_data["pnl"]) or 0.0,
                return_pct=_dec2float(type_data.get("return_pct")),
            )

        summary = DashboardSummary(
            as_of=raw["as_of"],
            total_market_value=_dec2float(raw["total_market_value"]) or 0.0,
            total_cost=_dec2float(raw["total_cost"]) or 0.0,
            total_pnl=_dec2float(raw["total_pnl"]) or 0.0,
            total_return_pct=_dec2float(raw.get("total_return_pct")),
            by_type=by_type,
            holdings=holdings,
        )

        return ApiResponse(data=summary)

    except Exception as exc:
        logger.exception("获取仪表盘摘要失败")
        return ApiResponse(code=500, message=f"获取仪表盘摘要失败: {exc}")


@router.get("/estimates", response_model=ApiResponse[list[EstimateItem]])
def dashboard_estimates(
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[list[EstimateItem]]:
    """获取当前持仓基金的盘中估值数据。

    从活跃持仓中提取基金代码，查询最新估值记录。
    """
    try:
        positions = repo.get_active_positions()
        fund_codes = list({p.fund_code for p in positions if p.fund_code})

        if not fund_codes:
            return ApiResponse(data=[])

        estimates = repo.get_latest_estimates(fund_codes)

        items = []
        for est in estimates:
            items.append(EstimateItem(
                fund_code=est.fund_code,
                estimate_date=est.estimate_date,
                estimate_nav=_dec2float(est.estimate_nav),
                estimate_return=_dec2float(est.estimate_return),
                estimate_time=est.estimate_time,
                source=est.source,
            ))

        return ApiResponse(data=items)

    except Exception as exc:
        logger.exception("获取估值数据失败")
        return ApiResponse(code=500, message=f"获取估值数据失败: {exc}")
