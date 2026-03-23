"""实时估值功能测试。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundEstimate
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


class TestFundEstimateModel:
    def test_create(self, session):
        est = FundEstimate(
            fund_code="110011",
            estimate_date=date(2026, 3, 20),
            estimate_nav=Decimal("2.3456"),
            estimate_return=Decimal("1.23"),
            estimate_time="14:30",
            source="akshare",
            updated_at=datetime.now(),
        )
        session.add(est)
        session.flush()
        result = session.get(FundEstimate, ("110011", date(2026, 3, 20)))
        assert result is not None
        assert result.estimate_nav == Decimal("2.3456")


class TestUpsertEstimate:
    def test_insert_new(self, repo, session):
        repo.upsert_estimate({
            "fund_code": "EST001",
            "estimate_date": date(2026, 3, 20),
            "estimate_nav": Decimal("1.5000"),
            "estimate_return": Decimal("0.50"),
            "estimate_time": "14:00",
            "source": "akshare",
        })
        result = session.get(FundEstimate, ("EST001", date(2026, 3, 20)))
        assert result is not None
        assert result.estimate_nav == Decimal("1.5000")

    def test_update_existing(self, repo, session):
        session.add(FundEstimate(
            fund_code="EST002",
            estimate_date=date(2026, 3, 20),
            estimate_nav=Decimal("1.0000"),
        ))
        session.flush()
        repo.upsert_estimate({
            "fund_code": "EST002",
            "estimate_date": date(2026, 3, 20),
            "estimate_nav": Decimal("1.1000"),
            "estimate_return": Decimal("10.00"),
        })
        session.expire_all()
        result = session.get(FundEstimate, ("EST002", date(2026, 3, 20)))
        assert result.estimate_nav == Decimal("1.1000")


class TestGetLatestEstimates:
    def test_returns_latest(self, repo, session):
        session.add_all([
            FundEstimate(fund_code="LAT001", estimate_date=date(2026, 3, 19), estimate_nav=Decimal("1.0")),
            FundEstimate(fund_code="LAT001", estimate_date=date(2026, 3, 20), estimate_nav=Decimal("1.1")),
        ])
        session.flush()
        results = repo.get_latest_estimates(["LAT001"])
        assert len(results) == 1
        assert results[0].estimate_date == date(2026, 3, 20)

    def test_empty_codes(self, repo):
        assert repo.get_latest_estimates([]) == []


from fund_analyzer.data.fetcher import FundFetcher


class TestFetchFundEstimate:
    def test_akshare_success(self, monkeypatch):
        import pandas as pd
        mock_df = pd.DataFrame([{
            "净值日期": "2026-03-20",
            "单位净值": 2.345,
            "日增长率": 1.23,
        }])
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_call_with_retry", lambda *a, **kw: mock_df)

        result = fetcher.fetch_fund_estimate("110011")
        assert result is not None
        assert result["source"] == "akshare"
        assert result["estimate_nav"] == 2.345

    def test_both_fail_returns_none(self, monkeypatch):
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_fetch_estimate_akshare", lambda code: None)
        monkeypatch.setattr(fetcher, "_fetch_estimate_eastmoney", lambda code: None)

        result = fetcher.fetch_fund_estimate("999999")
        assert result is None

    def test_batch(self, monkeypatch):
        fetcher = FundFetcher()
        call_count = {"n": 0}

        def mock_fetch(code):
            call_count["n"] += 1
            if code == "A":
                return {"estimate_nav": 1.0, "estimate_return": 0.5, "estimate_time": "14:00", "source": "akshare"}
            return None

        monkeypatch.setattr(fetcher, "fetch_fund_estimate", mock_fetch)
        results = fetcher.fetch_fund_estimate_batch(["A", "B"])
        assert len(results) == 1
        assert results[0]["fund_code"] == "A"


from unittest.mock import MagicMock
from fund_analyzer.data.sync import DataSyncer


class TestSyncEstimates:
    def test_sync_estimates_adds_date(self, monkeypatch):
        """sync_estimates 为每条估值补充 estimate_date。"""
        mock_repo = MagicMock()
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_fund_estimate_batch.return_value = [
            {"fund_code": "A", "estimate_nav": 1.5, "estimate_return": 0.5,
             "estimate_time": "14:00", "source": "akshare"},
        ]
        upserted_data = []
        mock_repo.upsert_estimate.side_effect = lambda d: upserted_data.append(d)

        syncer = DataSyncer(mock_repo, mock_fetcher)
        count = syncer.sync_estimates(["A"])

        assert count == 1
        assert "estimate_date" in upserted_data[0]
        assert upserted_data[0]["estimate_date"] == date.today()

    def test_sync_estimates_skips_none(self, monkeypatch):
        """防御性测试：即使 batch 返回含 None 的列表，sync 也能正确跳过。"""
        mock_repo = MagicMock()
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_fund_estimate_batch.return_value = [None, None]

        syncer = DataSyncer(mock_repo, mock_fetcher)
        count = syncer.sync_estimates(["A", "B"])
        assert count == 0
        mock_repo.upsert_estimate.assert_not_called()

    def test_sync_estimates_handles_upsert_error(self, monkeypatch):
        """upsert 失败时计数不增加，但继续处理后续数据。"""
        mock_repo = MagicMock()
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_fund_estimate_batch.return_value = [
            {"fund_code": "FAIL", "estimate_nav": 1.0, "estimate_return": 0,
             "estimate_time": "14:00", "source": "akshare"},
            {"fund_code": "OK", "estimate_nav": 2.0, "estimate_return": 1.0,
             "estimate_time": "14:30", "source": "akshare"},
        ]
        call_count = {"n": 0}
        def mock_upsert(d):
            call_count["n"] += 1
            if d["fund_code"] == "FAIL":
                raise Exception("DB error")
        mock_repo.upsert_estimate.side_effect = mock_upsert

        syncer = DataSyncer(mock_repo, mock_fetcher)
        count = syncer.sync_estimates(["FAIL", "OK"])
        assert count == 1  # 只有 OK 成功
        assert call_count["n"] == 2  # 两次都尝试了
