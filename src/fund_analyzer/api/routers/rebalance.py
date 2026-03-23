"""调仓建议路由模块。

提供调仓建议生成端点。
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends

from fund_analyzer.api.deps import get_rebalance_advisor, get_repo, get_settings
from fund_analyzer.api.schemas.common import ApiResponse
from fund_analyzer.api.schemas.rebalance import ActionItem, RebalanceResult
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.portfolio.rebalance import RebalanceAdvisor

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate", response_model=ApiResponse[RebalanceResult])
def generate_rebalance(
    repo: FundRepository = Depends(get_repo),
    advisor: RebalanceAdvisor = Depends(get_rebalance_advisor),
) -> ApiResponse[RebalanceResult]:
    """生成调仓建议。"""
    try:
        settings = get_settings()
        as_of = date.today()

        eligible = repo.get_eligible_funds(
            min_inception_years=settings.data.fund_pool.min_inception_years,
            min_size_billion=settings.data.fund_pool.min_size_billion,
            exclude_types=settings.data.fund_pool.exclude_types,
            as_of=as_of,
        )
        fund_codes = [f.fund_code for f in eligible]

        if not fund_codes:
            return ApiResponse(data=RebalanceResult(
                as_of=as_of.isoformat(),
                actions=[],
                core_picks=[],
                satellite_picks=[],
            ))

        raw = advisor.generate(fund_codes, as_of=as_of)

        actions = [
            ActionItem(
                fund_code=a["fund_code"],
                position_type=a["position_type"],
                action=a["action"],
                reason=a["reason"],
            )
            for a in raw.get("actions", [])
        ]

        result = RebalanceResult(
            as_of=raw["as_of"].isoformat() if hasattr(raw["as_of"], "isoformat") else str(raw["as_of"]),
            actions=actions,
            core_picks=[list(pair) for pair in raw.get("core_picks", [])],
            satellite_picks=[list(pair) for pair in raw.get("satellite_picks", [])],
        )
        return ApiResponse(data=result)

    except Exception as exc:
        logger.exception("生成调仓建议失败")
        return ApiResponse(code=500, message=f"生成调仓建议失败: {exc}")
