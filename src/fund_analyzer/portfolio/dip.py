"""定投管理模块（DipManager）。

提供定投计划的创建、到期检查、暂停/恢复/停止及列表查询功能。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Optional

from sqlalchemy import select

from fund_analyzer.data.models import DipPlan
from fund_analyzer.data.repository import FundRepository


class DipManager:
    """定投计划管理器。

    构造参数
    --------
    repo : FundRepository
        数据访问仓储，包含底层 SQLAlchemy Session。
    """

    def __init__(self, repo: FundRepository) -> None:
        self._repo = repo
        self._session = repo._session

    # -----------------------------------------------------------------------
    # 创建计划
    # -----------------------------------------------------------------------

    def create_plan(
        self,
        fund_code: str,
        amount: Decimal,
        frequency: str = "monthly",
        start_date: Optional[date] = None,
        smart: bool = False,
    ) -> DipPlan:
        """创建一条定投计划记录并持久化到数据库。

        参数
        ----
        fund_code : str
            基金代码。
        amount : Decimal
            每期定投金额。
        frequency : str
            定投频率，可选值：weekly / biweekly / monthly，默认 monthly。
        start_date : date, optional
            计划起始日期，默认为今日。
        smart : bool
            是否启用智能定投，默认 False。

        返回
        ----
        已持久化的 DipPlan 对象（id 已填充）。
        """
        if start_date is None:
            start_date = date.today()

        plan = DipPlan(
            fund_code=fund_code,
            amount=Decimal(str(amount)),
            frequency=frequency,
            start_date=start_date,
            status="active",
            smart_dip=smart,
        )
        self._session.add(plan)
        self._session.flush()
        return plan

    # -----------------------------------------------------------------------
    # 检查到期
    # -----------------------------------------------------------------------

    def check_due(self, as_of: Optional[date] = None) -> list[dict]:
        """检查所有 active 状态的计划，返回当日应执行的计划列表。

        参数
        ----
        as_of : date, optional
            检查基准日期，默认为今日。

        返回
        ----
        到期计划的字典列表，每个元素包含：
        plan_id, fund_code, amount, smart_dip。
        """
        if as_of is None:
            as_of = date.today()

        active_plans = self._repo.get_active_dip_plans()
        result = []
        for plan in active_plans:
            if self._is_due(plan, as_of):
                result.append(
                    {
                        "plan_id": plan.id,
                        "fund_code": plan.fund_code,
                        "amount": plan.amount,
                        "smart_dip": plan.smart_dip,
                    }
                )
        return result

    # -----------------------------------------------------------------------
    # 判断是否到期
    # -----------------------------------------------------------------------

    def _is_due(self, plan: DipPlan, as_of: date) -> bool:
        """判断某个定投计划在指定日期是否应执行。

        规则
        ----
        - start_date > as_of → False（计划尚未开始）
        - weekly：as_of 与 start_date 是同一星期几
        - biweekly：(as_of - start_date).days % 14 == 0
        - monthly：as_of 与 start_date 是同一天（day of month）

        参数
        ----
        plan : DipPlan
            定投计划对象。
        as_of : date
            检查日期。

        返回
        ----
        True 表示今日应执行，False 表示不应执行。
        """
        start_date = plan.start_date
        if start_date is None or start_date > as_of:
            return False

        frequency = plan.frequency
        if frequency == "weekly":
            return as_of.weekday() == start_date.weekday()
        elif frequency == "biweekly":
            return (as_of - start_date).days % 14 == 0
        elif frequency == "monthly":
            return as_of.day == start_date.day
        # 未知频率默认不触发
        return False

    # -----------------------------------------------------------------------
    # 计划状态管理
    # -----------------------------------------------------------------------

    def pause_plan(self, plan_id: int) -> None:
        """将指定定投计划状态设置为 paused。

        参数
        ----
        plan_id : int
            定投计划 ID。
        """
        plan = self._session.get(DipPlan, plan_id)
        if plan is None:
            raise ValueError(f"定投计划不存在：plan_id={plan_id}")
        plan.status = "paused"
        self._session.flush()

    def resume_plan(self, plan_id: int) -> None:
        """将指定定投计划状态恢复为 active。

        参数
        ----
        plan_id : int
            定投计划 ID。
        """
        plan = self._session.get(DipPlan, plan_id)
        if plan is None:
            raise ValueError(f"定投计划不存在：plan_id={plan_id}")
        plan.status = "active"
        self._session.flush()

    def stop_plan(self, plan_id: int) -> None:
        """将指定定投计划状态设置为 stopped。

        参数
        ----
        plan_id : int
            定投计划 ID。
        """
        plan = self._session.get(DipPlan, plan_id)
        if plan is None:
            raise ValueError(f"定投计划不存在：plan_id={plan_id}")
        plan.status = "stopped"
        self._session.flush()

    # -----------------------------------------------------------------------
    # 列出计划
    # -----------------------------------------------------------------------

    def list_plans(self) -> list[dict]:
        """返回所有 active 状态的定投计划（字典列表）。

        返回
        ----
        每个元素包含：id, fund_code, amount, frequency, start_date,
        status, smart_dip。
        """
        plans = self._repo.get_active_dip_plans()
        return [
            {
                "id": p.id,
                "fund_code": p.fund_code,
                "amount": p.amount,
                "frequency": p.frequency,
                "start_date": p.start_date,
                "status": p.status,
                "smart_dip": p.smart_dip,
            }
            for p in plans
        ]
