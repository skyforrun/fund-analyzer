"""Watchlist 路由模块。

提供自选列表查询、分组查询、添加自选、移除自选四个端点。
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from fund_analyzer.api.deps import get_db_session, get_repo
from fund_analyzer.api.schemas.common import ApiResponse
from fund_analyzer.api.schemas.watchlist import WatchlistCreateRequest, WatchlistItem
from fund_analyzer.data.repository import FundRepository

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=ApiResponse[list[WatchlistItem]])
def get_watchlist(
    group_name: str | None = None,
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[list[WatchlistItem]]:
    """获取自选列表，可按分组过滤。"""
    try:
        items = repo.get_watchlist(group_name=group_name)
        result = [
            WatchlistItem(
                id=item.id,
                fund_code=item.fund_code,
                fund_name=item.fund_name,
                group_name=item.group_name,
                notes=item.notes,
                added_at=item.added_at,
            )
            for item in items
        ]
        return ApiResponse(data=result)

    except Exception as exc:
        logger.exception("获取自选列表失败")
        return ApiResponse(code=500, message=f"获取自选列表失败: {exc}")


@router.get("/groups", response_model=ApiResponse[list[str]])
def get_watchlist_groups(
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[list[str]]:
    """获取所有自选分组名。"""
    try:
        groups = repo.get_watchlist_groups()
        return ApiResponse(data=groups)

    except Exception as exc:
        logger.exception("获取分组列表失败")
        return ApiResponse(code=500, message=f"获取分组列表失败: {exc}")


@router.post("", response_model=ApiResponse[WatchlistItem])
def add_watchlist(
    req: WatchlistCreateRequest,
    session: Session = Depends(get_db_session),
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[WatchlistItem]:
    """添加基金到自选列表。"""
    try:
        item = repo.add_to_watchlist(
            fund_code=req.fund_code,
            fund_name=req.fund_name,
            group_name=req.group_name,
            notes=req.notes,
        )
        session.commit()
        return ApiResponse(data=WatchlistItem(
            id=item.id,
            fund_code=item.fund_code,
            fund_name=item.fund_name,
            group_name=item.group_name,
            notes=item.notes,
            added_at=item.added_at,
        ))

    except Exception as exc:
        logger.exception("添加自选失败")
        return ApiResponse(code=500, message=f"添加自选失败: {exc}")


@router.delete("/{code}", response_model=ApiResponse[dict])
def remove_watchlist(
    code: str,
    group_name: str | None = None,
    session: Session = Depends(get_db_session),
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[dict]:
    """从自选列表移除基金。"""
    try:
        count = repo.remove_from_watchlist(code, group_name=group_name)
        session.commit()
        return ApiResponse(data={"removed": count})

    except Exception as exc:
        logger.exception("移除自选失败")
        return ApiResponse(code=500, message=f"移除自选失败: {exc}")
