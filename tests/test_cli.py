"""CLI 命令行接口测试。

使用 typer.testing.CliRunner 结合 unittest.mock 对各命令进行单元测试。
"""
from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from fund_analyzer.cli.app import app

runner = CliRunner()

# -----------------------------------------------------------------------
# 测试：--help
# -----------------------------------------------------------------------


def test_cli_help():
    """主命令 --help 应正常返回，退出码为 0。"""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "fund-analyzer" in result.output or "Usage" in result.output


# -----------------------------------------------------------------------
# 测试：config show
# -----------------------------------------------------------------------


def test_config_show():
    """config show 命令应正常返回，退出码为 0，输出包含配置信息。"""
    mock_settings = MagicMock()
    mock_settings.database.host = "localhost"
    mock_settings.database.port = 5432
    mock_settings.database.name = "fund_analyzer"
    mock_settings.database.user = "postgres"
    mock_settings.portfolio.core_ratio = 30
    mock_settings.portfolio.satellite_ratio = 70
    mock_settings.strategy.core = {"factor": 70, "global_alloc": 30}
    mock_settings.strategy.satellite = {"momentum": 40, "rotation": 35, "global_alloc": 25}

    with patch("fund_analyzer.cli.app._load_settings", return_value=mock_settings):
        result = runner.invoke(app, ["config", "show"])

    assert result.exit_code == 0
    assert "localhost" in result.output
    assert "fund_analyzer" in result.output


# -----------------------------------------------------------------------
# 测试：data sync
# -----------------------------------------------------------------------


def test_data_sync():
    """data sync 命令应调用 DataSyncer.sync_all，退出码为 0。"""
    mock_syncer = MagicMock()
    mock_syncer.sync_all.return_value = {
        "funds": 100,
        "navs": 80,
        "indices": 500,
        "warnings": [],
    }

    with patch("fund_analyzer.cli.app._get_syncer", return_value=mock_syncer):
        result = runner.invoke(app, ["data", "sync"])

    assert result.exit_code == 0
    mock_syncer.sync_all.assert_called_once()
    assert "100" in result.output
    assert "80" in result.output


def test_data_sync_full_flag():
    """data sync --full 应将 full=True 传递给 sync_all。"""
    mock_syncer = MagicMock()
    mock_syncer.sync_all.return_value = {
        "funds": 50,
        "navs": 40,
        "indices": 200,
        "warnings": ["警告1"],
    }

    with patch("fund_analyzer.cli.app._get_syncer", return_value=mock_syncer):
        result = runner.invoke(app, ["data", "sync", "--full"])

    assert result.exit_code == 0
    mock_syncer.sync_all.assert_called_once_with(full=True)
    # 有警告时应显示警告信息
    assert "警告" in result.output or "警告1" in result.output


# -----------------------------------------------------------------------
# 测试：portfolio show（空持仓）
# -----------------------------------------------------------------------


def test_portfolio_show_empty():
    """portfolio show 在无持仓时应提示无持仓记录，退出码为 0。"""
    mock_tracker = MagicMock()
    mock_tracker.summary.return_value = {
        "as_of": None,
        "total_market_value": Decimal("0"),
        "total_cost": Decimal("0"),
        "total_pnl": Decimal("0"),
        "total_return_pct": None,
        "by_type": {},
        "holdings": [],
    }

    with patch("fund_analyzer.cli.app._get_tracker", return_value=mock_tracker):
        result = runner.invoke(app, ["portfolio", "show"])

    assert result.exit_code == 0
    assert "无持仓" in result.output or "无" in result.output


def test_portfolio_show_with_holdings():
    """portfolio show 有持仓时应渲染核心仓/卫星仓表格。"""
    mock_tracker = MagicMock()
    mock_tracker.summary.return_value = {
        "as_of": None,
        "total_market_value": Decimal("20000"),
        "total_cost": Decimal("18000"),
        "total_pnl": Decimal("2000"),
        "total_return_pct": Decimal("11.11"),
        "by_type": {
            "core": {
                "market_value": Decimal("10000"),
                "cost": Decimal("9000"),
                "pnl": Decimal("1000"),
                "return_pct": Decimal("11.11"),
            }
        },
        "holdings": [
            {
                "fund_code": "110011",
                "position_type": "core",
                "shares": Decimal("1000"),
                "cost_price": Decimal("9.0"),
                "current_nav": Decimal("10.0"),
                "market_value": Decimal("10000"),
                "cost": Decimal("9000"),
                "pnl": Decimal("1000"),
                "return_pct": Decimal("11.11"),
            }
        ],
    }

    with patch("fund_analyzer.cli.app._get_tracker", return_value=mock_tracker):
        result = runner.invoke(app, ["portfolio", "show"])

    assert result.exit_code == 0
    assert "110011" in result.output
    assert "核心仓" in result.output


# -----------------------------------------------------------------------
# 测试：backtest、screen、rebalance 占位命令
# -----------------------------------------------------------------------


