"""测试 FundRepository 数据访问层。

使用 SQLite 内存数据库，验证所有 repository 方法的正确性。
"""
import pytest
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import create_engine
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
from fund_analyzer.data.repository import FundRepository


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


# ---------------------------------------------------------------------------
# FundInfo — get_fund_info
# ---------------------------------------------------------------------------

class TestGetFundInfo:
    def test_found(self, repo, session):
        """能按 fund_code 查到已存在的基金信息。"""
        session.add(FundInfo(
            fund_code="110011",
            fund_name="易方达蓝筹精选",
            fund_type="股票型",
            inception_date=date(2018, 9, 5),
            fund_size=Decimal("200.00"),
        ))
        session.flush()

        result = repo.get_fund_info("110011")
        assert result is not None
        assert result.fund_code == "110011"
        assert result.fund_name == "易方达蓝筹精选"

    def test_not_found(self, repo):
        """查询不存在的 fund_code 时返回 None。"""
        result = repo.get_fund_info("NONEXISTENT")
        assert result is None


# ---------------------------------------------------------------------------
# FundInfo — get_eligible_funds
# ---------------------------------------------------------------------------

class TestGetEligibleFunds:
    def _add_funds(self, session):
        """准备测试数据：4只基金，覆盖不同成立年限、规模、类型。"""
        funds = [
            FundInfo(
                fund_code="F001",
                fund_name="老牌大型股票基金",
                fund_type="股票型",
                inception_date=date(2010, 1, 1),   # 15年以上
                fund_size=Decimal("100.00"),         # 100亿
            ),
            FundInfo(
                fund_code="F002",
                fund_name="新成立小型基金",
                fund_type="股票型",
                inception_date=date(2023, 6, 1),    # 不足2年
                fund_size=Decimal("5.00"),            # 5亿
            ),
            FundInfo(
                fund_code="F003",
                fund_name="货币基金",
                fund_type="货币型",
                inception_date=date(2015, 1, 1),    # 满足年限
                fund_size=Decimal("500.00"),          # 规模很大
            ),
            FundInfo(
                fund_code="F004",
                fund_name="中型混合基金",
                fund_type="混合型",
                inception_date=date(2018, 1, 1),    # 约7年
                fund_size=Decimal("20.00"),           # 20亿
            ),
        ]
        session.add_all(funds)
        session.flush()

    def test_filters_by_inception_years(self, repo, session):
        """按成立年限过滤：成立不足2年的基金被排除。"""
        self._add_funds(session)

        results = repo.get_eligible_funds(
            min_inception_years=2,
            min_size_billion=0,
            exclude_types=[],
            as_of=date(2025, 1, 1),
        )
        codes = {f.fund_code for f in results}
        assert "F002" not in codes   # 2023年成立，不足2年

    def test_filters_by_size(self, repo, session):
        """按规模过滤：规模低于10亿的基金被排除。"""
        self._add_funds(session)

        results = repo.get_eligible_funds(
            min_inception_years=0,
            min_size_billion=10,
            exclude_types=[],
            as_of=date(2025, 1, 1),
        )
        codes = {f.fund_code for f in results}
        assert "F002" not in codes   # 5亿，低于10亿门槛

    def test_excludes_types(self, repo, session):
        """按基金类型排除：货币型基金被过滤掉。"""
        self._add_funds(session)

        results = repo.get_eligible_funds(
            min_inception_years=0,
            min_size_billion=0,
            exclude_types=["货币型"],
            as_of=date(2025, 1, 1),
        )
        codes = {f.fund_code for f in results}
        assert "F003" not in codes   # 货币型被排除

    def test_combined_filters(self, repo, session):
        """组合条件过滤：年限>=3年 & 规模>=10亿 & 排除货币型。"""
        self._add_funds(session)

        results = repo.get_eligible_funds(
            min_inception_years=3,
            min_size_billion=10,
            exclude_types=["货币型"],
            as_of=date(2025, 1, 1),
        )
        codes = {f.fund_code for f in results}
        # F001: 老牌大型股票基金，满足所有条件
        assert "F001" in codes
        # F004: 混合型，满足年限和规模
        assert "F004" in codes
        # F002: 年限不足且规模偏小
        assert "F002" not in codes
        # F003: 货币型被排除
        assert "F003" not in codes


# ---------------------------------------------------------------------------
# FundInfo — upsert_fund_info
# ---------------------------------------------------------------------------

class TestUpsertFundInfo:
    def test_insert_new(self, repo, session):
        """upsert 对不存在的 fund_code 执行插入。"""
        repo.upsert_fund_info({
            "fund_code": "UPSERT001",
            "fund_name": "新基金",
            "fund_type": "债券型",
        })
        result = session.get(FundInfo, "UPSERT001")
        assert result is not None
        assert result.fund_name == "新基金"

    def test_update_existing(self, repo, session):
        """upsert 对已存在的 fund_code 执行更新。"""
        session.add(FundInfo(fund_code="UPSERT002", fund_name="旧名称"))
        session.flush()

        repo.upsert_fund_info({
            "fund_code": "UPSERT002",
            "fund_name": "新名称",
        })
        session.expire_all()
        result = session.get(FundInfo, "UPSERT002")
        assert result.fund_name == "新名称"


