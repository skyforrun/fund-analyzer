"""系统设置路由模块。

提供配置查看、数据同步(SSE)、通知管理七个端点。
"""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sse_starlette.sse import EventSourceResponse

from fund_analyzer.api.deps import get_db_session, get_repo, get_settings, get_syncer
from fund_analyzer.api.schemas.common import ApiResponse
from fund_analyzer.api.schemas.settings import (
    NotificationConfigReq,
    NotificationConfigResp,
    NotificationRuleItem,
    ScheduleStatusResp,
    ScheduleToggleReq,
    SyncResultData,
)
from fund_analyzer.config import Settings
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.data.sync import DataSyncer
from fund_analyzer.notification.sender import WeChatSender

logger = logging.getLogger(__name__)

router = APIRouter()


# ---------------------------------------------------------------------------
# 0. 定时同步状态
# ---------------------------------------------------------------------------

@router.get("/schedule", response_model=ApiResponse[ScheduleStatusResp])
def get_schedule_status(
    settings: Settings = Depends(get_settings),
) -> ApiResponse[ScheduleStatusResp]:
    """获取定时同步状态。"""
    from fund_analyzer.api.main import scheduled_sync_task

    task_running = (
        scheduled_sync_task is not None and not scheduled_sync_task.done()
    )
    return ApiResponse(data=ScheduleStatusResp(
        enabled=settings.schedule.enabled,
        sync_time=settings.schedule.sync_time,
        max_nav_funds=settings.schedule.max_nav_funds,
        task_running=task_running,
    ))


@router.put("/schedule", response_model=ApiResponse[ScheduleStatusResp])
async def toggle_schedule(
    req: ScheduleToggleReq,
    settings: Settings = Depends(get_settings),
) -> ApiResponse[ScheduleStatusResp]:
    """开启/关闭定时同步。"""
    import asyncio
    from fund_analyzer.api import main as main_module

    settings.schedule.enabled = req.enabled

    if req.enabled and (
        main_module.scheduled_sync_task is None
        or main_module.scheduled_sync_task.done()
    ):
        main_module.scheduled_sync_task = asyncio.create_task(
            main_module._scheduled_sync(
                settings.schedule.sync_time,
                settings.schedule.max_nav_funds,
            )
        )
        logger.info("定时同步已手动开启")
    elif not req.enabled and main_module.scheduled_sync_task is not None:
        main_module.scheduled_sync_task.cancel()
        try:
            await main_module.scheduled_sync_task
        except asyncio.CancelledError:
            pass
        main_module.scheduled_sync_task = None
        logger.info("定时同步已手动关闭")

    task_running = (
        main_module.scheduled_sync_task is not None
        and not main_module.scheduled_sync_task.done()
    )
    return ApiResponse(data=ScheduleStatusResp(
        enabled=settings.schedule.enabled,
        sync_time=settings.schedule.sync_time,
        max_nav_funds=settings.schedule.max_nav_funds,
        task_running=task_running,
    ))


# ---------------------------------------------------------------------------
# 1. 配置查看
# ---------------------------------------------------------------------------

@router.get("/config", response_model=ApiResponse[dict])
def get_config(
    settings: Settings = Depends(get_settings),
) -> ApiResponse[dict]:
    """获取当前系统配置。"""
    try:
        data = asdict(settings)
        # 隐藏数据库密码
        if "database" in data and "password" in data["database"]:
            data["database"]["password"] = "***"
        return ApiResponse(data=data)
    except Exception as exc:
        logger.exception("获取配置失败")
        return ApiResponse(code=500, message=f"获取配置失败: {exc}")


# ---------------------------------------------------------------------------
# 2. 数据同步 (SSE)
# ---------------------------------------------------------------------------

@router.get("/sync/stream")
async def sync_stream(
    syncer: DataSyncer = Depends(get_syncer),
    session: Session = Depends(get_db_session),
):
    """SSE 数据同步进度流。"""
    queue: asyncio.Queue = asyncio.Queue()
    main_loop = asyncio.get_event_loop()

    def progress_callback(current, total, message):
        try:
            main_loop.call_soon_threadsafe(
                queue.put_nowait,
                {"current": current, "total": total, "message": message},
            )
        except Exception:
            pass

    async def generate():
        loop = asyncio.get_event_loop()
        task = loop.run_in_executor(
            None, lambda: syncer.sync_all(progress_callback=progress_callback)
        )

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                yield {
                    "event": "progress",
                    "data": json.dumps(event, ensure_ascii=False),
                }
            except asyncio.TimeoutError:
                if task.done():
                    break
                yield {"event": "ping", "data": ""}

        result = await task
        session.commit()
        yield {
            "event": "done",
            "data": json.dumps(result, default=str, ensure_ascii=False),
        }

    return EventSourceResponse(generate())


