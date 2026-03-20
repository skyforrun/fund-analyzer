"""数据访问层（Repository）。

封装所有数据库访问操作，提供统一的 CRUD 接口。
依赖 SQLAlchemy 2.0 Session，使用 select / and_ 构造查询。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from fund_analyzer.data.models import (
    Base,
    FundInfo,
    FundNav,
    IndexQuote,
    FundHolding,
    IndustryMapping,
    PortfolioPosition,
    PortfolioTransaction,
    StrategySignal,
    DipPlan,
)


class FundRepository:
    """封装所有数据库访问操作的仓储类。

    构造参数
    --------
    session : Session
        SQLAlchemy ORM Session，由调用方管理生命周期（事务控制）。
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    # -----------------------------------------------------------------------
    # FundInfo
    # -----------------------------------------------------------------------

    def get_fund_info(self, fund_code: str) -> Optional[FundInfo]:
        """按 fund_code 查询基金基本信息。

        参数
        ----
        fund_code : str
            基金代码

        返回
        ----
        FundInfo 对象，不存在时返回 None。
        """
        return self._session.get(FundInfo, fund_code)

    def get_eligible_funds(
        self,
        min_inception_years: float,
        min_size_billion: float,
        exclude_types: list[str],
        as_of: date,
    ) -> list[FundInfo]:
        """按成立年限、规模、基金类型过滤出符合条件的基金列表。

        参数
        ----
        min_inception_years : float
            最低成立年限（年）。成立日期须早于 as_of - min_inception_years * 365 天。
        min_size_billion : float
            最低规模（亿元）。
        exclude_types : list[str]
            需要排除的基金类型列表，如 ["货币型", "债券型"]。
        as_of : date
            计算成立年限时使用的基准日期。

        返回
        ----
        满足所有条件的 FundInfo 列表。
        """
        cutoff_date = as_of - timedelta(days=min_inception_years * 365)

        conditions = []

        # 成立日期须早于截止日期
        if min_inception_years > 0:
            conditions.append(FundInfo.inception_date <= cutoff_date)

        # 规模过滤
        if min_size_billion > 0:
            conditions.append(FundInfo.fund_size >= min_size_billion)

        # 排除指定类型
        if exclude_types:
            conditions.append(FundInfo.fund_type.notin_(exclude_types))

        stmt = select(FundInfo)
        if conditions:
            stmt = stmt.where(and_(*conditions))

        return list(self._session.execute(stmt).scalars().all())

    def upsert_fund_info(self, data: dict) -> FundInfo:
        """插入或更新基金基本信息。

        以 fund_code 为主键判断：存在则更新字段，不存在则新增记录。

        参数
        ----
        data : dict
            包含基金信息的字典，必须含 "fund_code" 键。

        返回
        ----
        操作后的 FundInfo 对象。
        """
        fund_code = data["fund_code"]
        obj = self._session.get(FundInfo, fund_code)
        if obj is None:
            obj = FundInfo(**data)
            self._session.add(obj)
        else:
            for key, value in data.items():
                if key != "fund_code":
                    setattr(obj, key, value)
        self._session.flush()
        return obj

    # -----------------------------------------------------------------------
    # FundNav
    # -----------------------------------------------------------------------

    def get_fund_nav(
        self,
        fund_code: str,
        start: date,
        end: date,
    ) -> list[FundNav]:
        """查询指定基金在日期范围内的净值记录，结果按日期升序排列。

        参数
        ----
        fund_code : str
            基金代码
        start : date
            起始日期（含）
        end : date
            结束日期（含）

        返回
        ----
        FundNav 列表，按 date 升序。
        """
        stmt = (
            select(FundNav)
            .where(
                and_(
                    FundNav.fund_code == fund_code,
                    FundNav.date >= start,
                    FundNav.date <= end,
                )
            )
            .order_by(FundNav.date)
        )
        return list(self._session.execute(stmt).scalars().all())

    def upsert_fund_navs(self, fund_code: str, rows: list[dict]) -> None:
        """批量插入或更新基金净值。

        以 (fund_code, date) 为复合主键判断：存在则更新，不存在则插入。

        参数
        ----
        fund_code : str
            基金代码
        rows : list[dict]
            净值数据列表，每个元素须含 "date" 键。
        """
        if not rows:
            return

        for row in rows:
            nav_date = row["date"]
            obj = self._session.get(FundNav, (fund_code, nav_date))
            if obj is None:
                obj = FundNav(fund_code=fund_code, **row)
                self._session.add(obj)
            else:
                for key, value in row.items():
                    if key != "date":
                        setattr(obj, key, value)
        self._session.flush()

    # -----------------------------------------------------------------------
    # IndexQuote
    # -----------------------------------------------------------------------

    def get_index_quote(
        self,
        index_code: str,
        start: date,
        end: date,
    ) -> list[IndexQuote]:
        """查询指定指数在日期范围内的行情记录，结果按日期升序排列。

        参数
        ----
        index_code : str
            指数代码
        start : date
            起始日期（含）
        end : date
            结束日期（含）

        返回
        ----
        IndexQuote 列表，按 date 升序。
        """
        stmt = (
            select(IndexQuote)
            .where(
                and_(
                    IndexQuote.index_code == index_code,
                    IndexQuote.date >= start,
                    IndexQuote.date <= end,
                )
            )
            .order_by(IndexQuote.date)
        )
        return list(self._session.execute(stmt).scalars().all())

    def upsert_index_quotes(self, index_code: str, rows: list[dict]) -> None:
        """批量插入或更新指数行情。

        以 (index_code, date) 为复合主键判断：存在则更新，不存在则插入。

        参数
        ----
        index_code : str
            指数代码
        rows : list[dict]
            行情数据列表，每个元素须含 "date" 键。
        """
        if not rows:
            return

        for row in rows:
            quote_date = row["date"]
            obj = self._session.get(IndexQuote, (index_code, quote_date))
            if obj is None:
                obj = IndexQuote(index_code=index_code, **row)
                self._session.add(obj)
            else:
                for key, value in row.items():
                    if key != "date":
                        setattr(obj, key, value)
        self._session.flush()

    # -----------------------------------------------------------------------
    # FundHolding
    # -----------------------------------------------------------------------

    def get_fund_holdings(
        self,
        fund_code: str,
        report_date: date,
    ) -> list[FundHolding]:
        """查询指定基金在某报告期的持仓列表。

        参数
        ----
        fund_code : str
            基金代码
        report_date : date
            报告期日期

        返回
        ----
        FundHolding 列表。
        """
        stmt = select(FundHolding).where(
            and_(
                FundHolding.fund_code == fund_code,
                FundHolding.report_date == report_date,
            )
        )
        return list(self._session.execute(stmt).scalars().all())

    # -----------------------------------------------------------------------
    # IndustryMapping
    # -----------------------------------------------------------------------

    def get_industry(self, stock_code: str) -> Optional[IndustryMapping]:
        """按 stock_code 查询行业映射。

        参数
        ----
        stock_code : str
            股票代码

        返回
        ----
        IndustryMapping 对象，不存在时返回 None。
        """
        return self._session.get(IndustryMapping, stock_code)

    # -----------------------------------------------------------------------
    # PortfolioPosition
    # -----------------------------------------------------------------------

    def get_active_positions(
        self,
        position_type: Optional[str] = None,
    ) -> list[PortfolioPosition]:
        """查询所有状态为 "holding" 的持仓记录，可按 position_type 过滤。

        参数
        ----
        position_type : str, optional
            持仓类型过滤条件，不传则返回全部 holding 持仓。

        返回
        ----
        PortfolioPosition 列表。
        """
        conditions = [PortfolioPosition.status == "holding"]
        if position_type is not None:
            conditions.append(PortfolioPosition.position_type == position_type)

        stmt = select(PortfolioPosition).where(and_(*conditions))
        return list(self._session.execute(stmt).scalars().all())

    # -----------------------------------------------------------------------
    # PortfolioTransaction
    # -----------------------------------------------------------------------

    def add_transaction(self, data: dict) -> PortfolioTransaction:
        """插入一条交易记录。

        参数
        ----
        data : dict
            交易数据字典，字段对应 PortfolioTransaction 各列。

        返回
        ----
        新插入的 PortfolioTransaction 对象（id 已填充）。
        """
        txn = PortfolioTransaction(**data)
        self._session.add(txn)
        self._session.flush()
        return txn

    # -----------------------------------------------------------------------
    # StrategySignal
    # -----------------------------------------------------------------------

    def save_signals(self, signals: list[dict]) -> None:
        """批量插入策略信号。

        参数
        ----
        signals : list[dict]
            策略信号数据列表，每个元素对应 StrategySignal 一行。
        """
        for signal_data in signals:
            obj = StrategySignal(**signal_data)
            self._session.add(obj)
        self._session.flush()

    # -----------------------------------------------------------------------
    # DipPlan
    # -----------------------------------------------------------------------

    def get_active_dip_plans(self) -> list[DipPlan]:
        """查询所有状态为 "active" 的定投计划。

        返回
        ----
        DipPlan 列表。
        """
        stmt = select(DipPlan).where(DipPlan.status == "active")
        return list(self._session.execute(stmt).scalars().all())
