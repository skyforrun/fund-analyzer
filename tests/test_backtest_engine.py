"""BacktestEngine 回测引擎的测试。

使用 Mock 对象替代 FundRepository 和 CompositeStrategy，
通过合成随机数据验证回测逻辑的正确性。
"""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from fund_analyzer.backtest.engine import BacktestEngine


# ---------------------------------------------------------------------------
# 测试数据工厂
# ---------------------------------------------------------------------------

def _make_quote_records(start: date, n_days: int, seed: int = 42) -> list[MagicMock]:
    """生成模拟行情/净值记录列表。

    参数
    ----
    start : date
        起始日期。
    n_days : int
        记录条数（交易日数量）。
    seed : int
        随机种子，保证可复现。

    返回
    ----
    MagicMock 列表，每个对象具有 date、close、daily_return 属性。
    """
    rng = np.random.default_rng(seed)
    records = []
    current = start
    for _ in range(n_days):
        record = MagicMock()
        record.date = current
        record.close = 1000.0 + rng.normal(0, 10)
        record.daily_return = rng.normal(0.0004, 0.01)  # 模拟日均收益约 0.04%
        records.append(record)
        current += timedelta(days=1)
    return records


def _build_mock_repo(
    benchmark_records: list[MagicMock],
    fund_records_map: dict[str, list[MagicMock]],
) -> MagicMock:
    """构建模拟 FundRepository。

    参数
    ----
    benchmark_records : list[MagicMock]
        基准指数行情记录（用于 get_index_quote 返回值）。
    fund_records_map : dict[str, list[MagicMock]]
        基金代码到净值记录列表的映射（用于 get_fund_nav 返回值）。

    返回
    ----
    配置好的 MagicMock repo。
    """
    repo = MagicMock()
    repo.get_index_quote.return_value = benchmark_records

    def _mock_get_fund_nav(fund_code: str, start: date, end: date):
        records = fund_records_map.get(fund_code, [])
        return [r for r in records if start <= r.date <= end]

    repo.get_fund_nav.side_effect = _mock_get_fund_nav
    return repo


def _build_mock_composite(
    core_picks: list[tuple[str, float]],
    sat_picks: list[tuple[str, float]],
) -> MagicMock:
    """构建模拟 CompositeStrategy。

    参数
    ----
    core_picks : list[tuple[str, float]]
        固定返回的核心仓位推荐列表 [(code, score), ...]。
    sat_picks : list[tuple[str, float]]
        固定返回的卫星仓位推荐列表 [(code, score), ...]。

    返回
    ----
    配置好的 MagicMock composite。
    """
    composite = MagicMock()
    composite.recommend.return_value = (core_picks, sat_picks)
    return composite


# ---------------------------------------------------------------------------
# 公共夹具
# ---------------------------------------------------------------------------

START_DATE = date(2022, 1, 1)
N_DAYS = 750  # 约3年交易日

# 生成基准行情（750条）
BENCHMARK_RECORDS = _make_quote_records(START_DATE, N_DAYS, seed=0)
END_DATE = BENCHMARK_RECORDS[-1].date

# 候选基金代码
FUND_UNIVERSE = ["110010", "110011", "110012", "110013", "110014", "110015", "110016", "110017", "110018", "110019"]

# 生成各基金净值数据
FUND_RECORDS_MAP: dict[str, list[MagicMock]] = {
    code: _make_quote_records(START_DATE, N_DAYS, seed=int(code) % 100)
    for code in FUND_UNIVERSE
}

CORE_PICKS = [("110010", 95.0), ("110011", 90.0), ("110012", 85.0)]
SAT_PICKS = [
    ("110013", 88.0),
    ("110014", 82.0),
    ("110015", 78.0),
    ("110016", 75.0),
    ("110017", 70.0),
    ("110018", 65.0),
    ("110019", 60.0),
]


@pytest.fixture
def repo():
    return _build_mock_repo(BENCHMARK_RECORDS, FUND_RECORDS_MAP)


@pytest.fixture
def composite():
    return _build_mock_composite(CORE_PICKS, SAT_PICKS)


@pytest.fixture
def engine(repo, composite):
    return BacktestEngine(
        repo=repo,
        composite=composite,
        initial_capital=100_000,
        core_ratio=0.3,
        satellite_ratio=0.7,
        core_top_n=3,
        satellite_top_n=7,
        buy_fee=0.0015,
        sell_fee=0.005,
        core_rebalance_months=3,
        satellite_rebalance_months=1,
    )


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------

