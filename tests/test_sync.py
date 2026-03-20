"""DataSyncer 单元测试。

使用 MagicMock 模拟 FundFetcher 与 FundRepository，
验证同步逻辑的正确性，包括净值异常跳变检测。
"""
from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import MagicMock, call

import pytest

from fund_analyzer.data.sync import DataSyncer


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_fetcher() -> MagicMock:
    """返回一个空的 FundFetcher Mock 对象。"""
    return MagicMock()


@pytest.fixture()
def mock_repo() -> MagicMock:
    """返回一个空的 FundRepository Mock 对象。"""
    return MagicMock()


@pytest.fixture()
def syncer(mock_repo: MagicMock, mock_fetcher: MagicMock) -> DataSyncer:
    """返回使用 Mock 对象构造的 DataSyncer 实例。"""
    return DataSyncer(repo=mock_repo, fetcher=mock_fetcher)


# ---------------------------------------------------------------------------
# test_sync_fund_list
# ---------------------------------------------------------------------------

class TestSyncFundList:
    """sync_fund_list 方法测试集。"""

    def test_sync_fund_list_returns_count(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """正常返回时，应调用 upsert_fund_info 并返回正确条数。"""
        mock_fetcher.fetch_fund_list.return_value = [
            {"fund_code": "110011", "fund_name": "易方达蓝筹精选"},
            {"fund_code": "000001", "fund_name": "华夏成长"},
        ]

        count = syncer.sync_fund_list()

        assert count == 2
        assert mock_repo.upsert_fund_info.call_count == 2
        mock_repo.upsert_fund_info.assert_any_call(
            {"fund_code": "110011", "fund_name": "易方达蓝筹精选"}
        )
        mock_repo.upsert_fund_info.assert_any_call(
            {"fund_code": "000001", "fund_name": "华夏成长"}
        )

    def test_sync_fund_list_empty(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """fetcher 返回空列表时，不应调用 upsert，返回 0。"""
        mock_fetcher.fetch_fund_list.return_value = []

        count = syncer.sync_fund_list()

        assert count == 0
        mock_repo.upsert_fund_info.assert_not_called()

    def test_sync_fund_list_upsert_error_skipped(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """upsert 部分失败时，应跳过失败项并继续，返回成功条数。"""
        mock_fetcher.fetch_fund_list.return_value = [
            {"fund_code": "110011", "fund_name": "易方达蓝筹精选"},
            {"fund_code": "BAD", "fund_name": "坏数据"},
            {"fund_code": "000001", "fund_name": "华夏成长"},
        ]
        # 第二次调用抛异常
        mock_repo.upsert_fund_info.side_effect = [None, Exception("DB Error"), None]

        count = syncer.sync_fund_list()

        assert count == 2


# ---------------------------------------------------------------------------
# test_sync_fund_navs
# ---------------------------------------------------------------------------

class TestSyncFundNav:
    """sync_fund_nav 方法测试集。"""

    def test_sync_fund_nav_parses_and_upserts(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """正常数据应被解析为 datetime.date 和 Decimal，并调用 upsert_fund_navs。"""
        mock_fetcher.fetch_fund_nav.return_value = [
            {"date": "2024-01-02", "nav": "1.2345", "acc_nav": "2.3456", "daily_return": "0.01"},
            {"date": "2024-01-03", "nav": "1.2400", "acc_nav": "2.3511", "daily_return": "0.005"},
        ]

        warnings = syncer.sync_fund_nav("110011")

        assert warnings == []
        mock_repo.upsert_fund_navs.assert_called_once()
        call_args = mock_repo.upsert_fund_navs.call_args
        fund_code_arg, rows_arg = call_args[0]

        assert fund_code_arg == "110011"
        assert len(rows_arg) == 2

        row0 = rows_arg[0]
        assert row0["date"] == datetime.date(2024, 1, 2)
        assert isinstance(row0["nav"], Decimal)
        assert row0["nav"] == Decimal("1.2345")
        assert isinstance(row0["acc_nav"], Decimal)
        assert isinstance(row0["daily_return"], Decimal)

    def test_sync_fund_nav_empty_returns_no_warnings(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """fetcher 返回空列表时，应返回空警告列表，不调用 upsert。"""
        mock_fetcher.fetch_fund_nav.return_value = []

        warnings = syncer.sync_fund_nav("110011")

        assert warnings == []
        mock_repo.upsert_fund_navs.assert_not_called()

    def test_sync_fund_nav_with_fund_info_pre_created(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """模拟基金信息已存在时，净值同步应正常运行。"""
        # 预先设置 repo 已有基金信息（通过 get_fund_info 返回 Mock 对象）
        fund_info_mock = MagicMock()
        fund_info_mock.fund_code = "110011"
        mock_repo.get_fund_info.return_value = fund_info_mock

        mock_fetcher.fetch_fund_nav.return_value = [
            {"date": "2024-03-01", "nav": "1.5000", "acc_nav": "3.0000", "daily_return": "0.002"},
        ]

        warnings = syncer.sync_fund_nav("110011")

        assert warnings == []
        mock_repo.upsert_fund_navs.assert_called_once()
        rows_arg = mock_repo.upsert_fund_navs.call_args[0][1]
        assert rows_arg[0]["date"] == datetime.date(2024, 3, 1)
        assert rows_arg[0]["nav"] == Decimal("1.5000")


# ---------------------------------------------------------------------------
# test_sync_validates_nav_jump
# ---------------------------------------------------------------------------

class TestSyncNavJumpValidation:
    """净值异常跳变检测测试集。"""

    def test_jump_over_15_percent_generates_warning(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """相邻净值涨幅超过 15% 时，应生成包含"异常"的警告信息。"""
        mock_fetcher.fetch_fund_nav.return_value = [
            {"date": "2024-01-02", "nav": "1.0000", "acc_nav": "1.0000", "daily_return": "0.0"},
            # 涨幅 = (1.2000 - 1.0000) / 1.0000 = 20% > 15%
            {"date": "2024-01-03", "nav": "1.2000", "acc_nav": "1.2000", "daily_return": "0.2"},
        ]

        warnings = syncer.sync_fund_nav("110011")

        assert len(warnings) == 1
        assert "异常" in warnings[0]

    def test_jump_exactly_15_percent_no_warning(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """涨幅恰好等于 15% 时，不应触发警告（阈值为严格大于）。"""
        mock_fetcher.fetch_fund_nav.return_value = [
            {"date": "2024-01-02", "nav": "1.0000", "acc_nav": "1.0000", "daily_return": "0.0"},
            # 涨幅 = 15%，不超过阈值
            {"date": "2024-01-03", "nav": "1.1500", "acc_nav": "1.1500", "daily_return": "0.15"},
        ]

        warnings = syncer.sync_fund_nav("110011")

        assert len(warnings) == 0

    def test_drop_over_15_percent_generates_warning(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """相邻净值跌幅超过 15% 时，同样应生成警告。"""
        mock_fetcher.fetch_fund_nav.return_value = [
            {"date": "2024-01-02", "nav": "1.0000", "acc_nav": "1.0000", "daily_return": "0.0"},
            # 跌幅 = 20%
            {"date": "2024-01-03", "nav": "0.8000", "acc_nav": "0.8000", "daily_return": "-0.2"},
        ]

        warnings = syncer.sync_fund_nav("110011")

        assert len(warnings) == 1
        assert "异常" in warnings[0]

    def test_multiple_jumps_multiple_warnings(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """多次跳变时，应生成多条警告。"""
        mock_fetcher.fetch_fund_nav.return_value = [
            {"date": "2024-01-02", "nav": "1.0000", "acc_nav": "1.0000", "daily_return": "0.0"},
            {"date": "2024-01-03", "nav": "1.2000", "acc_nav": "1.2000", "daily_return": "0.2"},
            # 此条基于 1.2000 计算，1.2000 → 0.9000：跌 25%
            {"date": "2024-01-04", "nav": "0.9000", "acc_nav": "0.9000", "daily_return": "-0.25"},
        ]

        warnings = syncer.sync_fund_nav("110011")

        assert len(warnings) == 2
        for w in warnings:
            assert "异常" in w

    def test_normal_fluctuation_no_warning(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """正常波动（<= 15%）不应产生任何警告。"""
        mock_fetcher.fetch_fund_nav.return_value = [
            {"date": "2024-01-02", "nav": "1.0000", "acc_nav": "1.0000", "daily_return": "0.0"},
            {"date": "2024-01-03", "nav": "1.0500", "acc_nav": "1.0500", "daily_return": "0.05"},
            {"date": "2024-01-04", "nav": "0.9800", "acc_nav": "0.9800", "daily_return": "-0.067"},
        ]

        warnings = syncer.sync_fund_nav("110011")

        assert warnings == []


# ---------------------------------------------------------------------------
# test_sync_index
# ---------------------------------------------------------------------------

class TestSyncIndex:
    """sync_index 方法测试集。"""

    def test_sync_index_calculates_daily_return(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """应基于相邻收盘价计算 daily_return 并 upsert。"""
        mock_fetcher.fetch_index_daily.return_value = [
            {"date": "2024-01-02", "close": "3000.00"},
            {"date": "2024-01-03", "close": "3030.00"},
            {"date": "2024-01-04", "close": "2970.00"},
        ]

        count = syncer.sync_index("000300")

        assert count == 3
        mock_repo.upsert_index_quotes.assert_called_once()
        rows_arg = mock_repo.upsert_index_quotes.call_args[0][1]

        # 第一条无前值，daily_return 应为 None
        assert rows_arg[0]["daily_return"] is None
        assert rows_arg[0]["close"] == Decimal("3000.00")

        # 第二条：(3030 - 3000) / 3000 = 0.01
        assert rows_arg[1]["daily_return"] == Decimal("3030.00") / Decimal("3000.00") - Decimal("1")

        # 第三条：(2970 - 3030) / 3030
        assert rows_arg[2]["daily_return"] == Decimal("2970.00") / Decimal("3030.00") - Decimal("1")

    def test_sync_index_empty_returns_zero(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """fetcher 返回空时，应返回 0 且不调用 upsert。"""
        mock_fetcher.fetch_index_daily.return_value = []

        count = syncer.sync_index("000300")

        assert count == 0
        mock_repo.upsert_index_quotes.assert_not_called()

    def test_sync_index_date_parsed(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """date 应被解析为 datetime.date 类型。"""
        mock_fetcher.fetch_index_daily.return_value = [
            {"date": "2024-01-02", "close": "3000.00"},
        ]

        syncer.sync_index("000688")

        rows_arg = mock_repo.upsert_index_quotes.call_args[0][1]
        assert rows_arg[0]["date"] == datetime.date(2024, 1, 2)


# ---------------------------------------------------------------------------
# test_sync_all
# ---------------------------------------------------------------------------

class TestSyncAll:
    """sync_all 方法测试集。"""

    def test_sync_all_returns_dict_structure(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """返回值应包含 funds/navs/indices/warnings 四个键。"""
        mock_fetcher.fetch_fund_list.return_value = []
        mock_fetcher.fetch_fund_nav.return_value = []
        mock_fetcher.fetch_index_daily.return_value = []
        mock_repo.get_eligible_funds.return_value = []

        result = syncer.sync_all()

        assert set(result.keys()) == {"funds", "navs", "indices", "warnings"}

    def test_sync_all_with_specified_fund_codes(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """指定 fund_codes 时，应同步指定的基金净值，不调用 get_eligible_funds。"""
        mock_fetcher.fetch_fund_list.return_value = [
            {"fund_code": "110011", "fund_name": "易方达蓝筹精选"},
        ]
        mock_fetcher.fetch_fund_nav.return_value = [
            {"date": "2024-01-02", "nav": "1.0000", "acc_nav": "1.0000", "daily_return": "0.0"},
        ]
        mock_fetcher.fetch_index_daily.return_value = [
            {"date": "2024-01-02", "close": "3000.00"},
        ]

        result = syncer.sync_all(fund_codes=["110011"])

        # 不应调用 get_eligible_funds
        mock_repo.get_eligible_funds.assert_not_called()
        assert result["funds"] == 1
        assert result["navs"] == 1  # 1 只基金成功同步
        assert result["warnings"] == []

    def test_sync_all_syncs_key_indices(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """sync_all 应同步 000688 和 000300 两个关键指数。"""
        mock_fetcher.fetch_fund_list.return_value = []
        mock_fetcher.fetch_index_daily.return_value = [
            {"date": "2024-01-02", "close": "1000.00"},
        ]
        mock_repo.get_eligible_funds.return_value = []

        syncer.sync_all()

        # 应调用两次 fetch_index_daily，各对应一个指数
        calls = [c[0][0] for c in mock_fetcher.fetch_index_daily.call_args_list]
        assert "000688" in calls
        assert "000300" in calls

    def test_sync_all_collects_nav_warnings(
        self,
        syncer: DataSyncer,
        mock_fetcher: MagicMock,
        mock_repo: MagicMock,
    ) -> None:
        """sync_all 应收集并汇总所有净值异常警告。"""
        mock_fetcher.fetch_fund_list.return_value = []
        mock_fetcher.fetch_fund_nav.return_value = [
            {"date": "2024-01-02", "nav": "1.0000", "acc_nav": "1.0000", "daily_return": "0.0"},
            # 20% 跳变
            {"date": "2024-01-03", "nav": "1.2000", "acc_nav": "1.2000", "daily_return": "0.2"},
        ]
        mock_fetcher.fetch_index_daily.return_value = []
        mock_repo.get_eligible_funds.return_value = []

        result = syncer.sync_all(fund_codes=["110011"])

        assert len(result["warnings"]) == 1
        assert "异常" in result["warnings"][0]
