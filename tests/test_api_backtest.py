"""Backtest API 端点测试。

使用 FastAPI TestClient + dependency_overrides + monkeypatch 模拟依赖，无需真实数据库。
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from fund_analyzer.api.deps import get_composite, get_repo, get_settings
from fund_analyzer.api.main import app
from fund_analyzer.api.routers.backtest import _safe_float, _safe_float_or_none


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_settings():
    """构造 mock Settings。"""
    settings = MagicMock()
    settings.data.fund_pool.min_inception_years = 2
    settings.data.fund_pool.min_size_billion = 1.0
    settings.data.fund_pool.exclude_types = ["货币型"]
    settings.backtest.core_top_n = 3
    settings.backtest.satellite_top_n = 7
    settings.backtest.buy_fee_rate = 0.0015
    settings.backtest.sell_fee_rate = 0.005
    settings.backtest.core_rebalance_freq = "quarterly"
    settings.backtest.satellite_rebalance_freq = "monthly"
    return settings


@pytest.fixture()
def mock_repo():
    """构造 mock FundRepository。"""
    repo = MagicMock()

    fund1 = MagicMock()
    fund1.fund_code = "110011"
    fund2 = MagicMock()
    fund2.fund_code = "000001"

    repo.get_eligible_funds.return_value = [fund1, fund2]
    return repo


@pytest.fixture()
def mock_composite():
    """构造 mock CompositeStrategy。"""
    return MagicMock()


@pytest.fixture()
def backtest_result():
    """构造预设的回测结果。"""
    dates = pd.date_range("2023-01-01", periods=5, freq="D")
    return {
        "portfolio_returns": pd.Series(
            [0.01, -0.005, 0.008, 0.003, -0.002], index=dates
        ),
        "benchmark_returns": pd.Series(
            [0.005, -0.003, 0.006, 0.002, -0.001], index=dates
        ),
        "portfolio_values": pd.Series(
            [100000, 101000, 100495, 101299, 101603], index=dates, dtype=float
        ),
        "metrics": {
            "annualized_return": 0.12,
            "annualized_volatility": 0.15,
            "max_drawdown": -0.08,
            "sharpe_ratio": 0.80,
            "sortino_ratio": 1.10,
            "calmar_ratio": 1.50,
            "monthly_win_rate": 0.67,
            "information_ratio": 0.45,
            "alpha": 0.03,
        },
        "total_fees_paid": 150.0,
        "final_value": 101603.0,
        "initial_capital": 100000.0,
    }


@pytest.fixture()
def client(mock_repo, mock_composite, mock_settings):
    """创建带有 mock 依赖的 TestClient。"""
    app.dependency_overrides[get_repo] = lambda: mock_repo
    app.dependency_overrides[get_composite] = lambda: mock_composite
    app.dependency_overrides[get_settings] = lambda: mock_settings
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/backtest/run
# ---------------------------------------------------------------------------

class TestBacktestRun:
    """测试回测运行端点。"""

    def test_run_success(self, client, backtest_result):
        """成功运行回测并返回结果。"""
        with patch(
            "fund_analyzer.api.routers.backtest.BacktestEngine"
        ) as MockEngine:
            engine_instance = MagicMock()
            engine_instance.run.return_value = backtest_result
            MockEngine.return_value = engine_instance

            resp = client.post(
                "/api/backtest/run",
                json={"start_date": "2023-01-01", "end_date": "2023-01-05"},
            )

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

        data = body["data"]

        # 验证 Series 数据格式
        assert len(data["portfolio_returns"]["dates"]) == 5
        assert len(data["portfolio_returns"]["values"]) == 5
        assert len(data["benchmark_returns"]["dates"]) == 5
        assert len(data["portfolio_values"]["dates"]) == 5

        # 验证 metrics
        metrics = data["metrics"]
        assert metrics["annualized_return"] == 0.12
        assert metrics["sharpe_ratio"] == 0.80
        assert metrics["alpha"] == 0.03

        # 验证汇总数据
        assert data["total_fees_paid"] == 150.0
        assert data["final_value"] == 101603.0
        assert data["initial_capital"] == 100000.0

    def test_run_with_default_params(self, client, backtest_result):
        """使用默认参数运行回测。"""
        with patch(
            "fund_analyzer.api.routers.backtest.BacktestEngine"
        ) as MockEngine:
            engine_instance = MagicMock()
            engine_instance.run.return_value = backtest_result
            MockEngine.return_value = engine_instance

            resp = client.post("/api/backtest/run", json={})

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0

    def test_run_custom_core_ratio(self, client, backtest_result):
        """自定义核心仓位比例。"""
        with patch(
            "fund_analyzer.api.routers.backtest.BacktestEngine"
        ) as MockEngine:
            engine_instance = MagicMock()
            engine_instance.run.return_value = backtest_result
            MockEngine.return_value = engine_instance

            resp = client.post(
                "/api/backtest/run",
                json={"core_ratio": 50, "initial_capital": 200000},
            )

        assert resp.status_code == 200

        # 验证 BacktestEngine 构造参数中 core_ratio = 0.5
        call_kwargs = MockEngine.call_args[1]
        assert call_kwargs["core_ratio"] == 0.5
        assert call_kwargs["satellite_ratio"] == 0.5
        assert call_kwargs["initial_capital"] == 200000

    def test_run_empty_fund_pool(self, client, mock_repo):
        """基金池为空时返回错误。"""
        mock_repo.get_eligible_funds.return_value = []

        resp = client.post("/api/backtest/run", json={})

        body = resp.json()
        assert body["code"] == 400
        assert "无符合条件的基金" in body["message"]

    def test_run_with_nan_metrics(self, client, backtest_result):
        """回测结果中含有 NaN 时正确处理。"""
        backtest_result["metrics"]["information_ratio"] = float("nan")
        backtest_result["metrics"]["alpha"] = float("nan")

        with patch(
            "fund_analyzer.api.routers.backtest.BacktestEngine"
        ) as MockEngine:
            engine_instance = MagicMock()
            engine_instance.run.return_value = backtest_result
            MockEngine.return_value = engine_instance

            resp = client.post("/api/backtest/run", json={})

        assert resp.status_code == 200
        body = resp.json()
        metrics = body["data"]["metrics"]
        # NaN 应被转为 None
        assert metrics["information_ratio"] is None
        assert metrics["alpha"] is None

    def test_run_with_nan_in_series(self, client):
        """Series 中含有 NaN 时替换为 0.0。"""
        dates = pd.date_range("2023-01-01", periods=3, freq="D")
        result_with_nan = {
            "portfolio_returns": pd.Series([0.01, float("nan"), 0.008], index=dates),
            "benchmark_returns": pd.Series([0.005, 0.003, float("nan")], index=dates),
            "portfolio_values": pd.Series([100000, float("nan"), 101000], index=dates),
            "metrics": {
                "annualized_return": 0.10,
                "annualized_volatility": 0.12,
                "max_drawdown": -0.05,
                "sharpe_ratio": 0.83,
                "sortino_ratio": 1.0,
                "calmar_ratio": 2.0,
                "monthly_win_rate": 0.60,
                "information_ratio": None,
                "alpha": None,
            },
            "total_fees_paid": 50.0,
            "final_value": 101000.0,
            "initial_capital": 100000.0,
        }

        with patch(
            "fund_analyzer.api.routers.backtest.BacktestEngine"
        ) as MockEngine:
            engine_instance = MagicMock()
            engine_instance.run.return_value = result_with_nan
            MockEngine.return_value = engine_instance

            resp = client.post("/api/backtest/run", json={})

        assert resp.status_code == 200
        body = resp.json()
        data = body["data"]

        # NaN in series should be replaced with 0.0
        assert data["portfolio_returns"]["values"][1] == 0.0
        assert data["benchmark_returns"]["values"][2] == 0.0
        assert data["portfolio_values"]["values"][1] == 0.0

    def test_run_engine_error(self, client):
        """回测引擎异常时返回错误响应。"""
        with patch(
            "fund_analyzer.api.routers.backtest.BacktestEngine"
        ) as MockEngine:
            engine_instance = MagicMock()
            engine_instance.run.side_effect = Exception("Backtest failed")
            MockEngine.return_value = engine_instance

            resp = client.post("/api/backtest/run", json={})

        body = resp.json()
        assert body["code"] == 500
        assert "回测运行失败" in body["message"]


# ---------------------------------------------------------------------------
# 工具函数测试
# ---------------------------------------------------------------------------

class TestSafeFloat:
    """测试 _safe_float 和 _safe_float_or_none 工具函数。"""

    def test_safe_float_normal(self):
        assert _safe_float(1.5) == 1.5

    def test_safe_float_none(self):
        assert _safe_float(None) == 0.0

    def test_safe_float_nan(self):
        assert _safe_float(float("nan")) == 0.0

    def test_safe_float_int(self):
        assert _safe_float(42) == 42.0

    def test_safe_float_or_none_normal(self):
        assert _safe_float_or_none(1.5) == 1.5

    def test_safe_float_or_none_none(self):
        assert _safe_float_or_none(None) is None

    def test_safe_float_or_none_nan(self):
        assert _safe_float_or_none(float("nan")) is None
