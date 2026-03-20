"""行业轮动策略（RotationStrategy）。

策略逻辑：
1. 计算各行业指数在 momentum_window 天内的动量（涨跌幅）。
2. 对行业动量进行排名，最强的行业得分为 100，最弱的为 0（线性映射）。
3. 对每只基金，根据最新报告期持仓按权重加权平均各持仓股票所属行业的排名，
   得到该基金的最终评分（0-100）。
4. 无持仓的基金评分为 0。
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.base import BaseStrategy

# 默认行业指数映射：行业名称 -> 指数代码
DEFAULT_INDUSTRY_INDICES: dict[str, str] = {
    "电子": "399673",
    "医药生物": "399913",
    "食品饮料": "399932",
    "计算机": "399671",
    "银行": "399986",
    "非银金融": "399975",
    "有色金属": "399395",
    "汽车": "399974",
    "机械设备": "399961",
    "化工": "399963",
}

# 季末月份
_QUARTER_END_MONTHS = {3, 6, 9, 12}


class RotationStrategy(BaseStrategy):
    """基于行业动量轮动的基金评分策略。

    Parameters
    ----------
    repo : FundRepository
        数据访问仓储。
    industry_indices : dict[str, str] | None
        行业名称到指数代码的映射，为 None 时使用内置默认映射。
    momentum_window : int
        计算动量所用的历史天数（交易日历窗口），默认 60 天。
    """

    def __init__(
        self,
        repo: FundRepository,
        industry_indices: dict[str, str] | None = None,
        momentum_window: int = 60,
    ) -> None:
        super().__init__(name="RotationStrategy")
        self._repo = repo
        self._industry_indices: dict[str, str] = (
            industry_indices if industry_indices is not None else DEFAULT_INDUSTRY_INDICES
        )
        self._momentum_window = momentum_window

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _get_industry_momentum(
        self,
        industry: str,
        as_of: date,
    ) -> Optional[float]:
        """计算指定行业在 as_of 日期前 momentum_window 天的动量（涨跌幅）。

        Parameters
        ----------
        industry : str
            行业名称，须在 industry_indices 映射中存在。
        as_of : date
            计算基准日期（含）。

        Returns
        -------
        float | None
            动量值（例如 0.15 表示涨 15%）；数据不足时返回 None。
        """
        index_code = self._industry_indices.get(industry)
        if index_code is None:
            return None

        start = as_of - timedelta(days=self._momentum_window)
        quotes = self._repo.get_index_quote(index_code, start, as_of)

        if len(quotes) < 2:
            return None

        # 使用窗口内最早与最晚收盘价计算涨跌幅
        first_close = quotes[0].close
        last_close = quotes[-1].close

        if first_close is None or last_close is None or first_close == 0:
            return None

        return float((last_close - first_close) / first_close)

    def _get_latest_report_date(self, as_of: date) -> date:
        """返回 as_of 日期前至少 30 天的最近季末日期。

        季末日期为每年的 3/31、6/30、9/30、12/31。

        Parameters
        ----------
        as_of : date
            基准日期。

        Returns
        -------
        date
            符合条件的最近季末日期。
        """
        # 候选季末日期：向前最多搜索 6 个季度确保能找到
        cutoff = as_of - timedelta(days=30)

        # 生成过去若干个季末日期并取最近满足条件的
        year = cutoff.year
        # 检查从当前年份到两年前的所有季末
        candidates: list[date] = []
        for y in range(year - 1, year + 1):
            for m, d_val in [(3, 31), (6, 30), (9, 30), (12, 31)]:
                candidates.append(date(y, m, d_val))

        # 筛选 <= cutoff 的季末，取最大值
        valid = [c for c in candidates if c <= cutoff]
        return max(valid)

    # ------------------------------------------------------------------
    # 公有方法
    # ------------------------------------------------------------------

    def score_batch(
        self,
        fund_codes: list[str],
        as_of: date,
    ) -> dict[str, float]:
        """批量计算基金行业轮动评分。

        Parameters
        ----------
        fund_codes : list[str]
            基金代码列表。
        as_of : date
            评分基准日期。

        Returns
        -------
        dict[str, float]
            以基金代码为键、评分（0-100）为值的字典。无持仓基金评分为 0。
        """
        # 1. 计算所有行业的动量
        momentum: dict[str, float] = {}
        for industry in self._industry_indices:
            m = self._get_industry_momentum(industry, as_of)
            if m is not None:
                momentum[industry] = m

        # 2. 对行业动量进行排名，映射到 0-100
        #    动量最高的行业排名为 100，最低的为 0（线性归一化）
        industry_rank: dict[str, float] = {}
        if momentum:
            n = len(momentum)
            if n == 1:
                # 只有一个行业时直接给 100
                for industry in momentum:
                    industry_rank[industry] = 100.0
            else:
                min_m = min(momentum.values())
                max_m = max(momentum.values())
                span = max_m - min_m
                for industry, m_val in momentum.items():
                    if span == 0:
                        industry_rank[industry] = 100.0
                    else:
                        industry_rank[industry] = (m_val - min_m) / span * 100.0

        # 3. 获取最新报告期
        report_date = self._get_latest_report_date(as_of)

        # 4. 为每只基金计算加权平均行业排名
        result: dict[str, float] = {}
        for fund_code in fund_codes:
            holdings = self._repo.get_fund_holdings(fund_code, report_date)

            if not holdings:
                result[fund_code] = 0.0
                continue

            total_weight = Decimal("0")
            weighted_rank = Decimal("0")

            for holding in holdings:
                if holding.industry is None or holding.weight is None:
                    continue
                rank = industry_rank.get(holding.industry)
                if rank is None:
                    # 行业未在映射中，动量未知，贡献 0 分
                    rank = 0.0
                weighted_rank += holding.weight * Decimal(str(rank))
                total_weight += holding.weight

            if total_weight == 0:
                result[fund_code] = 0.0
            else:
                score = float(weighted_rank / total_weight)
                # 确保评分在 0-100 范围内
                result[fund_code] = max(0.0, min(100.0, score))

        return result