# ---------------------------------------------------------------------------
# FundNav — get_fund_nav
# ---------------------------------------------------------------------------

class TestGetFundNav:
    def _add_navs(self, session, fund_code: str):
        """为指定基金插入5条净值记录（2024-01-02 到 2024-01-08）。"""
        dates = [
            date(2024, 1, 2),
            date(2024, 1, 3),
            date(2024, 1, 4),
            date(2024, 1, 5),
            date(2024, 1, 8),
        ]
        navs = [
            FundNav(fund_code=fund_code, date=d, nav=Decimal("1.0") + Decimal(str(i * 0.01)))
            for i, d in enumerate(dates)
        ]
        session.add_all(navs)
        session.flush()

    def test_returns_records_in_date_range(self, repo, session):
        """按日期范围查询净值，只返回范围内记录。"""
        self._add_navs(session, "NAV001")

        results = repo.get_fund_nav("NAV001", date(2024, 1, 3), date(2024, 1, 5))
        assert len(results) == 3
        for r in results:
            assert date(2024, 1, 3) <= r.date <= date(2024, 1, 5)

    def test_ordered_by_date(self, repo, session):
        """返回结果按日期升序排列。"""
        self._add_navs(session, "NAV002")

        results = repo.get_fund_nav("NAV002", date(2024, 1, 1), date(2024, 12, 31))
        dates = [r.date for r in results]
        assert dates == sorted(dates)

    def test_returns_empty_when_no_data(self, repo):
        """无匹配记录时返回空列表。"""
        results = repo.get_fund_nav("NOEXIST", date(2024, 1, 1), date(2024, 12, 31))
        assert results == []


# ---------------------------------------------------------------------------
# FundNav — upsert_fund_navs
# ---------------------------------------------------------------------------

class TestUpsertFundNavs:
    def test_bulk_insert(self, repo, session):
        """批量插入新净值记录。"""
        rows = [
            {"date": date(2024, 2, 1), "nav": Decimal("1.10"), "acc_nav": Decimal("2.20")},
            {"date": date(2024, 2, 2), "nav": Decimal("1.11"), "acc_nav": Decimal("2.21")},
            {"date": date(2024, 2, 5), "nav": Decimal("1.12"), "acc_nav": Decimal("2.22")},
        ]
        repo.upsert_fund_navs("BULK001", rows)

        results = repo.get_fund_nav("BULK001", date(2024, 2, 1), date(2024, 2, 5))
        assert len(results) == 3

    def test_upsert_updates_existing(self, repo, session):
        """对已存在记录执行更新。"""
        session.add(FundNav(
            fund_code="BULK002",
            date=date(2024, 3, 1),
            nav=Decimal("1.00"),
        ))
        session.flush()

        repo.upsert_fund_navs("BULK002", [
            {"date": date(2024, 3, 1), "nav": Decimal("1.99")},
        ])
        session.expire_all()
        result = session.get(FundNav, ("BULK002", date(2024, 3, 1)))
        assert result.nav == Decimal("1.99")

    def test_empty_rows_noop(self, repo, session):
        """传入空列表时不抛出异常。"""
        repo.upsert_fund_navs("BULK003", [])  # 不应抛出异常


# ---------------------------------------------------------------------------
# IndexQuote
# ---------------------------------------------------------------------------

class TestIndexQuote:
    def test_get_index_quote_with_date_range(self, repo, session):
        """按日期范围查询指数行情。"""
        session.add_all([
            IndexQuote(index_code="HS300", date=date(2024, 1, 2), close=Decimal("3500")),
            IndexQuote(index_code="HS300", date=date(2024, 1, 3), close=Decimal("3510")),
            IndexQuote(index_code="HS300", date=date(2024, 1, 4), close=Decimal("3520")),
        ])
        session.flush()

        results = repo.get_index_quote("HS300", date(2024, 1, 2), date(2024, 1, 3))
        assert len(results) == 2

    def test_upsert_index_quotes(self, repo, session):
        """批量插入指数行情。"""
        rows = [
            {"date": date(2024, 4, 1), "close": Decimal("4000"), "daily_return": Decimal("0.01")},
            {"date": date(2024, 4, 2), "close": Decimal("4010"), "daily_return": Decimal("0.0025")},
        ]
        repo.upsert_index_quotes("ZZ500", rows)

        results = repo.get_index_quote("ZZ500", date(2024, 4, 1), date(2024, 4, 2))
        assert len(results) == 2


# ---------------------------------------------------------------------------
# FundHolding
# ---------------------------------------------------------------------------

