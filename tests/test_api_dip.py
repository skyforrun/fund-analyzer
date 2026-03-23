"""定投 API 端点测试。

使用 FastAPI TestClient + dependency_overrides 模拟依赖。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from fund_analyzer.api.deps import get_db_session, get_dip_manager
from fund_analyzer.api.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_dip_manager():
    mgr = MagicMock()
    mgr.list_plans.return_value = [
        {
            "id": 1,
            "fund_code": "110011",
            "amount": Decimal("1000.00"),
            "frequency": "monthly",
            "start_date": date(2026, 1, 1),
            "status": "active",
            "smart_dip": False,
        },
        {
            "id": 2,
            "fund_code": "005827",
            "amount": Decimal("500.00"),
            "frequency": "weekly",
            "start_date": date(2026, 2, 1),
            "status": "active",
            "smart_dip": True,
        },
    ]
    mgr.check_due.return_value = [
        {
            "plan_id": 1,
            "fund_code": "110011",
            "amount": Decimal("1000.00"),
            "smart_dip": False,
        }
    ]

    plan_obj = MagicMock()
    plan_obj.id = 3
    plan_obj.fund_code = "000001"
    plan_obj.amount = Decimal("2000.00")
    plan_obj.frequency = "monthly"
    plan_obj.start_date = date(2026, 3, 20)
    plan_obj.status = "active"
    plan_obj.smart_dip = False
    mgr.create_plan.return_value = plan_obj

    return mgr


@pytest.fixture()
def mock_session():
    return MagicMock()


@pytest.fixture()
def client(mock_dip_manager, mock_session):
    app.dependency_overrides[get_dip_manager] = lambda: mock_dip_manager
    app.dependency_overrides[get_db_session] = lambda: mock_session
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDipPlans:
    def test_list_plans(self, client, mock_dip_manager):
        resp = client.get("/api/dip/plans")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert len(body["data"]) == 2
        assert body["data"][0]["fund_code"] == "110011"
        assert body["data"][0]["amount"] == 1000.0

    def test_check_due(self, client, mock_dip_manager):
        resp = client.get("/api/dip/due")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert len(body["data"]) == 1
        assert body["data"][0]["plan_id"] == 1

    def test_create_plan(self, client, mock_dip_manager, mock_session):
        resp = client.post("/api/dip/plans", json={
            "fund_code": "000001",
            "amount": 2000.0,
            "frequency": "monthly",
            "smart": False,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["id"] == 3
        assert body["data"]["fund_code"] == "000001"
        mock_dip_manager.create_plan.assert_called_once()
        mock_session.commit.assert_called_once()

    def test_pause_plan(self, client, mock_dip_manager, mock_session):
        resp = client.post("/api/dip/plans/1/pause")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        mock_dip_manager.pause_plan.assert_called_once_with(1)
        mock_session.commit.assert_called_once()

    def test_resume_plan(self, client, mock_dip_manager, mock_session):
        resp = client.post("/api/dip/plans/1/resume")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        mock_dip_manager.resume_plan.assert_called_once_with(1)

    def test_stop_plan(self, client, mock_dip_manager, mock_session):
        resp = client.post("/api/dip/plans/1/stop")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        mock_dip_manager.stop_plan.assert_called_once_with(1)

    def test_pause_plan_not_found(self, client, mock_dip_manager):
        mock_dip_manager.pause_plan.side_effect = ValueError("定投计划不存在：plan_id=999")
        resp = client.post("/api/dip/plans/999/pause")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 404
