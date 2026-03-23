"""Dashboard API 端点测试。

使用 FastAPI TestClient + monkeypatch 模拟依赖，无需真实数据库。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from fund_analyzer.api.deps import get_repo, get_tracker
from fund_analyzer.api.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_tracker():
    """构造一个 mock PortfolioTracker，返回预设的 summary 数据。"""
    tracker = MagicMock()
    tracker.summary.return_value = {
        "as_of": date(2026, 3, 20),
        "total_market_value": Decimal("105000.00"),
        "total_cost": Decimal("100000.00"),
        "total_pnl": Decimal("5000.00"),
        "total_return_pct": Decimal("5.00"),
        "by_type": {
            "core": {
                "market_value": Decimal("31500.00"),
                "cost": Decimal("30000.00"),
                "pnl": Decimal("1500.00"),
                "return_pct": Decimal("5.00"),
            },
            "satellite": {
                "market_value": Decimal("73500.00"),
                "cost": Decimal("70000.00"),
                "pnl": Decimal("3500.00"),
                "return_pct": Decimal("5.00"),
            },
        },
        "holdings": [
            {
                "fund_code": "110011",
                "position_type": "core",
                "shares": Decimal("1000.0000"),
                "cost_price": Decimal("1.5000"),
                "current_nav": Decimal("1.5750"),
                "market_value": Decimal("1575.00"),
                "cost": Decimal("1500.00"),
                "pnl": Decimal("75.00"),
                "return_pct": Decimal("5.00"),
                "buy_date": date(2025, 1, 15),
                "holding_days": 429,
            },
            {
                "fund_code": "000001",
                "position_type": "satellite",
                "shares": Decimal("2000.0000"),
                "cost_price": Decimal("2.0000"),
                "current_nav": None,
                "market_value": Decimal("4000.00"),
                "cost": Decimal("4000.00"),
                "pnl": Decimal("0.00"),
                "return_pct": None,
                "buy_date": None,
                "holding_days": 0,
            },
        ],
    }
    return tracker


@pytest.fixture()
def mock_repo():
    """构造一个 mock FundRepository，返回预设的持仓和估值数据。"""
    repo = MagicMock()

    # 模拟活跃持仓
    pos1 = MagicMock()
    pos1.fund_code = "110011"
    pos2 = MagicMock()
    pos2.fund_code = "000001"
    repo.get_active_positions.return_value = [pos1, pos2]

    # 模拟估值数据
    est1 = MagicMock()
    est1.fund_code = "110011"
    est1.estimate_date = date(2026, 3, 20)
    est1.estimate_nav = Decimal("1.5800")
    est1.estimate_return = Decimal("0.32")
    est1.estimate_time = "15:00"
    est1.source = "akshare"

    est2 = MagicMock()
    est2.fund_code = "000001"
    est2.estimate_date = date(2026, 3, 20)
    est2.estimate_nav = Decimal("2.0100")
    est2.estimate_return = Decimal("0.50")
    est2.estimate_time = "14:55"
    est2.source = "eastmoney"

    repo.get_latest_estimates.return_value = [est1, est2]
    return repo


@pytest.fixture()
def client(mock_tracker, mock_repo):
    """创建注入了 mock 依赖的 TestClient。"""
    app.dependency_overrides[get_tracker] = lambda: mock_tracker
    app.dependency_overrides[get_repo] = lambda: mock_repo
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/dashboard/summary 测试
# ---------------------------------------------------------------------------

class TestDashboardSummary:
    """仪表盘摘要端点测试。"""

    def test_summary_success(self, client, mock_tracker):
        """正常返回完整摘要数据。"""
        resp = client.get("/api/dashboard/summary")
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        assert body["message"] == "success"

        data = body["data"]
        assert data["as_of"] == "2026-03-20"
        assert data["total_market_value"] == 105000.0
        assert data["total_cost"] == 100000.0
        assert data["total_pnl"] == 5000.0
        assert data["total_return_pct"] == 5.0

        # 校验 by_type
        assert "core" in data["by_type"]
        assert "satellite" in data["by_type"]
        core = data["by_type"]["core"]
        assert core["market_value"] == 31500.0
        assert core["return_pct"] == 5.0

        # 校验 holdings
        assert len(data["holdings"]) == 2
        h0 = data["holdings"][0]
        assert h0["fund_code"] == "110011"
        assert h0["position_type"] == "core"
        assert h0["current_nav"] == 1.575
        assert h0["buy_date"] == "2025-01-15"
        assert h0["holding_days"] == 429

        # 第二笔：current_nav 和 return_pct 可为 None
        h1 = data["holdings"][1]
        assert h1["fund_code"] == "000001"
        assert h1["current_nav"] is None
        assert h1["return_pct"] is None

    def test_summary_empty_portfolio(self, mock_repo):
        """空持仓时返回零值摘要。"""
        tracker = MagicMock()
        tracker.summary.return_value = {
            "as_of": date(2026, 3, 20),
            "total_market_value": Decimal("0"),
            "total_cost": Decimal("0"),
            "total_pnl": Decimal("0"),
            "total_return_pct": None,
            "by_type": {},
            "holdings": [],
        }
        app.dependency_overrides[get_tracker] = lambda: tracker
        app.dependency_overrides[get_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.get("/api/dashboard/summary")

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_market_value"] == 0.0
        assert data["total_return_pct"] is None
        assert data["holdings"] == []
        assert data["by_type"] == {}

        app.dependency_overrides.clear()

    def test_summary_tracker_error(self, mock_repo):
        """tracker 异常时返回错误码 500。"""
        tracker = MagicMock()
        tracker.summary.side_effect = RuntimeError("DB connection lost")
        app.dependency_overrides[get_tracker] = lambda: tracker
        app.dependency_overrides[get_repo] = lambda: mock_repo

        client = TestClient(app)
        resp = client.get("/api/dashboard/summary")

        assert resp.status_code == 200  # HTTP 200，业务码 500
        body = resp.json()
        assert body["code"] == 500
        assert "DB connection lost" in body["message"]

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/dashboard/estimates 测试
# ---------------------------------------------------------------------------

class TestDashboardEstimates:
    """盘中估值端点测试。"""

    def test_estimates_success(self, client, mock_repo):
        """正常返回估值列表。"""
        resp = client.get("/api/dashboard/estimates")
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert len(data) == 2

        e0 = data[0]
        assert e0["fund_code"] == "110011"
        assert e0["estimate_date"] == "2026-03-20"
        assert e0["estimate_nav"] == 1.58
        assert e0["estimate_return"] == 0.32
        assert e0["estimate_time"] == "15:00"
        assert e0["source"] == "akshare"

        e1 = data[1]
        assert e1["fund_code"] == "000001"
        assert e1["source"] == "eastmoney"

    def test_estimates_no_positions(self, mock_tracker):
        """无活跃持仓时返回空列表。"""
        repo = MagicMock()
        repo.get_active_positions.return_value = []
        app.dependency_overrides[get_tracker] = lambda: mock_tracker
        app.dependency_overrides[get_repo] = lambda: repo

        client = TestClient(app)
        resp = client.get("/api/dashboard/estimates")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"] == []

        app.dependency_overrides.clear()

    def test_estimates_repo_error(self, mock_tracker):
        """repo 异常时返回错误码 500。"""
        repo = MagicMock()
        repo.get_active_positions.side_effect = RuntimeError("DB error")
        app.dependency_overrides[get_tracker] = lambda: mock_tracker
        app.dependency_overrides[get_repo] = lambda: repo

        client = TestClient(app)
        resp = client.get("/api/dashboard/estimates")

        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 500
        assert "DB error" in body["message"]

        app.dependency_overrides.clear()

    def test_estimates_with_null_fund_code(self, mock_tracker):
        """持仓中 fund_code 为 None 时应被过滤掉。"""
        repo = MagicMock()
        pos1 = MagicMock()
        pos1.fund_code = "110011"
        pos_null = MagicMock()
        pos_null.fund_code = None
        repo.get_active_positions.return_value = [pos1, pos_null]
        repo.get_latest_estimates.return_value = []

        app.dependency_overrides[get_tracker] = lambda: mock_tracker
        app.dependency_overrides[get_repo] = lambda: repo

        client = TestClient(app)
        resp = client.get("/api/dashboard/estimates")

        assert resp.status_code == 200
        # 确认只用有效的 fund_code 调用了 get_latest_estimates
        repo.get_latest_estimates.assert_called_once_with(["110011"])

        app.dependency_overrides.clear()
