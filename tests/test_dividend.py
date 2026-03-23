"""分红数据测试。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundDividend
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


class TestUpsertDividends:
    def test_insert(self, repo, session):
        repo.upsert_dividends("DIV001", [
            {"ex_date": date(2025, 6, 15), "dividend_per_unit": Decimal("0.50"), "dividend_type": "现金分红"},
        ])
        result = session.get(FundDividend, ("DIV001", date(2025, 6, 15)))
        assert result is not None
        assert result.dividend_per_unit == Decimal("0.50")

    def test_update(self, repo, session):
        session.add(FundDividend(fund_code="DIV002", ex_date=date(2025, 1, 1), dividend_per_unit=Decimal("0.10")))
        session.flush()
        repo.upsert_dividends("DIV002", [
            {"ex_date": date(2025, 1, 1), "dividend_per_unit": Decimal("0.20")},
        ])
        session.expire_all()
        result = session.get(FundDividend, ("DIV002", date(2025, 1, 1)))
        assert result.dividend_per_unit == Decimal("0.20")


class TestGetDividends:
    def test_returns_ordered(self, repo, session):
        session.add_all([
            FundDividend(fund_code="DIV003", ex_date=date(2025, 1, 1), dividend_per_unit=Decimal("0.10")),
            FundDividend(fund_code="DIV003", ex_date=date(2025, 6, 1), dividend_per_unit=Decimal("0.20")),
        ])
        session.flush()
        results = repo.get_dividends("DIV003")
        assert len(results) == 2
        assert results[0].ex_date > results[1].ex_date

    def test_filter_by_start_date(self, repo, session):
        session.add_all([
            FundDividend(fund_code="DIV004", ex_date=date(2024, 1, 1)),
            FundDividend(fund_code="DIV004", ex_date=date(2025, 6, 1)),
        ])
        session.flush()
        results = repo.get_dividends("DIV004", start_date=date(2025, 1, 1))
        assert len(results) == 1
