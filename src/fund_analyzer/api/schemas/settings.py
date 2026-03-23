"""系统设置相关 API 数据模型。"""
from __future__ import annotations

from pydantic import BaseModel


class NotificationConfigReq(BaseModel):
    """通知配置请求体。"""

    webhook_url: str
    enabled: bool = True


class NotificationConfigResp(BaseModel):
    """通知配置响应。"""

    id: int | None = None
    channel: str
    webhook_url: str | None = None
    enabled: bool
    updated_at: str | None = None


class NotificationRuleItem(BaseModel):
    """通知规则项。"""

    id: int | None = None
    rule_type: str
    params: dict | None = None
    enabled: bool = True


class SyncResultData(BaseModel):
    """数据同步结果。"""

    funds: int = 0
    navs: int = 0
    indices: int = 0
    estimates: int = 0
    fee_schedules: int = 0
    warnings: list[str] = []


class ScheduleStatusResp(BaseModel):
    """定时同步状态响应。"""

    enabled: bool
    sync_time: str
    max_nav_funds: int
    task_running: bool


class ScheduleToggleReq(BaseModel):
    """定时同步开关请求。"""

    enabled: bool