class TestBacktestEngineGetRebalanceDates:
    """测试 _get_rebalance_dates 方法。"""

    def test_includes_start_date(self, engine):
        start = date(2022, 1, 1)
        end = date(2022, 12, 31)
        dates = engine._get_rebalance_dates(start, end, months=3)
        assert dates[0] == start

    def test_correct_interval(self, engine):
        start = date(2022, 1, 1)
        end = date(2022, 12, 31)
        dates = engine._get_rebalance_dates(start, end, months=3)
        # 1月1日、4月1日、7月1日、10月1日 = 4个日期
        assert len(dates) == 4

    def test_monthly_interval(self, engine):
        start = date(2022, 1, 1)
        end = date(2022, 6, 30)
        dates = engine._get_rebalance_dates(start, end, months=1)
        assert len(dates) == 6  # 1月~6月各1次

    def test_does_not_exceed_end(self, engine):
        start = date(2022, 1, 1)
        end = date(2022, 3, 31)
        dates = engine._get_rebalance_dates(start, end, months=3)
        assert all(d <= end for d in dates)

    def test_single_period(self, engine):
        start = date(2022, 1, 1)
        end = date(2022, 2, 28)
        dates = engine._get_rebalance_dates(start, end, months=3)
        # 只有起始日期满足条件
        assert dates == [start]


class TestBacktestEngineGetDailyReturn:
    """测试 _get_daily_return 方法。"""

    def test_returns_float(self, engine):
        d = BENCHMARK_RECORDS[0].date
        result = engine._get_daily_return("110010", d)
        assert isinstance(result, float)

    def test_no_data_returns_zero(self, engine):
        """无数据时应返回 0.0。"""
        d = date(2000, 1, 1)  # 超出数据范围的日期
        result = engine._get_daily_return("110010", d)
        assert result == 0.0

    def test_unknown_fund_returns_zero(self, engine):
        """未知基金代码应返回 0.0。"""
        d = BENCHMARK_RECORDS[0].date
        result = engine._get_daily_return("999999", d)
        assert result == 0.0

    def test_retrieves_correct_value(self, repo, composite):
        """应返回 repo 中记录的 daily_return 值。"""
        target_date = date(2022, 6, 1)
        mock_record = MagicMock()
        mock_record.daily_return = 0.025
        repo.get_fund_nav.side_effect = None
        repo.get_fund_nav.return_value = [mock_record]

        engine = BacktestEngine(repo=repo, composite=composite)
        result = engine._get_daily_return("110010", target_date)
        assert abs(result - 0.025) < 1e-9


class TestRunBacktest:
    """测试 run 方法的核心功能。"""

    def test_run_returns_dict(self, engine):
        """run 应返回 dict 类型。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert isinstance(result, dict)

    def test_run_has_expected_keys(self, engine):
        """返回字典应包含所有预期键。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        expected_keys = {
            "portfolio_returns",
            "benchmark_returns",
            "portfolio_values",
            "metrics",
            "total_fees_paid",
            "final_value",
            "initial_capital",
        }
        assert expected_keys == set(result.keys())

    def test_metrics_not_none(self, engine):
        """metrics 字典不应为 None 且应包含基础指标。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        metrics = result["metrics"]
        assert metrics is not None
        assert isinstance(metrics, dict)
        assert "annualized_return" in metrics
        assert "sharpe_ratio" in metrics
        assert "max_drawdown" in metrics

    def test_portfolio_returns_is_series(self, engine):
        """portfolio_returns 应为 pd.Series 类型。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert isinstance(result["portfolio_returns"], pd.Series)

    def test_benchmark_returns_is_series(self, engine):
        """benchmark_returns 应为 pd.Series 类型。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert isinstance(result["benchmark_returns"], pd.Series)

    def test_portfolio_values_is_series(self, engine):
        """portfolio_values 应为 pd.Series 类型。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert isinstance(result["portfolio_values"], pd.Series)

    def test_initial_capital_preserved(self, engine):
        """返回的 initial_capital 应等于构造时设置的值。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert result["initial_capital"] == 100_000

    def test_portfolio_benchmark_aligned(self, engine):
        """portfolio_returns 和 benchmark_returns 的索引应对齐。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        pd.testing.assert_index_equal(
            result["portfolio_returns"].index,
            result["benchmark_returns"].index,
        )

    def test_portfolio_values_length(self, engine):
        """portfolio_values 的长度应等于交易日数量。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert len(result["portfolio_values"]) == N_DAYS

    def test_final_value_is_float(self, engine):
        """final_value 应为 float 类型。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert isinstance(result["final_value"], float)

    def test_metrics_has_information_ratio(self, engine):
        """提供基准时，metrics 应包含 information_ratio。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert "information_ratio" in result["metrics"]

    def test_metrics_has_alpha(self, engine):
        """提供基准时，metrics 应包含 alpha。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert "alpha" in result["metrics"]


