"""FactorStrategy 单元测试。"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from fund_analyzer.strategy.factor import FactorStrategy, _DEFAULT_WEIGHTS


# ---------------------------------------------------------------------------
# 辅助工具函数
# ---------------------------------------------------------------------------


def _make_nav_records(n: int, daily_return: float = 0.0005) -> list[MagicMock]:
    """生成 n 条模拟净值记录，每条记录包含 daily_return 和 acc_nav 属性。"""
    records = []
    nav = 1.0
    for i in range(n):
        rec = MagicMock()
        rec.daily_return = Decimal(str(daily_return))
        nav *= 1 + daily_return
        rec.acc_nav = Decimal(str(round(nav, 4)))
        records.append(rec)
    return records


def _make_repo(
    nav_count: int = 200,
    daily_return: float = 0.0005,
    fund_size: float = 50.0,
    manager_tenure_years: float = 5.0,
    as_of: date | None = None,
) -> MagicMock:
    """构造模拟 FundRepository。"""
    if as_of is None:
        as_of = date(2024, 1, 1)

    repo = MagicMock()
    repo.get_fund_nav.return_value = _make_nav_records(nav_count, daily_return)

    fund_info = MagicMock()
    fund_info.fund_size = Decimal(str(fund_size))
    fund_info.manager_start_date = as_of - timedelta(days=int(manager_tenure_years * 365.25))
    repo.get_fund_info.return_value = fund_info

    return repo


# ---------------------------------------------------------------------------
# 测试：score_batch 返回有效评分（0-100）
# ---------------------------------------------------------------------------


class TestScoreBatchReturnsScores:
    """验证 score_batch 对有效数据返回 0-100 范围内的评分。"""

    def test_score_in_valid_range(self):
        """标准输入时评分应在 [0, 100] 范围内。"""
        as_of = date(2024, 1, 1)
        repo = _make_repo(nav_count=200, as_of=as_of)
        strategy = FactorStrategy(repo)
        scores = strategy.score_batch(["000001"], as_of)

        assert "000001" in scores
        score = scores["000001"]
        assert 0.0 <= score <= 100.0

    def test_multiple_funds_all_in_range(self):
        """多只基金全部应有 0-100 评分。"""
        as_of = date(2024, 1, 1)
        repo = _make_repo(nav_count=200, as_of=as_of)
        strategy = FactorStrategy(repo)
        codes = ["000001", "000002", "000003"]
        scores = strategy.score_batch(codes, as_of)

        assert set(scores.keys()) == set(codes)
        for code, score in scores.items():
            assert 0.0 <= score <= 100.0, f"{code} 的评分 {score} 超出 [0, 100]"

    def test_score_is_float(self):
        """评分应为 float 类型。"""
        as_of = date(2024, 1, 1)
        repo = _make_repo(nav_count=200, as_of=as_of)
        strategy = FactorStrategy(repo)
        scores = strategy.score_batch(["000001"], as_of)

        assert isinstance(scores["000001"], float)

    def test_higher_return_yields_higher_score(self):
        """相同条件下，日收益率更高的基金评分应更高。"""
        as_of = date(2024, 1, 1)

        repo_low = _make_repo(nav_count=200, daily_return=-0.001, as_of=as_of)
        repo_high = _make_repo(nav_count=200, daily_return=0.002, as_of=as_of)

        strategy_low = FactorStrategy(repo_low)
        strategy_high = FactorStrategy(repo_high)

        score_low = strategy_low.score_batch(["000001"], as_of)["000001"]
        score_high = strategy_high.score_batch(["000001"], as_of)["000001"]

        assert score_high > score_low

    def test_custom_weights_accepted(self):
        """自定义权重时评分仍应在 [0, 100] 范围内。"""
        as_of = date(2024, 1, 1)
        repo = _make_repo(nav_count=200, as_of=as_of)
        custom_weights = {"sharpe": 1.0}
        strategy = FactorStrategy(repo, weights=custom_weights)
        scores = strategy.score_batch(["000001"], as_of)

        score = scores["000001"]
        assert 0.0 <= score <= 100.0

    def test_default_weights_used_when_none_provided(self):
        """不传 weights 时应使用默认权重。"""
        as_of = date(2024, 1, 1)
        repo = _make_repo(nav_count=200, as_of=as_of)
        strategy = FactorStrategy(repo)
        assert strategy._weights == _DEFAULT_WEIGHTS


# ---------------------------------------------------------------------------
# 测试：极端规模基金评分惩罚
# ---------------------------------------------------------------------------


class TestScorePenalizesExtremeFundSize:
    """验证规模过大（500B）或过小的基金会受到评分惩罚。"""

    def test_extreme_large_fund_score_lower_than_normal(self):
        """500B 超大基金的评分应低于正常规模（50B）基金。"""
        as_of = date(2024, 1, 1)

        repo_normal = _make_repo(nav_count=200, fund_size=50.0, as_of=as_of)
        repo_huge = _make_repo(nav_count=200, fund_size=500.0, as_of=as_of)

        # 使用只含 fund_size 权重的策略，排除其他因子干扰
        weights = {"fund_size": 1.0}
        strategy_normal = FactorStrategy(repo_normal, weights=weights)
        strategy_huge = FactorStrategy(repo_huge, weights=weights)

        score_normal = strategy_normal.score_batch(["000001"], as_of)["000001"]
        score_huge = strategy_huge.score_batch(["000001"], as_of)["000001"]

        assert score_normal > score_huge, (
            f"正常规模评分 ({score_normal:.2f}) 应高于超大规模评分 ({score_huge:.2f})"
        )

    def test_500b_fund_size_factor_score(self):
        """直接测试 _factor_to_score 对 500B 基金规模的打分低于 2B-200B 区间。"""
        repo = MagicMock()
        strategy = FactorStrategy(repo)

        score_normal = strategy._factor_to_score("fund_size", 50.0)   # 正常规模
        score_huge = strategy._factor_to_score("fund_size", 500.0)    # 超大规模

        assert score_normal == pytest.approx(90.0)
        assert score_huge < score_normal

    def test_tiny_fund_penalized(self):
        """极小规模基金（0.5B）评分应低于正常区间。"""
        repo = MagicMock()
        strategy = FactorStrategy(repo)

        score_small = strategy._factor_to_score("fund_size", 0.5)
        score_normal = strategy._factor_to_score("fund_size", 50.0)

        assert score_small < score_normal

    def test_500b_full_strategy_score_in_range(self):
        """500B 基金完整评分仍应在 [0, 100] 范围内。"""
        as_of = date(2024, 1, 1)
        repo = _make_repo(nav_count=200, fund_size=500.0, as_of=as_of)
        strategy = FactorStrategy(repo)
        scores = strategy.score_batch(["000001"], as_of)

        score = scores["000001"]
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# 测试：无净值数据时评分为 0
# ---------------------------------------------------------------------------


class TestScoreWithNoNavData:
    """验证净值数据不足时评分返回 0。"""

    def test_no_nav_data_returns_zero(self):
        """get_fund_nav 返回空列表时，评分应为 0。"""
        as_of = date(2024, 1, 1)
        repo = MagicMock()
        repo.get_fund_nav.return_value = []

        strategy = FactorStrategy(repo)
        scores = strategy.score_batch(["000001"], as_of)

        assert scores["000001"] == 0.0

    def test_insufficient_nav_data_returns_zero(self):
        """不足 60 条净值记录时，评分应为 0。"""
        as_of = date(2024, 1, 1)
        repo = MagicMock()
        repo.get_fund_nav.return_value = _make_nav_records(30)  # 仅 30 条

        strategy = FactorStrategy(repo)
        scores = strategy.score_batch(["000001"], as_of)

        assert scores["000001"] == 0.0

    def test_exactly_60_data_points_not_zero(self):
        """恰好 60 条净值记录时，应正常计算（不为 0）。"""
        as_of = date(2024, 1, 1)
        repo = _make_repo(nav_count=60, as_of=as_of)
        strategy = FactorStrategy(repo)
        scores = strategy.score_batch(["000001"], as_of)

        assert scores["000001"] != 0.0
        assert 0.0 < scores["000001"] <= 100.0

    def test_missing_fund_info_does_not_crash(self):
        """get_fund_info 返回 None 时，不应崩溃，评分仍在合法范围内。"""
        as_of = date(2024, 1, 1)
        repo = MagicMock()
        repo.get_fund_nav.return_value = _make_nav_records(200)
        repo.get_fund_info.return_value = None  # 无基金信息

        strategy = FactorStrategy(repo)
        scores = strategy.score_batch(["000001"], as_of)

        score = scores["000001"]
        assert 0.0 <= score <= 100.0

    def test_multiple_funds_some_without_nav(self):
        """部分基金无数据时，无数据的评分为 0，其余正常。"""
        as_of = date(2024, 1, 1)
        repo = MagicMock()

        def side_effect(fund_code, start, end):
            if fund_code == "000001":
                return _make_nav_records(200)
            return []

        def info_side_effect(fund_code):
            info = MagicMock()
            info.fund_size = Decimal("50.0")
            info.manager_start_date = as_of - timedelta(days=5 * 365)
            return info

        repo.get_fund_nav.side_effect = side_effect
        repo.get_fund_info.side_effect = info_side_effect

        strategy = FactorStrategy(repo)
        scores = strategy.score_batch(["000001", "000002"], as_of)

        assert 0.0 < scores["000001"] <= 100.0
        assert scores["000002"] == 0.0


# ---------------------------------------------------------------------------
# 测试：_factor_to_score 边界行为
# ---------------------------------------------------------------------------


class TestFactorToScore:
    """验证 _factor_to_score 的各因子映射逻辑。"""

    def setup_method(self):
        self.strategy = FactorStrategy(MagicMock())

    def test_nan_returns_50(self):
        """NaN 因子值应返回中性分数 50。"""
        import math
        score = self.strategy._factor_to_score("sharpe", math.nan)
        assert score == pytest.approx(50.0)

    def test_inf_returns_50(self):
        """Inf 因子值应返回中性分数 50。"""
        score = self.strategy._factor_to_score("calmar", float("inf"))
        assert score == pytest.approx(50.0)

    def test_return_1y_high_gets_high_score(self):
        """高年化收益率（40%）应接近满分。"""
        score = self.strategy._factor_to_score("return_1y", 0.40)
        assert score == pytest.approx(100.0)

    def test_return_1y_low_gets_low_score(self):
        """极低年化收益率（-20%）应接近 0 分。"""
        score = self.strategy._factor_to_score("return_1y", -0.20)
        assert score == pytest.approx(0.0)

    def test_max_drawdown_zero_gets_100(self):
        """零回撤应得 100 分。"""
        score = self.strategy._factor_to_score("max_drawdown", 0.0)
        assert score == pytest.approx(100.0)

    def test_max_drawdown_60pct_gets_0(self):
        """60% 最大回撤应得 0 分。"""
        score = self.strategy._factor_to_score("max_drawdown", 0.60)
        assert score == pytest.approx(0.0)

    def test_volatility_zero_gets_100(self):
        """零波动率应得 100 分。"""
        score = self.strategy._factor_to_score("volatility", 0.0)
        assert score == pytest.approx(100.0)

    def test_manager_tenure_5y_gets_90(self):
        """5 年任职期应得 90 分。"""
        score = self.strategy._factor_to_score("manager_tenure", 5.0)
        assert score == pytest.approx(90.0)

    def test_manager_tenure_under_1y_gets_20(self):
        """不足 1 年任职期应得 20 分。"""
        score = self.strategy._factor_to_score("manager_tenure", 0.5)
        assert score == pytest.approx(20.0)

    def test_fund_size_in_optimal_range_gets_90(self):
        """2B-200B 规模应得 90 分。"""
        for size in [2.0, 50.0, 100.0, 200.0]:
            score = self.strategy._factor_to_score("fund_size", size)
            assert score == pytest.approx(90.0), f"规模 {size}B 的评分应为 90，实际为 {score}"

    def test_score_clamped_to_0_100(self):
        """超出映射范围的值应被截断到 [0, 100]。"""
        # 极端高收益，应截断为 100
        score = self.strategy._factor_to_score("return_1y", 999.0)
        assert score == pytest.approx(100.0)

        # 极端负收益，应截断为 0
        score = self.strategy._factor_to_score("return_1y", -999.0)
        assert score == pytest.approx(0.0)
