"""调仓建议 API 端点测试。

使用 FastAPI TestClient + dependency_overrides 模拟依赖。
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from fund_analyzer.api.deps import get_rebalance_advisor, get_repo, get_settings
from fund_analyzer.api.main import app
from fund_analyzer.config import Settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_repo():
    repo = MagicMock()
    fund1 = MagicMock()
    fund1.fund_code = "110011"
    fund2 = MagicMock()
    fund2.fund_code = "005827"
    repo.get_eligible_funds.return_value = [fund1, fund2]
    return repo


@pytest.fixture()
def mock_advisor():
    advisor = MagicMock()
    advisor.generate.return_value = {
        "as_of": date(2026, 3, 20),
        "actions": [
            {
                "fund_code": "110011",
                "position_type": "core",
                "action": "buy",
                "reason": "核心推荐新增",
            }
        ],
        "core_picks": [["110011", 85.5]],
        "satellite_picks": [["005827", 78.0]],
    }
    return advisor


@pytest.fixture()
def client(mock_repo, mock_advisor):
    app.dependency_overrides[get_repo] = lambda: mock_repo
    app.dependency_overrides[get_rebalance_advisor] = lambda: mock_advisor
    app.dependency_overrides[get_settings] = lambda: Settings()
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRebalance:
    def test_generate(self, client, mock_advisor):
        resp = client.post("/api/rebalance/generate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["as_of"] == "2026-03-20"
        assert len(body["data"]["actions"]) == 1
        assert body["data"]["actions"][0]["action"] == "buy"
        assert len(body["data"]["core_picks"]) == 1

    def test_generate_empty_universe(self, client, mock_repo):
        mock_repo.get_eligible_funds.return_value = []
        resp = client.post("/api/rebalance/generate")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["actions"] == []
