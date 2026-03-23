"""风险评估路由模块。

提供问卷获取、评估提交、评估结果查询三个端点。
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from fund_analyzer.api.deps import get_db_session, get_repo
from fund_analyzer.api.schemas.common import ApiResponse
from fund_analyzer.api.schemas.risk import RiskProfileResponse, RiskSubmitRequest
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.risk.assessor import RiskAssessor
from fund_analyzer.risk.questionnaire import QUESTIONS

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/questions", response_model=ApiResponse[list[dict]])
def get_questions() -> ApiResponse[list[dict]]:
    """获取风险评估问卷。"""
    return ApiResponse(data=QUESTIONS)


@router.get("/profile", response_model=ApiResponse[RiskProfileResponse | None])
def get_profile(
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[RiskProfileResponse | None]:
    """获取最新风险评估结果。"""
    try:
        profile = repo.get_latest_risk_profile()
        if profile is None:
            return ApiResponse(data=None)
        return ApiResponse(data=RiskProfileResponse(
            id=profile.id,
            risk_level=profile.risk_level,
            risk_label=profile.risk_label,
            core_ratio=profile.core_ratio,
            satellite_ratio=profile.satellite_ratio,
            assessment_date=profile.assessment_date.isoformat() if hasattr(profile.assessment_date, "isoformat") else str(profile.assessment_date),
            answers=profile.answers,
        ))
    except Exception as exc:
        logger.exception("获取风险评估结果失败")
        return ApiResponse(code=500, message=f"获取风险评估结果失败: {exc}")


@router.post("/assess", response_model=ApiResponse[RiskProfileResponse])
def assess_risk(
    req: RiskSubmitRequest,
    session: Session = Depends(get_db_session),
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[RiskProfileResponse]:
    """提交问卷评估风险等级。"""
    try:
        assessor = RiskAssessor()
        score = assessor.calculate_score(req.answers)
        level = assessor.score_to_level(score)
        label = assessor.get_level_label(level)
        core_ratio, satellite_ratio = assessor.get_recommended_ratios(level)

        profile = repo.save_risk_profile({
            "risk_level": level,
            "risk_label": label,
            "core_ratio": core_ratio,
            "satellite_ratio": satellite_ratio,
            "assessment_date": date.today(),
            "answers": req.answers,
        })
        session.commit()

        return ApiResponse(data=RiskProfileResponse(
            id=profile.id,
            risk_level=profile.risk_level,
            risk_label=profile.risk_label,
            core_ratio=profile.core_ratio,
            satellite_ratio=profile.satellite_ratio,
            assessment_date=profile.assessment_date.isoformat(),
            answers=profile.answers,
        ))
    except Exception as exc:
        logger.exception("风险评估失败")
        return ApiResponse(code=500, message=f"风险评估失败: {exc}")