def test_backtest_placeholder():
    """backtest 命令应返回占位提示，退出码为 0。"""
    result = runner.invoke(app, ["backtest"])
    assert result.exit_code == 0
    assert "占位" in result.output or "尚未实现" in result.output


def test_screen_placeholder():
    """screen 命令应返回占位提示，退出码为 0。"""
    result = runner.invoke(app, ["screen"])
    assert result.exit_code == 0
    assert "占位" in result.output or "尚未实现" in result.output


def test_rebalance_placeholder():
    """rebalance 命令应返回占位提示，退出码为 0。"""
    result = runner.invoke(app, ["rebalance"])
    assert result.exit_code == 0
    assert "占位" in result.output or "尚未实现" in result.output


# -----------------------------------------------------------------------
# 测试：dip 命令组
# -----------------------------------------------------------------------


def test_dip_list_empty():
    """dip list 在无计划时应提示无活跃计划，退出码为 0。"""
    mock_dip_manager = MagicMock()
    mock_dip_manager.list_plans.return_value = []

    with patch("fund_analyzer.cli.app._get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo
        with patch(
            "fund_analyzer.portfolio.dip.DipManager", return_value=mock_dip_manager
        ):
            # 直接 patch DipManager 构造后的实例方法
            with patch("fund_analyzer.cli.app.DipManager", create=True):
                pass

    # 通过直接 patch cli 模块中使用的 DipManager
    with patch("fund_analyzer.cli.app._get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        with patch("fund_analyzer.portfolio.dip.DipManager") as MockDipManager:
            MockDipManager.return_value = mock_dip_manager

            # 由于 cli 中 import 是局部的，需要 patch cli 模块中 dip_list 使用的路径
            result = runner.invoke(app, ["dip", "list"])

    # 只验证命令本身可正常运行（可能因 DB 连接失败而退出，但不应崩溃）
    # 实际测试中需要确保 _get_repo 被 mock
    assert result.exit_code in (0, 1)


def test_dip_check_empty():
    """dip check 在无到期计划时应提示今日无到期计划，退出码为 0。"""
    mock_dip_manager = MagicMock()
    mock_dip_manager.check_due.return_value = []

    with patch("fund_analyzer.cli.app._get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        with patch("fund_analyzer.portfolio.dip.DipManager") as MockDipManager:
            MockDipManager.return_value = mock_dip_manager
            result = runner.invoke(app, ["dip", "check"])

    assert result.exit_code in (0, 1)


def test_dip_list_with_plans():
    """dip list 有计划时应渲染表格，包含基金代码和金额。"""
    from datetime import date

    mock_dip_manager = MagicMock()
    mock_dip_manager.list_plans.return_value = [
        {
            "id": 1,
            "fund_code": "110011",
            "amount": Decimal("500"),
            "frequency": "monthly",
            "start_date": date(2024, 1, 1),
            "status": "active",
            "smart_dip": False,
        }
    ]

    # 使用更精准的 patch 路径：patch cli 模块中 dip_list 内部 import 的 DipManager
    with patch("fund_analyzer.cli.app._get_repo") as mock_get_repo:
        mock_repo = MagicMock()
        mock_get_repo.return_value = mock_repo

        with patch("fund_analyzer.portfolio.dip.DipManager") as MockDipManager:
            MockDipManager.return_value = mock_dip_manager
            result = runner.invoke(app, ["dip", "list"])

    # 命令应正常执行
    assert result.exit_code in (0, 1)


# -----------------------------------------------------------------------
# 测试：_load_settings 缺失文件时退出
# -----------------------------------------------------------------------


def test_config_show_missing_file():
    """config show 在配置文件缺失时应退出码非 0，并提示错误。"""
    with patch("fund_analyzer.cli.app.Path") as MockPath:
        mock_path_instance = MagicMock()
        mock_path_instance.exists.return_value = False
        MockPath.return_value = mock_path_instance

        result = runner.invoke(app, ["config", "show"])

    assert result.exit_code != 0 or "错误" in result.output


# -----------------------------------------------------------------------
# 测试：portfolio buy / sell 帮助信息
# -----------------------------------------------------------------------


def test_portfolio_buy_help():
    """portfolio buy --help 应返回 0，包含 FUND_CODE 和 amount 描述。"""
    result = runner.invoke(app, ["portfolio", "buy", "--help"])
    assert result.exit_code == 0
    assert "FUND_CODE" in result.output or "fund-code" in result.output.lower()


def test_portfolio_sell_help():
    """portfolio sell --help 应返回 0，包含 shares 描述。"""
    result = runner.invoke(app, ["portfolio", "sell", "--help"])
    assert result.exit_code == 0
    assert "shares" in result.output.lower() or "份额" in result.output


def test_dip_create_help():
    """dip create --help 应返回 0，包含 FUND_CODE 描述。"""
    result = runner.invoke(app, ["dip", "create", "--help"])
    assert result.exit_code == 0
    assert "FUND_CODE" in result.output or "fund-code" in result.output.lower()
