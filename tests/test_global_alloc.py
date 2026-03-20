"""GlobalAllocStrategy 单元测试。

使用 mock repo 隔离数据库依赖，验证：
1. 基本评分逻辑（score_batch 返回合法评分）
2. 美股行情强势时，美股基金评分高于 A 股基金
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from fund_analyzer.strategy.global_alloc import GlobalAllocStrategy


# ---------------------------------------------------------------------------
# 辅助工厂函数
# ---------------------------------------------------------------------------

def _make_quotes(base_close: float, increment: float, count: int) -> list[MagicMock]:
    """生成 count 条模拟行情记录，close 从 base_close 开始按 increment 递增。"""
    quotes = []
    for i in range(count):
        q = MagicMock()
        q.close = base_close + increment * i
        quotes.append(q)
    return quotes


def _make_fund_info(market: str) -> MagicMock:
    """生成带指定 market 属性的模拟 FundInfo 对象。"""
    info = MagicMock()
    info.market = market
    return info


def _make_repo(
    *,
    a_share_base: float = 1000.0,
    a_share_increment: float = 1.0,
    us_base: float = 4000.0,
    us_increment: float = 1.0,
    fund_markets: dict[str, str] | None = None,
    quote_count: int = 10,
) -> MagicMock:
    """构造模拟 FundRepository。

    参数
    ----
    a_share_base : float
        A 股指数起始收盘价。
    a_share_increment : float
        A 股指数每条记录的收盘价增量。
    us_base : float
        美股指数起始收盘价。
    us_increment : float
        美股指数每条记录的收盘价增量。
    fund_markets : dict[str, str]
        基金代码 → 市场映射，不在此字典中的基金返回 None。
    quote_count : int
        每个指数生成的行情条数。
    """
    fund_markets = fund_markets or {}

    a_share_quotes = _make_quotes(a_share_base, a_share_increment, quote_count)
    us_quotes = _make_quotes(us_base, us_increment, quote_count)

    def _get_index_quote(index_code: str, start: date, end: date) -> list[MagicMock]:
        if index_code == "000688":
            return a_share_quotes
        if index_code == "SPX":
            return us_quotes
        return []

    def _get_fund_info(fund_code: str):
        market = fund_markets.get(fund_code)
        if market is None:
            return None
        return _make_fund_info(market)

    repo = MagicMock()
    repo.get_index_quote.side_effect = _get_index_quote
    repo.get_fund_info.side_effect = _get_fund_info
    return repo


# ---------------------------------------------------------------------------
# TestScoreBatch — 基本评分逻辑
# ---------------------------------------------------------------------------


class TestScoreBatch:
    """验证 score_batch 返回值合法，且结构正确。"""

    def test_returns_dict_with_all_fund_codes(self):
        """score_batch 应为每只基金返回一个评分。"""
        repo = _make_repo(
            fund_markets={"110020": "a_share", "000001": "us"},
        )
        strategy = GlobalAllocStrategy(repo=repo)
        scores = strategy.score_batch(["110020", "000001"], date(2024, 6, 1))

        assert set(scores.keys()) == {"110020", "000001"}

    def test_all_scores_in_valid_range(self):
        """所有评分必须在 0-100 之间。"""
        repo = _make_repo(
            fund_markets={"110020": "a_share", "000001": "us"},
            a_share_increment=1.0,
            us_increment=5.0,
        )
        strategy = GlobalAllocStrategy(repo=repo)
        scores = strategy.score_batch(["110020", "000001"], date(2024, 6, 1))

        for code, score in scores.items():
            assert 0.0 <= score <= 100.0, f"{code} 的评分 {score} 超出范围 [0, 100]"

    def test_no_fund_info_returns_neutral_score(self):
        """找不到基金信息时，应返回中性分 50。"""
        repo = _make_repo(fund_markets={})  # 没有任何基金信息
        strategy = GlobalAllocStrategy(repo=repo)
        scores = strategy.score_batch(["UNKNOWN"], date(2024, 6, 1))

        assert scores["UNKNOWN"] == pytest.approx(50.0)

    def test_unknown_market_uses_a_share_score(self):
        """未知市场的基金应使用 a_share 评分。"""
        repo = _make_repo(
            fund_markets={"EXOTIC": "exotic_market", "LOCAL": "a_share"},
            a_share_increment=1.0,
            us_increment=1.0,
        )
        strategy = GlobalAllocStrategy(repo=repo)
        scores = strategy.score_batch(["EXOTIC", "LOCAL"], date(2024, 6, 1))

        # exotic_market 不在 market_indices 中，应使用 a_share 分数
        assert scores["EXOTIC"] == pytest.approx(scores["LOCAL"])

    def test_hk_fund_uses_average_of_all_markets(self):
        """港股基金应使用所有市场的平均评分。"""
        # A 股动量：(1000 + 9*1 - 1000) / 1000 = 0.009
        # 美股动量：(4000 + 9*20 - 4000) / 4000 = 0.045
        # A 股得分 = 0，美股得分 = 100，平均 = 50
        repo = _make_repo(
            fund_markets={"HKFUND": "hk"},
            a_share_increment=1.0,
            us_increment=20.0,
        )
        strategy = GlobalAllocStrategy(repo=repo)
        scores = strategy.score_batch(["HKFUND"], date(2024, 6, 1))

        # hk 基金应等于所有市场平均分
        assert 0.0 <= scores["HKFUND"] <= 100.0

    def test_global_fund_uses_average_of_all_markets(self):
        """全球基金应与港股基金一样使用平均评分。"""
        repo = _make_repo(
            fund_markets={"GLOBALFUND_HK": "hk", "GLOBALFUND_GL": "global"},
            a_share_increment=1.0,
            us_increment=20.0,
        )
        strategy = GlobalAllocStrategy(repo=repo)
        scores = strategy.score_batch(["GLOBALFUND_HK", "GLOBALFUND_GL"], date(2024, 6, 1))

        # hk 和 global 基金应获得相同评分（均为平均分）
        assert scores["GLOBALFUND_HK"] == pytest.approx(scores["GLOBALFUND_GL"])

    def test_empty_fund_list_returns_empty_dict(self):
        """空列表输入应返回空字典。"""
        repo = _make_repo()
        strategy = GlobalAllocStrategy(repo=repo)
        scores = strategy.score_batch([], date(2024, 6, 1))

        assert scores == {}


# ---------------------------------------------------------------------------
# TestUsStrongScenario — 美股强势场景
# ---------------------------------------------------------------------------


class TestUsStrongScenario:
    """验证美股强势时，美股基金评分高于 A 股基金。"""

    def test_us_fund_scores_higher_when_us_strong(self):
        """美股行情大幅上涨（+20/day）、A 股基本持平（+1/day）时，
        美股基金评分应明显高于 A 股基金。
        """
        # 美股：4000 起，每条 +20，10 条数据
        # 动量 = (4000 + 9*20 - 4000) / 4000 = 180/4000 = 0.045
        # A 股：1000 起，每条 +1，10 条数据
        # 动量 = (1000 + 9*1 - 1000) / 1000 = 9/1000 = 0.009
        repo = _make_repo(
            a_share_base=1000.0,
            a_share_increment=1.0,
            us_base=4000.0,
            us_increment=20.0,
            fund_markets={
                "QDII_US": "us",      # 美股 QDII 基金
                "A_FUND": "a_share",  # A 股基金
            },
            quote_count=10,
        )
        strategy = GlobalAllocStrategy(repo=repo)
        scores = strategy.score_batch(["QDII_US", "A_FUND"], date(2024, 6, 1))

        # 美股基金得分应高于 A 股基金得分
        assert scores["QDII_US"] > scores["A_FUND"], (
            f"美股基金得分 {scores['QDII_US']:.2f} 应高于 A 股基金得分 {scores['A_FUND']:.2f}"
        )

    def test_us_strong_gives_us_fund_top_score(self):
        """美股动量最强时，美股基金应获得满分 100。"""
        repo = _make_repo(
            a_share_base=1000.0,
            a_share_increment=1.0,
            us_base=4000.0,
            us_increment=20.0,
            fund_markets={"QDII_US": "us"},
            quote_count=10,
        )
        strategy = GlobalAllocStrategy(repo=repo)
        scores = strategy.score_batch(["QDII_US"], date(2024, 6, 1))

        assert scores["QDII_US"] == pytest.approx(100.0)

    def test_a_share_flat_gives_lowest_score(self):
        """A 股动量最弱时，A 股基金应获得最低分 0。"""
        repo = _make_repo(
            a_share_base=1000.0,
            a_share_increment=1.0,
            us_base=4000.0,
            us_increment=20.0,
            fund_markets={"A_FUND": "a_share"},
            quote_count=10,
        )
        strategy = GlobalAllocStrategy(repo=repo)
        scores = strategy.score_batch(["A_FUND"], date(2024, 6, 1))

        assert scores["A_FUND"] == pytest.approx(0.0)

    def test_scores_are_proportional_to_momentum(self):
        """评分应与动量线性相关：两市场时，强市 100 分，弱市 0 分。"""
        repo = _make_repo(
            a_share_increment=1.0,
            us_increment=20.0,
            fund_markets={"US": "us", "CN": "a_share"},
            quote_count=10,
        )
        strategy = GlobalAllocStrategy(repo=repo)
        scores = strategy.score_batch(["US", "CN"], date(2024, 6, 1))

        assert scores["US"] == pytest.approx(100.0)
        assert scores["CN"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestMarketMomentum — 私有方法单元测试
# ---------------------------------------------------------------------------


class TestMarketMomentum:
    """对 _market_momentum 私有方法进行直接测试。"""

    def test_returns_none_when_no_data(self):
        """行情数据为空时，动量应返回 None。"""
        repo = MagicMock()
        repo.get_index_quote.return_value = []
        strategy = GlobalAllocStrategy(repo=repo)

        result = strategy._market_momentum("a_share", date(2024, 6, 1))
        assert result is None

    def test_returns_none_when_only_one_data_point(self):
        """只有一条行情时，无法计算收益率，应返回 None。"""
        q = MagicMock()
        q.close = 1000.0
        repo = MagicMock()
        repo.get_index_quote.return_value = [q]
        strategy = GlobalAllocStrategy(repo=repo)

        result = strategy._market_momentum("a_share", date(2024, 6, 1))
        assert result is None

    def test_returns_correct_momentum(self):
        """动量 = (末值 - 首值) / 首值，应精确计算。"""
        quotes = _make_quotes(1000.0, 10.0, 5)  # close: 1000, 1010, 1020, 1030, 1040
        repo = MagicMock()
        repo.get_index_quote.return_value = quotes
        strategy = GlobalAllocStrategy(repo=repo)

        result = strategy._market_momentum("a_share", date(2024, 6, 1))
        # 动量 = (1040 - 1000) / 1000 = 0.04
        assert result == pytest.approx(0.04)

    def test_returns_none_for_unknown_market(self):
        """market_indices 中不存在的市场应返回 None。"""
        repo = MagicMock()
        strategy = GlobalAllocStrategy(repo=repo)

        result = strategy._market_momentum("nonexistent_market", date(2024, 6, 1))
        assert result is None


# ---------------------------------------------------------------------------
# TestMarketScores — 私有方法单元测试
# ---------------------------------------------------------------------------


class TestMarketScores:
    """对 _market_scores 私有方法进行直接测试。"""

    def test_all_neutral_when_no_data(self):
        """所有市场均无数据时，全部应返回 50。"""
        repo = MagicMock()
        repo.get_index_quote.return_value = []
        strategy = GlobalAllocStrategy(repo=repo)

        scores = strategy._market_scores(date(2024, 6, 1))
        for market, score in scores.items():
            assert score == pytest.approx(50.0), f"{market} 无数据时应为 50，实际为 {score}"

    def test_all_100_when_same_momentum(self):
        """所有市场动量相同时，均应得 100 分。"""
        # 两个市场使用相同的行情数据（相同增量）
        same_quotes = _make_quotes(1000.0, 5.0, 10)
        repo = MagicMock()
        repo.get_index_quote.return_value = same_quotes
        strategy = GlobalAllocStrategy(repo=repo)

        scores = strategy._market_scores(date(2024, 6, 1))
        for market, score in scores.items():
            assert score == pytest.approx(100.0), (
                f"{market} 动量相同时应为 100，实际为 {score}"
            )

    def test_top_market_gets_100(self):
        """动量最高的市场应获得 100 分。"""
        a_share_quotes = _make_quotes(1000.0, 1.0, 10)
        us_quotes = _make_quotes(4000.0, 20.0, 10)

        def _get_index_quote(index_code, start, end):
            if index_code == "000688":
                return a_share_quotes
            if index_code == "SPX":
                return us_quotes
            return []

        repo = MagicMock()
        repo.get_index_quote.side_effect = _get_index_quote
        strategy = GlobalAllocStrategy(repo=repo)

        scores = strategy._market_scores(date(2024, 6, 1))
        assert scores["us"] == pytest.approx(100.0)
        assert scores["a_share"] == pytest.approx(0.0)
