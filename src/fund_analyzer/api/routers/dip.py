"""定投管理路由模块。

提供定投计划的列表、到期检查、创建、暂停、恢复、停止六个端点。
"""
from __future__ import annotations

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from fund_analyzer.api.deps import get_db_session, get_dip_manager
from fund_analyzer.api.schemas.common import ApiResponse
from fund_analyzer.api.schemas.dip import DipDueItem, DipPlanCreate, DipPlanItem
from fund_analyzer.portfolio.dip import DipManager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/plans", response_model=ApiResponse[list[DipPlanItem]])
def list_plans(
    dip: DipManager = Depends(get_dip_manager),
) -> ApiResponse[list[DipPlanItem]]:
    """获取所有定投计划。"""
    try:
        raw = dip.list_plans()
        items = []
        for p in raw:
            items.append(DipPlanItem(
                id=p["id"],
                fund_code=p["fund_code"],
                amount=float(p["amount"]),
                frequency=p["frequency"],
                start_date=p["start_date"].isoformat() if p.get("start_date") else None,
                status=p["status"],
                smart_dip=p.get("smart_dip"),
            ))
        return ApiResponse(data=items)
    except Exception as exc:
        logger.exception("获取定投计划列表失败")
        return ApiResponse(code=500, message=f"获取定投计划列表失败: {exc}")


@router.get("/due", response_model=ApiResponse[list[DipDueItem]])
def check_due(
    dip: DipManager = Depends(get_dip_manager),
) -> ApiResponse[list[DipDueItem]]:
    """检查今日到期定投。"""
    try:
        raw = dip.check_due()
        items = []
        for d in raw:
            items.append(DipDueItem(
                plan_id=d["plan_id"],
                fund_code=d["fund_code"],
                amount=float(d["amount"]),
                smart_dip=d.get("smart_dip"),
            ))
        return ApiResponse(data=items)
    except Exception as exc:
        logger.exception("检查定投到期失败")
        return ApiResponse(code=500, message=f"检查定投到期失败: {exc}")


@router.post("/plans", response_model=ApiResponse[DipPlanItem])
def create_plan(
    req: DipPlanCreate,
    session: Session = Depends(get_db_session),
    dip: DipManager = Depends(get_dip_manager),
) -> ApiResponse[DipPlanItem]:
    """创建定投计划。"""
    try:
        plan = dip.create_plan(
            fund_code=req.fund_code,
            amount=Decimal(str(req.amount)),
            frequency=req.frequency,
            smart=req.smart,
        )
        session.commit()
        return ApiResponse(data=DipPlanItem(
            id=plan.id,
            fund_code=plan.fund_code,
            amount=float(plan.amount),
            frequency=plan.frequency,
            start_date=plan.start_date.isoformat() if plan.start_date else None,
            status=plan.status,
            smart_dip=plan.smart_dip,
        ))
    except Exception as exc:
        logger.exception("创建定投计划失败")
        return ApiResponse(code=500, message=f"创建定投计划失败: {exc}")


@router.post("/plans/{plan_id}/pause", response_model=ApiResponse)
def pause_plan(
    plan_id: int,
    session: Session = Depends(get_db_session),
    dip: DipManager = Depends(get_dip_manager),
) -> ApiResponse:
    """暂停定投计划。"""
    try:
        dip.pause_plan(plan_id)
        session.commit()
        return ApiResponse(message="计划已暂停")
    except ValueError as exc:
        return ApiResponse(code=404, message=str(exc))
    except Exception as exc:
        logger.exception("暂停定投计划失败")
        return ApiResponse(code=500, message=f"暂停定投计划失败: {exc}")


@router.post("/plans/{plan_id}/resume", response_model=ApiResponse)
def resume_plan(
    plan_id: int,
    session: Session = Depends(get_db_session),
    dip: DipManager = Depends(get_dip_manager),
) -> ApiResponse:
    """恢复定投计划。"""
    try:
        dip.resume_plan(plan_id)
        session.commit()
        return ApiResponse(message="计划已恢复")
    except ValueError as exc:
        return ApiResponse(code=404, message=str(exc))
    except Exception as exc:
        logger.exception("恢复定投计划失败")
        return ApiResponse(code=500, message=f"恢复定投计划失败: {exc}")


@router.post("/plans/{plan_id}/stop", response_model=ApiResponse)
def stop_plan(
    plan_id: int,
    session: Session = Depends(get_db_session),
    dip: DipManager = Depends(get_dip_manager),
) -> ApiResponse:
    """停止定投计划。"""
    try:
        dip.stop_plan(plan_id)
        session.commit()
        return ApiResponse(message="计划已停止")
    except ValueError as exc:
        return ApiResponse(code=404, message=str(exc))
    except Exception as exc:
        logger.exception("停止定投计划失败")
        return ApiResponse(code=500, message=f"停止定投计划失败: {exc}")
