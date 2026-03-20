"""测试 ORM 数据模型。

使用 SQLite 内存数据库进行测试，验证所有9张表的创建、主键约束及可空字段。
"""
import pytest
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine, inspect
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def engine():
    """创建 SQLite 内存数据库引擎并初始化所有表。"""
    _engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)
    _engine.dispose()


@pytest.fixture()
def session(engine):
    """每个测试提供独立 Session，测试后回滚，保证隔离。"""
    with Session(engine) as s:
        yield s
        s.rollback()


# ---------------------------------------------------------------------------
# 辅助：检查表是否存在
# ---------------------------------------------------------------------------

def test_all_nine_tables_created(engine):
    """验证9张表均已在数据库中创建。"""
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    expected = {
        "fund_info",
        "fund_nav",
        "index_quote",
        "fund_holding",
        "industry_mapping",
        "portfolio_position",
        "portfolio_transaction",
        "strategy_signal",
        "dip_plan",
    }
    assert expected.issubset(table_names), (
        f"缺少以下表: {expected - table_names}"
    )


# ---------------------------------------------------------------------------
# FundInfo
# ---------------------------------------------------------------------------

class TestFundInfo:
    def test_create_fund_info(self, session):
        """测试创建基金基本信息记录。"""
        fund = FundInfo(
            fund_code="000001",
            fund_name="华夏成长",
            fund_type="股票型",
            market="A股",
            manager="张三",
            manager_start_date=date(2020, 1, 1),
            company="华夏基金",
            inception_date=date(2001, 11, 28),
            fund_size=Decimal("100.50"),
            benchmark="沪深300",
            updated_at=datetime(2024, 1, 1, 12, 0, 0),
        )
        session.add(fund)
        session.flush()

        result = session.get(FundInfo, "000001")
        assert result is not None
        assert result.fund_name == "华夏成长"
        assert result.fund_size == Decimal("100.50")

    def test_fund_info_primary_key(self, session):
        """测试 fund_code 为主键。"""
        fund = FundInfo(fund_code="000002", fund_name="测试基金")
        session.add(fund)
        session.flush()
        result = session.get(FundInfo, "000002")
        assert result.fund_code == "000002"


# ---------------------------------------------------------------------------
# FundNav
# ---------------------------------------------------------------------------

class TestFundNav:
    def test_create_fund_nav(self, session):
        """测试创建基金净值记录。"""
        nav = FundNav(
            fund_code="000001",
            date=date(2024, 1, 2),
            nav=Decimal("1.2345"),
            acc_nav=Decimal("2.3456"),
            daily_return=Decimal("0.005678"),
        )
        session.add(nav)
        session.flush()

        result = session.get(FundNav, ("000001", date(2024, 1, 2)))
        assert result is not None
        assert result.nav == Decimal("1.2345")

    def test_fund_nav_composite_pk(self, session):
        """测试 (fund_code, date) 复合主键。"""
        nav1 = FundNav(fund_code="000003", date=date(2024, 1, 1), nav=Decimal("1.0"))
        nav2 = FundNav(fund_code="000003", date=date(2024, 1, 2), nav=Decimal("1.1"))
        session.add_all([nav1, nav2])
        session.flush()

        r1 = session.get(FundNav, ("000003", date(2024, 1, 1)))
        r2 = session.get(FundNav, ("000003", date(2024, 1, 2)))
        assert r1.nav != r2.nav


# ---------------------------------------------------------------------------
# IndexQuote
# ---------------------------------------------------------------------------

