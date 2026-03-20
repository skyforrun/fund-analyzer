"""组合管理模块（Portfolio Manager）。

提供基金组合的买入、卖出和持仓查询功能。
支持卫星仓/核心仓分类、FIFO 卖出逻辑、以及与定投计划的关联。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from sqlalchemy import select, and_

from fund_analyzer.data.models import (
    FundInfo,
    PortfolioPosition,
    PortfolioTransaction,
)
from fund_analyzer.data.repository import FundRepository


class PortfolioManager:
    """组合管理器。

    封装基金买入、卖出和持仓查询操作。

    构造参数
    --------
    repo : FundRepository
        数据访问仓储对象，持有 Session 引用。
    """

    def __init__(self, repo: FundRepository) -> None:
        self._repo = repo
        self._session = repo._session

    # -----------------------------------------------------------------------
    # 买入
    # -----------------------------------------------------------------------

    def buy(
        self,
        fund_code: str,
        amount: float | Decimal,
        nav: float | Decimal,
        position_type: str = "satellite",
        buy_date: Optional[date] = None,
        dip_plan_id: Optional[int] = None,
    ) -> PortfolioPosition:
        """买入基金，创建持仓记录和交易记录。

        参数
        ----
        fund_code : str
            基金代码
        amount : float | Decimal
            买入金额（元）
        nav : float | Decimal
            买入净值（单位净值）
        position_type : str
            持仓类型，默认 "satellite"（卫星仓）
        buy_date : date, optional
            买入日期，默认使用今天
        dip_plan_id : int, optional
            关联的定投计划 ID，存在时交易类型为 "dip"，否则为 "buy"

        返回
        ----
        新创建的 PortfolioPosition 对象。
        """
        amount = Decimal(str(amount))
        nav = Decimal(str(nav))

        if buy_date is None:
            buy_date = date.today()

        # 计算份额，保留4位小数
        shares = (amount / nav).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        # 创建持仓记录
        position = PortfolioPosition(
            fund_code=fund_code,
            position_type=position_type,
            buy_date=buy_date,
            shares=shares,
            cost_price=nav,
            status="holding",
        )
        self._session.add(position)
        self._session.flush()  # 获取自增 id

        # 交易类型：有定投计划 ID 则为 "dip"，否则为 "buy"
        txn_type = "dip" if dip_plan_id is not None else "buy"

        # 创建交易记录
        self._repo.add_transaction({
            "fund_code": fund_code,
            "date": buy_date,
            "type": txn_type,
            "amount": amount,
            "shares": shares,
            "nav": nav,
            "position_type": position_type,
            "dip_plan_id": dip_plan_id,
        })

        return position

    # -----------------------------------------------------------------------
    # 卖出
    # -----------------------------------------------------------------------

    def sell(
        self,
        fund_code: str,
        shares: float | Decimal,
        nav: float | Decimal,
        sell_date: Optional[date] = None,
    ) -> None:
        """卖出基金，按 FIFO 顺序减少持仓。

        参数
        ----
        fund_code : str
            基金代码
        shares : float | Decimal
            卖出份额
        nav : float | Decimal
            卖出净值（单位净值）
        sell_date : date, optional
            卖出日期，默认使用今天
        """
        shares = Decimal(str(shares))
        nav = Decimal(str(nav))

        if sell_date is None:
            sell_date = date.today()

        # 查询该基金的所有活跃持仓，按买入日期升序（FIFO）
        stmt = (
            select(PortfolioPosition)
            .where(
                and_(
                    PortfolioPosition.fund_code == fund_code,
                    PortfolioPosition.status == "holding",
                )
            )
            .order_by(PortfolioPosition.buy_date, PortfolioPosition.id)
        )
        positions = list(self._session.execute(stmt).scalars().all())

        remaining = shares

        for pos in positions:
            if remaining <= Decimal("0"):
                break

            pos_shares = Decimal(str(pos.shares))

            if pos_shares <= remaining:
                # 整个持仓全部卖出
                sold_shares = pos_shares
                remaining -= pos_shares
                pos.status = "cleared"
                pos.sell_date = sell_date
                pos.sell_price = nav
            else:
                # 部分卖出
                sold_shares = remaining
                pos.shares = pos_shares - remaining
                remaining = Decimal("0")

            # 记录卖出交易
            sell_amount = (sold_shares * nav).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            self._repo.add_transaction({
                "fund_code": fund_code,
                "date": sell_date,
                "type": "sell",
                "amount": sell_amount,
                "shares": sold_shares,
                "nav": nav,
                "position_type": pos.position_type,
                "dip_plan_id": None,
            })

        self._session.flush()

    # -----------------------------------------------------------------------
    # 查询持仓
    # -----------------------------------------------------------------------

    def get_holdings(self, position_type: Optional[str] = None) -> list[dict]:
        """获取当前活跃持仓列表，关联基金名称信息。

        参数
        ----
        position_type : str, optional
            持仓类型过滤条件，不传则返回全部 holding 持仓。

        返回
        ----
        持仓字典列表，每个字典包含：
            - fund_code: 基金代码
            - fund_name: 基金名称（不存在则为 None）
            - position_type: 持仓类型
            - shares: 持有份额
            - cost_price: 买入净值（成本价）
            - buy_date: 买入日期
        """
        positions = self._repo.get_active_positions(position_type=position_type)

        result = []
        for pos in positions:
            fund_info = self._session.get(FundInfo, pos.fund_code)
            fund_name = fund_info.fund_name if fund_info is not None else None

            result.append({
                "fund_code": pos.fund_code,
                "fund_name": fund_name,
                "position_type": pos.position_type,
                "shares": pos.shares,
                "cost_price": pos.cost_price,
                "buy_date": pos.buy_date,
            })

        return result
