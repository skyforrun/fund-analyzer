"""费率差异化测试。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundFeeSchedule
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


class TestUpsertFeeSchedule:
    def test_insert(self, repo, session):
        repo.upsert_fee_schedule("FEE001", [
            {"fee_type": "redemption", "min_holding_days": 0, "max_holding_days": 7, "fee_rate": Decimal("0.015000")},
            {"fee_type": "redemption", "min_holding_days": 7, "max_holding_days": 365, "fee_rate": Decimal("0.005000")},
            {"fee_type": "redemption", "min_holding_days": 365, "max_holding_days": 999999, "fee_rate": Decimal("0.000000")},
        ])
        stmt = select(FundFeeSchedule).where(FundFeeSchedule.fund_code == "FEE001")
        results = list(session.execute(stmt).scalars().all())
        assert len(results) == 3

    def test_upsert_purchase_multiple_amounts(self, repo, session):
        """多条不同金额区间的申购费率不应互相覆盖。"""
        repo.upsert_fee_schedule("FEE_P01", [
            {"fee_type": "purchase", "min_holding_days": 0, "min_amount": Decimal("0"),
             "max_amount": Decimal("1000000"), "fee_rate": Decimal("0.001500")},
            {"fee_type": "purchase", "min_holding_days": 0, "min_amount": Decimal("1000000"),
             "max_amount": Decimal("5000000"), "fee_rate": Decimal("0.001000")},
        ])
        stmt = select(FundFeeSchedule).where(
            FundFeeSchedule.fund_code == "FEE_P01",
            FundFeeSchedule.fee_type == "purchase",
        )
        results = list(session.execute(stmt).scalars().all())
        assert len(results) == 2


class TestGetFeeRate:
    def test_redemption_by_holding_days(self, repo, session):
        repo.upsert_fee_schedule("FEE002", [
            {"fee_type": "redemption", "min_holding_days": 0, "max_holding_days": 7, "fee_rate": Decimal("0.015000")},
            {"fee_type": "redemption", "min_holding_days": 7, "max_holding_days": 365, "fee_rate": Decimal("0.005000")},
            {"fee_type": "redemption", "min_holding_days": 365, "max_holding_days": 999999, "fee_rate": Decimal("0.000000")},
        ])

        rate_3d = repo.get_fee_rate("FEE002", "redemption", holding_days=3)
        assert rate_3d == Decimal("0.015000")

        rate_30d = repo.get_fee_rate("FEE002", "redemption", holding_days=30)
        assert rate_30d == Decimal("0.005000")

        rate_400d = repo.get_fee_rate("FEE002", "redemption", holding_days=400)
        assert rate_400d == Decimal("0.000000")

    def test_not_found_returns_none(self, repo):
        result = repo.get_fee_rate("NONEXIST", "purchase")
        assert result is None


class TestBacktestFeeIntegration:
    def test_get_sell_fee_rate_with_data(self, repo, session):
        """有费率数据时使用实际费率。"""
        repo.upsert_fee_schedule("BT001", [
            {"fee_type": "redemption", "min_holding_days": 0, "max_holding_days": 7, "fee_rate": Decimal("0.015000")},
            {"fee_type": "redemption", "min_holding_days": 7, "max_holding_days": 999999, "fee_rate": Decimal("0.001000")},
        ])
        rate = repo.get_fee_rate("BT001", "redemption", holding_days=3)
        assert rate == Decimal("0.015000")
        rate = repo.get_fee_rate("BT001", "redemption", holding_days=30)
        assert rate == Decimal("0.001000")

    def test_get_fee_rate_fallback(self, repo):
        """无费率数据时返回 None，由调用方使用默认值。"""
        rate = repo.get_fee_rate("NO_DATA", "redemption", holding_days=30)
        assert rate is None


class TestGetFeeSchedules:
    def test_returns_ordered_list(self, repo, session):
        repo.upsert_fee_schedule("SCHED01", [
            {"fee_type": "redemption", "min_holding_days": 7, "max_holding_days": 365, "fee_rate": Decimal("0.005000")},
            {"fee_type": "redemption", "min_holding_days": 0, "max_holding_days": 7, "fee_rate": Decimal("0.015000")},
            {"fee_type": "purchase", "min_holding_days": 0, "min_amount": Decimal("0"),
             "max_amount": Decimal("1000000"), "fee_rate": Decimal("0.001500")},
        ])
        schedules = repo.get_fee_schedules("SCHED01")
        assert len(schedules) == 3
        assert schedules[0].fee_type == "purchase"
        assert schedules[1].fee_type == "redemption"
        assert schedules[1].min_holding_days == 0

    def test_empty_returns_empty_list(self, repo):
        assert repo.get_fee_schedules("NONEXIST") == []


from fund_analyzer.data.fetcher import FundFetcher


class TestFetchFundFeeSchedule:
    def test_fetch_success(self, monkeypatch):
        import pandas as pd
        mock_df = pd.DataFrame([
            {"项目": "适用金额", "数据": "适用金额"},
            {"项目": "小于100万元", "数据": "0.15%"},
            {"项目": "大于等于100万元，小于500万元", "数据": "0.12%"},
            {"项目": "适用期限", "数据": "适用期限"},
            {"项目": "小于7天", "数据": "1.50%"},
            {"项目": "大于等于7天，小于365天", "数据": "0.50%"},
            {"项目": "大于等于365天", "数据": "0.00%"},
        ])
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_call_with_retry", lambda *a, **kw: mock_df)
        result = fetcher.fetch_fund_fee_schedule("110011")
        purchase = [r for r in result if r["fee_type"] == "purchase"]
        redemption = [r for r in result if r["fee_type"] == "redemption"]
        assert len(purchase) == 2
        assert len(redemption) == 3
        assert purchase[0]["fee_rate"] == Decimal("0.001500")

    def test_fetch_empty(self, monkeypatch):
        import pandas as pd
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_call_with_retry", lambda *a, **kw: pd.DataFrame())
        result = fetcher.fetch_fund_fee_schedule("999999")
        assert result == []

    def test_fetch_api_error(self, monkeypatch):
        def raise_error(*a, **kw):
            raise Exception("API error")
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_call_with_retry", raise_error)
        result = fetcher.fetch_fund_fee_schedule("999999")
        assert result == []

    def test_fetch_partial_parse_error(self, monkeypatch):
        """部分行解析失败时跳过，不影响其他行。"""
        import pandas as pd
        mock_df = pd.DataFrame([
            {"项目": "适用期限", "数据": "适用期限"},
            {"项目": "小于7天", "数据": "1.50%"},
            {"项目": "无法解析的行", "数据": "无效数据"},
            {"项目": "大于等于7天", "数据": "0.00%"},
        ])
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_call_with_retry", lambda *a, **kw: mock_df)
        result = fetcher.fetch_fund_fee_schedule("110011")
        assert len(result) == 2
