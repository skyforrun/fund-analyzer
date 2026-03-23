"""动量策略（MomentumStrategy）实现。

基于多时间窗口的加权动量评分，并对反转风险进行惩罚。
最终评分通过批量内相对排名（百分位，0-100）归一化。
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """动量策略：基于多时间窗口加权动量进行基金评分。

    评分流程
    --------
    1. 对每只基金计算多个时间窗口的动量（收益率）。
    2. 加权汇总各窗口动量得到综合动量分数。
    3. 检测短期反转风险，若触发则对该基金加权动量乘以 0.7 惩罚。
    4. 在批次内对加权动量进行相对排名（百分位 0-100），
       无效数据（数据不足）的基金评分为 0。

    参数
    ----
    repo : FundRepository
        数据访问对象。
    windows : list[int] | None
        动量计算时间窗口（交易日数），默认 [20, 60, 120]。
    window_weights : list[float] | None
        各窗口权重，须与 windows 等长且总和为 1，默认 [0.4, 0.35, 0.25]。
    """

    def __init__(
        self,
        repo: FundRepository,
        windows: list[int] | None = None,
        window_weights: list[float] | None = None,
    ) -> None:
        super().__init__(name="MomentumStrategy")
        self._repo = repo
        self.windows: list[int] = windows if windows is not None else [20, 60, 120]
        self.window_weights: list[float] = (
            window_weights if window_weights is not None else [0.4, 0.35, 0.25]
        )

    # ------------------------------------------------------------------
    # 私有方法
    # ------------------------------------------------------------------

    def _compute_momentum(
        self,
        fund_code: str,
        as_of: date,
    ) -> Optional[dict]:
        """计算指定基金在 as_of 日期的动量指标。

        参数
        ----
        fund_code : str
            基金代码。
        as_of : date
            评分基准日期。

        返回
        ----
        包含动量指标的字典，数据不足时返回 None。字典键：
        - ``weighted_momentum``: 加权综合动量
        - ``reversal_risk``: 反转风险标记（0.0 或 1.0）
        - 各窗口动量：``momentum_{window}``
        """
        max_window = max(self.windows)
        # 获取 max_window * 1.5 天内的历史数据
        lookback_days = int(max_window * 1.5)
        start = as_of - timedelta(days=lookback_days)

        nav_records = self._repo.get_fund_nav(fund_code, start, as_of)

        if len(nav_records) < 20:
            return None

        acc_navs = [r.acc_nav if r.acc_nav is not None else r.nav for r in nav_records]
        n = len(acc_navs)

        # 计算各窗口动量
        window_momentums: list[float] = []
        momentum_detail: dict[str, float] = {}

        for window in self.windows:
            if n > window:
                mom = acc_navs[-1] / acc_navs[-window - 1] - 1
            elif n >= 2:
                # 数据不够覆盖窗口，使用全部可用数据
                mom = acc_navs[-1] / acc_navs[0] - 1
            else:
                mom = 0.0
            window_momentums.append(mom)
            momentum_detail[f"momentum_{window}"] = mom

        # 加权综合动量
        weighted_momentum = sum(
            w * m for w, m in zip(self.window_weights, window_momentums)
        )

        # 反转风险检测：中期动量（20日）> 5% 且短期动量（5日）< -3%
        reversal_risk = 0.0
        if n > 20:
            mid_mom = acc_navs[-1] / acc_navs[-21] - 1
        else:
            mid_mom = 0.0

        if n > 5:
            short_mom = acc_navs[-1] / acc_navs[-6] - 1
        else:
            short_mom = 0.0

        if mid_mom > 0.05 and short_mom < -0.03:
            reversal_risk = 1.0

        return {
            "weighted_momentum": weighted_momentum,
            "reversal_risk": reversal_risk,
            **momentum_detail,
        }

    # ------------------------------------------------------------------
    # 公开方法
    # ------------------------------------------------------------------

    def score_batch(
        self,
        fund_codes: list[str],
        as_of: date,
    ) -> dict[str, float]:
        """批量计算基金动量评分（相对排名，0-100）。

        参数
        ----
        fund_codes : list[str]
            待评分的基金代码列表。
        as_of : date
            评分基准日期。

        返回
        ----
        以基金代码为键、评分（0-100）为值的字典。
        数据不足的基金评分为 0。
        """
        if not fund_codes:
            return {}

        # 第一步：计算各基金的加权动量（应用反转惩罚）
        raw_scores: dict[str, Optional[float]] = {}
        for code in fund_codes:
            result = self._compute_momentum(code, as_of)
            if result is None:
                raw_scores[code] = None
            else:
                wm = result["weighted_momentum"]
                if result["reversal_risk"] == 1.0:
                    wm *= 0.7
                raw_scores[code] = wm

        # 第二步：筛选有效数据，进行相对排名（百分位，0-100）
        valid_codes = [c for c, v in raw_scores.items() if v is not None]
        valid_values = [raw_scores[c] for c in valid_codes]  # type: ignore[misc]

        final_scores: dict[str, float] = {c: 0.0 for c in fund_codes}

        n_valid = len(valid_codes)
        if n_valid == 0:
            return final_scores

        if n_valid == 1:
            # 只有一只基金有数据时，直接给 100 分
            final_scores[valid_codes[0]] = 100.0
            return final_scores

        # 按加权动量升序排序，计算百分位
        sorted_pairs = sorted(zip(valid_values, valid_codes))
        for rank, (_, code) in enumerate(sorted_pairs):
            # 百分位：rank / (n_valid - 1) * 100，最低 0，最高 100
            percentile = rank / (n_valid - 1) * 100.0
            final_scores[code] = percentile

        return final_scores
