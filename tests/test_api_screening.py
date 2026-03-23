"""Screening API 端点测试。

使用 FastAPI TestClient + dependency_overrides 模拟依赖，无需真实数据库。
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from fund_analyzer.api.deps import get_composite, get_repo, get_settings
from fund_analyzer.api.main import app
from fund_analyzer.strategy.base import Signal


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
    return settings


@pytest.fixture()
def mock_repo():
    """构造 mock FundRepository。"""
    repo = MagicMock()
    repo.get_funds_with_nav.return_value = ["110011", "000001", "000002"]

    # 构造 eligible funds
    fund1 = MagicMock()
    fund1.fund_code = "110011"
    fund1.fund_name = "易方达沪深300"
    fund1.fund_type = "指数型"

    fund2 = MagicMock()
    fund2.fund_code = "000001"
    fund2.fund_name = "华夏成长"
    fund2.fund_type = "混合型"

    fund3 = MagicMock()
    fund3.fund_code = "000002"
    fund3.fund_name = "华夏回报"
    fund3.fund_type = "混合型"

    repo.get_eligible_funds.return_value = [fund1, fund2, fund3]

    # 费率数据
    fee1 = MagicMock()
    fee1.fee_type = "purchase"
    fee1.min_holding_days = 0
    fee1.max_holding_days = 0
    fee1.fee_rate = 0.0015
    fee1.min_amount = 0
    fee1.max_amount = None

    fee2 = MagicMock()
    fee2.fee_type = "redemption"
    fee2.min_holding_days = 0
    fee2.max_holding_days = 7
    fee2.fee_rate = 0.015
    fee2.min_amount = 0
    fee2.max_amount = None

    fee3 = MagicMock()
    fee3.fee_type = "redemption"
    fee3.min_holding_days = 7
    fee3.max_holding_days = 365
    fee3.fee_rate = 0.005
    fee3.min_amount = 0
    fee3.max_amount = None

    repo.get_fee_schedules.return_value = [fee1, fee2, fee3]
    return repo


@pytest.fixture()
def mock_composite():
    """构造 mock CompositeStrategy。"""
    composite = MagicMock()
    composite.score_satellite.return_value = {
        "110011": 85.5,
        "000001": 72.3,
        "000002": 68.1,
    }
    composite.score_core.return_value = {
        "110011": 90.0,
        "000001": 75.0,
        "000002": 60.0,
    }
    composite.signal.return_value = Signal(
        action="buy", confidence=0.85, reason="综合得分较高"
    )
    return composite


@pytest.fixture()
def client(mock_repo, mock_composite, mock_settings):
    """创建带有 mock 依赖的 TestClient。"""
    app.dependency_overrides[get_repo] = lambda: mock_repo
    app.dependency_overrides[get_composite] = lambda: mock_composite
    app.dependency_overrides[get_settings] = lambda: mock_settings
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/screening/score
# ---------------------------------------------------------------------------

class TestScreeningScore:
    """测试基金筛选评分端点。"""

    def test_score_satellite_default(self, client, mock_composite):
        """默认卫星仓位评分，返回 top_n 结果。"""
        resp = client.post("/api/screening/score", json={})
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        assert body["message"] == "success"

        data = body["data"]
        assert len(data) == 3  # 总共 3 只基金
        # 第一名应该是得分最高的 110011
        assert data[0]["fund_code"] == "110011"
        assert data[0]["score"] == 85.5
        assert data[0]["fund_name"] == "易方达沪深300"
        assert data[0]["action"] == "买入"
        assert data[0]["confidence"] == "85%"

        mock_composite.score_satellite.assert_called_once()

    def test_score_core(self, client, mock_composite):
        """核心仓位评分。"""
        resp = client.post(
            "/api/screening/score",
            json={"position_type": "core", "top_n": 2},
        )
        assert resp.status_code == 200

        body = resp.json()
        data = body["data"]
        assert len(data) == 2
        assert data[0]["fund_code"] == "110011"
        assert data[0]["score"] == 90.0

        mock_composite.score_core.assert_called_once()

    def test_score_top_n_limits_results(self, client):
        """top_n 限制返回数量。"""
        resp = client.post(
            "/api/screening/score",
            json={"top_n": 1},
        )
        body = resp.json()
        assert len(body["data"]) == 1

    def test_score_empty_fund_pool(self, client, mock_repo):
        """基金池为空时返回空列表。"""
        mock_repo.get_funds_with_nav.return_value = []
        resp = client.post("/api/screening/score", json={})
        body = resp.json()
        assert body["code"] == 0
        assert body["data"] == []

    def test_score_signal_failure_handled(self, client, mock_composite):
        """signal 调用失败时不影响整体结果，信号字段为 None。"""
        mock_composite.signal.side_effect = Exception("strategy error")
        resp = client.post("/api/screening/score", json={"top_n": 1})

        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert len(data) == 1
        assert data[0]["action"] is None
        assert data[0]["confidence"] is None
        assert data[0]["reason"] is None

    def test_score_sorted_descending(self, client):
        """结果按得分降序排列。"""
        resp = client.post("/api/screening/score", json={})
        body = resp.json()
        data = body["data"]
        scores = [item["score"] for item in data]
        assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# GET /api/screening/fees/{code}
# ---------------------------------------------------------------------------

class TestScreeningFees:
    """测试费率查询端点。"""

    def test_fees_success(self, client, mock_repo):
        """成功查询费率明细。"""
        resp = client.get("/api/screening/fees/110011")
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert len(data) == 3

        # 验证申购费
        purchase = data[0]
        assert purchase["fee_type"] == "purchase"
        assert purchase["fee_rate"] == 0.0015

        # 验证赎回费（短期）
        redeem_short = data[1]
        assert redeem_short["fee_type"] == "redemption"
        assert redeem_short["max_holding_days"] == 7
        assert redeem_short["fee_rate"] == 0.015

        mock_repo.get_fee_schedules.assert_called_once_with("110011")

    def test_fees_empty(self, client, mock_repo):
        """无费率数据时返回空列表。"""
        mock_repo.get_fee_schedules.return_value = []
        resp = client.get("/api/screening/fees/999999")

        body = resp.json()
        assert body["code"] == 0
        assert body["data"] == []

    def test_fees_repo_error(self, client, mock_repo):
        """Repository 异常时返回错误响应。"""
        mock_repo.get_fee_schedules.side_effect = Exception("DB error")
        resp = client.get("/api/screening/fees/110011")

        body = resp.json()
        assert body["code"] == 500
        assert "获取费率信息失败" in body["message"]