class TestIndexQuote:
    def test_create_index_quote(self, session):
        """测试创建指数行情记录。"""
        quote = IndexQuote(
            index_code="000300",
            date=date(2024, 1, 2),
            close=Decimal("3500.1234"),
            daily_return=Decimal("0.012345"),
        )
        session.add(quote)
        session.flush()

        result = session.get(IndexQuote, ("000300", date(2024, 1, 2)))
        assert result is not None
        assert result.close == Decimal("3500.1234")

    def test_index_quote_composite_pk(self, session):
        """测试 (index_code, date) 复合主键。"""
        q1 = IndexQuote(index_code="000001", date=date(2024, 1, 1), close=Decimal("3000"))
        q2 = IndexQuote(index_code="000001", date=date(2024, 1, 2), close=Decimal("3010"))
        session.add_all([q1, q2])
        session.flush()

        r1 = session.get(IndexQuote, ("000001", date(2024, 1, 1)))
        r2 = session.get(IndexQuote, ("000001", date(2024, 1, 2)))
        assert r1.close != r2.close


# ---------------------------------------------------------------------------
# FundHolding
# ---------------------------------------------------------------------------

class TestFundHolding:
    def test_create_fund_holding(self, session):
        """测试创建基金持仓记录。"""
        holding = FundHolding(
            fund_code="000001",
            report_date=date(2024, 3, 31),
            stock_code="600519",
            stock_name="贵州茅台",
            industry="白酒",
            weight=Decimal("8.50"),
        )
        session.add(holding)
        session.flush()

        result = session.get(
            FundHolding, ("000001", date(2024, 3, 31), "600519")
        )
        assert result is not None
        assert result.stock_name == "贵州茅台"
        assert result.weight == Decimal("8.50")

    def test_fund_holding_composite_pk(self, session):
        """测试 (fund_code, report_date, stock_code) 三列复合主键。"""
        h1 = FundHolding(
            fund_code="000004",
            report_date=date(2024, 3, 31),
            stock_code="600000",
            weight=Decimal("5.00"),
        )
        h2 = FundHolding(
            fund_code="000004",
            report_date=date(2024, 3, 31),
            stock_code="600001",
            weight=Decimal("3.00"),
        )
        session.add_all([h1, h2])
        session.flush()

        r1 = session.get(FundHolding, ("000004", date(2024, 3, 31), "600000"))
        r2 = session.get(FundHolding, ("000004", date(2024, 3, 31), "600001"))
        assert r1.weight != r2.weight


# ---------------------------------------------------------------------------
# IndustryMapping
# ---------------------------------------------------------------------------

class TestIndustryMapping:
    def test_create_industry_mapping(self, session):
        """测试创建行业映射记录。"""
        mapping = IndustryMapping(
            stock_code="600519",
            stock_name="贵州茅台",
            industry_l1="消费",
            industry_l2="白酒",
            updated_at=datetime(2024, 1, 1),
        )
        session.add(mapping)
        session.flush()

        result = session.get(IndustryMapping, "600519")
        assert result is not None
        assert result.industry_l1 == "消费"


# ---------------------------------------------------------------------------
# PortfolioPosition
# ---------------------------------------------------------------------------

class TestPortfolioPosition:
    def test_create_portfolio_position(self, session):
        """测试创建持仓记录，包含可空字段 sell_date、sell_price。"""
        pos = PortfolioPosition(
            fund_code="000001",
            position_type="fixed",
            buy_date=date(2024, 1, 2),
            shares=Decimal("1000.0000"),
            cost_price=Decimal("1.2345"),
            status="holding",
            sell_date=None,
            sell_price=None,
        )
        session.add(pos)
        session.flush()

        assert pos.id is not None
        assert pos.sell_date is None
        assert pos.sell_price is None

    def test_portfolio_position_with_sell_info(self, session):
        """测试已卖出持仓记录，sell_date 和 sell_price 非空。"""
        pos = PortfolioPosition(
            fund_code="000001",
            position_type="dip",
            buy_date=date(2023, 6, 1),
            shares=Decimal("500.0000"),
            cost_price=Decimal("1.1000"),
            status="sold",
            sell_date=date(2024, 1, 10),
            sell_price=Decimal("1.3000"),
        )
        session.add(pos)
        session.flush()

        assert pos.sell_date == date(2024, 1, 10)
        assert pos.sell_price == Decimal("1.3000")

    def test_portfolio_position_serial_pk(self, session):
        """测试 id 为自增主键。"""
        pos1 = PortfolioPosition(fund_code="000001", buy_date=date(2024, 1, 1))
        pos2 = PortfolioPosition(fund_code="000001", buy_date=date(2024, 1, 2))
        session.add_all([pos1, pos2])
        session.flush()
        assert pos1.id != pos2.id


