"""定投管理（DipManager）单元测试。

使用 SQLite 内存数据库 + 真实 ORM 模型进行测试。
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.portfolio.dip import DipManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def session():
    """每个测试用例使用独立的 SQLite 内存数据库。"""
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    with Session(engine) as sess:
        yield sess


@pytest.fixture
def manager(session):
    """基于内存 Session 构造 DipManager。"""
    repo = FundRepository(session)
    return DipManager(repo)


# ---------------------------------------------------------------------------
# 测试：创建定投计划
# ---------------------------------------------------------------------------


def test_create_dip_plan(manager, session):
    """创建定投计划后应能从数据库中查询到，且字段正确。"""
    start = date(2024, 1, 15)
    plan = manager.create_plan(
        fund_code="000001",
        amount=Decimal("500.00"),
        frequency="monthly",
        start_date=start,
        smart=True,
    )

    # 返回值验证
    assert plan.id is not None
    assert plan.fund_code == "000001"
    assert plan.amount == Decimal("500.00")
    assert plan.frequency == "monthly"
    assert plan.start_date == start
    assert plan.status == "active"
    assert plan.smart_dip is True

    # 从数据库重新查询
    from fund_analyzer.data.models import DipPlan
    db_plan = session.get(DipPlan, plan.id)
    assert db_plan is not None
    assert db_plan.fund_code == "000001"


# ---------------------------------------------------------------------------
# 测试：月度到期检查（同一天 → 应触发）
# ---------------------------------------------------------------------------


def test_check_due_monthly(manager):
    """月度计划：检查日与起始日同为每月15日，应出现在到期列表中。"""
    start = date(2024, 1, 15)
    plan = manager.create_plan(
        fund_code="000002",
        amount=Decimal("1000.00"),
        frequency="monthly",
        start_date=start,
    )

    # 同月日（3月15日）检查
    due_list = manager.check_due(as_of=date(2024, 3, 15))
    plan_ids = [item["plan_id"] for item in due_list]
    assert plan.id in plan_ids

    # 验证返回字段完整
    matched = next(item for item in due_list if item["plan_id"] == plan.id)
    assert matched["fund_code"] == "000002"
    assert matched["amount"] == Decimal("1000.00")
    assert matched["smart_dip"] is False


# ---------------------------------------------------------------------------
# 测试：非到期日不触发
# ---------------------------------------------------------------------------


def test_check_not_due(manager):
    """月度计划：检查日与起始日不同天，不应出现在到期列表中。"""
    start = date(2024, 1, 15)
    plan = manager.create_plan(
        fund_code="000003",
        amount=Decimal("300.00"),
        frequency="monthly",
        start_date=start,
    )

    # 不同日（3月20日）检查 → 不应触发
    due_list = manager.check_due(as_of=date(2024, 3, 20))
    plan_ids = [item["plan_id"] for item in due_list]
    assert plan.id not in plan_ids


# ---------------------------------------------------------------------------
# 测试：暂停与恢复
# ---------------------------------------------------------------------------


def test_pause_and_resume(manager):
    """暂停计划后不出现在到期列表；恢复后重新出现。"""
    start = date(2024, 1, 15)
    plan = manager.create_plan(
        fund_code="000004",
        amount=Decimal("200.00"),
        frequency="monthly",
        start_date=start,
    )
    check_date = date(2024, 3, 15)

    # 暂停前：应在到期列表中
    due_list = manager.check_due(as_of=check_date)
    assert plan.id in [item["plan_id"] for item in due_list]

    # 暂停后：不应在到期列表中
    manager.pause_plan(plan.id)
    due_list = manager.check_due(as_of=check_date)
    assert plan.id not in [item["plan_id"] for item in due_list]

    # list_plans 也不应包含已暂停的计划
    active_ids = [p["id"] for p in manager.list_plans()]
    assert plan.id not in active_ids

    # 恢复后：重新出现在到期列表中
    manager.resume_plan(plan.id)
    due_list = manager.check_due(as_of=check_date)
    assert plan.id in [item["plan_id"] for item in due_list]

    # list_plans 应重新包含该计划
    active_ids = [p["id"] for p in manager.list_plans()]
    assert plan.id in active_ids


# ---------------------------------------------------------------------------
# 补充测试：停止计划
# ---------------------------------------------------------------------------


def test_stop_plan(manager):
    """停止计划后状态变为 stopped，不出现在到期列表中。"""
    start = date(2024, 1, 15)
    plan = manager.create_plan(
        fund_code="000005",
        amount=Decimal("100.00"),
        frequency="monthly",
        start_date=start,
    )

    manager.stop_plan(plan.id)

    # 不应出现在到期列表中
    due_list = manager.check_due(as_of=date(2024, 3, 15))
    assert plan.id not in [item["plan_id"] for item in due_list]


# ---------------------------------------------------------------------------
# 补充测试：start_date 未到不触发
# ---------------------------------------------------------------------------


def test_check_not_due_before_start(manager):
    """检查日早于起始日时，计划不应触发。"""
    start = date(2024, 6, 15)
    plan = manager.create_plan(
        fund_code="000006",
        amount=Decimal("100.00"),
        frequency="monthly",
        start_date=start,
    )

    # 检查日早于起始日
    due_list = manager.check_due(as_of=date(2024, 3, 15))
    assert plan.id not in [item["plan_id"] for item in due_list]


# ---------------------------------------------------------------------------
# 补充测试：每周定投
# ---------------------------------------------------------------------------


def test_check_due_weekly(manager):
    """每周定投：相同星期几应触发，不同星期几不触发。"""
    # 2024-01-15 是星期一（weekday=0）
    start = date(2024, 1, 15)
    plan = manager.create_plan(
        fund_code="000007",
        amount=Decimal("100.00"),
        frequency="weekly",
        start_date=start,
    )

    # 2024-01-22 也是星期一 → 应触发
    due_list = manager.check_due(as_of=date(2024, 1, 22))
    assert plan.id in [item["plan_id"] for item in due_list]

    # 2024-01-23 是星期二 → 不触发
    due_list = manager.check_due(as_of=date(2024, 1, 23))
    assert plan.id not in [item["plan_id"] for item in due_list]


# ---------------------------------------------------------------------------
# 补充测试：双周定投
# ---------------------------------------------------------------------------


def test_check_due_biweekly(manager):
    """双周定投：间隔14天应触发，间隔7天不触发。"""
    start = date(2024, 1, 15)
    plan = manager.create_plan(
        fund_code="000008",
        amount=Decimal("100.00"),
        frequency="biweekly",
        start_date=start,
    )

    # 间隔14天 → 应触发
    due_list = manager.check_due(as_of=date(2024, 1, 29))
    assert plan.id in [item["plan_id"] for item in due_list]

    # 间隔7天 → 不触发
    due_list = manager.check_due(as_of=date(2024, 1, 22))
    assert plan.id not in [item["plan_id"] for item in due_list]
