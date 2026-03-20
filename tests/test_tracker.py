"""测试 PortfolioTracker 收益追踪模块。

使用 unittest.mock.MagicMock 模拟 FundRepository，
不依赖真实数据库，仅测试业务逻辑的正确性。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from fund_analyzer.portfolio.tracker import PortfolioTracker


# ---------------------------------------------------------------------------
# 辅助函数：构造 Mock Position 和 Mock Nav
# ---------------------------------------------------------------------------

def _make_position(
    fund_code: str,
    position_type: str,
    shares: str,
    cost_price: str,
) -> MagicMock:
    """构造模拟的 PortfolioPosition 对象。"""
    pos = MagicMock()
    pos.fund_code = fund_code
    pos.position_type = position_type
    pos.shares = Decimal(shares)
    pos.cost_price = Decimal(cost_price)
    return pos


def _make_nav_record(nav: str) -> MagicMock:
    """构造模拟的 FundNav 对象。"""
    record = MagicMock()
    record.nav = Decimal(nav)
    return record


# ---------------------------------------------------------------------------
# TestComputePortfolioSummary — 验证汇总计算
# ---------------------------------------------------------------------------

class TestComputePortfolioSummary:
    """测试 summary() 方法的整体汇总数值是否正确。

    持仓设置：
        - 基金 A（core）：1000 份，成本价 2.0，当前净值 2.5
          → market_value=2500, cost=2000, pnl=500, return_pct=25%
        - 基金 B（satellite）：2000 份，成本价 1.5，当前净值 1.8
          → market_value=3600, cost=3000, pnl=600, return_pct=20%

    总计：
        total_market_value = 2500 + 3600 = 6100
        total_cost          = 2000 + 3000 = 5000
        total_pnl           = 500  + 600  = 1100
        total_return_pct    = 1100 / 5000 * 100 = 22%
    """

    @pytest.fixture()
    def tracker(self):
        repo = MagicMock()
        repo.get_active_positions.return_value = [
            _make_position("000001", "core", "1000", "2.0"),
            _make_position("000002", "satellite", "2000", "1.5"),
        ]

        def _nav_side_effect(fund_code, start, end):
            nav_map = {
                "000001": "2.5",
                "000002": "1.8",
            }
            if fund_code in nav_map:
                return [_make_nav_record(nav_map[fund_code])]
            return []

        repo.get_fund_nav.side_effect = _nav_side_effect
        return PortfolioTracker(repo)

    def test_total_market_value(self, tracker):
        result = tracker.summary(as_of=date(2024, 1, 31))
        assert result["total_market_value"] == Decimal("6100")

    def test_total_cost(self, tracker):
        result = tracker.summary(as_of=date(2024, 1, 31))
        assert result["total_cost"] == Decimal("5000")

    def test_total_pnl(self, tracker):
        result = tracker.summary(as_of=date(2024, 1, 31))
        assert result["total_pnl"] == Decimal("1100")

    def test_total_return_pct(self, tracker):
        result = tracker.summary(as_of=date(2024, 1, 31))
        assert result["total_return_pct"] == Decimal("22")

    def test_as_of_date_in_result(self, tracker):
        target_date = date(2024, 1, 31)
        result = tracker.summary(as_of=target_date)
        assert result["as_of"] == target_date

    def test_holdings_count(self, tracker):
        result = tracker.summary(as_of=date(2024, 1, 31))
        assert len(result["holdings"]) == 2

    def test_holdings_fund_codes(self, tracker):
        result = tracker.summary(as_of=date(2024, 1, 31))
        codes = {h["fund_code"] for h in result["holdings"]}
        assert codes == {"000001", "000002"}


# ---------------------------------------------------------------------------
# TestCoreSatelliteBreakdown — 验证按 position_type 分组的结果
# ---------------------------------------------------------------------------

class TestCoreSatelliteBreakdown:
    """测试 summary() 方法中 by_type 分组数据是否正确。

    core 组：
        基金 A：1000 份 * 2.5 净值 = 2500 市值，2000 成本
        → market_value=2500, cost=2000, pnl=500, return_pct=25%

    satellite 组：
        基金 B：2000 份 * 1.8 净值 = 3600 市值，3000 成本
        → market_value=3600, cost=3000, pnl=600, return_pct=20%
    """

    @pytest.fixture()
    def result(self):
        repo = MagicMock()
        repo.get_active_positions.return_value = [
            _make_position("000001", "core", "1000", "2.0"),
            _make_position("000002", "satellite", "2000", "1.5"),
        ]

        def _nav_side_effect(fund_code, start, end):
            nav_map = {
                "000001": "2.5",
                "000002": "1.8",
            }
            if fund_code in nav_map:
                return [_make_nav_record(nav_map[fund_code])]
            return []

        repo.get_fund_nav.side_effect = _nav_side_effect
        tracker = PortfolioTracker(repo)
        return tracker.summary(as_of=date(2024, 1, 31))

    # -- core 组 --

    def test_core_market_value(self, result):
        """core 组市值 = 1000 * 2.5 = 2500"""
        assert result["by_type"]["core"]["market_value"] == Decimal("2500")

    def test_core_cost(self, result):
        """core 组成本 = 1000 * 2.0 = 2000"""
        assert result["by_type"]["core"]["cost"] == Decimal("2000")

    def test_core_pnl(self, result):
        """core 组盈亏 = 2500 - 2000 = 500"""
        assert result["by_type"]["core"]["pnl"] == Decimal("500")

    def test_core_return_pct(self, result):
        """core 组收益率 = 500 / 2000 * 100 = 25%"""
        assert result["by_type"]["core"]["return_pct"] == Decimal("25")

    # -- satellite 组 --

    def test_satellite_market_value(self, result):
        """satellite 组市值 = 2000 * 1.8 = 3600"""
        assert result["by_type"]["satellite"]["market_value"] == Decimal("3600")

    def test_satellite_cost(self, result):
        """satellite 组成本 = 2000 * 1.5 = 3000"""
        assert result["by_type"]["satellite"]["cost"] == Decimal("3000")

    def test_satellite_pnl(self, result):
        """satellite 组盈亏 = 3600 - 3000 = 600"""
        assert result["by_type"]["satellite"]["pnl"] == Decimal("600")

    def test_satellite_return_pct(self, result):
        """satellite 组收益率 = 600 / 3000 * 100 = 20%"""
        assert result["by_type"]["satellite"]["return_pct"] == Decimal("20")


# ---------------------------------------------------------------------------
# TestGetLatestNav — 验证净值回溯逻辑
# ---------------------------------------------------------------------------

class TestGetLatestNav:
    """测试 _get_latest_nav() 的回溯逻辑。"""

    def test_returns_nav_on_exact_date(self):
        """当 as_of 日期有净值时，直接返回该净值。"""
        repo = MagicMock()
        repo.get_fund_nav.return_value = [_make_nav_record("1.2345")]
        tracker = PortfolioTracker(repo)
        nav = tracker._get_latest_nav("000001", date(2024, 1, 31))
        assert nav == Decimal("1.2345")

    def test_returns_none_when_no_nav(self):
        """当日期范围内无净值记录时，返回 None。"""
        repo = MagicMock()
        repo.get_fund_nav.return_value = []
        tracker = PortfolioTracker(repo)
        nav = tracker._get_latest_nav("000001", date(2024, 1, 31))
        assert nav is None

    def test_returns_latest_when_multiple_records(self):
        """有多条记录时，返回日期最近（列表最后）的净值。"""
        repo = MagicMock()
        records = [
            _make_nav_record("1.1000"),  # 较早
            _make_nav_record("1.2000"),  # 较新
        ]
        repo.get_fund_nav.return_value = records
        tracker = PortfolioTracker(repo)
        nav = tracker._get_latest_nav("000001", date(2024, 1, 31))
        assert nav == Decimal("1.2000")

    def test_skips_none_nav_records(self):
        """跳过 nav 为 None 的记录，返回最近一条有效净值。"""
        repo = MagicMock()
        record_valid = MagicMock()
        record_valid.nav = Decimal("1.5000")
        record_none = MagicMock()
        record_none.nav = None
        # 列表升序：较早有效记录在前，最新记录 nav=None
        repo.get_fund_nav.return_value = [record_valid, record_none]
        tracker = PortfolioTracker(repo)
        nav = tracker._get_latest_nav("000001", date(2024, 1, 31))
        assert nav == Decimal("1.5000")

    def test_lookback_window_is_10_days(self):
        """确认查询窗口为 as_of 前 10 天到 as_of 当天。"""
        repo = MagicMock()
        repo.get_fund_nav.return_value = []
        tracker = PortfolioTracker(repo)
        as_of = date(2024, 1, 31)
        tracker._get_latest_nav("000001", as_of)
        call_args = repo.get_fund_nav.call_args
        assert call_args[0][1] == date(2024, 1, 21)   # start = as_of - 10 days
        assert call_args[0][2] == as_of                # end = as_of


# ---------------------------------------------------------------------------
# TestSummaryEdgeCases — 边界情况测试
# ---------------------------------------------------------------------------

class TestSummaryEdgeCases:
    """测试 summary() 的边界情况。"""

    def test_empty_positions(self):
        """无持仓时，所有汇总数值为 0，by_type 为空字典。"""
        repo = MagicMock()
        repo.get_active_positions.return_value = []
        tracker = PortfolioTracker(repo)
        result = tracker.summary(as_of=date(2024, 1, 31))
        assert result["total_market_value"] == Decimal("0")
        assert result["total_cost"] == Decimal("0")
        assert result["total_pnl"] == Decimal("0")
        assert result["total_return_pct"] is None
        assert result["by_type"] == {}
        assert result["holdings"] == []

    def test_nav_missing_falls_back_to_cost_price(self):
        """当净值缺失时，以成本价代替净值计算市值，盈亏为 0。"""
        repo = MagicMock()
        repo.get_active_positions.return_value = [
            _make_position("000001", "core", "1000", "2.0"),
        ]
        repo.get_fund_nav.return_value = []  # 无净值
        tracker = PortfolioTracker(repo)
        result = tracker.summary(as_of=date(2024, 1, 31))
        assert result["total_market_value"] == Decimal("2000")
        assert result["total_cost"] == Decimal("2000")
        assert result["total_pnl"] == Decimal("0")
        assert result["total_return_pct"] == Decimal("0")

    def test_default_as_of_is_today(self):
        """不传 as_of 时，默认使用 date.today()。"""
        from datetime import date as date_cls
        repo = MagicMock()
        repo.get_active_positions.return_value = []
        tracker = PortfolioTracker(repo)
        result = tracker.summary()
        assert result["as_of"] == date_cls.today()