# ---------------------------------------------------------------------------
# PortfolioTransaction
# ---------------------------------------------------------------------------

class TestPortfolioTransaction:
    def test_create_portfolio_transaction(self, session):
        """测试创建交易记录，dip_plan_id 可空。"""
        txn = PortfolioTransaction(
            fund_code="000001",
            date=date(2024, 1, 2),
            type="buy",
            amount=Decimal("10000.00"),
            shares=Decimal("8100.0000"),
            nav=Decimal("1.2345"),
            position_type="fixed",
            dip_plan_id=None,
        )
        session.add(txn)
        session.flush()

        assert txn.id is not None
        assert txn.dip_plan_id is None

    def test_portfolio_transaction_with_dip_plan(self, session):
        """测试关联 dip_plan_id 的交易记录。"""
        txn = PortfolioTransaction(
            fund_code="000001",
            date=date(2024, 2, 1),
            type="buy",
            amount=Decimal("500.00"),
            shares=Decimal("400.0000"),
            nav=Decimal("1.2500"),
            position_type="dip",
            dip_plan_id=1,
        )
        session.add(txn)
        session.flush()

        assert txn.dip_plan_id == 1

    def test_portfolio_transaction_serial_pk(self, session):
        """测试 id 为自增主键。"""
        t1 = PortfolioTransaction(fund_code="000001", date=date(2024, 3, 1))
        t2 = PortfolioTransaction(fund_code="000001", date=date(2024, 3, 2))
        session.add_all([t1, t2])
        session.flush()
        assert t1.id != t2.id


# ---------------------------------------------------------------------------
# StrategySignal
# ---------------------------------------------------------------------------

class TestStrategySignal:
    def test_create_strategy_signal(self, session):
        """测试创建策略信号记录。"""
        signal = StrategySignal(
            strategy_name="ma_cross",
            date=date(2024, 1, 2),
            fund_code="000001",
            score=Decimal("85.50"),
            action="buy",
            position_type="fixed",
        )
        session.add(signal)
        session.flush()

        assert signal.id is not None
        assert signal.score == Decimal("85.50")

    def test_strategy_signal_serial_pk(self, session):
        """测试 id 为自增主键。"""
        s1 = StrategySignal(strategy_name="s1", date=date(2024, 1, 1), fund_code="000001")
        s2 = StrategySignal(strategy_name="s2", date=date(2024, 1, 2), fund_code="000001")
        session.add_all([s1, s2])
        session.flush()
        assert s1.id != s2.id


# ---------------------------------------------------------------------------
# DipPlan
# ---------------------------------------------------------------------------

class TestDipPlan:
    def test_create_dip_plan(self, session):
        """测试创建定投计划记录。"""
        plan = DipPlan(
            fund_code="000001",
            amount=Decimal("1000.00"),
            frequency="monthly",
            start_date=date(2024, 1, 1),
            status="active",
            smart_dip=True,
        )
        session.add(plan)
        session.flush()

        assert plan.id is not None
        assert plan.smart_dip is True

    def test_dip_plan_smart_dip_false(self, session):
        """测试 smart_dip 为 False 的定投计划。"""
        plan = DipPlan(
            fund_code="000001",
            amount=Decimal("500.00"),
            frequency="weekly",
            start_date=date(2024, 1, 1),
            status="paused",
            smart_dip=False,
        )
        session.add(plan)
        session.flush()

        assert plan.smart_dip is False

    def test_dip_plan_serial_pk(self, session):
        """测试 id 为自增主键。"""
        p1 = DipPlan(fund_code="000001", start_date=date(2024, 1, 1))
        p2 = DipPlan(fund_code="000001", start_date=date(2024, 2, 1))
        session.add_all([p1, p2])
        session.flush()
        assert p1.id != p2.id
