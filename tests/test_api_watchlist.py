"""Watchlist API 端点测试。

使用 FastAPI TestClient + dependency_overrides 模拟依赖，无需真实数据库。
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from fund_analyzer.api.deps import get_db_session, get_repo
from fund_analyzer.api.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_session():
    """构造一个 mock Session。"""
    return MagicMock()


@pytest.fixture()
def mock_repo():
    """构造一个 mock FundRepository。"""
    repo = MagicMock()

    # 默认 get_watchlist 返回值
    item1 = MagicMock()
    item1.id = 1
    item1.fund_code = "110011"
    item1.fund_name = "易方达中小盘"
    item1.group_name = "核心"
    item1.notes = "长期持有"
    item1.added_at = datetime(2026, 1, 10, 9, 30, 0)

    item2 = MagicMock()
    item2.id = 2
    item2.fund_code = "000001"
    item2.fund_name = "华夏成长"
    item2.group_name = "默认"
    item2.notes = ""
    item2.added_at = datetime(2026, 2, 15, 14, 0, 0)

    repo.get_watchlist.return_value = [item1, item2]
    repo.get_watchlist_groups.return_value = ["核心", "默认"]
    repo.remove_from_watchlist.return_value = 1

    return repo


@pytest.fixture()
def client(mock_session, mock_repo):
    """创建注入了 mock 依赖的 TestClient。"""
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_repo] = lambda: mock_repo
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/watchlist
# ---------------------------------------------------------------------------

class TestGetWatchlist:
    """自选列表查询端点测试。"""

    def test_get_watchlist_success(self, client):
        """正常返回自选列表。"""
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert len(data) == 2

        assert data[0]["id"] == 1
        assert data[0]["fund_code"] == "110011"
        assert data[0]["fund_name"] == "易方达中小盘"
        assert data[0]["group_name"] == "核心"
        assert data[0]["notes"] == "长期持有"

        assert data[1]["fund_code"] == "000001"
        assert data[1]["group_name"] == "默认"

    def test_get_watchlist_with_group(self, client, mock_repo):
        """带 group_name 参数查询。"""
        resp = client.get("/api/watchlist?group_name=核心")
        assert resp.status_code == 200
        mock_repo.get_watchlist.assert_called_with(group_name="核心")

    def test_get_watchlist_empty(self, mock_session):
        """空自选列表返回空数组。"""
        repo = MagicMock()
        repo.get_watchlist.return_value = []
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_repo] = lambda: repo

        c = TestClient(app)
        resp = c.get("/api/watchlist")
        assert resp.json()["data"] == []

        app.dependency_overrides.clear()

    def test_get_watchlist_error(self, mock_session):
        """repo 异常时返回 500 业务码。"""
        repo = MagicMock()
        repo.get_watchlist.side_effect = RuntimeError("db error")
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_repo] = lambda: repo

        c = TestClient(app)
        resp = c.get("/api/watchlist")
        assert resp.json()["code"] == 500
        assert "db error" in resp.json()["message"]

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# GET /api/watchlist/groups
# ---------------------------------------------------------------------------

class TestGetWatchlistGroups:
    """自选分组查询端点测试。"""

    def test_groups_success(self, client):
        """正常返回分组列表。"""
        resp = client.get("/api/watchlist/groups")
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        assert body["data"] == ["核心", "默认"]

    def test_groups_empty(self, mock_session):
        """无分组时返回空列表。"""
        repo = MagicMock()
        repo.get_watchlist_groups.return_value = []
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_repo] = lambda: repo

        c = TestClient(app)
        resp = c.get("/api/watchlist/groups")
        assert resp.json()["data"] == []

        app.dependency_overrides.clear()

    def test_groups_error(self, mock_session):
        """异常时返回 500 业务码。"""
        repo = MagicMock()
        repo.get_watchlist_groups.side_effect = RuntimeError("fail")
        app.dependency_overrides[get_db_session] = lambda: mock_session
        app.dependency_overrides[get_repo] = lambda: repo

        c = TestClient(app)
        resp = c.get("/api/watchlist/groups")
        assert resp.json()["code"] == 500

        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/watchlist
# ---------------------------------------------------------------------------

class TestAddWatchlist:
    """添加自选端点测试。"""

    def test_add_success(self, client, mock_repo, mock_session):
        """正常添加自选基金。"""
        created = MagicMock()
        created.id = 3
        created.fund_code = "519003"
        created.fund_name = "海富通收益"
        created.group_name = "默认"
        created.notes = "观察中"
        created.added_at = datetime(2026, 3, 20, 10, 0, 0)
        mock_repo.add_to_watchlist.return_value = created

        resp = client.post("/api/watchlist", json={
            "fund_code": "519003",
            "fund_name": "海富通收益",
            "group_name": "默认",
            "notes": "观察中",
        })
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        data = body["data"]
        assert data["id"] == 3
        assert data["fund_code"] == "519003"
        assert data["fund_name"] == "海富通收益"
        assert data["group_name"] == "默认"
        assert data["notes"] == "观察中"

        mock_repo.add_to_watchlist.assert_called_once_with(
            fund_code="519003",
            fund_name="海富通收益",
            group_name="默认",
            notes="观察中",
        )
        mock_session.commit.assert_called_once()

    def test_add_default_values(self, client, mock_repo, mock_session):
        """使用默认值添加自选。"""
        created = MagicMock()
        created.id = 4
        created.fund_code = "000001"
        created.fund_name = ""
        created.group_name = "默认"
        created.notes = ""
        created.added_at = datetime(2026, 3, 20, 10, 0, 0)
        mock_repo.add_to_watchlist.return_value = created

        resp = client.post("/api/watchlist", json={
            "fund_code": "000001",
        })
        assert resp.status_code == 200
        mock_repo.add_to_watchlist.assert_called_once_with(
            fund_code="000001",
            fund_name="",
            group_name="默认",
            notes="",
        )

    def test_add_error(self, client, mock_repo):
        """添加异常时返回 500 业务码。"""
        mock_repo.add_to_watchlist.side_effect = RuntimeError("duplicate")
        resp = client.post("/api/watchlist", json={
            "fund_code": "110011",
        })
        assert resp.json()["code"] == 500
        assert "duplicate" in resp.json()["message"]


# ---------------------------------------------------------------------------
# DELETE /api/watchlist/{code}
# ---------------------------------------------------------------------------

class TestRemoveWatchlist:
    """移除自选端点测试。"""

    def test_remove_success(self, client, mock_repo, mock_session):
        """正常移除自选基金。"""
        resp = client.delete("/api/watchlist/110011")
        assert resp.status_code == 200

        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["removed"] == 1

        mock_repo.remove_from_watchlist.assert_called_once_with("110011", group_name=None)
        mock_session.commit.assert_called_once()

    def test_remove_with_group(self, client, mock_repo, mock_session):
        """带 group_name 参数移除。"""
        resp = client.delete("/api/watchlist/110011?group_name=核心")
        assert resp.status_code == 200
        mock_repo.remove_from_watchlist.assert_called_once_with("110011", group_name="核心")

    def test_remove_not_found(self, client, mock_repo, mock_session):
        """移除不存在的基金返回 removed=0。"""
        mock_repo.remove_from_watchlist.return_value = 0
        resp = client.delete("/api/watchlist/999999")
        assert resp.json()["data"]["removed"] == 0

    def test_remove_error(self, client, mock_repo):
        """异常时返回 500 业务码。"""
        mock_repo.remove_from_watchlist.side_effect = RuntimeError("fail")
        resp = client.delete("/api/watchlist/110011")
        assert resp.json()["code"] == 500