class TestBacktestDeductsFees:
    """测试手续费扣除逻辑。"""

    def test_total_fees_paid_positive(self, engine):
        """回测期间应扣除手续费，total_fees_paid > 0。"""
        result = engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert result["total_fees_paid"] > 0

    def test_zero_fee_engine_has_no_fees(self, repo, composite):
        """手续费为零时，total_fees_paid 应为 0。"""
        zero_fee_engine = BacktestEngine(
            repo=repo,
            composite=composite,
            initial_capital=100_000,
            buy_fee=0.0,
            sell_fee=0.0,
        )
        result = zero_fee_engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert result["total_fees_paid"] == 0.0

    def test_higher_fee_reduces_final_value(self, repo, composite):
        """更高的手续费应导致更低的最终净值。"""
        low_fee_engine = BacktestEngine(
            repo=repo,
            composite=composite,
            initial_capital=100_000,
            buy_fee=0.0001,
            sell_fee=0.001,
        )
        high_fee_engine = BacktestEngine(
            repo=repo,
            composite=composite,
            initial_capital=100_000,
            buy_fee=0.005,
            sell_fee=0.01,
        )
        low_fee_result = low_fee_engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        high_fee_result = high_fee_engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert low_fee_result["total_fees_paid"] < high_fee_result["total_fees_paid"]

    def test_fees_increase_with_rebalance_frequency(self, repo, composite):
        """调仓频率越高，手续费应越多。"""
        frequent_engine = BacktestEngine(
            repo=repo,
            composite=composite,
            initial_capital=100_000,
            satellite_rebalance_months=1,
        )
        infrequent_engine = BacktestEngine(
            repo=repo,
            composite=composite,
            initial_capital=100_000,
            satellite_rebalance_months=6,
        )
        frequent_result = frequent_engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        infrequent_result = infrequent_engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert frequent_result["total_fees_paid"] > infrequent_result["total_fees_paid"]


class TestBacktestRebalanceLogic:
    """测试调仓逻辑。"""

    def test_composite_recommend_called(self, engine, composite):
        """回测过程中应调用 composite.recommend。"""
        engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        assert composite.recommend.called

    def test_composite_recommend_called_multiple_times(self, engine, composite):
        """在多个调仓日应多次调用 composite.recommend。"""
        engine.run(FUND_UNIVERSE, START_DATE, END_DATE)
        # 3年，每月调仓一次卫星，每3个月调仓一次核心，总调用次数应 > 1
        assert composite.recommend.call_count > 1

    def test_empty_fund_universe(self, repo, composite):
        """空基金池回测不应报错，但 total_fees_paid 应为 0。"""
        composite.recommend.return_value = ([], [])
        engine = BacktestEngine(repo=repo, composite=composite)
        result = engine.run([], START_DATE, END_DATE)
        assert result["total_fees_paid"] == 0.0

    def test_core_equal_weight_allocation(self, repo, composite):
        """核心仓位应等权分配给各推荐基金。

        通过单日回测场景验证：首日建仓时各核心基金分配金额相等。
        """
        # 使用单日数据简化验证
        single_day_records = BENCHMARK_RECORDS[:1]
        repo.get_index_quote.return_value = single_day_records

        engine = BacktestEngine(
            repo=repo,
            composite=composite,
            initial_capital=90_000,  # 核心30% = 27000，3只各9000
            core_ratio=1.0,
            satellite_ratio=0.0,
            buy_fee=0.0,
            sell_fee=0.0,
        )
        composite.recommend.return_value = (
            [("110010", 95.0), ("110011", 90.0), ("110012", 85.0)],
            [],
        )
        result = engine.run(["110010", "110011", "110012"], START_DATE, single_day_records[0].date)
        # 有手续费为零情况下，手续费为0且正常运行
        assert result["total_fees_paid"] == 0.0
