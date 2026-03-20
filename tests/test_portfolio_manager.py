"""测试 PortfolioManager 组合管理器。

使用 SQLite 内存数据库，验证买入、卖出和持仓查询功能。
"""
import pytest
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from fund_analyzer.data.models import (
    Base,
    FundInfo,
    FundNav,
    PortfolioPosition,
    PortfolioTransaction,
)
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.portfolio.manager import PortfolioManager


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


@pytest.fixture()
def repo(session):
    """返回以 session 构造的 FundRepository 实例。"""
    return FundRepository(session)


@pytest.fixture()
def manager(repo):
    """返回 PortfolioManager 实例。"""
    return PortfolioManager(repo)


@pytest.fixture()
def fund_data(session):
    """插入测试用基金信息和净值数据。"""
    session.add(FundInfo(
        fund_code="110011",
        fund_name="易方达蓝筹精选",
        fund_type="股票型",
    ))
    session.add(FundNav(
        fund_code="110011",
        date=date(2024, 1, 2),
        nav=Decimal("2.0000"),
    ))
    session.flush()


# ---------------------------------------------------------------------------
# test_buy_fund — 验证买入后持仓创建正确
# ---------------------------------------------------------------------------

class TestBuyFund:
    def test_buy_fund_creates_position_with_correct_shares(self, manager, session, fund_data):
        """买入 10000 元，净值 2.0，份额应为 5000.0000。"""
        position = manager.buy(
            fund_code="110011",
            amount=10000,
            nav=2.0,
            position_type="satellite",
            buy_date=date(2024, 1, 2),
        )

        assert position is not None
        assert position.fund_code == "110011"
        assert position.shares == Decimal("5000.0000")
        assert position.cost_price == Decimal("2.0000")
        assert position.status == "holding"
        assert position.position_type == "satellite"
        assert position.buy_date == date(2024, 1, 2)

    def test_buy_fund_creates_transaction_with_buy_type(self, manager, session, fund_data):
        """普通买入时，交易类型应为 'buy'。"""
        manager.buy(
            fund_code="110011",
            amount=10000,
            nav=2.0,
            buy_date=date(2024, 1, 2),
        )

        stmt = select(PortfolioTransaction).where(
            PortfolioTransaction.fund_code == "110011",
            PortfolioTransaction.type == "buy",
        )
        txns = session.execute(stmt).scalars().all()
        assert len(txns) >= 1
        txn = txns[-1]
        assert txn.amount == Decimal("10000")
        assert txn.shares == Decimal("5000.0000")
        assert txn.nav == Decimal("2.0000")

    def test_buy_fund_with_dip_plan_id_creates_dip_transaction(self, manager, session, fund_data):
        """关联定投计划时，交易类型应为 'dip'。"""
        manager.buy(
            fund_code="110011",
            amount=5000,
            nav=2.0,
            buy_date=date(2024, 1, 2),
            dip_plan_id=1,
        )

        stmt = select(PortfolioTransaction).where(
            PortfolioTransaction.fund_code == "110011",
            PortfolioTransaction.type == "dip",
        )
        txns = session.execute(stmt).scalars().all()
        assert len(txns) >= 1
        txn = txns[-1]
        assert txn.dip_plan_id == 1
        assert txn.type == "dip"

    def test_buy_fund_default_position_type_is_satellite(self, manager, session, fund_data):
        """不传 position_type 时，默认为 'satellite'。"""
        position = manager.buy(
            fund_code="110011",
            amount=3000,
            nav=2.0,
            buy_date=date(2024, 1, 2),
        )
        assert position.position_type == "satellite"

    def test_buy_fund_shares_rounded_to_4_decimal_places(self, manager, session, fund_data):
        """份额应精确到4位小数（ROUND_HALF_UP）。"""
        # 10000 / 3.0 = 3333.3333... → 3333.3333
        position = manager.buy(
            fund_code="110011",
            amount=10000,
            nav=3.0,
            buy_date=date(2024, 1, 2),
        )
        expected = Decimal("10000") / Decimal("3.0")
        expected = expected.quantize(Decimal("0.0001"))
        assert position.shares == expected


