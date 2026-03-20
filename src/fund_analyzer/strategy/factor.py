"""因子筛选策略模块。

基于多因子加权评分对基金进行量化评估，支持自定义因子权重。
"""
from __future__ import annotations

import math
from datetime import date, timedelta
from typing import Optional

import pandas as pd

from fund_analyzer.backtest.metrics import (
    annualized_return,
    annualized_volatility,
    max_drawdown,
    sharpe_ratio,
    calmar_ratio,
    sortino_ratio,
)
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.base import BaseStrategy

# 默认因子权重，合计 1.0
_DEFAULT_WEIGHTS: dict[str, float] = {
    "return_1y": 0.10,
    "return_3y": 0.10,
    "max_drawdown": 0.10,
    "volatility": 0.05,
    "sharpe": 0.25,
    "calmar": 0.10,
    "sortino": 0.10,
    "manager_tenure": 0.10,
    "fund_size": 0.10,
}

# 3年近似交易日数
_TRADING_DAYS_3Y = 252 * 3
# 1年近似交易日数
_TRADING_DAYS_1Y = 252
# 最少所需数据点数
_MIN_DATA_POINTS = 60


class FactorStrategy(BaseStrategy):
    """基于多因子加权的基金筛选策略。

    参数
    ----
    repo : FundRepository
        数据访问对象，提供基金信息与净值查询接口。
    weights : dict[str, float] | None
        各因子权重字典，为 None 时使用默认权重。
        权重之和建议为 1.0，否则最终评分会相应缩放。
    """

    def __init__(
        self,
        repo: FundRepository,
        weights: dict[str, float] | None = None,
    ) -> None:
        super().__init__(name="FactorStrategy")
        self._repo = repo
        self._weights = weights if weights is not None else dict(_DEFAULT_WEIGHTS)

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _compute_factors(
        self,
        fund_code: str,
        as_of: date,
    ) -> Optional[dict[str, float]]:
        """计算单只基金的各因子原始值。

        从 repo 获取最近 3 年的净值数据，依据日收益率序列计算所有因子。
        若数据点数不足 60，则返回 None。

        参数
        ----
        fund_code : str
            基金代码。
        as_of : date
            评分基准日期（含）。

        返回
        ----
        因子名称到原始值的字典，或 None（数据不足）。
        """
        start = as_of - timedelta(days=int(_TRADING_DAYS_3Y / 252 * 365) + 30)
        nav_records = self._repo.get_fund_nav(fund_code, start, as_of)

        if len(nav_records) < _MIN_DATA_POINTS:
            return None

        # 构建日收益率序列
        daily_returns = pd.Series(
            [float(r.daily_return) for r in nav_records],
            dtype=float,
        )

        # 全量 3 年数据指标
        ret_3y = annualized_return(daily_returns)
        mdd = max_drawdown(daily_returns)
        vol = annualized_volatility(daily_returns)
        sharpe = sharpe_ratio(daily_returns)
        calmar = calmar_ratio(daily_returns)
        sortino = sortino_ratio(daily_returns)

        # 近 1 年数据指标（取最后 252 个交易日，若不够则全量）
        last_1y = daily_returns.iloc[-_TRADING_DAYS_1Y:] if len(daily_returns) >= _TRADING_DAYS_1Y else daily_returns
        ret_1y = annualized_return(last_1y)

        # 基金信息类因子
        fund_info = self._repo.get_fund_info(fund_code)
        if fund_info is not None and fund_info.fund_size is not None:
            fund_size = float(fund_info.fund_size)
        else:
            fund_size = float("nan")

        if (
            fund_info is not None
            and fund_info.manager_start_date is not None
        ):
            manager_tenure = (as_of - fund_info.manager_start_date).days / 365.25
        else:
            manager_tenure = float("nan")

        return {
            "return_1y": ret_1y,
            "return_3y": ret_3y,
            "max_drawdown": mdd,
            "volatility": vol,
            "sharpe": sharpe,
            "calmar": calmar,
            "sortino": sortino,
            "manager_tenure": manager_tenure,
            "fund_size": fund_size,
        }

    def _factor_to_score(self, name: str, value: float) -> float:
        """将单个因子的原始值映射到 0-100 的评分。

        映射规则：
        - return_1y / return_3y：年化收益越高越好，以 -0.20 到 +0.40 线性映射到 0-100
        - sharpe / calmar / sortino：比率越高越好，以 -1 到 +3 线性映射到 0-100
        - max_drawdown：回撤越低越好，以 0 到 0.60 逆向映射到 0-100
        - volatility：波动率越低越好，以 0 到 0.50 逆向映射到 0-100
        - fund_size：2B-200B 区间得 90 分，过小或过大均降分
        - manager_tenure：3y-10y 区间得 90 分，不足 1 年极低，超过 15 年略降

        参数
        ----
        name : str
            因子名称。
        value : float
            因子原始值。

        返回
        ----
        0-100 之间的分数，NaN 值一律返回 50（中性分数）。
        """
        # NaN 处理：返回中性分数
        if math.isnan(value) or math.isinf(value):
            return 50.0

        if name in ("return_1y", "return_3y"):
            # 年化收益：[-0.20, +0.40] -> [0, 100]
            lo, hi = -0.20, 0.40
            score = (value - lo) / (hi - lo) * 100
            return float(max(0.0, min(100.0, score)))

        if name in ("sharpe", "calmar", "sortino"):
            # 比率类：[-1, +3] -> [0, 100]
            lo, hi = -1.0, 3.0
            score = (value - lo) / (hi - lo) * 100
            return float(max(0.0, min(100.0, score)))

        if name == "max_drawdown":
            # 回撤越低越好：[0, 0.60] -> [100, 0]
            lo, hi = 0.0, 0.60
            score = (1.0 - (value - lo) / (hi - lo)) * 100
            return float(max(0.0, min(100.0, score)))

        if name == "volatility":
            # 波动率越低越好：[0, 0.50] -> [100, 0]
            lo, hi = 0.0, 0.50
            score = (1.0 - (value - lo) / (hi - lo)) * 100
            return float(max(0.0, min(100.0, score)))

        if name == "fund_size":
            # 规模：2B-200B 最优（90分），过小或过大均降分
            # 单位：亿元
            if 2.0 <= value <= 200.0:
                return 90.0
            elif value < 2.0:
                # 规模过小，线性衰减至 0
                return float(max(0.0, value / 2.0 * 90.0))
            else:
                # 规模过大（>200B），超出部分惩罚
                # 200B->90分，500B->50分，1000B以上->10分
                excess = value - 200.0
                penalty = excess / 800.0 * 80.0
                return float(max(10.0, 90.0 - penalty))

        if name == "manager_tenure":
            # 任职年限：3-10年 = 90分
            # <1年极低（20分），1-3年线性增长，10-15年轻微降分，>15年降至70分
            if 3.0 <= value <= 10.0:
                return 90.0
            elif value < 1.0:
                return 20.0
            elif value < 3.0:
                # 1年->20分，3年->90分，线性插值
                return float(20.0 + (value - 1.0) / 2.0 * 70.0)
            elif value <= 15.0:
                # 10年->90分，15年->70分，线性插值
                return float(90.0 - (value - 10.0) / 5.0 * 20.0)
            else:
                return 70.0

        # 未知因子：返回中性分数
        return 50.0

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def score_batch(
        self,
        fund_codes: list[str],
        as_of: date,
    ) -> dict[str, float]:
        """批量计算基金因子加权评分。

        对每只基金：
        1. 调用 _compute_factors 获取原始因子值；
        2. 用 _factor_to_score 将每个因子映射为 0-100 分；
        3. 按权重加权求和得到综合评分（0-100）。

        若某基金数据不足（_compute_factors 返回 None），则评分为 0。

        参数
        ----
        fund_codes : list[str]
            待评分的基金代码列表。
        as_of : date
            评分基准日期。

        返回
        ----
        以基金代码为键、综合评分为值的字典。
        """
        results: dict[str, float] = {}
        for code in fund_codes:
            factors = self._compute_factors(code, as_of)
            if factors is None:
                results[code] = 0.0
                continue

            total_score = 0.0
            for factor_name, weight in self._weights.items():
                raw_value = factors.get(factor_name, float("nan"))
                factor_score = self._factor_to_score(factor_name, raw_value)
                total_score += factor_score * weight

            results[code] = float(max(0.0, min(100.0, total_score)))

        return results
