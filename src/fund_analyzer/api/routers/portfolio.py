"""Portfolio 路由模块。

提供持仓概览、持仓列表、买入、卖出、分红记录、赎回费率六个端点。
"""
from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from fund_analyzer.api.deps import get_db_session, get_manager, get_repo, get_tracker
from fund_analyzer.api.schemas.common import ApiResponse
from fund_analyzer.api.schemas.portfolio import (
    BuyRequest,
    DividendItem,
    FeeRateItem,
    HoldingItem,
    SellRequest,
)
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.portfolio.manager import PortfolioManager
from fund_analyzer.portfolio.tracker import PortfolioTracker

logger = logging.getLogger(__name__)

router = APIRouter()


def _dec2float(val: Decimal | float | int | None) -> float | None:
    """将 Decimal 转为 float，None 保持 None。"""
    if val is None:
        return None
    return float(val)


@router.get("/summary", response_model=ApiResponse[dict])
def portfolio_summary(
    tracker: PortfolioTracker = Depends(get_tracker),
) -> ApiResponse[dict]:
    """获取持仓概览数据。"""
    try:
        raw = tracker.summary()

        holdings = []
        for h in raw.get("holdings", []):
            holdings.append({
                "fund_code": h["fund_code"],
                "position_type": h["position_type"],
                "shares": _dec2float(h["shares"]) or 0.0,
                "cost_price": _dec2float(h["cost_price"]) or 0.0,
                "current_nav": _dec2float(h.get("current_nav")),
                "market_value": _dec2float(h["market_value"]) or 0.0,
                "cost": _dec2float(h["cost"]) or 0.0,
                "pnl": _dec2float(h["pnl"]) or 0.0,
                "return_pct": _dec2float(h.get("return_pct")),
                "buy_date": h.get("buy_date"),
                "holding_days": h.get("holding_days", 0),
            })

        by_type = {}
        for type_name, type_data in raw.get("by_type", {}).items():
            by_type[type_name] = {
                "market_value": _dec2float(type_data["market_value"]) or 0.0,
                "cost": _dec2float(type_data["cost"]) or 0.0,
                "pnl": _dec2float(type_data["pnl"]) or 0.0,
                "return_pct": _dec2float(type_data.get("return_pct")),
            }

        summary = {
            "as_of": raw["as_of"].isoformat() if raw.get("as_of") else None,
            "total_market_value": _dec2float(raw["total_market_value"]) or 0.0,
            "total_cost": _dec2float(raw["total_cost"]) or 0.0,
            "total_pnl": _dec2float(raw["total_pnl"]) or 0.0,
            "total_return_pct": _dec2float(raw.get("total_return_pct")),
            "by_type": by_type,
            "holdings": holdings,
        }

        return ApiResponse(data=summary)

    except Exception as exc:
        logger.exception("获取持仓概览失败")
        return ApiResponse(code=500, message=f"获取持仓概览失败: {exc}")


@router.get("/holdings", response_model=ApiResponse[list[HoldingItem]])
def portfolio_holdings(
    position_type: str | None = None,
    manager: PortfolioManager = Depends(get_manager),
) -> ApiResponse[list[HoldingItem]]:
    """获取持仓列表。"""
    try:
        raw_holdings = manager.get_holdings(position_type=position_type)
        items = []
        for h in raw_holdings:
            items.append(HoldingItem(
                fund_code=h["fund_code"],
                fund_name=h.get("fund_name"),
                position_type=h.get("position_type"),
                shares=_dec2float(h["shares"]) or 0.0,
                cost_price=_dec2float(h["cost_price"]) or 0.0,
                buy_date=h.get("buy_date"),
            ))
        return ApiResponse(data=items)

    except Exception as exc:
        logger.exception("获取持仓列表失败")
        return ApiResponse(code=500, message=f"获取持仓列表失败: {exc}")


@router.post("/buy", response_model=ApiResponse[dict])
def portfolio_buy(
    req: BuyRequest,
    session: Session = Depends(get_db_session),
    manager: PortfolioManager = Depends(get_manager),
) -> ApiResponse[dict]:
    """买入基金。"""
    try:
        position = manager.buy(
            fund_code=req.fund_code,
            amount=req.amount,
            nav=req.nav,
            position_type=req.position_type,
        )
        session.commit()
        return ApiResponse(data={
            "fund_code": position.fund_code,
            "shares": _dec2float(position.shares),
            "cost_price": _dec2float(position.cost_price),
        })

    except Exception as exc:
        logger.exception("买入失败")
        return ApiResponse(code=500, message=f"买入失败: {exc}")


@router.post("/sell", response_model=ApiResponse[dict])
def portfolio_sell(
    req: SellRequest,
    session: Session = Depends(get_db_session),
    manager: PortfolioManager = Depends(get_manager),
) -> ApiResponse[dict]:
    """卖出基金。"""
    try:
        manager.sell(
            fund_code=req.fund_code,
            shares=req.shares,
            nav=req.nav,
        )
        session.commit()
        return ApiResponse(data={"fund_code": req.fund_code, "shares_sold": req.shares})

    except Exception as exc:
        logger.exception("卖出失败")
        return ApiResponse(code=500, message=f"卖出失败: {exc}")


@router.get("/dividends", response_model=ApiResponse[list[DividendItem]])
def portfolio_dividends(
    tracker: PortfolioTracker = Depends(get_tracker),
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[list[DividendItem]]:
    """获取当前持仓基金的分红记录。"""
    try:
        raw = tracker.summary()
        holdings = raw.get("holdings", [])

        items = []
        for h in holdings:
            fund_code = h["fund_code"]
            dividends = repo.get_dividends(fund_code)
            for d in dividends:
                items.append(DividendItem(
                    fund_code=d.fund_code,
                    ex_date=d.ex_date,
                    dividend_per_unit=_dec2float(d.dividend_per_unit),
                    dividend_type=d.dividend_type,
                ))

        return ApiResponse(data=items)

    except Exception as exc:
        logger.exception("获取分红记录失败")
        return ApiResponse(code=500, message=f"获取分红记录失败: {exc}")


@router.get("/fee-rate", response_model=ApiResponse[list[FeeRateItem]])
def portfolio_fee_rate(
    tracker: PortfolioTracker = Depends(get_tracker),
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[list[FeeRateItem]]:
    """获取当前持仓基金的赎回费率。"""
    try:
        raw = tracker.summary()
        holdings = raw.get("holdings", [])

        items = []
        for h in holdings:
            fund_code = h["fund_code"]
            holding_days = h.get("holding_days", 0)
            fee_rate = repo.get_fee_rate(fund_code, "redemption", holding_days=holding_days)
            items.append(FeeRateItem(
                fund_code=fund_code,
                holding_days=holding_days,
                fee_rate=_dec2float(fee_rate),
            ))

        return ApiResponse(data=items)

    except Exception as exc:
        logger.exception("获取赎回费率失败")
        return ApiResponse(code=500, message=f"获取赎回费率失败: {exc}")