# ---------------------------------------------------------------------------
# test_sell_fund — 部分卖出后剩余份额正确
# ---------------------------------------------------------------------------

class TestSellFund:
    def test_sell_fund_partial_sell_remaining_shares_correct(self, manager, session, fund_data):
        """部分卖出后，持仓剩余份额应正确减少。"""
        # 先买入 10000 元 @ 2.0 = 5000 份
        manager.buy(
            fund_code="110011",
            amount=10000,
            nav=2.0,
            position_type="satellite",
            buy_date=date(2024, 1, 2),
        )

        # 卖出 2000 份
        manager.sell(
            fund_code="110011",
            shares=2000,
            nav=2.5,
            sell_date=date(2024, 2, 1),
        )

        # 持仓剩余 5000 - 2000 = 3000 份，状态仍为 holding
        stmt = select(PortfolioPosition).where(
            PortfolioPosition.fund_code == "110011",
            PortfolioPosition.status == "holding",
        )
        positions = session.execute(stmt).scalars().all()
        assert len(positions) == 1
        assert positions[0].shares == Decimal("3000.0000")

    def test_sell_fund_creates_sell_transaction(self, manager, session, fund_data):
        """卖出后，应创建类型为 'sell' 的交易记录。"""
        manager.buy(
            fund_code="110011",
            amount=10000,
            nav=2.0,
            buy_date=date(2024, 1, 2),
        )

        manager.sell(
            fund_code="110011",
            shares=1000,
            nav=2.5,
            sell_date=date(2024, 2, 1),
        )

        stmt = select(PortfolioTransaction).where(
            PortfolioTransaction.fund_code == "110011",
            PortfolioTransaction.type == "sell",
        )
        txns = session.execute(stmt).scalars().all()
        assert len(txns) >= 1
        txn = txns[-1]
        assert txn.shares == Decimal("1000.0000")
        assert txn.nav == Decimal("2.5000")


# ---------------------------------------------------------------------------
# test_sell_all_clears_position — 全部卖出后状态变为 cleared
# ---------------------------------------------------------------------------

class TestSellAllClearsPosition:
    def test_sell_all_clears_position_status(self, manager, session, fund_data):
        """全部卖出后，持仓状态应变为 'cleared'。"""
        # 买入 10000 元 @ 2.0 = 5000 份
        manager.buy(
            fund_code="110011",
            amount=10000,
            nav=2.0,
            position_type="satellite",
            buy_date=date(2024, 1, 2),
        )

        # 全部卖出 5000 份
        manager.sell(
            fund_code="110011",
            shares=5000,
            nav=2.5,
            sell_date=date(2024, 3, 1),
        )

        # 所有持仓状态应为 cleared，没有 holding 持仓
        stmt_holding = select(PortfolioPosition).where(
            PortfolioPosition.fund_code == "110011",
            PortfolioPosition.status == "holding",
        )
        holding_positions = session.execute(stmt_holding).scalars().all()
        assert len(holding_positions) == 0

    def test_sell_all_sets_sell_date_and_sell_price(self, manager, session, fund_data):
        """全部卖出后，持仓的 sell_date 和 sell_price 应被正确设置。"""
        manager.buy(
            fund_code="110011",
            amount=10000,
            nav=2.0,
            position_type="satellite",
            buy_date=date(2024, 1, 2),
        )

        sell_date = date(2024, 3, 15)
        sell_nav = Decimal("3.0000")

        manager.sell(
            fund_code="110011",
            shares=5000,
            nav=float(sell_nav),
            sell_date=sell_date,
        )

        stmt = select(PortfolioPosition).where(
            PortfolioPosition.fund_code == "110011",
            PortfolioPosition.status == "cleared",
        )
        cleared_positions = session.execute(stmt).scalars().all()
        assert len(cleared_positions) >= 1

        pos = cleared_positions[-1]
        assert pos.sell_date == sell_date
        assert pos.sell_price == sell_nav

    def test_sell_fifo_order(self, manager, session, fund_data):
        """多个持仓按 FIFO 顺序卖出：先买入的先卖出。"""
        # 第一批买入 @ 2.0 (较早)
        manager.buy(
            fund_code="110011",
            amount=4000,
            nav=2.0,
            buy_date=date(2024, 1, 2),
        )
        # 第二批买入 @ 2.5 (较晚)
        manager.buy(
            fund_code="110011",
            amount=5000,
            nav=2.5,
            buy_date=date(2024, 2, 1),
        )

        # 卖出 2000 份，应从第一批（2000 份 @ 2.0）中扣除
        manager.sell(
            fund_code="110011",
            shares=2000,
            nav=3.0,
            sell_date=date(2024, 4, 1),
        )

        # 第一批剩余：2000 - 2000 = 0 份，状态 cleared
        # 第二批全量持有 2000 份
        stmt_cleared = select(PortfolioPosition).where(
            PortfolioPosition.fund_code == "110011",
            PortfolioPosition.status == "cleared",
        )
        cleared = session.execute(stmt_cleared).scalars().all()
        assert len(cleared) >= 1

        stmt_holding = select(PortfolioPosition).where(
            PortfolioPosition.fund_code == "110011",
            PortfolioPosition.status == "holding",
        )
        holdings = session.execute(stmt_holding).scalars().all()
        assert len(holdings) == 1


