"""Portfolio API 端点测试。

使用 FastAPI TestClient + dependency_overrides 模拟依赖，无需真实数据库。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from fund_analyzer.api.deps import get_db_session, get_manager, get_repo, get_tracker
from fund_analyzer.api.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_session():
    """构造一个 mock Session。"""
    return MagicMock()


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
def mock_manager():
    """构造一个 mock PortfolioManager。"""
    manager = MagicMock()
    # 默认 get_holdings 返回值
    manager.get_holdings.return_value = [
        {
            "fund_code": "110011",
            "fund_name": "易方达中小盘",
            "position_type": "core",
            "shares": Decimal("1000.0000"),
            "cost_price": Decimal("1.5000"),
            "buy_date": date(2025, 1, 15),
        },
    ]
    return manager


@pytest.fixture()
def mock_repo():
    """构造一个 mock FundRepository。"""
    repo = MagicMock()
    repo.get_dividends.return_value = []
    repo.get_fee_rate.return_value = None
    return repo


@pytest.fixture()
def client(mock_session, mock_tracker, mock_manager, mock_repo):
    """创建注入了 mock 依赖的 TestClient。"""
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_tracker] = lambda: mock_tracker
    app.dependency_overrides[get_manager] = lambda: mock_manager
    app.dependency_overrides[get_repo] = lambda: mock_repo
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/portfolio/summary
# ---------------------------------------------------------------------------

class TestPortfolioSummary:
    """持仓概览端点测试。"""

    def test_summary_success(self, client):
        """正常返回持仓概览。"""
        resp = client.get("/api/portfolio/summary")
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["as_of"] == "2026-03-20"
        assert data["total_market_value"] == 105000.0
        assert data["total_pnl"] == 5000.0
        assert "core" in data["by_type"]
        assert len(data["holdings"]) == 2

    def test_summary_error(self, mock_session, mock_manager, mock_repo):
        """tracker 异常时返回 500 业务码。"""
        tracker = MagicMock()
        tracker.summary.side_effect = RuntimeError("db error")
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_tracker] = lambda: tracker
        app.dependency_overrides[get_manager] = lambda: mock_manager
        app.dependency_overrides[get_repo] = lambda: mock_repo

        c = TestClient(app)
        resp = c.get("/api/portfolio/summary")
        assert resp.status_code == 200
        assert resp.json()["code"] == 500
        assert "db error" in resp.json()["message"]

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/portfolio/holdings
# ---------------------------------------------------------------------------

class TestPortfolioHoldings:
    """持仓列表端点测试。"""

    def test_holdings_success(self, client, mock_manager):
        """正常返回持仓列表。"""
        resp = client.get("/api/portfolio/holdings")
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        items = body["data"]
        assert len(items) == 1
        assert items[0]["fund_code"] == "110011"
        assert items[0]["fund_name"] == "易方达中小盘"
        assert items[0]["shares"] == 1000.0
        assert items[0]["buy_date"] == "2025-01-15"

    def test_holdings_with_position_type(self, client, mock_manager):
        """带 position_type 参数查询。"""
        resp = client.get("/api/portfolio/holdings?position_type=core")
        assert resp.status_code == 200
        mock_manager.get_holdings.assert_called_with(position_type="core")

    def test_holdings_empty(self, mock_session, mock_tracker, mock_repo):
        """空持仓返回空列表。"""
        manager = MagicMock()
        manager.get_holdings.return_value = []
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_tracker] = lambda: mock_tracker
        app.dependency_overrides[get_manager] = lambda: manager
        app.dependency_overrides[get_repo] = lambda: mock_repo

        c = TestClient(app)
        resp = c.get("/api/portfolio/holdings")
        assert resp.json()["data"] == []

        app.dependency_overrides.clear()

    def test_holdings_error(self, mock_session, mock_tracker, mock_repo):
        """manager 异常时返回 500 业务码。"""
        manager = MagicMock()
        manager.get_holdings.side_effect = RuntimeError("fail")
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_tracker] = lambda: mock_tracker
        app.dependency_overrides[get_manager] = lambda: manager
        app.dependency_overrides[get_repo] = lambda: mock_repo

        c = TestClient(app)
        resp = c.get("/api/portfolio/holdings")
        assert resp.json()["code"] == 500

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/portfolio/buy
# ---------------------------------------------------------------------------

class TestPortfolioBuy:
    """买入端点测试。"""

    def test_buy_success(self, client, mock_manager, mock_session):
        """正常买入并返回结果。"""
        position = MagicMock()
        position.fund_code = "110011"
        position.shares = Decimal("666.6667")
        position.cost_price = Decimal("1.5000")
        mock_manager.buy.return_value = position

        resp = client.post("/api/portfolio/buy", json={
            "fund_code": "110011",
            "amount": 1000.0,
            "nav": 1.5,
            "position_type": "core",
        })
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["fund_code"] == "110011"
        assert body["data"]["shares"] == 666.6667

        mock_manager.buy.assert_called_once_with(
            fund_code="110011",
            amount=1000.0,
            nav=1.5,
            position_type="core",
        )
        mock_session.commit.assert_called_once()

    def test_buy_default_position_type(self, client, mock_manager, mock_session):
        """不传 position_type 默认为 satellite。"""
        position = MagicMock()
        position.fund_code = "000001"
        position.shares = Decimal("500")
        position.cost_price = Decimal("2.0")
        mock_manager.buy.return_value = position

        resp = client.post("/api/portfolio/buy", json={
            "fund_code": "000001",
            "amount": 1000.0,
            "nav": 2.0,
        })
        assert resp.status_code == 200
        mock_manager.buy.assert_called_once_with(
            fund_code="000001",
            amount=1000.0,
            nav=2.0,
            position_type="satellite",
        )

    def test_buy_error(self, client, mock_manager):
        """买入异常时返回 500 业务码。"""
        mock_manager.buy.side_effect = ValueError("余额不足")
        resp = client.post("/api/portfolio/buy", json={
            "fund_code": "110011",
            "amount": 1000.0,
            "nav": 1.5,
        })
        assert resp.json()["code"] == 500
        assert "余额不足" in resp.json()["message"]


# ---------------------------------------------------------------------------
# POST /api/portfolio/sell
# ---------------------------------------------------------------------------

class TestPortfolioSell:
    """卖出端点测试。"""

    def test_sell_success(self, client, mock_manager, mock_session):
        """正常卖出并返回结果。"""
        resp = client.post("/api/portfolio/sell", json={
            "fund_code": "110011",
            "shares": 500.0,
            "nav": 1.6,
        })
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["fund_code"] == "110011"
        assert body["data"]["shares_sold"] == 500.0

        mock_manager.sell.assert_called_once_with(
            fund_code="110011",
            shares=500.0,
            nav=1.6,
        )
        mock_session.commit.assert_called_once()

    def test_sell_error(self, client, mock_manager):
        """卖出异常时返回 500 业务码。"""
        mock_manager.sell.side_effect = ValueError("份额不足")
        resp = client.post("/api/portfolio/sell", json={
            "fund_code": "110011",
            "shares": 99999.0,
            "nav": 1.5,
        })
        assert resp.json()["code"] == 500
        assert "份额不足" in resp.json()["message"]


# ---------------------------------------------------------------------------
# GET /api/portfolio/dividends
# ---------------------------------------------------------------------------

class TestPortfolioDividends:
    """分红记录端点测试。"""

    def test_dividends_success(self, client, mock_repo):
        """正常返回分红记录。"""
        div1 = MagicMock()
        div1.fund_code = "110011"
        div1.ex_date = date(2025, 12, 15)
        div1.dividend_per_unit = Decimal("0.15")
        div1.dividend_type = "现金分红"

        div2 = MagicMock()
        div2.fund_code = "110011"
        div2.ex_date = date(2025, 6, 10)
        div2.dividend_per_unit = Decimal("0.10")
        div2.dividend_type = "红利再投"

        mock_repo.get_dividends.return_value = [div1, div2]

        resp = client.get("/api/portfolio/dividends")
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        # 两只持仓基金，第一只返回2条分红，第二只返回2条(同mock)
        # mock_repo.get_dividends 会被调用两次（两只持仓）
        data = body["data"]
        assert len(data) >= 2
        assert data[0]["fund_code"] == "110011"
        assert data[0]["ex_date"] == "2025-12-15"
        assert data[0]["dividend_per_unit"] == 0.15
        assert data[0]["dividend_type"] == "现金分红"

    def test_dividends_no_holdings(self, mock_session, mock_manager, mock_repo):
        """无持仓时返回空分红列表。"""
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
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_tracker] = lambda: tracker
        app.dependency_overrides[get_manager] = lambda: mock_manager
        app.dependency_overrides[get_repo] = lambda: mock_repo

        c = TestClient(app)
        resp = c.get("/api/portfolio/dividends")
        assert resp.json()["data"] == []

        app.dependency_overrides.clear()

    def test_dividends_error(self, mock_session, mock_manager, mock_repo):
        """tracker 异常时返回 500 业务码。"""
        tracker = MagicMock()
        tracker.summary.side_effect = RuntimeError("db error")
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_tracker] = lambda: tracker
        app.dependency_overrides[get_manager] = lambda: mock_manager
        app.dependency_overrides[get_repo] = lambda: mock_repo

        c = TestClient(app)
        resp = c.get("/api/portfolio/dividends")
        assert resp.json()["code"] == 500

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/portfolio/fee-rate
# ---------------------------------------------------------------------------

class TestPortfolioFeeRate:
    """赎回费率端点测试。"""

    def test_fee_rate_success(self, client, mock_repo):
        """正常返回赎回费率。"""
        # 第一只基金有费率，第二只为 None
        mock_repo.get_fee_rate.side_effect = [Decimal("0.005"), None]

        resp = client.get("/api/portfolio/fee-rate")
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert len(data) == 2

        assert data[0]["fund_code"] == "110011"
        assert data[0]["holding_days"] == 429
        assert data[0]["fee_rate"] == 0.005

        assert data[1]["fund_code"] == "000001"
        assert data[1]["holding_days"] == 0
        assert data[1]["fee_rate"] is None

    def test_fee_rate_error(self, mock_session, mock_manager, mock_repo):
        """异常时返回 500 业务码。"""
        tracker = MagicMock()
        tracker.summary.side_effect = RuntimeError("fail")
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_tracker] = lambda: tracker
        app.dependency_overrides[get_manager] = lambda: mock_manager
        app.dependency_overrides[get_repo] = lambda: mock_repo

        c = TestClient(app)
        resp = c.get("/api/portfolio/fee-rate")
        assert resp.json()["code"] == 500

        app.dependency_overrides.clear()