# ---------------------------------------------------------------------------
# 3. 通知配置
# ---------------------------------------------------------------------------

@router.get("/notification", response_model=ApiResponse[NotificationConfigResp | None])
def get_notification(
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[NotificationConfigResp | None]:
    """获取通知配置。"""
    try:
        config = repo.get_notification_config()
        if config is None:
            return ApiResponse(data=None)
        return ApiResponse(data=NotificationConfigResp(
            id=config.id,
            channel=config.channel,
            webhook_url=config.webhook_url,
            enabled=config.enabled,
            updated_at=config.updated_at.isoformat() if config.updated_at else None,
        ))
    except Exception as exc:
        logger.exception("获取通知配置失败")
        return ApiResponse(code=500, message=f"获取通知配置失败: {exc}")


@router.put("/notification", response_model=ApiResponse[NotificationConfigResp])
def save_notification(
    req: NotificationConfigReq,
    session: Session = Depends(get_db_session),
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[NotificationConfigResp]:
    """保存通知配置。"""
    try:
        config = repo.save_notification_config(
            webhook_url=req.webhook_url,
            enabled=req.enabled,
        )
        session.commit()
        return ApiResponse(data=NotificationConfigResp(
            id=config.id,
            channel=config.channel,
            webhook_url=config.webhook_url,
            enabled=config.enabled,
            updated_at=config.updated_at.isoformat() if config.updated_at else None,
        ))
    except Exception as exc:
        logger.exception("保存通知配置失败")
        return ApiResponse(code=500, message=f"保存通知配置失败: {exc}")


# ---------------------------------------------------------------------------
# 4. 通知规则
# ---------------------------------------------------------------------------

@router.get("/notification/rules", response_model=ApiResponse[list[NotificationRuleItem]])
def get_notification_rules(
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[list[NotificationRuleItem]]:
    """获取通知规则列表。"""
    try:
        rules = repo.get_notification_rules()
        items = [
            NotificationRuleItem(
                id=r.id,
                rule_type=r.rule_type,
                params=r.params,
                enabled=r.enabled,
            )
            for r in rules
        ]
        return ApiResponse(data=items)
    except Exception as exc:
        logger.exception("获取通知规则失败")
        return ApiResponse(code=500, message=f"获取通知规则失败: {exc}")


@router.put("/notification/rules", response_model=ApiResponse[list[NotificationRuleItem]])
def save_notification_rules(
    rules: list[NotificationRuleItem],
    session: Session = Depends(get_db_session),
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse[list[NotificationRuleItem]]:
    """批量保存通知规则。"""
    try:
        saved = []
        for rule in rules:
            obj = repo.save_notification_rule(
                rule_type=rule.rule_type,
                params=rule.params,
                enabled=rule.enabled,
            )
            saved.append(NotificationRuleItem(
                id=obj.id,
                rule_type=obj.rule_type,
                params=obj.params,
                enabled=obj.enabled,
            ))
        session.commit()
        return ApiResponse(data=saved)
    except Exception as exc:
        logger.exception("保存通知规则失败")
        return ApiResponse(code=500, message=f"保存通知规则失败: {exc}")


# ---------------------------------------------------------------------------
# 5. 通知测试
# ---------------------------------------------------------------------------

@router.post("/notification/test", response_model=ApiResponse)
def test_notification(
    repo: FundRepository = Depends(get_repo),
) -> ApiResponse:
    """发送测试通知。"""
    try:
        config = repo.get_notification_config()
        if config is None or not config.webhook_url:
            return ApiResponse(code=400, message="未配置通知渠道 Webhook 地址")

        sender = WeChatSender(config.webhook_url)
        ok = sender.test()
        if ok:
            return ApiResponse(message="测试通知发送成功")
        return ApiResponse(code=500, message="测试通知发送失败，请检查 Webhook 地址")
    except Exception as exc:
        logger.exception("发送测试通知失败")
        return ApiResponse(code=500, message=f"发送测试通知失败: {exc}")
