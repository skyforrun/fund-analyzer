"""收益追踪模块（PortfolioTracker）。

根据当前所有活跃持仓（状态为 holding）以及对应日期的净值，
计算组合整体及按 position_type 分组的市值、成本、盈亏和收益率。
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fund_analyzer.data.repository import FundRepository


class PortfolioTracker:
    """组合收益追踪器。

    构造参数
    --------
    repo : FundRepository
        数据仓储，用于查询持仓和净值。
    """

    def __init__(self, repo: FundRepository) -> None:
        self._repo = repo

    # -----------------------------------------------------------------------
    # 内部辅助方法
    # -----------------------------------------------------------------------

    def _get_latest_nav(
        self,
        fund_code: str,
        as_of: date,
    ) -> Optional[Decimal]:
        """获取指定基金在 as_of 日期或其前最多 10 个自然日内最新的净值。

        查询策略：从 as_of 往前回溯最多 10 天，取最近一条有净值记录的数据。
        若均无数据，则返回 None。

        参数
        ----
        fund_code : str
            基金代码
        as_of : date
            查询基准日期（含当天）

        返回
        ----
        最新净值（Decimal），不存在时返回 None。
        """
        start = as_of - timedelta(days=10)
        navs = self._repo.get_fund_nav(fund_code, start, as_of)
        # navs 按日期升序，取最后一条（最接近 as_of）
        for record in reversed(navs):
            if record.nav is not None:
                return Decimal(str(record.nav))
        return None

    # -----------------------------------------------------------------------
    # 公共方法
    # -----------------------------------------------------------------------

    def summary(self, as_of: Optional[date] = None) -> dict:
        """计算组合收益摘要。

        参数
        ----
        as_of : date, optional
            计算基准日期，默认为今天（date.today()）。

        返回
        ----
        dict，结构如下：
        {
            "as_of": date,
            "total_market_value": Decimal,
            "total_cost": Decimal,
            "total_pnl": Decimal,
            "total_return_pct": Decimal | None,   # 成本为 0 时为 None
            "by_type": {
                "<position_type>": {
                    "market_value": Decimal,
                    "cost": Decimal,
                    "pnl": Decimal,
                    "return_pct": Decimal | None,
                },
                ...
            },
            "holdings": [
                {
                    "fund_code": str,
                    "position_type": str,
                    "shares": Decimal,
                    "cost_price": Decimal,
                    "current_nav": Decimal | None,
                    "market_value": Decimal,
                    "cost": Decimal,
                    "pnl": Decimal,
                    "return_pct": Decimal | None,
                },
                ...
            ],
        }
        """
        if as_of is None:
            as_of = date.today()

        positions = self._repo.get_active_positions()

        holdings = []
        by_type: dict[str, dict] = {}

        total_market_value = Decimal("0")
        total_cost = Decimal("0")

        for pos in positions:
            fund_code = pos.fund_code or ""
            position_type = pos.position_type or "unknown"
            shares = Decimal(str(pos.shares)) if pos.shares is not None else Decimal("0")
            cost_price = Decimal(str(pos.cost_price)) if pos.cost_price is not None else Decimal("0")

            current_nav = self._get_latest_nav(fund_code, as_of)

            # 市值：若净值缺失则以成本价代替（保守估计）
            if current_nav is not None:
                market_value = shares * current_nav
            else:
                market_value = shares * cost_price

            cost = shares * cost_price
            pnl = market_value - cost
            return_pct = (pnl / cost * Decimal("100")) if cost != Decimal("0") else None

            buy_date_val = pos.buy_date if hasattr(pos, "buy_date") else None
            holding_days = (as_of - buy_date_val).days if buy_date_val else 0

            holdings.append({
                "fund_code": fund_code,
                "position_type": position_type,
                "shares": shares,
                "cost_price": cost_price,
                "current_nav": current_nav,
                "market_value": market_value,
                "cost": cost,
                "pnl": pnl,
                "return_pct": return_pct,
                "buy_date": buy_date_val,
                "holding_days": holding_days,
            })

            total_market_value += market_value
            total_cost += cost

            # 按 position_type 分组累计
            if position_type not in by_type:
                by_type[position_type] = {
                    "market_value": Decimal("0"),
                    "cost": Decimal("0"),
                    "pnl": Decimal("0"),
                    "return_pct": None,
                }
            by_type[position_type]["market_value"] += market_value
            by_type[position_type]["cost"] += cost
            by_type[position_type]["pnl"] += pnl

        # 计算各分组的 return_pct
        for type_data in by_type.values():
            grp_cost = type_data["cost"]
            type_data["return_pct"] = (
                type_data["pnl"] / grp_cost * Decimal("100")
                if grp_cost != Decimal("0")
                else None
            )

        total_pnl = total_market_value - total_cost
        total_return_pct = (
            total_pnl / total_cost * Decimal("100")
            if total_cost != Decimal("0")
            else None
        )

        return {
            "as_of": as_of,
            "total_market_value": total_market_value,
            "total_cost": total_cost,
            "total_pnl": total_pnl,
            "total_return_pct": total_return_pct,
            "by_type": by_type,
            "holdings": holdings,
        }
