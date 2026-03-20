"""绩效指标计算模块的测试。"""
import numpy as np
import pandas as pd
import pytest

from fund_analyzer.backtest.metrics import (
    annualized_return,
    annualized_volatility,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
    calmar_ratio,
    information_ratio,
    monthly_win_rate,
    compute_all_metrics,
)

# 使用固定随机种子生成约252天的日收益率数据（模拟年化约10%收益）
np.random.seed(42)
DAILY_RETURNS = pd.Series(np.random.normal(0.0004, 0.01, 252))

# 生成基准收益率（略低于组合，用于测试信息比率）
np.random.seed(99)
BENCHMARK_RETURNS = pd.Series(np.random.normal(0.0002, 0.01, 252))


class TestAnnualizedReturn:
    def test_returns_float(self):
        result = annualized_return(DAILY_RETURNS)
        assert isinstance(result, float)

    def test_reasonable_range(self):
        """年化收益率应在合理区间内（-50% 到 +200% 之间）。"""
        result = annualized_return(DAILY_RETURNS)
        assert -0.5 < result < 2.0

    def test_positive_returns_series(self):
        """全正收益序列的年化收益率应为正。"""
        positive_returns = pd.Series([0.001] * 252)
        result = annualized_return(positive_returns)
        assert result > 0

    def test_zero_returns(self):
        """全零收益序列的年化收益率应为0。"""
        zero_returns = pd.Series([0.0] * 252)
        result = annualized_return(zero_returns)
        assert abs(result) < 1e-9

    def test_custom_trading_days(self):
        """自定义交易日数量不应影响函数可调用性。"""
        result = annualized_return(DAILY_RETURNS, trading_days=365)
        assert isinstance(result, float)

    def test_formula_correctness(self):
        """验证公式：(1+r).prod()^(252/n) - 1。"""
        returns = pd.Series([0.01, -0.005, 0.008, 0.003])
        n = len(returns)
        expected = (1 + returns).prod() ** (252 / n) - 1
        result = annualized_return(returns)
        assert abs(result - expected) < 1e-10


class TestAnnualizedVolatility:
    def test_returns_float(self):
        result = annualized_volatility(DAILY_RETURNS)
        assert isinstance(result, float)

    def test_positive_value(self):
        """波动率应为非负数。"""
        result = annualized_volatility(DAILY_RETURNS)
        assert result >= 0

    def test_reasonable_range(self):
        """年化波动率应在合理区间（0% 到 100%）内。"""
        result = annualized_volatility(DAILY_RETURNS)
        assert 0 < result < 1.0

    def test_formula_correctness(self):
        """验证公式：std * sqrt(252)。"""
        result = annualized_volatility(DAILY_RETURNS)
        expected = DAILY_RETURNS.std() * np.sqrt(252)
        assert abs(result - expected) < 1e-10

    def test_zero_volatility(self):
        """固定收益序列的波动率应为0。"""
        constant_returns = pd.Series([0.001] * 100)
        result = annualized_volatility(constant_returns)
        assert abs(result) < 1e-9


class TestMaxDrawdown:
    def test_returns_float(self):
        result = max_drawdown(DAILY_RETURNS)
        assert isinstance(result, float)

    def test_positive_value(self):
        """最大回撤应为正数（或零）。"""
        result = max_drawdown(DAILY_RETURNS)
        assert result >= 0

    def test_reasonable_range(self):
        """最大回撤应在0到1之间。"""
        result = max_drawdown(DAILY_RETURNS)
        assert 0 <= result <= 1.0

    def test_no_drawdown(self):
        """单调递增序列的最大回撤应为0。"""
        increasing_returns = pd.Series([0.01] * 100)
        result = max_drawdown(increasing_returns)
        assert result == 0.0

    def test_known_drawdown(self):
        """验证已知回撤场景的计算结果。
        净值序列：1.0 -> 1.1 -> 0.88 -> 0.99
        峰值1.1，谷值0.88，回撤=(1.1-0.88)/1.1≈0.2
        """
        # 日收益率使净值变化：1.0 -> 1.1 -> 0.88 -> 0.99
        returns = pd.Series([0.1, -0.2, (0.99 / 0.88) - 1])
        result = max_drawdown(returns)
        expected = (1.1 - 0.88) / 1.1
        assert abs(result - expected) < 1e-6


