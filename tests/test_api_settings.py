"""系统设置 API 端点测试。

使用 FastAPI TestClient + dependency_overrides 模拟依赖。
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from fund_analyzer.api.deps import get_db_session, get_repo, get_settings, get_syncer
from fund_analyzer.api.main import app
from fund_analyzer.config import Settings


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def mock_repo():
    repo = MagicMock()

    # NotificationConfig
    config = MagicMock()
    config.id = 1
    config.channel = "wechat"
    config.webhook_url = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test"
    config.enabled = True
    config.updated_at = datetime(2026, 3, 20, 10, 0, 0)
    repo.get_notification_config.return_value = config

    def fake_save_config(webhook_url, enabled):
        saved = MagicMock()
        saved.id = 1
        saved.channel = "wechat"
        saved.webhook_url = webhook_url
        saved.enabled = enabled
        saved.updated_at = datetime(2026, 3, 20, 10, 0, 0)
        return saved

    repo.save_notification_config.side_effect = fake_save_config

    # NotificationRules
    rule1 = MagicMock()
    rule1.id = 1
    rule1.rule_type = "dip_reminder"
    rule1.params = None
    rule1.enabled = True

    rule2 = MagicMock()
    rule2.id = 2
    rule2.rule_type = "drop_alert"
    rule2.params = {"threshold": -3.0}
    rule2.enabled = True

    repo.get_notification_rules.return_value = [rule1, rule2]

    def fake_save_rule(rule_type, params, enabled):
        obj = MagicMock()
        obj.id = 10
        obj.rule_type = rule_type
        obj.params = params
        obj.enabled = enabled
        return obj

    repo.save_notification_rule.side_effect = fake_save_rule

    return repo


@pytest.fixture()
def mock_session():
    return MagicMock()


@pytest.fixture()
def mock_syncer():
    syncer = MagicMock()
    syncer.sync_all.return_value = {
        "funds": 100,
        "navs": 5000,
        "indices": 20,
        "estimates": 50,
        "fee_schedules": 200,
        "warnings": [],
    }
    return syncer


@pytest.fixture()
def client(mock_repo, mock_session, mock_syncer):
    app.dependency_overrides[get_repo] = lambda: mock_repo
    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_syncer] = lambda: mock_syncer
    app.dependency_overrides[get_settings] = lambda: Settings()
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSettingsConfig:
    def test_get_config(self, client):
        resp = client.get("/api/settings/config")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "database" in body["data"]
        # 密码应被隐藏
        assert body["data"]["database"]["password"] == "***"
        assert "strategy" in body["data"]


class TestNotification:
    def test_get_notification(self, client):
        resp = client.get("/api/settings/notification")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["channel"] == "wechat"
        assert body["data"]["enabled"] is True

    def test_get_notification_none(self, client, mock_repo):
        mock_repo.get_notification_config.return_value = None
        resp = client.get("/api/settings/notification")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"] is None

    def test_save_notification(self, client, mock_session):
        resp = client.put("/api/settings/notification", json={
            "webhook_url": "https://example.com/webhook",
            "enabled": True,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert body["data"]["webhook_url"] == "https://example.com/webhook"
        mock_session.commit.assert_called_once()

    def test_get_notification_rules(self, client):
        resp = client.get("/api/settings/notification/rules")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert len(body["data"]) == 2
        assert body["data"][0]["rule_type"] == "dip_reminder"

    def test_save_notification_rules(self, client, mock_session):
        resp = client.put("/api/settings/notification/rules", json=[
            {"rule_type": "dip_reminder", "enabled": True},
            {"rule_type": "drop_alert", "params": {"threshold": -5.0}, "enabled": False},
        ])
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert len(body["data"]) == 2
        mock_session.commit.assert_called_once()

    @patch("fund_analyzer.api.routers.settings.WeChatSender")
    def test_notification_test_success(self, mock_sender_cls, client, mock_repo):
        mock_sender_instance = MagicMock()
        mock_sender_instance.test.return_value = True
        mock_sender_cls.return_value = mock_sender_instance

        resp = client.post("/api/settings/notification/test")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 0
        assert "成功" in body["message"]

    def test_notification_test_no_config(self, client, mock_repo):
        mock_repo.get_notification_config.return_value = None
        resp = client.post("/api/settings/notification/test")
        assert resp.status_code == 200
        body = resp.json()
        assert body["code"] == 400


class TestSyncStream:
    def test_sync_stream(self, client, mock_syncer):
        """测试 SSE 同步端点返回 event-stream 并以 done 事件结束。"""
        resp = client.get("/api/settings/sync/stream")
        assert resp.status_code == 200
        # SSE 返回 text/event-stream
        assert "text/event-stream" in resp.headers.get("content-type", "")
        # 应该包含 done 事件
        text = resp.text
        assert "event: done" in text
