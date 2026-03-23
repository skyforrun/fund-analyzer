"""Screening（基金筛选）路由模块。

提供基金评分筛选和费率查询两个端点。
"""
from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, Depends

from fund_analyzer.api.deps import get_repo, get_composite, get_settings
from fund_analyzer.api.schemas.common import ApiResponse
from fund_analyzer.api.schemas.screening import (
    FeeScheduleItem,
    ScreenRequest,
    ScreenResultItem,
)
from fund_analyzer.config import Settings
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.composite import CompositeStrategy

logger = logging.getLogger(__name__)

_ACTION_MAP = {"buy": "买入", "sell": "卖出", "hold": "持有"}

router = APIRouter()


@router.post("/score", response_model=ApiResponse[list[ScreenResultItem]])
def screening_score(
    req: ScreenRequest,
    repo: FundRepository = Depends(get_repo),
    composite: CompositeStrategy = Depends(get_composite),
    settings: Settings = Depends(get_settings),
) -> ApiResponse[list[ScreenResultItem]]:
    """基金评分筛选。

    根据仓位类型对符合条件的基金池进行评分，返回得分最高的 top_n 只基金。
    """
    try:
        pool_cfg = settings.data.fund_pool
        as_of = date.today()

        # 获取有净值数据的基金
        nav_codes = set(repo.get_funds_with_nav())

        # 获取符合条件的基金
        eligible = repo.get_eligible_funds(
            min_inception_years=pool_cfg.min_inception_years,
            min_size_billion=pool_cfg.min_size_billion,
            exclude_types=pool_cfg.exclude_types,
            as_of=as_of,
        )

        # 取交集：既有净值又满足筛选条件
        eligible_map = {f.fund_code: f for f in eligible if f.fund_code in nav_codes}
        fund_codes = list(eligible_map.keys())

        if not fund_codes:
            return ApiResponse(data=[])

        # 按仓位类型评分
        if req.position_type == "core":
            scores = composite.score_core(fund_codes, as_of)
        else:
            scores = composite.score_satellite(fund_codes, as_of)

        # 排序取 top_n
        sorted_codes = sorted(scores, key=lambda c: scores[c], reverse=True)[: req.top_n]

        # 构造结果
        items: list[ScreenResultItem] = []
        for code in sorted_codes:
            info = eligible_map.get(code)
            # 获取信号
            action_str = None
            confidence_str = None
            reason_str = None
            try:
                sig = composite.signal(code, as_of, req.position_type)
                action_str = _ACTION_MAP.get(sig.action, sig.action)
                confidence_str = f"{sig.confidence * 100:.0f}%"
                reason_str = sig.reason
            except Exception:
                logger.debug("获取基金 %s 信号失败，跳过", code)

            items.append(
                ScreenResultItem(
                    fund_code=code,
                    fund_name=info.fund_name if info else None,
                    fund_type=info.fund_type if info else None,
                    score=round(scores[code], 2),
                    action=action_str,
                    confidence=confidence_str,
                    reason=reason_str,
                )
            )

        return ApiResponse(data=items)

    except Exception as exc:
        logger.exception("基金筛选评分失败")
        return ApiResponse(code=500, message=f"基金筛选评分失败: {exc}")


@router.get("/fees/{code}", response_model=ApiResponse[list[FeeScheduleItem]])
def screening_fees(
    code: str,
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[list[FeeScheduleItem]]:
    """查询指定基金的费率明细。"""
    try:
        schedules = repo.get_fee_schedules(code)

        items = [
            FeeScheduleItem(
                fee_type=s.fee_type,
                min_holding_days=s.min_holding_days,
                max_holding_days=s.max_holding_days,
                fee_rate=float(s.fee_rate),
                min_amount=float(s.min_amount),
                max_amount=float(s.max_amount) if s.max_amount is not None else None,
            )
            for s in schedules
        ]

        return ApiResponse(data=items)

    except Exception as exc:
        logger.exception("获取费率信息失败")
        return ApiResponse(code=500, message=f"获取费率信息失败: {exc}")
