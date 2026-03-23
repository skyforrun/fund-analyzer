"""数据访问层（Repository）。

封装所有数据库访问操作，提供统一的 CRUD 接口。
依赖 SQLAlchemy 2.0 Session，使用 select / and_ 构造查询。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from sqlalchemy import select, and_, or_
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
    FundEstimate,
    FundWatchlist,
    NotificationConfig,
    NotificationRule,
    FundDividend,
    FundFeeSchedule,
    RiskProfile,
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
        require_nav: bool = True,
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
        require_nav : bool
            是否要求基金已有净值数据，默认 True。同步场景应设为 False。

        返回
        ----
        满足所有条件的 FundInfo 列表。
        """
        cutoff_date = as_of - timedelta(days=min_inception_years * 365)

        conditions = []

        # 成立日期须早于截止日期（NULL通过，尚未同步详情的基金允许参与）
        if min_inception_years > 0:
            conditions.append(
                or_(FundInfo.inception_date.is_(None), FundInfo.inception_date <= cutoff_date)
            )

        # 规模过滤（NULL通过）
        if min_size_billion > 0:
            conditions.append(
                or_(FundInfo.fund_size.is_(None), FundInfo.fund_size >= min_size_billion)
            )

        # 排除指定类型（模糊匹配，如 "货币型" 匹配 "货币型-xxx"）
        if exclude_types:
            for et in exclude_types:
                conditions.append(
                    or_(FundInfo.fund_type.is_(None), ~FundInfo.fund_type.contains(et))
                )

        stmt = select(FundInfo)

        # 只返回已有净值数据的基金（避免返回海量未同步的基金）
        if require_nav:
            from fund_analyzer.data.models import FundNav
            has_nav = select(FundNav.fund_code).distinct().subquery()
            stmt = stmt.where(FundInfo.fund_code.in_(select(has_nav.c.fund_code)))

        if conditions:
            stmt = stmt.where(and_(*conditions))

        return list(self._session.execute(stmt).scalars().all())

    def get_funds_with_nav(self) -> list[str]:
        """返回有净值数据的基金代码列表。"""
        stmt = select(FundNav.fund_code).distinct()
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

    # -----------------------------------------------------------------------
    # FundEstimate — 实时估值
    # -----------------------------------------------------------------------

    def upsert_estimate(self, data: dict) -> FundEstimate:
        """插入或更新基金估值数据。

        参数
        ----
        data : dict
            必须包含 fund_code, estimate_date 键。

        返回
        ----
        FundEstimate 对象。
        """
        key = (data["fund_code"], data["estimate_date"])
        obj = self._session.get(FundEstimate, key)
        if obj is None:
            obj = FundEstimate(**data)
            self._session.add(obj)
        else:
            for k, v in data.items():
                if k not in ("fund_code", "estimate_date"):
                    setattr(obj, k, v)
        self._session.flush()
        return obj

    def get_latest_estimates(self, fund_codes: list[str]) -> list[FundEstimate]:
        """获取指定基金列表的最新估值记录。

        参数
        ----
        fund_codes : list[str]
            基金代码列表。

        返回
        ----
        每只基金最新日期的估值记录列表。
        """
        if not fund_codes:
            return []
        from sqlalchemy import func
        subq = (
            select(
                FundEstimate.fund_code,
                func.max(FundEstimate.estimate_date).label("max_date"),
            )
            .where(FundEstimate.fund_code.in_(fund_codes))
            .group_by(FundEstimate.fund_code)
            .subquery()
        )
        stmt = select(FundEstimate).join(
            subq,
            and_(
                FundEstimate.fund_code == subq.c.fund_code,
                FundEstimate.estimate_date == subq.c.max_date,
            ),
        )
        return list(self._session.execute(stmt).scalars().all())

    # -----------------------------------------------------------------------
    # FundWatchlist — 自选关注
    # -----------------------------------------------------------------------

    def add_to_watchlist(
        self,
        fund_code: str,
        fund_name: str = "",
        group_name: str = "默认",
        notes: str = "",
    ) -> FundWatchlist:
        """添加基金到自选列表。若已存在则更新备注。"""
        from datetime import datetime as dt
        stmt = select(FundWatchlist).where(
            and_(
                FundWatchlist.fund_code == fund_code,
                FundWatchlist.group_name == group_name,
            )
        )
        obj = self._session.execute(stmt).scalar_one_or_none()
        if obj is None:
            obj = FundWatchlist(
                fund_code=fund_code,
                fund_name=fund_name,
                group_name=group_name,
                notes=notes,
                added_at=dt.now(),
            )
            self._session.add(obj)
        else:
            obj.notes = notes
            if fund_name:
                obj.fund_name = fund_name
        self._session.flush()
        return obj

    def remove_from_watchlist(
        self, fund_code: str, group_name: str | None = None
    ) -> int:
        """从自选列表移除基金。

        参数
        ----
        fund_code : str
            基金代码。
        group_name : str | None
            分组名。None 时删除该基金在所有分组的记录。

        返回
        ----
        删除的记录数。
        """
        conditions = [FundWatchlist.fund_code == fund_code]
        if group_name is not None:
            conditions.append(FundWatchlist.group_name == group_name)
        stmt = select(FundWatchlist).where(and_(*conditions))
        items = list(self._session.execute(stmt).scalars().all())
        for item in items:
            self._session.delete(item)
        self._session.flush()
        return len(items)

    def get_watchlist(self, group_name: str | None = None) -> list[FundWatchlist]:
        """获取自选列表，可按分组过滤。"""
        stmt = select(FundWatchlist)
        if group_name is not None:
            stmt = stmt.where(FundWatchlist.group_name == group_name)
        stmt = stmt.order_by(FundWatchlist.added_at.desc())
        return list(self._session.execute(stmt).scalars().all())

    def get_watchlist_groups(self) -> list[str]:
        """获取所有自选分组名。"""
        from sqlalchemy import func, distinct
        stmt = select(distinct(FundWatchlist.group_name))
        return list(self._session.execute(stmt).scalars().all())

    # -----------------------------------------------------------------------
    # NotificationConfig / NotificationRule — 通知管理
    # -----------------------------------------------------------------------

    def get_notification_config(self) -> NotificationConfig | None:
        """获取当前通知配置（仅支持单渠道）。"""
        stmt = select(NotificationConfig).where(NotificationConfig.enabled == True).limit(1)
        return self._session.execute(stmt).scalar_one_or_none()

    def save_notification_config(self, webhook_url: str, enabled: bool = True) -> NotificationConfig:
        """保存通知配置。若已有配置则更新，否则新建。"""
        from datetime import datetime as dt
        stmt = select(NotificationConfig).limit(1)
        obj = self._session.execute(stmt).scalar_one_or_none()
        if obj is None:
            obj = NotificationConfig(
                channel="wechat",
                webhook_url=webhook_url,
                enabled=enabled,
                updated_at=dt.now(),
            )
            self._session.add(obj)
        else:
            obj.webhook_url = webhook_url
            obj.enabled = enabled
            obj.updated_at = dt.now()
        self._session.flush()
        return obj

    def get_notification_rules(self) -> list[NotificationRule]:
        """获取所有通知规则。"""
        stmt = select(NotificationRule)
        return list(self._session.execute(stmt).scalars().all())

    def save_notification_rule(self, rule_type: str, params: dict | None, enabled: bool = True) -> NotificationRule:
        """保存通知规则。同类型规则存在则更新。"""
        stmt = select(NotificationRule).where(NotificationRule.rule_type == rule_type)
        obj = self._session.execute(stmt).scalar_one_or_none()
        if obj is None:
            obj = NotificationRule(rule_type=rule_type, params=params, enabled=enabled)
            self._session.add(obj)
        else:
            obj.params = params
            obj.enabled = enabled
        self._session.flush()
        return obj

    # -----------------------------------------------------------------------
    # FundDividend — 分红记录
    # -----------------------------------------------------------------------

    def upsert_dividends(self, fund_code: str, rows: list[dict]) -> None:
        """批量插入或更新分红记录。"""
        for row in rows:
            key = (fund_code, row["ex_date"])
            obj = self._session.get(FundDividend, key)
            if obj is None:
                obj = FundDividend(fund_code=fund_code, **row)
                self._session.add(obj)
            else:
                for k, v in row.items():
                    if k != "ex_date":
                        setattr(obj, k, v)
        self._session.flush()

    def get_dividends(
        self, fund_code: str, start_date: date | None = None
    ) -> list[FundDividend]:
        """查询基金分红历史。"""
        stmt = select(FundDividend).where(FundDividend.fund_code == fund_code)
        if start_date is not None:
            stmt = stmt.where(FundDividend.ex_date >= start_date)
        stmt = stmt.order_by(FundDividend.ex_date.desc())
        return list(self._session.execute(stmt).scalars().all())

    # -----------------------------------------------------------------------
    # FundFeeSchedule — 费率阶梯
    # -----------------------------------------------------------------------

    def upsert_fee_schedule(self, fund_code: str, schedules: list[dict]) -> None:
        """批量插入或更新费率阶梯。"""
        for row in schedules:
            stmt = select(FundFeeSchedule).where(
                and_(
                    FundFeeSchedule.fund_code == fund_code,
                    FundFeeSchedule.fee_type == row["fee_type"],
                    FundFeeSchedule.min_holding_days == row.get("min_holding_days", 0),
                    FundFeeSchedule.min_amount == row.get("min_amount", 0),
                )
            )
            obj = self._session.execute(stmt).scalar_one_or_none()
            if obj is None:
                obj = FundFeeSchedule(fund_code=fund_code, **row)
                self._session.add(obj)
            else:
                for k, v in row.items():
                    setattr(obj, k, v)
        self._session.flush()

    def get_fee_rate(
        self,
        fund_code: str,
        fee_type: str,
        holding_days: int | None = None,
        amount: float | None = None,
    ) -> Decimal | None:
        """查询实际适用费率。

        Parameters
        ----------
        fund_code : str
            基金代码。
        fee_type : str
            "purchase" 或 "redemption"。
        holding_days : int | None
            持有天数（赎回费用时使用）。
        amount : float | None
            申购金额（申购费用时使用）。

        Returns
        -------
        Decimal | None
            适用费率，无数据时返回 None。
        """
        stmt = select(FundFeeSchedule).where(
            and_(
                FundFeeSchedule.fund_code == fund_code,
                FundFeeSchedule.fee_type == fee_type,
            )
        )

        if fee_type == "redemption" and holding_days is not None:
            stmt = stmt.where(
                and_(
                    FundFeeSchedule.min_holding_days <= holding_days,
                    FundFeeSchedule.max_holding_days > holding_days,
                )
            )
        elif fee_type == "purchase" and amount is not None:
            stmt = stmt.where(
                or_(
                    FundFeeSchedule.min_amount.is_(None),
                    and_(
                        FundFeeSchedule.min_amount <= amount,
                        or_(
                            FundFeeSchedule.max_amount.is_(None),
                            FundFeeSchedule.max_amount > amount,
                        ),
                    ),
                )
            )

        stmt = stmt.order_by(FundFeeSchedule.min_holding_days.asc()).limit(1)
        result = self._session.execute(stmt).scalar_one_or_none()
        return result.fee_rate if result else None

    def get_fee_schedules(self, fund_code: str) -> list[FundFeeSchedule]:
        """获取基金的完整费率阶梯列表。"""
        stmt = (
            select(FundFeeSchedule)
            .where(FundFeeSchedule.fund_code == fund_code)
            .order_by(FundFeeSchedule.fee_type, FundFeeSchedule.min_holding_days)
        )
        return list(self._session.execute(stmt).scalars().all())

    # -----------------------------------------------------------------------
    # RiskProfile — 风险评估
    # -----------------------------------------------------------------------

    def save_risk_profile(self, data: dict) -> RiskProfile:
        """保存风险评估结果。"""
        obj = RiskProfile(**data)
        self._session.add(obj)
        self._session.flush()
        return obj

    def get_latest_risk_profile(self) -> RiskProfile | None:
        """获取最新的风险评估结果。"""
        stmt = select(RiskProfile).order_by(RiskProfile.assessment_date.desc()).limit(1)
        return self._session.execute(stmt).scalar_one_or_none()
