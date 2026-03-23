"""风险评估 API 端点测试。

使用 FastAPI TestClient + dependency_overrides 模拟依赖。
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from fund_analyzer.api.deps import get_db_session, get_repo
from fund_analyzer.api.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_repo():
    repo = MagicMock()
    profile = MagicMock()
    profile.id = 1
    profile.risk_level = 3
    profile.risk_label = "平衡型"
    profile.core_ratio = 30
    profile.satellite_ratio = 70
    profile.assessment_date = date(2026, 3, 20)
    profile.answers = {"experience": 15, "loss_tolerance": 15}
    repo.get_latest_risk_profile.return_value = profile

    def fake_save(data):
        saved = MagicMock()
        saved.id = 2
        saved.risk_level = data["risk_level"]
        saved.risk_label = data["risk_label"]
        saved.core_ratio = data["core_ratio"]
        saved.satellite_ratio = data["satellite_ratio"]
        saved.assessment_date = data["assessment_date"]
        saved.answers = data["answers"]
        return saved

    repo.save_risk_profile.side_effect = fake_save
    return repo


@pytest.fixture()
def mock_session():
    return MagicMock()


@pytest.fixture()
def client(mock_repo, mock_session):
    app.dependency_overrides[get_repo] = lambda: mock_repo
    app.dependency_overrides[get_db_session] = lambda: mock_session
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRisk:
    def test_get_questions(self, client):
        resp = client.get("/api/risk/questions")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 5
        assert body["data"][0]["id"] == "experience"

    def test_get_profile(self, client):
        resp = client.get("/api/risk/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["risk_level"] == 3
        assert body["data"]["risk_label"] == "平衡型"

    def test_get_profile_none(self, client, mock_repo):
        mock_repo.get_latest_risk_profile.return_value = None
        resp = client.get("/api/risk/profile")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"] is None

    def test_assess(self, client, mock_session):
        answers = {
            "experience": 15,
            "loss_tolerance": 15,
            "investment_horizon": 15,
            "income_stability": 10,
            "investment_goal": 10,
        }
        resp = client.post("/api/risk/assess", json={"answers": answers})
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        # Total score = 65, level = 3 (平衡型)
        assert body["data"]["risk_level"] == 3
        assert body["data"]["risk_label"] == "平衡型"
        assert body["data"]["core_ratio"] == 30
        assert body["data"]["satellite_ratio"] == 70
        mock_session.commit.assert_called_once()