class TestFundHolding:
    def test_get_fund_holdings(self, repo, session):
        """按 fund_code 和 report_date 查询基金持仓。"""
        session.add_all([
            FundHolding(fund_code="H001", report_date=date(2024, 3, 31), stock_code="600519", weight=Decimal("8.5")),
            FundHolding(fund_code="H001", report_date=date(2024, 3, 31), stock_code="000858", weight=Decimal("5.2")),
            FundHolding(fund_code="H001", report_date=date(2023, 12, 31), stock_code="600519", weight=Decimal("7.0")),
        ])
        session.flush()

        results = repo.get_fund_holdings("H001", date(2024, 3, 31))
        assert len(results) == 2
        codes = {r.stock_code for r in results}
        assert codes == {"600519", "000858"}


# ---------------------------------------------------------------------------
# IndustryMapping
# ---------------------------------------------------------------------------

class TestIndustryMapping:
    def test_get_industry_found(self, repo, session):
        """能按 stock_code 查到行业映射。"""
        session.add(IndustryMapping(
            stock_code="600519",
            stock_name="贵州茅台",
            industry_l1="消费",
            industry_l2="白酒",
        ))
        session.flush()

        result = repo.get_industry("600519")
        assert result is not None
        assert result.industry_l1 == "消费"

    def test_get_industry_not_found(self, repo):
        """查询不存在的 stock_code 时返回 None。"""
        result = repo.get_industry("NOTEXIST")
        assert result is None


# ---------------------------------------------------------------------------
# PortfolioPosition
# ---------------------------------------------------------------------------

class TestPortfolioPosition:
    def test_get_active_positions_all(self, repo, session):
        """无 position_type 过滤时，返回所有 status=holding 的持仓。"""
        session.add_all([
            PortfolioPosition(fund_code="P001", status="holding", position_type="fixed"),
            PortfolioPosition(fund_code="P002", status="holding", position_type="dip"),
            PortfolioPosition(fund_code="P003", status="sold", position_type="fixed"),
        ])
        session.flush()

        results = repo.get_active_positions()
        codes = {r.fund_code for r in results}
        assert "P001" in codes
        assert "P002" in codes
        assert "P003" not in codes

    def test_get_active_positions_filtered_by_type(self, repo, session):
        """传入 position_type 时，只返回该类型的 holding 持仓。"""
        session.add_all([
            PortfolioPosition(fund_code="PT001", status="holding", position_type="fixed"),
            PortfolioPosition(fund_code="PT002", status="holding", position_type="dip"),
        ])
        session.flush()

        results = repo.get_active_positions(position_type="fixed")
        types = {r.position_type for r in results}
        assert types == {"fixed"} or "dip" not in {r.fund_code for r in results if r.position_type == "dip"}
        # 确保 dip 类型未混入
        for r in results:
            if r.fund_code == "PT002":
                pytest.fail("PT002(dip) 不应出现在 fixed 过滤结果中")


# ---------------------------------------------------------------------------
# PortfolioTransaction
# ---------------------------------------------------------------------------

class TestPortfolioTransaction:
    def test_add_transaction(self, repo, session):
        """add_transaction 成功插入并返回 PortfolioTransaction 对象。"""
        txn = repo.add_transaction({
            "fund_code": "T001",
            "date": date(2024, 5, 1),
            "type": "buy",
            "amount": Decimal("10000.00"),
            "shares": Decimal("8000.0000"),
            "nav": Decimal("1.2500"),
            "position_type": "fixed",
        })
        assert txn.id is not None
        assert txn.fund_code == "T001"
        assert txn.type == "buy"


# ---------------------------------------------------------------------------
# StrategySignal
# ---------------------------------------------------------------------------

class TestStrategySignal:
    def test_save_signals(self, repo, session):
        """save_signals 批量插入策略信号。"""
        signals = [
            {
                "strategy_name": "ma_cross",
                "date": date(2024, 6, 1),
                "fund_code": "S001",
                "score": Decimal("80.00"),
                "action": "buy",
                "position_type": "fixed",
            },
            {
                "strategy_name": "ma_cross",
                "date": date(2024, 6, 1),
                "fund_code": "S002",
                "score": Decimal("60.00"),
                "action": "hold",
                "position_type": "dip",
            },
        ]
        repo.save_signals(signals)
        session.flush()

        from sqlalchemy import select
        stmt = select(StrategySignal).where(StrategySignal.strategy_name == "ma_cross")
        rows = session.execute(stmt).scalars().all()
        codes = {r.fund_code for r in rows}
        assert "S001" in codes
        assert "S002" in codes


# ---------------------------------------------------------------------------
# DipPlan
# ---------------------------------------------------------------------------

class TestDipPlan:
    def test_get_active_dip_plans(self, repo, session):
        """只返回 status=active 的定投计划。"""
        session.add_all([
            DipPlan(fund_code="D001", status="active", frequency="monthly"),
            DipPlan(fund_code="D002", status="active", frequency="weekly"),
            DipPlan(fund_code="D003", status="paused", frequency="monthly"),
        ])
        session.flush()

        results = repo.get_active_dip_plans()
        codes = {r.fund_code for r in results}
        assert "D001" in codes
        assert "D002" in codes
        assert "D003" not in codes
