"""自选关注列表测试。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundWatchlist
from fund_analyzer.data.repository import FundRepository


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


class TestAddToWatchlist:
    def test_add_new(self, repo, session):
        result = repo.add_to_watchlist("110011", "易方达蓝筹精选")
        assert result.fund_code == "110011"
        assert result.group_name == "默认"

    def test_duplicate_updates_notes(self, repo):
        repo.add_to_watchlist("DUP001", "基金A", notes="旧备注")
        repo.add_to_watchlist("DUP001", "基金A", notes="新备注")
        items = repo.get_watchlist()
        matching = [w for w in items if w.fund_code == "DUP001"]
        assert len(matching) == 1
        assert matching[0].notes == "新备注"

    def test_different_groups(self, repo):
        repo.add_to_watchlist("GRP001", "基金B", group_name="核心观察")
        repo.add_to_watchlist("GRP001", "基金B", group_name="待买入")
        items = repo.get_watchlist()
        matching = [w for w in items if w.fund_code == "GRP001"]
        assert len(matching) == 2


class TestRemoveFromWatchlist:
    def test_remove_all_groups(self, repo):
        repo.add_to_watchlist("RM001", "基金C", group_name="A")
        repo.add_to_watchlist("RM001", "基金C", group_name="B")
        count = repo.remove_from_watchlist("RM001")
        assert count == 2

    def test_remove_specific_group(self, repo):
        repo.add_to_watchlist("RM002", "基金D", group_name="A")
        repo.add_to_watchlist("RM002", "基金D", group_name="B")
        count = repo.remove_from_watchlist("RM002", group_name="A")
        assert count == 1
        remaining = repo.get_watchlist()
        matching = [w for w in remaining if w.fund_code == "RM002"]
        assert len(matching) == 1
        assert matching[0].group_name == "B"


class TestGetWatchlistGroups:
    def test_returns_groups(self, repo):
        repo.add_to_watchlist("G001", "基金", group_name="核心")
        repo.add_to_watchlist("G002", "基金", group_name="卫星")
        groups = repo.get_watchlist_groups()
        assert "核心" in groups
        assert "卫星" in groups
