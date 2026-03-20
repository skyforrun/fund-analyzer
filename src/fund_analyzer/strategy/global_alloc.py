"""全球配置策略（GlobalAllocStrategy）。

基于各市场动量评分，对基金进行全球市场配置维度的打分。
市场动量越强，对应市场的基金得分越高（最高 100 分）。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.base import BaseStrategy

# 默认市场指数映射
_DEFAULT_MARKET_INDICES: dict[str, str] = {
    "a_share": "000688",
    "us": "SPX",
}


class GlobalAllocStrategy(BaseStrategy):
    """全球配置策略。

    根据各市场指数的动量（回看期收益率）对基金评分：
    - 动量最强的市场得 100 分，其余按比例线性排名。
    - 若某市场无行情数据，则该市场得 50 分（中性）。
    - 港股 / 全球基金取所有可用市场的平均分。
    - 未知市场的基金沿用 a_share 市场得分。
    - 无基金信息的基金得 50 分（中性）。

    参数
    ----
    repo : FundRepository
        数据访问对象。
    market_indices : dict[str, str] | None
        市场名称到指数代码的映射，默认 {"a_share": "000688", "us": "SPX"}。
    lookback_days : int
        计算动量的回看天数，默认 120 天。
    """

    def __init__(
        self,
        repo: FundRepository,
        market_indices: dict[str, str] | None = None,
        lookback_days: int = 120,
    ) -> None:
        super().__init__(name="GlobalAllocStrategy")
        self._repo = repo
        self._market_indices: dict[str, str] = (
            market_indices if market_indices is not None else dict(_DEFAULT_MARKET_INDICES)
        )
        self._lookback_days = lookback_days

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _market_momentum(self, market: str, as_of: date) -> Optional[float]:
        """计算指定市场在回看期内的收益率。

        参数
        ----
        market : str
            市场名称，必须存在于 self._market_indices 中。
        as_of : date
            评分基准日期。

        返回
        ----
        回看期收益率（浮点数），若无足够数据则返回 None。
        """
        index_code = self._market_indices.get(market)
        if index_code is None:
            return None

        start = as_of - timedelta(days=self._lookback_days)
        quotes = self._repo.get_index_quote(index_code, start, as_of)

        # 至少需要两个数据点才能计算收益率
        if not quotes or len(quotes) < 2:
            return None

        first_close = float(quotes[0].close)
        last_close = float(quotes[-1].close)

        if first_close == 0:
            return None

        return (last_close - first_close) / first_close

    def _market_scores(self, as_of: date) -> dict[str, float]:
        """计算所有市场的评分（基于动量排名）。

        动量最高的市场得 100 分，最低的市场得分与动量成比例。
        若所有市场均无数据，则全部赋予 50 分（中性）。

        参数
        ----
        as_of : date
            评分基准日期。

        返回
        ----
        市场名称到评分（0-100）的字典。
        """
        # 收集各市场的动量数据
        momentums: dict[str, float] = {}
        for market in self._market_indices:
            mom = self._market_momentum(market, as_of)
            if mom is not None:
                momentums[market] = mom

        scores: dict[str, float] = {}

        if not momentums:
            # 所有市场均无数据，赋予中性分 50
            for market in self._market_indices:
                scores[market] = 50.0
            return scores

        if len(momentums) == 1:
            # 只有一个市场有数据，直接给满分 100
            only_market = next(iter(momentums))
            for market in self._market_indices:
                if market in momentums:
                    scores[market] = 100.0
                else:
                    scores[market] = 50.0
            return scores

        # 多个市场：按动量线性排名，最大值 = 100，最小值 = 0
        min_mom = min(momentums.values())
        max_mom = max(momentums.values())
        mom_range = max_mom - min_mom

        for market in self._market_indices:
            if market not in momentums:
                scores[market] = 50.0
            elif mom_range == 0:
                # 所有有数据的市场动量相同，均给 100 分
                scores[market] = 100.0
            else:
                scores[market] = (momentums[market] - min_mom) / mom_range * 100.0

        return scores

    # ------------------------------------------------------------------
    # 公共方法
    # ------------------------------------------------------------------

    def score_batch(
        self,
        fund_codes: list[str],
        as_of: date,
    ) -> dict[str, float]:
        """批量计算基金的全球配置评分。

        参数
        ----
        fund_codes : list[str]
            基金代码列表。
        as_of : date
            评分基准日期。

        返回
        ----
        以基金代码为键、评分（0-100）为值的字典。
        """
        market_scores = self._market_scores(as_of)

        # 所有有数据市场分数的平均值，用于 hk/global 基金
        available_scores = list(market_scores.values())
        avg_score = sum(available_scores) / len(available_scores) if available_scores else 50.0

        # a_share 分数，用于未知市场的基金
        a_share_score = market_scores.get("a_share", 50.0)

        results: dict[str, float] = {}

        for fund_code in fund_codes:
            fund_info = self._repo.get_fund_info(fund_code)

            if fund_info is None:
                results[fund_code] = 50.0
                continue

            market = fund_info.market

            if market in ("hk", "global"):
                results[fund_code] = avg_score
            elif market in market_scores:
                results[fund_code] = market_scores[market]
            else:
                # 未知市场，沿用 a_share 分数
                results[fund_code] = a_share_score

        return results
