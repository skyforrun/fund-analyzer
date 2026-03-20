"""调仓建议模块（RebalanceAdvisor）。

根据当前持仓与策略最新推荐结果，生成买入/卖出的调仓行动列表。
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.composite import CompositeStrategy


class RebalanceAdvisor:
    """调仓建议生成器。

    对比当前持仓与策略最新推荐，输出需要买入或卖出的调仓行动。

    参数
    ----
    repo : FundRepository
        数据访问仓储，用于查询当前持仓。
    composite : CompositeStrategy
        综合评分策略，用于生成最新推荐列表。
    core_top_n : int
        核心仓位推荐数量，默认 3。
    satellite_top_n : int
        卫星仓位推荐数量，默认 7。
    """

    def __init__(
        self,
        repo: FundRepository,
        composite: CompositeStrategy,
        core_top_n: int = 3,
        satellite_top_n: int = 7,
    ) -> None:
        self._repo = repo
        self._composite = composite
        self._core_top_n = core_top_n
        self._satellite_top_n = satellite_top_n

    def generate(
        self,
        fund_universe: list[str],
        as_of: Optional[date] = None,
    ) -> dict:
        """生成调仓建议。

        步骤：
        1. 从 repo 获取当前所有持仓（status='holding'）。
        2. 调用 composite.recommend() 得到最新核心/卫星推荐列表。
        3. 比较当前持仓与新推荐：
           - 核心持仓中不在新核心推荐里的 → sell 行动
           - 新核心推荐中不在当前核心持仓里的 → buy 行动
           - 卫星持仓中不在新卫星推荐里的 → sell 行动
           - 新卫星推荐中不在当前卫星持仓里的 → buy 行动

        参数
        ----
        fund_universe : list[str]
            候选基金代码列表，传入 composite.recommend()。
        as_of : date, optional
            调仓基准日期，为 None 时使用今日日期。

        返回
        ----
        dict，包含以下键：
            - as_of : date
            - actions : list[dict]，每个元素含 fund_code、position_type、action、reason
            - core_picks : list[tuple[str, float]]
            - satellite_picks : list[tuple[str, float]]
        """
        if as_of is None:
            as_of = date.today()

        # 1. 获取当前持仓，按 position_type 分组
        active_positions = self._repo.get_active_positions()
        current_core: set[str] = set()
        current_satellite: set[str] = set()
        for pos in active_positions:
            pos_type = getattr(pos, "position_type", None)
            fund_code = getattr(pos, "fund_code", None)
            if fund_code is None:
                continue
            if pos_type == "core":
                current_core.add(fund_code)
            else:
                current_satellite.add(fund_code)

        # 2. 获取新推荐列表
        core_picks, satellite_picks = self._composite.recommend(
            fund_universe,
            as_of,
            core_top_n=self._core_top_n,
            satellite_top_n=self._satellite_top_n,
        )
        new_core: set[str] = {code for code, _ in core_picks}
        new_satellite: set[str] = {code for code, _ in satellite_picks}

        actions: list[dict] = []

        # 3. 核心仓位调仓行动
        # 3a. 当前核心持仓中不在新推荐里的 → sell
        for fund_code in current_core - new_core:
            signal = self._composite.signal(fund_code, as_of, position_type="core")
            actions.append(
                {
                    "fund_code": fund_code,
                    "position_type": "core",
                    "action": "sell",
                    "reason": signal.reason,
                }
            )

        # 3b. 新核心推荐中不在当前持仓里的 → buy
        for fund_code in new_core - current_core:
            signal = self._composite.signal(fund_code, as_of, position_type="core")
            actions.append(
                {
                    "fund_code": fund_code,
                    "position_type": "core",
                    "action": "buy",
                    "reason": signal.reason,
                }
            )

        # 4. 卫星仓位调仓行动
        # 4a. 当前卫星持仓中不在新推荐里的 → sell
        for fund_code in current_satellite - new_satellite:
            signal = self._composite.signal(fund_code, as_of, position_type="satellite")
            actions.append(
                {
                    "fund_code": fund_code,
                    "position_type": "satellite",
                    "action": "sell",
                    "reason": signal.reason,
                }
            )

        # 4b. 新卫星推荐中不在当前持仓里的 → buy
        for fund_code in new_satellite - current_satellite:
            signal = self._composite.signal(fund_code, as_of, position_type="satellite")
            actions.append(
                {
                    "fund_code": fund_code,
                    "position_type": "satellite",
                    "action": "buy",
                    "reason": signal.reason,
                }
            )

        return {
            "as_of": as_of,
            "actions": actions,
            "core_picks": core_picks,
            "satellite_picks": satellite_picks,
        }
