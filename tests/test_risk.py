"""风险测评测试。"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, RiskProfile
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.risk.assessor import RiskAssessor
from fund_analyzer.risk.questionnaire import QUESTIONS


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


class TestQuestionnaire:
    def test_has_questions(self):
        assert len(QUESTIONS) == 5

    def test_question_structure(self):
        for q in QUESTIONS:
            assert "id" in q
            assert "text" in q
            assert "options" in q
            assert len(q["options"]) >= 2
            for opt in q["options"]:
                assert "label" in opt
                assert "score" in opt


class TestRiskAssessor:
    def test_conservative_score(self):
        assessor = RiskAssessor()
        answers = {q["id"]: q["options"][0]["score"] for q in QUESTIONS}
        score = assessor.calculate_score(answers)
        level = assessor.score_to_level(score)
        assert level == 1
        assert assessor.get_level_label(level) == "保守型"

    def test_aggressive_score(self):
        assessor = RiskAssessor()
        answers = {q["id"]: q["options"][-1]["score"] for q in QUESTIONS}
        score = assessor.calculate_score(answers)
        level = assessor.score_to_level(score)
        assert level == 5
        assert assessor.get_level_label(level) == "激进型"

    def test_balanced_score(self):
        assessor = RiskAssessor()
        answers = {"experience": 10, "loss_tolerance": 15, "investment_horizon": 10, "income_stability": 10, "investment_goal": 10}
        score = assessor.calculate_score(answers)
        assert score == 55
        level = assessor.score_to_level(score)
        assert level == 3

    def test_get_recommended_ratios(self):
        assessor = RiskAssessor()
        core, sat = assessor.get_recommended_ratios(1)
        assert core == 70
        assert sat == 30
        core, sat = assessor.get_recommended_ratios(5)
        assert core == 10
        assert sat == 90


class TestRiskProfileRepository:
    def test_save_and_get(self, repo):
        repo.save_risk_profile({
            "risk_level": 3,
            "risk_label": "平衡型",
            "core_ratio": 30,
            "satellite_ratio": 70,
            "assessment_date": date(2026, 3, 20),
            "answers": {"experience": 10},
        })
        result = repo.get_latest_risk_profile()
        assert result is not None
        assert result.risk_level == 3
        assert result.risk_label == "平衡型"
