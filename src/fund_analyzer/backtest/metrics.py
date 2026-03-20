"""绩效指标计算模块。

提供基于日收益率序列的常用量化投资绩效评估指标计算函数。
所有函数接受 pd.Series 类型的日收益率数据作为输入。
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def annualized_return(daily_returns: pd.Series, trading_days: int = 252) -> float:
    """计算年化收益率。

    公式：(1 + r).prod() ^ (trading_days / n) - 1

    Args:
        daily_returns: 日收益率序列（小数形式，如 0.01 代表 1%）。
        trading_days: 年交易日数量，默认 252。

    Returns:
        年化收益率（小数形式）。
    """
    n = len(daily_returns)
    cumulative = (1 + daily_returns).prod()
    return float(cumulative ** (trading_days / n) - 1)


def annualized_volatility(daily_returns: pd.Series, trading_days: int = 252) -> float:
    """计算年化波动率。

    公式：std(daily_returns) * sqrt(trading_days)

    Args:
        daily_returns: 日收益率序列。
        trading_days: 年交易日数量，默认 252。

    Returns:
        年化波动率（小数形式）。
    """
    return float(daily_returns.std() * np.sqrt(trading_days))


def max_drawdown(daily_returns: pd.Series) -> float:
    """计算最大回撤（从峰值到谷值的最大跌幅）。

    返回正数，表示最大跌幅比例。

    Args:
        daily_returns: 日收益率序列。

    Returns:
        最大回撤（正数，小数形式）。
    """
    # 计算累计净值序列（从1开始）
    cumulative_value = (1 + daily_returns).cumprod()

    # 计算历史最高净值（滚动最大值）
    rolling_peak = cumulative_value.cummax()

    # 计算回撤序列：(峰值 - 当前值) / 峰值
    drawdown = (rolling_peak - cumulative_value) / rolling_peak

    return float(drawdown.max())


def sharpe_ratio(
    daily_returns: pd.Series,
    risk_free_rate: float = 0.02,
    trading_days: int = 252,
) -> float:
    """计算夏普比率。

    公式：(年化收益率 - 无风险利率) / 年化波动率

    Args:
        daily_returns: 日收益率序列。
        risk_free_rate: 年化无风险利率，默认 0.02（2%）。
        trading_days: 年交易日数量，默认 252。

    Returns:
        夏普比率。
    """
    ann_ret = annualized_return(daily_returns, trading_days)
    ann_vol = annualized_volatility(daily_returns, trading_days)

    if ann_vol == 0:
        return float("nan")

    return float((ann_ret - risk_free_rate) / ann_vol)


def sortino_ratio(
    daily_returns: pd.Series,
    risk_free_rate: float = 0.02,
    trading_days: int = 252,
) -> float:
    """计算索提诺比率（仅使用下行波动率）。

    公式：(年化收益率 - 无风险利率) / 下行波动率
    下行波动率：仅统计超额收益为负的日子的标准差，年化处理。

    Args:
        daily_returns: 日收益率序列。
        risk_free_rate: 年化无风险利率，默认 0.02（2%）。
        trading_days: 年交易日数量，默认 252。

    Returns:
        索提诺比率。
    """
    ann_ret = annualized_return(daily_returns, trading_days)

    # 将年化无风险利率转换为日度
    rf_daily = risk_free_rate / trading_days
    excess_daily = daily_returns - rf_daily

    # 仅取超额收益为负的部分计算下行波动率
    downside_returns = excess_daily[excess_daily < 0]

    if len(downside_returns) == 0:
        return float("nan")

    downside_vol = downside_returns.std() * np.sqrt(trading_days)

    if downside_vol == 0:
        return float("nan")

    return float((ann_ret - risk_free_rate) / downside_vol)


def calmar_ratio(daily_returns: pd.Series, trading_days: int = 252) -> float:
    """计算卡玛比率。

    公式：年化收益率 / 最大回撤

    Args:
        daily_returns: 日收益率序列。
        trading_days: 年交易日数量，默认 252。

    Returns:
        卡玛比率。最大回撤为 0 时返回 inf 或 nan（取决于年化收益率符号）。
    """
    ann_ret = annualized_return(daily_returns, trading_days)
    mdd = max_drawdown(daily_returns)

    if mdd == 0:
        if ann_ret > 0:
            return float("inf")
        elif ann_ret < 0:
            return float("-inf")
        else:
            return float("nan")

    return float(ann_ret / mdd)


def information_ratio(
    daily_returns: pd.Series,
    benchmark_returns: pd.Series,
    trading_days: int = 252,
) -> float:
    """计算信息比率。

    公式：年化超额收益（Alpha） / 跟踪误差
    跟踪误差 = std(daily_returns - benchmark_returns) * sqrt(trading_days)
    Alpha = mean(daily_returns - benchmark_returns) * trading_days

    Args:
        daily_returns: 组合日收益率序列。
        benchmark_returns: 基准日收益率序列。
        trading_days: 年交易日数量，默认 252。

    Returns:
        信息比率。
    """
    excess_returns = daily_returns - benchmark_returns
    tracking_error = excess_returns.std() * np.sqrt(trading_days)
    alpha = excess_returns.mean() * trading_days

    if tracking_error == 0:
        return float("nan")

    return float(alpha / tracking_error)


def monthly_win_rate(daily_returns: pd.Series, days_per_month: int = 21) -> float:
    """计算月度胜率（收益为正的月份占比）。

    以每 21 个交易日为一个月份窗口，计算各月份累计收益，
    统计累计收益为正的月份占总月份数的比例。

    Args:
        daily_returns: 日收益率序列。
        days_per_month: 每月交易日数量，默认 21。

    Returns:
        月度胜率（0 到 1 之间的小数）。
    """
    n = len(daily_returns)
    num_months = n // days_per_month

    if num_months == 0:
        # 数据不足一个月，直接判断整段是否盈利
        monthly_return = (1 + daily_returns).prod() - 1
        return 1.0 if monthly_return > 0 else 0.0

    positive_months = 0
    for i in range(num_months):
        start = i * days_per_month
        end = start + days_per_month
        monthly_return = (1 + daily_returns.iloc[start:end]).prod() - 1
        if monthly_return > 0:
            positive_months += 1

    return float(positive_months / num_months)


def compute_all_metrics(
    daily_returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    risk_free_rate: float = 0.02,
    trading_days: int = 252,
) -> dict[str, float]:
    """计算所有绩效指标。

    Args:
        daily_returns: 日收益率序列。
        benchmark_returns: 基准日收益率序列（可选）。提供时额外计算信息比率和 Alpha。
        risk_free_rate: 年化无风险利率，默认 0.02（2%）。
        trading_days: 年交易日数量，默认 252。

    Returns:
        包含所有绩效指标的字典，键为指标名称，值为 float 类型的指标数值。
        基础指标（始终包含）：
            - annualized_return: 年化收益率
            - annualized_volatility: 年化波动率
            - max_drawdown: 最大回撤
            - sharpe_ratio: 夏普比率
            - sortino_ratio: 索提诺比率
            - calmar_ratio: 卡玛比率
            - monthly_win_rate: 月度胜率
        仅在提供 benchmark_returns 时包含：
            - information_ratio: 信息比率
            - alpha: 年化超额收益（Alpha）
    """
    metrics: dict[str, float] = {
        "annualized_return": annualized_return(daily_returns, trading_days),
        "annualized_volatility": annualized_volatility(daily_returns, trading_days),
        "max_drawdown": max_drawdown(daily_returns),
        "sharpe_ratio": sharpe_ratio(daily_returns, risk_free_rate, trading_days),
        "sortino_ratio": sortino_ratio(daily_returns, risk_free_rate, trading_days),
        "calmar_ratio": calmar_ratio(daily_returns, trading_days),
        "monthly_win_rate": monthly_win_rate(daily_returns),
    }

    if benchmark_returns is not None:
        excess_returns = daily_returns - benchmark_returns
        metrics["information_ratio"] = information_ratio(
            daily_returns, benchmark_returns, trading_days
        )
        metrics["alpha"] = float(excess_returns.mean() * trading_days)

    return metrics