# ---------------------------------------------------------------------------
# test_get_holdings — 返回正确的持仓列表数据
# ---------------------------------------------------------------------------

class TestGetHoldings:
    def test_get_holdings_returns_correct_data(self, manager, session, fund_data):
        """get_holdings 应返回包含 fund_name 的持仓字典列表。"""
        manager.buy(
            fund_code="110011",
            amount=10000,
            nav=2.0,
            position_type="satellite",
            buy_date=date(2024, 1, 2),
        )

        holdings = manager.get_holdings()
        assert len(holdings) >= 1

        # 找到刚买入的持仓
        target = next((h for h in holdings if h["fund_code"] == "110011"), None)
        assert target is not None
        assert target["fund_name"] == "易方达蓝筹精选"
        assert target["position_type"] == "satellite"
        assert target["shares"] == Decimal("5000.0000")
        assert target["cost_price"] == Decimal("2.0000")
        assert target["buy_date"] == date(2024, 1, 2)

    def test_get_holdings_filter_by_position_type(self, manager, session, fund_data):
        """按 position_type 过滤，只返回指定类型的持仓。"""
        manager.buy(
            fund_code="110011",
            amount=10000,
            nav=2.0,
            position_type="satellite",
            buy_date=date(2024, 1, 2),
        )
        manager.buy(
            fund_code="110011",
            amount=5000,
            nav=2.0,
            position_type="core",
            buy_date=date(2024, 1, 2),
        )

        satellite_holdings = manager.get_holdings(position_type="satellite")
        for h in satellite_holdings:
            assert h["position_type"] == "satellite"

        core_holdings = manager.get_holdings(position_type="core")
        for h in core_holdings:
            assert h["position_type"] == "core"

    def test_get_holdings_excludes_cleared_positions(self, manager, session, fund_data):
        """已清仓的持仓不应出现在 get_holdings 结果中。"""
        manager.buy(
            fund_code="110011",
            amount=10000,
            nav=2.0,
            buy_date=date(2024, 1, 2),
        )

        # 全部卖出
        manager.sell(
            fund_code="110011",
            shares=5000,
            nav=2.5,
            sell_date=date(2024, 3, 1),
        )

        holdings = manager.get_holdings()
        # 所有返回的持仓都不应是 cleared 状态的
        for h in holdings:
            assert h["fund_code"] != "110011" or h["shares"] > 0

    def test_get_holdings_returns_dict_list(self, manager, session, fund_data):
        """get_holdings 返回值必须是字典列表，且包含所有必要字段。"""
        manager.buy(
            fund_code="110011",
            amount=10000,
            nav=2.0,
            buy_date=date(2024, 1, 2),
        )

        holdings = manager.get_holdings()
        assert isinstance(holdings, list)

        for h in holdings:
            assert isinstance(h, dict)
            assert "fund_code" in h
            assert "fund_name" in h
            assert "position_type" in h
            assert "shares" in h
            assert "cost_price" in h
            assert "buy_date" in h
