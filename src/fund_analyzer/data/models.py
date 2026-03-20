"""SQLAlchemy 2.0 ORM 数据模型定义。

共9张表：
    fund_info            — 基金基本信息
    fund_nav             — 基金净值
    index_quote          — 指数行情
    fund_holding         — 基金持仓
    industry_mapping     — 行业映射
    portfolio_position   — 组合持仓
    portfolio_transaction — 组合交易记录
    strategy_signal      — 策略信号
    dip_plan             — 定投计划
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    """所有 ORM 模型的公共基类。"""
    pass


# ---------------------------------------------------------------------------
# 1. FundInfo — 基金基本信息
# ---------------------------------------------------------------------------

class FundInfo(Base):
    """基金基本信息表。

    主键：fund_code
    """

    __tablename__ = "fund_info"

    fund_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    fund_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    fund_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    market: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    manager: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    manager_start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    company: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    inception_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fund_size: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(14, 2), nullable=True
    )
    benchmark: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<FundInfo fund_code={self.fund_code!r} fund_name={self.fund_name!r}>"


# ---------------------------------------------------------------------------
# 2. FundNav — 基金净值
# ---------------------------------------------------------------------------

class FundNav(Base):
    """基金净值表。

    复合主键：(fund_code, date)
    """

    __tablename__ = "fund_nav"

    fund_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    acc_nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    daily_return: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True
    )

    def __repr__(self) -> str:
        return f"<FundNav fund_code={self.fund_code!r} date={self.date!r} nav={self.nav!r}>"


# ---------------------------------------------------------------------------
# 3. IndexQuote — 指数行情
# ---------------------------------------------------------------------------

class IndexQuote(Base):
    """指数行情表。

    复合主键：(index_code, date)
    """

    __tablename__ = "index_quote"

    index_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    close: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    daily_return: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 6), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<IndexQuote index_code={self.index_code!r} date={self.date!r} "
            f"close={self.close!r}>"
        )


# ---------------------------------------------------------------------------
# 4. FundHolding — 基金持仓
# ---------------------------------------------------------------------------

class FundHolding(Base):
    """基金持仓表。

    复合主键：(fund_code, report_date, stock_code)
    """

    __tablename__ = "fund_holding"

    fund_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    stock_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    weight: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<FundHolding fund_code={self.fund_code!r} report_date={self.report_date!r} "
            f"stock_code={self.stock_code!r}>"
        )


# ---------------------------------------------------------------------------
# 5. IndustryMapping — 行业映射
# ---------------------------------------------------------------------------

class IndustryMapping(Base):
    """行业映射表。

    主键：stock_code
    """

    __tablename__ = "industry_mapping"

    stock_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    stock_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry_l1: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    industry_l2: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<IndustryMapping stock_code={self.stock_code!r} "
            f"industry_l1={self.industry_l1!r}>"
        )


# ---------------------------------------------------------------------------
# 6. PortfolioPosition — 组合持仓
# ---------------------------------------------------------------------------

class PortfolioPosition(Base):
    """组合持仓表。

    主键：id（自增）
    可空字段：sell_date, sell_price
    """

    __tablename__ = "portfolio_position"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    position_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    buy_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    shares: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    cost_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sell_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    sell_price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<PortfolioPosition id={self.id!r} fund_code={self.fund_code!r} "
            f"status={self.status!r}>"
        )


# ---------------------------------------------------------------------------
# 7. PortfolioTransaction — 组合交易记录
# ---------------------------------------------------------------------------

class PortfolioTransaction(Base):
    """组合交易记录表。

    主键：id（自增）
    可空字段：dip_plan_id
    索引：(fund_code, date), (dip_plan_id)
    """

    __tablename__ = "portfolio_transaction"
    __table_args__ = (
        Index("ix_portfolio_transaction_fund_date", "fund_code", "date"),
        Index("ix_portfolio_transaction_dip_plan_id", "dip_plan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    shares: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 4), nullable=True)
    nav: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4), nullable=True)
    position_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    dip_plan_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<PortfolioTransaction id={self.id!r} fund_code={self.fund_code!r} "
            f"date={self.date!r} type={self.type!r}>"
        )


# ---------------------------------------------------------------------------
# 8. StrategySignal — 策略信号
# ---------------------------------------------------------------------------

class StrategySignal(Base):
    """策略信号表。

    主键：id（自增）
    索引：(date, fund_code), (strategy_name, date)
    """

    __tablename__ = "strategy_signal"
    __table_args__ = (
        Index("ix_strategy_signal_date_fund", "date", "fund_code"),
        Index("ix_strategy_signal_name_date", "strategy_name", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    fund_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    score: Mapped[Optional[Decimal]] = mapped_column(Numeric(6, 2), nullable=True)
    action: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    position_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<StrategySignal id={self.id!r} strategy_name={self.strategy_name!r} "
            f"date={self.date!r} fund_code={self.fund_code!r}>"
        )


# ---------------------------------------------------------------------------
# 9. DipPlan — 定投计划
# ---------------------------------------------------------------------------

class DipPlan(Base):
    """定投计划表。

    主键：id（自增）
    """

    __tablename__ = "dip_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    frequency: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    smart_dip: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    def __repr__(self) -> str:
        return (
            f"<DipPlan id={self.id!r} fund_code={self.fund_code!r} "
            f"frequency={self.frequency!r} status={self.status!r}>"
        )