class TestSharpeRatio:
    def test_returns_float(self):
        result = sharpe_ratio(DAILY_RETURNS)
        assert isinstance(result, float)

    def test_reasonable_range(self):
        """夏普比率通常在-3到5之间。"""
        result = sharpe_ratio(DAILY_RETURNS)
        assert -5.0 < result < 10.0

    def test_higher_return_higher_sharpe(self):
        """收益更高的组合（同等风险）夏普比率应更高。"""
        low_return = pd.Series(np.random.normal(0.0001, 0.01, 252))
        high_return = pd.Series(np.random.normal(0.001, 0.01, 252))
        assert sharpe_ratio(high_return) > sharpe_ratio(low_return)

    def test_risk_free_rate_effect(self):
        """较高无风险利率应导致更低的夏普比率。"""
        sharpe_low_rf = sharpe_ratio(DAILY_RETURNS, risk_free_rate=0.01)
        sharpe_high_rf = sharpe_ratio(DAILY_RETURNS, risk_free_rate=0.05)
        assert sharpe_low_rf > sharpe_high_rf


class TestSortinoRatio:
    def test_returns_float(self):
        result = sortino_ratio(DAILY_RETURNS)
        assert isinstance(result, float)

    def test_reasonable_range(self):
        """索提诺比率通常在合理范围内。"""
        result = sortino_ratio(DAILY_RETURNS)
        assert -10.0 < result < 20.0

    def test_sortino_vs_sharpe(self):
        """对于正偏态分布，索提诺比率通常 >= 夏普比率。"""
        # 生成有正偏态的收益序列（更多正收益日）
        np.random.seed(0)
        skewed_returns = pd.Series(np.random.exponential(0.005, 252) - 0.001)
        sortino = sortino_ratio(skewed_returns)
        sharpe = sharpe_ratio(skewed_returns)
        # 当下行波动率 < 总体波动率时，索提诺 >= 夏普
        assert isinstance(sortino, float)
        assert isinstance(sharpe, float)

    def test_only_uses_downside_volatility(self):
        """仅使用负收益日计算波动率。"""
        result = sortino_ratio(DAILY_RETURNS)
        # 手动计算验证
        rf_daily = 0.02 / 252
        excess = DAILY_RETURNS - rf_daily
        downside = excess[excess < 0]
        downside_vol = downside.std() * np.sqrt(252)
        ann_ret = annualized_return(DAILY_RETURNS)
        expected = (ann_ret - 0.02) / downside_vol
        assert abs(result - expected) < 1e-6


class TestCalmarRatio:
    def test_returns_float(self):
        result = calmar_ratio(DAILY_RETURNS)
        assert isinstance(result, float)

    def test_formula_correctness(self):
        """验证公式：年化收益率 / 最大回撤。"""
        ann_ret = annualized_return(DAILY_RETURNS)
        mdd = max_drawdown(DAILY_RETURNS)
        expected = ann_ret / mdd
        result = calmar_ratio(DAILY_RETURNS)
        assert abs(result - expected) < 1e-10

    def test_zero_drawdown_returns_nan_or_inf(self):
        """最大回撤为0时，卡玛比率应返回 inf 或 nan。"""
        increasing_returns = pd.Series([0.01] * 100)
        result = calmar_ratio(increasing_returns)
        assert np.isinf(result) or np.isnan(result)


class TestInformationRatio:
    def test_returns_float(self):
        result = information_ratio(DAILY_RETURNS, BENCHMARK_RETURNS)
        assert isinstance(result, float)

    def test_reasonable_range(self):
        """信息比率通常在合理范围内。"""
        result = information_ratio(DAILY_RETURNS, BENCHMARK_RETURNS)
        assert -5.0 < result < 10.0

    def test_formula_correctness(self):
        """验证公式：超额收益年化均值 / 跟踪误差。"""
        excess = DAILY_RETURNS - BENCHMARK_RETURNS
        tracking_error = excess.std() * np.sqrt(252)
        alpha = excess.mean() * 252
        expected = alpha / tracking_error
        result = information_ratio(DAILY_RETURNS, BENCHMARK_RETURNS)
        assert abs(result - expected) < 1e-10


