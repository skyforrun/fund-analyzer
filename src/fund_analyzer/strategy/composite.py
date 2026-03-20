"""综合评分策略（CompositeStrategy）。

将多个子策略的评分按权重加权合并，支持核心仓位与卫星仓位分别配置权重，
并提供买入/卖出信号及基金推荐功能。
"""
from __future__ import annotations

from datetime import date

from fund_analyzer.strategy.base import BaseStrategy, Signal, score_to_signal


class CompositeStrategy:
    """综合评分策略协调器。

    本类不继承 BaseStrategy，而是作为多个子策略的调度器，
    将不同策略的评分按权重合并，输出综合信号与推荐结果。

    参数
    ----
    strategies : dict[str, BaseStrategy]
        策略名称到策略实例的映射，键名须与 core_weights / satellite_weights 中的键一致。
    core_weights : dict[str, float]
        核心仓位评分所用的策略权重，键为策略名称，值为权重（无需归一化）。
    satellite_weights : dict[str, float]
        卫星仓位评分所用的策略权重，键为策略名称，值为权重（无需归一化）。
    buy_threshold : float
        买入阈值，默认 80。
    sell_threshold : float
        卖出阈值，默认 60。
    """

    def __init__(
        self,
        strategies: dict[str, BaseStrategy],
        core_weights: dict[str, float],
        satellite_weights: dict[str, float],
        buy_threshold: float = 80,
        sell_threshold: float = 60,
    ) -> None:
        self._strategies = strategies
        self._core_weights = core_weights
        self._satellite_weights = satellite_weights
        self._buy_threshold = buy_threshold
        self._sell_threshold = sell_threshold

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _weighted_score(
        self,
        fund_codes: list[str],
        as_of: date,
        weights: dict[str, float],
    ) -> dict[str, float]:
        """对给定基金列表按权重字典计算加权平均评分。

        对 weights 中的每个策略名称，调用对应策略的 score_batch，
        再将各策略得分按权重加权求和后除以总权重。

        参数
        ----
        fund_codes : list[str]
            待评分的基金代码列表。
        as_of : date
            评分基准日期。
        weights : dict[str, float]
            策略名称到权重的映射。

        返回
        ----
        以基金代码为键、加权平均评分为值的字典。
        """
        total_weight = sum(weights.values())
        if total_weight == 0:
            return {code: 0.0 for code in fund_codes}

        # 累加加权分数
        accumulated: dict[str, float] = {code: 0.0 for code in fund_codes}
        for strategy_name, weight in weights.items():
            strategy = self._strategies[strategy_name]
            scores = strategy.score_batch(fund_codes, as_of)
            for code in fund_codes:
                accumulated[code] += scores.get(code, 0.0) * weight

        return {code: accumulated[code] / total_weight for code in fund_codes}

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def score_core(
        self,
        fund_codes: list[str],
        as_of: date,
    ) -> dict[str, float]:
        """使用核心仓位权重对基金批量评分。

        参数
        ----
        fund_codes : list[str]
            待评分的基金代码列表。
        as_of : date
            评分基准日期。

        返回
        ----
        以基金代码为键、核心仓位加权评分为值的字典。
        """
        return self._weighted_score(fund_codes, as_of, self._core_weights)

    def score_satellite(
        self,
        fund_codes: list[str],
        as_of: date,
    ) -> dict[str, float]:
        """使用卫星仓位权重对基金批量评分。

        参数
        ----
        fund_codes : list[str]
            待评分的基金代码列表。
        as_of : date
            评分基准日期。

        返回
        ----
        以基金代码为键、卫星仓位加权评分为值的字典。
        """
        return self._weighted_score(fund_codes, as_of, self._satellite_weights)

    def signal(
        self,
        fund_code: str,
        as_of: date,
        position_type: str = "satellite",
    ) -> Signal:
        """生成单只基金的交易信号。

        根据 position_type 选择核心或卫星权重评分，再通过 score_to_signal 转换为信号。

        参数
        ----
        fund_code : str
            基金代码。
        as_of : date
            信号基准日期。
        position_type : str
            仓位类型，"core" 使用核心权重，其他值使用卫星权重。

        返回
        ----
        Signal 实例。
        """
        if position_type == "core":
            scores = self.score_core([fund_code], as_of)
        else:
            scores = self.score_satellite([fund_code], as_of)

        score = scores[fund_code]
        return score_to_signal(score, self._buy_threshold, self._sell_threshold)

    def recommend(
        self,
        fund_codes: list[str],
        as_of: date,
        core_top_n: int = 3,
        satellite_top_n: int = 7,
    ) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
        """推荐核心仓位与卫星仓位基金。

        分别用核心权重和卫星权重对所有基金评分，按评分降序排列后各取前 N 只。

        参数
        ----
        fund_codes : list[str]
            候选基金代码列表。
        as_of : date
            评分基准日期。
        core_top_n : int
            核心仓位推荐数量，默认 3。
        satellite_top_n : int
            卫星仓位推荐数量，默认 7。

        返回
        ----
        (core_picks, satellite_picks) 元组，各为按评分降序排列的 (code, score) 列表。
        """
        core_scores = self.score_core(fund_codes, as_of)
        satellite_scores = self.score_satellite(fund_codes, as_of)

        core_picks = sorted(
            core_scores.items(), key=lambda x: x[1], reverse=True
        )[:core_top_n]

        satellite_picks = sorted(
            satellite_scores.items(), key=lambda x: x[1], reverse=True
        )[:satellite_top_n]

        return list(core_picks), list(satellite_picks)
