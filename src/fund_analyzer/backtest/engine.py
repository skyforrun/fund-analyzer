"""回测引擎（BacktestEngine）。

基于历史数据对核心-卫星策略进行回测，支持自定义初始资金、仓位比例、
调仓频率、手续费等参数，输出完整绩效指标。
"""
from __future__ import annotations

from datetime import date
from dateutil.relativedelta import relativedelta

import numpy as np
import pandas as pd

from fund_analyzer.backtest.metrics import compute_all_metrics


class BacktestEngine:
    """核心-卫星策略回测引擎。

    参数
    ----
    repo
        FundRepository 实例，提供基金净值和指数行情数据。
    composite
        CompositeStrategy 实例，提供基金推荐功能。
    initial_capital : float
        初始资金，默认 100_000 元。
    core_ratio : float
        核心仓位占总资金的比例，默认 0.3。
    satellite_ratio : float
        卫星仓位占总资金的比例，默认 0.7。
    core_top_n : int
        核心仓位推荐基金数量，默认 3。
    satellite_top_n : int
        卫星仓位推荐基金数量，默认 7。
    buy_fee : float
        买入手续费率，默认 0.0015（0.15%）。
    sell_fee : float
        卖出手续费率，默认 0.005（0.5%）。
    core_rebalance_months : int
        核心仓位调仓间隔月数，默认 3。
    satellite_rebalance_months : int
        卫星仓位调仓间隔月数，默认 1。
    """

    def __init__(
        self,
        repo,
        composite,
        initial_capital: float = 100_000,
        core_ratio: float = 0.3,
        satellite_ratio: float = 0.7,
        core_top_n: int = 3,
        satellite_top_n: int = 7,
        buy_fee: float = 0.0015,
        sell_fee: float = 0.005,
        core_rebalance_months: int = 3,
        satellite_rebalance_months: int = 1,
    ) -> None:
        self._repo = repo
        self._composite = composite
        self.initial_capital = initial_capital
        self.core_ratio = core_ratio
        self.satellite_ratio = satellite_ratio
        self.core_top_n = core_top_n
        self.satellite_top_n = satellite_top_n
        self.buy_fee = buy_fee
        self.sell_fee = sell_fee
        self.core_rebalance_months = core_rebalance_months
        self.satellite_rebalance_months = satellite_rebalance_months

    # ------------------------------------------------------------------
    # 私有辅助方法
    # ------------------------------------------------------------------

    def _get_rebalance_dates(self, start: date, end: date, months: int) -> list[date]:
        """生成调仓日期列表。

        从 start 开始，每隔 months 个月生成一个调仓日期，直到不超过 end 为止。

        参数
        ----
        start : date
            起始日期（包含在结果中）。
        end : date
            结束日期（包含在结果中，若恰好落在该日期）。
        months : int
            调仓间隔月数。

        返回
        ----
        调仓日期列表（含 start，不超过 end）。
        """
        dates: list[date] = []
        current = start
        while current <= end:
            dates.append(current)
            current = current + relativedelta(months=months)
        return dates

    def _get_sell_fee_rate(self, fund_code: str, holding_days: int) -> float:
        """获取卖出费率，优先查数据库，无数据时使用默认值。"""
        rate = self._repo.get_fee_rate(fund_code, "redemption", holding_days=holding_days)
        if rate is not None:
            return float(rate)
        return self.sell_fee

    def _get_buy_fee_rate(self, fund_code: str, amount: float) -> float:
        """获取买入费率，优先查数据库，无数据时使用默认值。"""
        rate = self._repo.get_fee_rate(fund_code, "purchase", amount=amount)
        if rate is not None:
            return float(rate)
        return self.buy_fee

    def _get_daily_return(self, fund_code: str, d: date) -> float:
        """获取指定基金在某日的日收益率。

        参数
        ----
        fund_code : str
            基金代码。
        d : date
            目标日期。

        返回
        ----
        日收益率（小数形式）。若无数据则返回 0.0。
        """
        records = self._repo.get_fund_nav(fund_code, d, d)
        if not records:
            return 0.0
        record = records[0]
        daily_ret = getattr(record, "daily_return", None)
        if daily_ret is None:
            return 0.0
        return float(daily_ret)

    # ------------------------------------------------------------------
    # 核心回测方法
    # ------------------------------------------------------------------

    def run(
        self,
        fund_universe: list[str],
        start: date,
        end: date,
        benchmark_code: str = "000688",
    ) -> dict:
        """执行回测。

        回测流程：
        1. 从 repo 获取基准指数的交易日历和日收益率序列。
        2. 在核心调仓日：卖出全部核心持仓（扣除卖出手续费），
           调用 composite.recommend 获取新核心持仓，等权买入（扣除买入手续费）。
        3. 在卫星调仓日：卖出全部卫星持仓（扣除卖出手续费），
           调用 composite.recommend 获取新卫星持仓，按评分加权买入（扣除买入手续费）。
        4. 每日对所有持仓应用日收益率，更新持仓市值。
        5. 计算组合每日收益率序列，与基准对齐后调用 compute_all_metrics。

        参数
        ----
        fund_universe : list[str]
            候选基金代码列表。
        start : date
            回测起始日期。
        end : date
            回测结束日期。
        benchmark_code : str
            基准指数代码，默认 "000688"（科创板 50）。

        返回
        ----
        dict，包含以下键：
            - portfolio_returns: pd.Series，组合日收益率序列（以日期为索引）
            - benchmark_returns: pd.Series，基准日收益率序列（对齐后）
            - portfolio_values: pd.Series，组合每日总市值序列
            - metrics: dict，compute_all_metrics 返回的绩效指标字典
            - total_fees_paid: float，回测期间累计手续费
            - final_value: float，回测结束时的组合总市值
            - initial_capital: float，初始资金
        """
        # 1. 获取基准行情
        benchmark_quotes = self._repo.get_index_quote(benchmark_code, start, end)
        if not benchmark_quotes:
            raise ValueError(
                f"未能获取基准指数 {benchmark_code} 在 {start}~{end} 的行情数据"
            )

        # 构建基准日收益率 Series（以 date 为索引）
        benchmark_dates = [q.date for q in benchmark_quotes]
        benchmark_daily_returns = pd.Series(
            [float(q.daily_return) for q in benchmark_quotes],
            index=benchmark_dates,
            dtype=float,
        )

        # 2. 生成调仓日期
        core_rebalance_dates = set(
            self._get_rebalance_dates(start, end, self.core_rebalance_months)
        )
        satellite_rebalance_dates = set(
            self._get_rebalance_dates(start, end, self.satellite_rebalance_months)
        )

        # 3. 初始化持仓和资金追踪
        # holdings 格式：{fund_code: [current_value, buy_date]}
        core_holdings: dict[str, list] = {}
        sat_holdings: dict[str, list] = {}
        total_fees_paid: float = 0.0

        # 初始分配资金
        core_capital = self.initial_capital * self.core_ratio
        sat_capital = self.initial_capital * self.satellite_ratio

        portfolio_values: list[float] = []
        portfolio_returns_list: list[float] = []
        portfolio_dates: list[date] = []

        # 4. 逐日模拟
        prev_total_value = self.initial_capital

        for q in benchmark_quotes:
            d = q.date

            # ---- 核心仓位调仓 ----
            if d in core_rebalance_dates:
                # 卖出所有核心持仓
                sell_proceeds = 0.0
                for fund_code, holding in core_holdings.items():
                    value, buy_date = holding[0], holding[1]
                    holding_days = (d - buy_date).days
                    fee_rate = self._get_sell_fee_rate(fund_code, holding_days)
                    fee = value * fee_rate
                    total_fees_paid += fee
                    sell_proceeds += value - fee
                core_holdings = {}

                # 若之前没有持仓（首次建仓），直接使用分配给核心的资金
                if sell_proceeds == 0.0:
                    sell_proceeds = core_capital

                # 获取新核心标的
                core_picks, _ = self._composite.recommend(
                    fund_universe, d,
                    core_top_n=self.core_top_n,
                    satellite_top_n=self.satellite_top_n,
                )

                # 等权买入
                if core_picks:
                    per_fund_capital = sell_proceeds / len(core_picks)
                    for fund_code, _score in core_picks:
                        fee_rate = self._get_buy_fee_rate(fund_code, per_fund_capital)
                        fee = per_fund_capital * fee_rate
                        total_fees_paid += fee
                        core_holdings[fund_code] = [per_fund_capital - fee, d]
                else:
                    # 无推荐标的，资金暂存（不买入）
                    core_capital = sell_proceeds

            # ---- 卫星仓位调仓 ----
            if d in satellite_rebalance_dates:
                # 卖出所有卫星持仓
                sell_proceeds = 0.0
                for fund_code, holding in sat_holdings.items():
                    value, buy_date = holding[0], holding[1]
                    holding_days = (d - buy_date).days
                    fee_rate = self._get_sell_fee_rate(fund_code, holding_days)
                    fee = value * fee_rate
                    total_fees_paid += fee
                    sell_proceeds += value - fee
                sat_holdings = {}

                if sell_proceeds == 0.0:
                    sell_proceeds = sat_capital

                # 获取新卫星标的
                _, sat_picks = self._composite.recommend(
                    fund_universe, d,
                    core_top_n=self.core_top_n,
                    satellite_top_n=self.satellite_top_n,
                )

                # 按评分加权买入
                if sat_picks:
                    total_score = sum(score for _, score in sat_picks)
                    if total_score <= 0:
                        # 均匀分配
                        weights = [1.0 / len(sat_picks)] * len(sat_picks)
                    else:
                        weights = [score / total_score for _, score in sat_picks]

                    for (fund_code, _score), weight in zip(sat_picks, weights):
                        alloc = sell_proceeds * weight
                        fee_rate = self._get_buy_fee_rate(fund_code, alloc)
                        fee = alloc * fee_rate
                        total_fees_paid += fee
                        sat_holdings[fund_code] = [alloc - fee, d]
                else:
                    sat_capital = sell_proceeds

            # ---- 每日更新持仓市值 ----
            for fund_code in list(core_holdings.keys()):
                daily_ret = self._get_daily_return(fund_code, d)
                core_holdings[fund_code][0] *= (1 + daily_ret)

            for fund_code in list(sat_holdings.keys()):
                daily_ret = self._get_daily_return(fund_code, d)
                sat_holdings[fund_code][0] *= (1 + daily_ret)

            # ---- 计算当日总净值 ----
            # 未投资部分：初始资金减去已实际投入的部分
            core_invested = sum(h[0] for h in core_holdings.values())
            sat_invested = sum(h[0] for h in sat_holdings.values())

            # 未投入的现金（首次调仓前或无推荐时）
            uninvested_core = core_capital if not core_holdings else 0.0
            uninvested_sat = sat_capital if not sat_holdings else 0.0

            total_value = core_invested + sat_invested + uninvested_core + uninvested_sat

            # 计算当日组合收益率
            if prev_total_value > 0:
                daily_portfolio_return = (total_value - prev_total_value) / prev_total_value
            else:
                daily_portfolio_return = 0.0

            portfolio_values.append(total_value)
            portfolio_returns_list.append(daily_portfolio_return)
            portfolio_dates.append(d)

            prev_total_value = total_value

        # 5. 构建结果 Series
        portfolio_returns = pd.Series(
            portfolio_returns_list, index=portfolio_dates, dtype=float
        )
        portfolio_values_series = pd.Series(
            portfolio_values, index=portfolio_dates, dtype=float
        )

        # 与基准对齐（取共同日期）
        common_dates = portfolio_returns.index.intersection(benchmark_daily_returns.index)
        aligned_portfolio = portfolio_returns.loc[common_dates]
        aligned_benchmark = benchmark_daily_returns.loc[common_dates]

        # 6. 计算绩效指标
        metrics = compute_all_metrics(
            aligned_portfolio,
            benchmark_returns=aligned_benchmark,
        )

        final_value = portfolio_values[-1] if portfolio_values else self.initial_capital

        return {
            "portfolio_returns": aligned_portfolio,
            "benchmark_returns": aligned_benchmark,
            "portfolio_values": portfolio_values_series,
            "metrics": metrics,
            "total_fees_paid": total_fees_paid,
            "final_value": final_value,
            "initial_capital": self.initial_capital,
        }
