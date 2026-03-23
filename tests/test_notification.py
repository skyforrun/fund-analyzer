"""消息提醒测试。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import (
    Base, DipPlan, FundEstimate, FundWatchlist,
    NotificationConfig, NotificationRule,
)
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.notification.sender import WeChatSender
from fund_analyzer.notification.checker import NotificationChecker


@pytest.fixture(scope="module")
def engine():
    _engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)
    _engine.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()


@pytest.fixture()
def repo(session):
    return FundRepository(session)


class TestWeChatSender:
    def test_send_success(self, monkeypatch):
        sender = WeChatSender("https://example.com/webhook")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0}
        mock_resp.raise_for_status = MagicMock()
        monkeypatch.setattr("fund_analyzer.notification.sender.requests.post", lambda *a, **kw: mock_resp)

        assert sender.send("标题", "内容") is True

    def test_send_failure(self, monkeypatch):
        sender = WeChatSender("https://example.com/webhook")
        monkeypatch.setattr(
            "fund_analyzer.notification.sender.requests.post",
            MagicMock(side_effect=Exception("network error")),
        )
        assert sender.send("标题", "内容") is False


class TestNotificationChecker:
    def test_check_dip_due(self, repo, session):
        today = date.today()
        session.add(DipPlan(
            fund_code="DIP001",
            amount=Decimal("1000"),
            frequency="weekly",
            start_date=today,
            status="active",
            smart_dip=False,
        ))
        session.flush()

        sender = MagicMock()
        sender.send = MagicMock(return_value=True)
        checker = NotificationChecker(repo, sender)
        count = checker.check_dip_due()
        assert count == 1
        sender.send.assert_called_once()

    def test_check_drop_alert(self, repo, session):
        session.add(FundWatchlist(
            fund_code="DROP001", fund_name="跌基", group_name="默认",
            added_at=datetime.now(),
        ))
        session.add(FundEstimate(
            fund_code="DROP001", estimate_date=date.today(),
            estimate_return=Decimal("-5.00"),
        ))
        session.flush()

        sender = MagicMock()
        sender.send = MagicMock(return_value=True)
        checker = NotificationChecker(repo, sender)
        count = checker.check_drop_alert(threshold=-3.0)
        assert count == 1
        sender.send.assert_called_once()