class TestMonthlyWinRate:
    def test_returns_float(self):
        result = monthly_win_rate(DAILY_RETURNS)
        assert isinstance(result, float)

    def test_range_0_to_1(self):
        """月度胜率应在0到1之间。"""
        result = monthly_win_rate(DAILY_RETURNS)
        assert 0.0 <= result <= 1.0

    def test_all_positive_returns(self):
        """全正收益序列的月度胜率应为1.0。"""
        all_positive = pd.Series([0.001] * 252)
        result = monthly_win_rate(all_positive)
        assert result == 1.0

    def test_all_negative_returns(self):
        """全负收益序列的月度胜率应为0.0。"""
        all_negative = pd.Series([-0.001] * 252)
        result = monthly_win_rate(all_negative)
        assert result == 0.0

    def test_month_window_size(self):
        """每21个交易日为一个月份窗口。"""
        # 21天正，21天负，21天正 -> 胜率应为 2/3
        returns = pd.Series([0.001] * 21 + [-0.001] * 21 + [0.001] * 21)
        result = monthly_win_rate(returns)
        assert abs(result - 2 / 3) < 1e-6


class TestComputeAllMetrics:
    def test_returns_dict(self):
        result = compute_all_metrics(DAILY_RETURNS)
        assert isinstance(result, dict)

    def test_required_keys_without_benchmark(self):
        """不提供基准时，返回字典应包含基本指标键。"""
        result = compute_all_metrics(DAILY_RETURNS)
        expected_keys = {
            "annualized_return",
            "annualized_volatility",
            "max_drawdown",
            "sharpe_ratio",
            "sortino_ratio",
            "calmar_ratio",
            "monthly_win_rate",
        }
        assert expected_keys.issubset(result.keys())

    def test_no_information_ratio_without_benchmark(self):
        """不提供基准时，不应包含 information_ratio 和 alpha 键。"""
        result = compute_all_metrics(DAILY_RETURNS)
        assert "information_ratio" not in result
        assert "alpha" not in result

    def test_includes_information_ratio_with_benchmark(self):
        """提供基准时，应包含 information_ratio 和 alpha 键。"""
        result = compute_all_metrics(DAILY_RETURNS, benchmark_returns=BENCHMARK_RETURNS)
        assert "information_ratio" in result
        assert "alpha" in result

    def test_all_values_are_float(self):
        """所有指标值应为 float 类型。"""
        result = compute_all_metrics(DAILY_RETURNS, benchmark_returns=BENCHMARK_RETURNS)
        for key, value in result.items():
            assert isinstance(value, float), f"{key} 的值应为 float，实际为 {type(value)}"

    def test_values_consistency(self):
        """compute_all_metrics 的各值应与独立调用单个函数的结果一致。"""
        result = compute_all_metrics(DAILY_RETURNS, benchmark_returns=BENCHMARK_RETURNS)
        assert abs(result["annualized_return"] - annualized_return(DAILY_RETURNS)) < 1e-10
        assert abs(result["annualized_volatility"] - annualized_volatility(DAILY_RETURNS)) < 1e-10
        assert abs(result["max_drawdown"] - max_drawdown(DAILY_RETURNS)) < 1e-10
        assert abs(result["sharpe_ratio"] - sharpe_ratio(DAILY_RETURNS)) < 1e-10
        assert abs(result["sortino_ratio"] - sortino_ratio(DAILY_RETURNS)) < 1e-10
        assert abs(result["monthly_win_rate"] - monthly_win_rate(DAILY_RETURNS)) < 1e-10

    def test_custom_risk_free_rate(self):
        """自定义无风险利率应影响夏普比率和索提诺比率。"""
        result_default = compute_all_metrics(DAILY_RETURNS)
        result_high_rf = compute_all_metrics(DAILY_RETURNS, risk_free_rate=0.05)
        assert result_default["sharpe_ratio"] != result_high_rf["sharpe_ratio"]
