"""行业轮动策略（RotationStrategy）单元测试。

测试覆盖：
- test_score_batch：单只基金，结果在 0-100 之间
- test_fund_in_strong_industry_scores_higher：重仓上涨行业的基金评分更高
- test_no_holdings_returns_zero：无持仓基金评分为 0
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from fund_analyzer.strategy.rotation import RotationStrategy


# ---------------------------------------------------------------------------
# 测试辅助工厂函数
# ---------------------------------------------------------------------------


def make_holding(industry: str, weight: Decimal) -> MagicMock:
    """创建模拟持仓对象。"""
    h = MagicMock()
    h.industry = industry
    h.weight = weight
    return h


def make_quote(close: Decimal) -> MagicMock:
    """创建模拟指数行情对象。"""
    q = MagicMock()
    q.close = close
    return q


def make_quotes_series(start_close: Decimal, end_close: Decimal, n: int = 10) -> list[MagicMock]:
    """生成从 start_close 到 end_close 线性变化的 n 条行情数据。"""
    quotes = []
    for i in range(n):
        if n == 1:
            close = start_close
        else:
            close = start_close + (end_close - start_close) * Decimal(i) / Decimal(n - 1)
        quotes.append(make_quote(close))
    return quotes


# ---------------------------------------------------------------------------
# 测试用行业指数配置
# ---------------------------------------------------------------------------

INDUSTRY_INDICES = {
    "电子": "IDX_ELEC",
    "医药生物": "IDX_MED",
}

AS_OF = date(2024, 6, 30)  # 基准日期


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------


class TestScoreBatch:
    """测试 score_batch 基本功能：单只基金，结果在 0-100 之间。"""

    def _make_repo(self) -> MagicMock:
        """构造模拟 repo：
        - 电子指数：强势上涨（动量为正）
        - 医药生物指数：下跌（动量为负）
        - 基金 '000001' 的持仓：电子 60%，医药生物 40%
        """
        repo = MagicMock()

        # 电子指数：从 100 涨到 130（+30%）
        repo.get_index_quote.side_effect = lambda index_code, start, end: {
            "IDX_ELEC": make_quotes_series(Decimal("100"), Decimal("130")),
            "IDX_MED": make_quotes_series(Decimal("100"), Decimal("80")),
        }.get(index_code, [])

        # 基金持仓
        report_date = date(2024, 3, 31)  # as_of=2024-06-30，30天前 = 2024-05-31，最近季末 = 2024-03-31
        repo.get_fund_holdings.return_value = [
            make_holding("电子", Decimal("60")),
            make_holding("医药生物", Decimal("40")),
        ]

        return repo

    def test_score_is_between_0_and_100(self):
        """评分结果应在 [0, 100] 范围内。"""
        repo = self._make_repo()
        strategy = RotationStrategy(repo=repo, industry_indices=INDUSTRY_INDICES, momentum_window=60)

        scores = strategy.score_batch(["000001"], AS_OF)

        assert "000001" in scores
        score = scores["000001"]
        assert 0.0 <= score <= 100.0

    def test_returns_dict_with_all_fund_codes(self):
        """返回的字典应包含所有输入的基金代码。"""
        repo = self._make_repo()
        strategy = RotationStrategy(repo=repo, industry_indices=INDUSTRY_INDICES, momentum_window=60)

        scores = strategy.score_batch(["000001"], AS_OF)

        assert isinstance(scores, dict)
        assert set(scores.keys()) == {"000001"}

    def test_score_is_float(self):
        """评分应为 float 类型。"""
        repo = self._make_repo()
        strategy = RotationStrategy(repo=repo, industry_indices=INDUSTRY_INDICES, momentum_window=60)

        scores = strategy.score_batch(["000001"], AS_OF)

        assert isinstance(scores["000001"], float)


class TestFundInStrongIndustryScoresHigher:
    """测试重仓上涨行业的基金得分高于重仓下跌行业的基金。"""

    def _make_repo(self, strong_fund_code: str, weak_fund_code: str) -> MagicMock:
        """构造模拟 repo：
        - 电子指数：强势上涨 +40%
        - 医药生物指数：明显下跌 -20%
        - strong_fund：电子 90%，医药生物 10%
        - weak_fund：电子 10%，医药生物 90%
        """
        repo = MagicMock()

        # 行情数据
        elec_quotes = make_quotes_series(Decimal("100"), Decimal("140"))   # +40%
        med_quotes = make_quotes_series(Decimal("100"), Decimal("80"))     # -20%

        repo.get_index_quote.side_effect = lambda index_code, start, end: {
            "IDX_ELEC": elec_quotes,
            "IDX_MED": med_quotes,
        }.get(index_code, [])

        # 按基金代码返回不同持仓
        def get_holdings(fund_code: str, report_date: date) -> list[MagicMock]:
            if fund_code == strong_fund_code:
                return [
                    make_holding("电子", Decimal("90")),
                    make_holding("医药生物", Decimal("10")),
                ]
            elif fund_code == weak_fund_code:
                return [
                    make_holding("电子", Decimal("10")),
                    make_holding("医药生物", Decimal("90")),
                ]
            return []

        repo.get_fund_holdings.side_effect = get_holdings

        return repo

    def test_strong_industry_fund_scores_higher(self):
        """重仓强势（上涨）行业的基金评分应高于重仓弱势（下跌）行业的基金。"""
        strong_fund = "STRONG_FUND"
        weak_fund = "WEAK_FUND"

        repo = self._make_repo(strong_fund, weak_fund)
        strategy = RotationStrategy(
            repo=repo,
            industry_indices=INDUSTRY_INDICES,
            momentum_window=60,
        )

        scores = strategy.score_batch([strong_fund, weak_fund], AS_OF)

        assert scores[strong_fund] > scores[weak_fund], (
            f"期望 {strong_fund} 评分({scores[strong_fund]:.2f}) "
            f"> {weak_fund} 评分({scores[weak_fund]:.2f})"
        )

    def test_score_difference_is_significant(self):
        """两只基金的评分差距应体现行业强弱，差距大于 30 分。"""
        strong_fund = "STRONG_FUND"
        weak_fund = "WEAK_FUND"

        repo = self._make_repo(strong_fund, weak_fund)
        strategy = RotationStrategy(
            repo=repo,
            industry_indices=INDUSTRY_INDICES,
            momentum_window=60,
        )

        scores = strategy.score_batch([strong_fund, weak_fund], AS_OF)

        diff = scores[strong_fund] - scores[weak_fund]
        assert diff > 30, f"评分差距 {diff:.2f} 应大于 30 分"

    def test_strong_fund_score_close_to_100(self):
        """几乎完全重仓强势行业的基金评分应接近 100。"""
        strong_fund = "STRONG_FUND"
        weak_fund = "WEAK_FUND"

        repo = self._make_repo(strong_fund, weak_fund)
        strategy = RotationStrategy(
            repo=repo,
            industry_indices=INDUSTRY_INDICES,
            momentum_window=60,
        )

        scores = strategy.score_batch([strong_fund, weak_fund], AS_OF)

        assert scores[strong_fund] > 80, f"强势基金评分 {scores[strong_fund]:.2f} 应高于 80"

    def test_weak_fund_score_close_to_0(self):
        """几乎完全重仓弱势行业的基金评分应接近 0。"""
        strong_fund = "STRONG_FUND"
        weak_fund = "WEAK_FUND"

        repo = self._make_repo(strong_fund, weak_fund)
        strategy = RotationStrategy(
            repo=repo,
            industry_indices=INDUSTRY_INDICES,
            momentum_window=60,
        )

        scores = strategy.score_batch([strong_fund, weak_fund], AS_OF)

        assert scores[weak_fund] < 20, f"弱势基金评分 {scores[weak_fund]:.2f} 应低于 20"


class TestNoHoldingsReturnsZero:
    """测试无持仓基金的评分为 0。"""

    def _make_repo_no_holdings(self) -> MagicMock:
        """构造模拟 repo：行情数据正常，但持仓为空列表。"""
        repo = MagicMock()

        repo.get_index_quote.side_effect = lambda index_code, start, end: {
            "IDX_ELEC": make_quotes_series(Decimal("100"), Decimal("130")),
            "IDX_MED": make_quotes_series(Decimal("100"), Decimal("80")),
        }.get(index_code, [])

        # 返回空持仓
        repo.get_fund_holdings.return_value = []

        return repo

    def test_no_holdings_returns_zero(self):
        """无持仓基金的评分应为 0。"""
        repo = self._make_repo_no_holdings()
        strategy = RotationStrategy(
            repo=repo,
            industry_indices=INDUSTRY_INDICES,
            momentum_window=60,
        )

        scores = strategy.score_batch(["NO_HOLDING_FUND"], AS_OF)

        assert scores["NO_HOLDING_FUND"] == 0.0

    def test_multiple_funds_some_with_no_holdings(self):
        """多基金中部分无持仓的基金应得 0，有持仓的正常评分。"""
        repo = MagicMock()

        repo.get_index_quote.side_effect = lambda index_code, start, end: {
            "IDX_ELEC": make_quotes_series(Decimal("100"), Decimal("130")),
            "IDX_MED": make_quotes_series(Decimal("100"), Decimal("80")),
        }.get(index_code, [])

        def get_holdings(fund_code: str, report_date: date) -> list[MagicMock]:
            if fund_code == "FUND_WITH_HOLDINGS":
                return [make_holding("电子", Decimal("100"))]
            return []

        repo.get_fund_holdings.side_effect = get_holdings

        strategy = RotationStrategy(
            repo=repo,
            industry_indices=INDUSTRY_INDICES,
            momentum_window=60,
        )

        scores = strategy.score_batch(["FUND_WITH_HOLDINGS", "FUND_NO_HOLDINGS"], AS_OF)

        assert scores["FUND_NO_HOLDINGS"] == 0.0
        assert scores["FUND_WITH_HOLDINGS"] > 0.0


# ---------------------------------------------------------------------------
# 辅助方法测试
# ---------------------------------------------------------------------------


class TestGetLatestReportDate:
    """测试 _get_latest_report_date 辅助方法的正确性。"""

    def _make_strategy(self) -> RotationStrategy:
        repo = MagicMock()
        repo.get_index_quote.return_value = []
        repo.get_fund_holdings.return_value = []
        return RotationStrategy(repo=repo, industry_indices=INDUSTRY_INDICES)

    def test_as_of_june_30_returns_march_31(self):
        """as_of=2024-06-30（恰好是季末，但不满足30天条件），应返回 2024-03-31。"""
        strategy = self._make_strategy()
        # 2024-06-30 - 30天 = 2024-05-31，最近季末 <= 2024-05-31 是 2024-03-31
        report_date = strategy._get_latest_report_date(date(2024, 6, 30))
        assert report_date == date(2024, 3, 31)

    def test_as_of_april_30_returns_march_31(self):
        """as_of=2024-04-30，cutoff=2024-03-31，最近季末 = 2024-03-31。"""
        strategy = self._make_strategy()
        report_date = strategy._get_latest_report_date(date(2024, 4, 30))
        assert report_date == date(2024, 3, 31)

    def test_as_of_july_31_returns_june_30(self):
        """as_of=2024-07-31，cutoff=2024-07-01，最近季末 = 2024-06-30。"""
        strategy = self._make_strategy()
        report_date = strategy._get_latest_report_date(date(2024, 7, 31))
        assert report_date == date(2024, 6, 30)

    def test_as_of_january_15_returns_september_30_of_prev_year(self):
        """as_of=2024-01-15，cutoff=2023-12-16，2023-12-31 > cutoff 不满足条件，最近季末 = 2023-09-30。"""
        strategy = self._make_strategy()
        report_date = strategy._get_latest_report_date(date(2024, 1, 15))
        assert report_date == date(2023, 9, 30)


class TestGetIndustryMomentum:
    """测试 _get_industry_momentum 辅助方法。"""

    def _make_strategy(self, quotes_map: dict) -> RotationStrategy:
        repo = MagicMock()
        repo.get_index_quote.side_effect = (
            lambda index_code, start, end: quotes_map.get(index_code, [])
        )
        repo.get_fund_holdings.return_value = []
        return RotationStrategy(repo=repo, industry_indices=INDUSTRY_INDICES, momentum_window=60)

    def test_returns_none_for_unknown_industry(self):
        """未在映射中的行业应返回 None。"""
        strategy = self._make_strategy({})
        result = strategy._get_industry_momentum("未知行业", AS_OF)
        assert result is None

    def test_returns_none_when_insufficient_data(self):
        """数据不足（少于2条）时应返回 None。"""
        strategy = self._make_strategy({"IDX_ELEC": [make_quote(Decimal("100"))]})
        result = strategy._get_industry_momentum("电子", AS_OF)
        assert result is None

    def test_returns_correct_momentum_for_rising_index(self):
        """上涨行情应返回正的动量值。"""
        quotes = make_quotes_series(Decimal("100"), Decimal("130"), n=5)
        strategy = self._make_strategy({"IDX_ELEC": quotes})
        result = strategy._get_industry_momentum("电子", AS_OF)
        assert result is not None
        assert result == pytest.approx(0.30, rel=1e-4)

    def test_returns_correct_momentum_for_falling_index(self):
        """下跌行情应返回负的动量值。"""
        quotes = make_quotes_series(Decimal("100"), Decimal("80"), n=5)
        strategy = self._make_strategy({"IDX_MED": quotes})
        result = strategy._get_industry_momentum("医药生物", AS_OF)
        assert result is not None
        assert result == pytest.approx(-0.20, rel=1e-4)
