"""测试 FundFetcher 数据采集层。

全部 akshare 调用通过 ``@patch("fund_analyzer.data.fetcher.ak")`` mock，
不依赖真实网络。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import math
import pandas as pd
import pytest

from fund_analyzer.data.fetcher import FundFetcher


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _make_fetcher(**kwargs) -> FundFetcher:
    """创建一个 request_interval=0（加速测试）的 FundFetcher。"""
    kwargs.setdefault("request_interval", 0)
    kwargs.setdefault("retry_count", 3)
    return FundFetcher(**kwargs)


# ---------------------------------------------------------------------------
# test_fetch_fund_list
# ---------------------------------------------------------------------------

class TestFetchFundList:
    """测试 fetch_fund_list 方法。"""

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_fund_list_returns_list_of_dicts(self, mock_ak):
        """正常情况：返回包含 fund_code / fund_name 的字典列表。

        fetcher 内部调用 ak.fund_name_em，返回 DataFrame 中
        第0列为基金代码，第2列为基金名称，第3列为基金类型。
        """
        mock_ak.fund_name_em.return_value = pd.DataFrame(
            [
                ["110011", "SH", "易方达蓝筹精选", "股票型"],
                ["000001", "SH", "华夏成长", "混合型"],
            ]
        )
        fetcher = _make_fetcher()
        result = fetcher.fetch_fund_list()

        assert len(result) == 2
        assert result[0]["fund_code"] == "110011"
        assert result[0]["fund_name"] == "易方达蓝筹精选"
        assert result[1]["fund_code"] == "000001"
        assert result[1]["fund_name"] == "华夏成长"

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_fund_list_empty_df_returns_empty_list(self, mock_ak):
        """akshare 返回空 DataFrame 时，fetch_fund_list 返回空列表。"""
        mock_ak.fund_name_em.return_value = pd.DataFrame()
        fetcher = _make_fetcher()
        result = fetcher.fetch_fund_list()
        assert result == []

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_fund_list_exception_returns_empty_list(self, mock_ak):
        """akshare 抛出异常时，fetch_fund_list 返回空列表而非抛出。"""
        mock_ak.fund_name_em.side_effect = RuntimeError("网络错误")
        fetcher = _make_fetcher()
        result = fetcher.fetch_fund_list()
        assert result == []


# ---------------------------------------------------------------------------
# test_fetch_fund_nav_history
# ---------------------------------------------------------------------------

class TestFetchFundNavHistory:
    """测试 fetch_fund_nav 方法的正常流程。"""

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_fund_nav_history_basic(self, mock_ak):
        """正常情况：返回含 date/nav/acc_nav/daily_return 字段的字典列表。"""
        mock_ak.fund_open_fund_daily_em.return_value = pd.DataFrame(
            [
                ["2024-01-02", 1.2345, 2.3456, 1.50],
                ["2024-01-03", 1.2400, 2.3500, 0.44],
            ],
            columns=["净值日期", "单位净值", "累计净值", "日增长率"],
        )
        fetcher = _make_fetcher()
        result = fetcher.fetch_fund_nav("110011")

        assert len(result) == 2

        row0 = result[0]
        assert row0["date"] == "2024-01-02"
        assert row0["nav"] == pytest.approx(1.2345)
        assert row0["acc_nav"] == pytest.approx(2.3456)
        # 1.50% → 0.015
        assert row0["daily_return"] == pytest.approx(0.015)

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_fund_nav_handles_nan_daily_return(self, mock_ak):
        """daily_return 为 NaN 时，对应字段应为 None。"""
        mock_ak.fund_open_fund_daily_em.return_value = pd.DataFrame(
            [["2024-01-02", 1.10, 2.20, float("nan")]],
            columns=["净值日期", "单位净值", "累计净值", "日增长率"],
        )
        fetcher = _make_fetcher()
        result = fetcher.fetch_fund_nav("110011")

        assert len(result) == 1
        assert result[0]["daily_return"] is None

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_fund_nav_start_date_filter(self, mock_ak):
        """传入 start_date 时，早于该日期的记录应被过滤掉。"""
        mock_ak.fund_open_fund_daily_em.return_value = pd.DataFrame(
            [
                ["2023-12-29", 1.00, 2.00, 0.0],
                ["2024-01-02", 1.01, 2.01, 1.0],
                ["2024-01-03", 1.02, 2.02, 0.99],
            ],
            columns=["净值日期", "单位净值", "累计净值", "日增长率"],
        )
        fetcher = _make_fetcher()
        result = fetcher.fetch_fund_nav("110011", start_date="2024-01-01")

        assert len(result) == 2
        for row in result:
            assert row["date"] >= "2024-01-01"

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_fund_nav_empty_df_returns_empty_list(self, mock_ak):
        """akshare 返回空 DataFrame 时，fetch_fund_nav 返回空列表。"""
        mock_ak.fund_open_fund_daily_em.return_value = pd.DataFrame()
        fetcher = _make_fetcher()
        result = fetcher.fetch_fund_nav("110011")
        assert result == []

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_fund_nav_exception_returns_empty_list(self, mock_ak):
        """akshare 抛出异常时，fetch_fund_nav 返回空列表。"""
        mock_ak.fund_open_fund_daily_em.side_effect = RuntimeError("超时")
        fetcher = _make_fetcher()
        result = fetcher.fetch_fund_nav("110011")
        assert result == []

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_fund_nav_passes_correct_args(self, mock_ak):
        """确认调用 akshare 时传入了正确的参数。"""
        mock_ak.fund_open_fund_daily_em.return_value = pd.DataFrame()
        fetcher = _make_fetcher()
        fetcher.fetch_fund_nav("000001")

        mock_ak.fund_open_fund_daily_em.assert_called_once_with(
            fund="000001",
            indicator="单位净值走势",
        )


# ---------------------------------------------------------------------------
# test_fetch_fund_nav_with_retry_on_failure
# ---------------------------------------------------------------------------

class TestFetchFundNavWithRetryOnFailure:
    """测试 _call_with_retry 的重试机制。"""

    @patch("fund_analyzer.data.fetcher.ak")
    def test_retry_succeeds_on_second_attempt(self, mock_ak):
        """第1次调用失败，第2次成功，最终返回正确数据。"""
        success_df = pd.DataFrame(
            [["2024-01-02", 1.10, 2.20, 0.5]],
            columns=["净值日期", "单位净值", "累计净值", "日增长率"],
        )
        mock_ak.fund_open_fund_daily_em.side_effect = [
            RuntimeError("第1次失败"),
            success_df,
        ]
        fetcher = _make_fetcher(retry_count=3)
        result = fetcher.fetch_fund_nav("110011")

        assert len(result) == 1
        assert mock_ak.fund_open_fund_daily_em.call_count == 2

    @patch("fund_analyzer.data.fetcher.ak")
    def test_retry_exhausted_returns_empty_list(self, mock_ak):
        """所有重试次数耗尽后仍失败，返回空列表。"""
        mock_ak.fund_open_fund_daily_em.side_effect = RuntimeError("持续失败")
        fetcher = _make_fetcher(retry_count=2)
        result = fetcher.fetch_fund_nav("110011")

        assert result == []
        # 总调用次数 = 1（首次）+ 2（重试）= 3
        assert mock_ak.fund_open_fund_daily_em.call_count == 3

    @patch("fund_analyzer.data.fetcher.ak")
    def test_retry_count_zero_no_retry(self, mock_ak):
        """retry_count=0 时，调用失败后不重试，直接返回空列表。"""
        mock_ak.fund_open_fund_daily_em.side_effect = RuntimeError("失败")
        fetcher = _make_fetcher(retry_count=0)
        result = fetcher.fetch_fund_nav("110011")

        assert result == []
        assert mock_ak.fund_open_fund_daily_em.call_count == 1

    @patch("fund_analyzer.data.fetcher.time")
    @patch("fund_analyzer.data.fetcher.ak")
    def test_retry_uses_exponential_backoff(self, mock_ak, mock_time):
        """重试时每次等待时间应按指数增长。"""
        success_df = pd.DataFrame(
            [["2024-01-02", 1.0, 2.0, 0.0]],
            columns=["净值日期", "单位净值", "累计净值", "日增长率"],
        )
        mock_ak.fund_open_fund_daily_em.side_effect = [
            RuntimeError("第1次"),
            RuntimeError("第2次"),
            success_df,
        ]
        fetcher = FundFetcher(request_interval=1.0, retry_count=3)
        fetcher.fetch_fund_nav("110011")

        sleep_calls = [call.args[0] for call in mock_time.sleep.call_args_list]
        # 第1次重试等待 1.0 * 2^0 = 1.0
        # 第2次重试等待 1.0 * 2^1 = 2.0
        # 最终成功后等待 request_interval = 1.0
        assert sleep_calls[0] == pytest.approx(1.0)
        assert sleep_calls[1] == pytest.approx(2.0)


# ---------------------------------------------------------------------------
# test_fetch_index_daily
# ---------------------------------------------------------------------------

class TestFetchIndexDaily:
    """测试 fetch_index_daily 方法。"""

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_index_daily_basic(self, mock_ak):
        """正常情况：返回含 date / close 字段的字典列表。"""
        mock_ak.stock_zh_index_daily_em.return_value = pd.DataFrame(
            [
                ["2024-01-02", 3500.12],
                ["2024-01-03", 3510.56],
                ["2024-01-04", 3498.00],
            ],
            columns=["date", "close"],
        )
        fetcher = _make_fetcher()
        result = fetcher.fetch_index_daily("sh000300")

        assert len(result) == 3
        assert result[0]["date"] == "2024-01-02"
        assert result[0]["close"] == pytest.approx(3500.12)
        assert result[2]["date"] == "2024-01-04"

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_index_daily_passes_correct_args(self, mock_ak):
        """确认调用 akshare 时传入了 symbol 与 start_date 参数。"""
        mock_ak.stock_zh_index_daily_em.return_value = pd.DataFrame()
        fetcher = _make_fetcher()
        fetcher.fetch_index_daily("sh000300", start_date="20200101")

        mock_ak.stock_zh_index_daily_em.assert_called_once_with(
            symbol="sh000300",
            start_date="20200101",
        )

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_index_daily_default_start_date(self, mock_ak):
        """未传 start_date 时，使用默认值 '20100101'。"""
        mock_ak.stock_zh_index_daily_em.return_value = pd.DataFrame()
        fetcher = _make_fetcher()
        fetcher.fetch_index_daily("sh000300")

        mock_ak.stock_zh_index_daily_em.assert_called_once_with(
            symbol="sh000300",
            start_date="20100101",
        )

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_index_daily_empty_df_returns_empty_list(self, mock_ak):
        """akshare 返回空 DataFrame 时，返回空列表。"""
        mock_ak.stock_zh_index_daily_em.return_value = pd.DataFrame()
        fetcher = _make_fetcher()
        result = fetcher.fetch_index_daily("sh000300")
        assert result == []

    @patch("fund_analyzer.data.fetcher.ak")
    def test_fetch_index_daily_exception_returns_empty_list(self, mock_ak):
        """akshare 抛出异常时，返回空列表。"""
        mock_ak.stock_zh_index_daily_em.side_effect = Exception("接口异常")
        fetcher = _make_fetcher()
        result = fetcher.fetch_index_daily("sh000300")
        assert result == []


# ---------------------------------------------------------------------------
# 额外：fetch_fund_holding / fetch_industry_classification 冒烟测试
# ---------------------------------------------------------------------------

class TestFetchFundHolding:
    @patch("fund_analyzer.data.fetcher.ak")
    def test_returns_list_of_dicts(self, mock_ak):
        """fetch_fund_holding 正常情况下返回持仓字典列表。"""
        mock_ak.fund_portfolio_hold_em.return_value = pd.DataFrame(
            [["600519", "贵州茅台", "消费", 8.5]],
            columns=["股票代码", "股票名称", "行业", "占净值比例"],
        )
        fetcher = _make_fetcher()
        result = fetcher.fetch_fund_holding("110011", "2023")

        assert len(result) == 1
        assert result[0]["股票代码"] == "600519"

    @patch("fund_analyzer.data.fetcher.ak")
    def test_exception_returns_empty_list(self, mock_ak):
        mock_ak.fund_portfolio_hold_em.side_effect = Exception("失败")
        fetcher = _make_fetcher()
        result = fetcher.fetch_fund_holding("110011", "2023")
        assert result == []


class TestFetchIndustryClassification:
    @patch("fund_analyzer.data.fetcher.ak")
    def test_returns_list_of_dicts(self, mock_ak):
        """fetch_industry_classification 正常情况下返回行业字典列表。"""
        mock_ak.stock_board_industry_name_em.return_value = pd.DataFrame(
            [["白酒"], ["半导体"]],
            columns=["板块名称"],
        )
        fetcher = _make_fetcher()
        result = fetcher.fetch_industry_classification()

        assert len(result) == 2
        assert result[0]["板块名称"] == "白酒"

    @patch("fund_analyzer.data.fetcher.ak")
    def test_exception_returns_empty_list(self, mock_ak):
        mock_ak.stock_board_industry_name_em.side_effect = Exception("失败")
        fetcher = _make_fetcher()
        result = fetcher.fetch_industry_classification()
        assert result == []
