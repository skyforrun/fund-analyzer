"""通知规则检查器。"""
from __future__ import annotations

import logging
from datetime import date

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.notification.sender import WeChatSender

logger = logging.getLogger(__name__)


class NotificationChecker:
    """检查通知规则并发送提醒。"""

    def __init__(self, repo: FundRepository, sender: WeChatSender) -> None:
        self._repo = repo
        self._sender = sender

    def check_dip_due(self) -> int:
        """检查今日到期的定投计划并推送提醒。返回推送的提醒数。"""
        plans = self._repo.get_active_dip_plans()
        today = date.today()
        due_plans = []

        for plan in plans:
            if self._is_due(plan, today):
                due_plans.append(plan)

        if not due_plans:
            return 0

        lines = []
        for p in due_plans:
            lines.append(f"- 基金 **{p.fund_code}**，金额 ¥{float(p.amount):,.2f}，频率 {p.frequency}")

        content = f"今日有 {len(due_plans)} 个定投计划到期：\n" + "\n".join(lines)
        self._sender.send("定投提醒", content)
        return len(due_plans)

    def check_drop_alert(self, threshold: float = -3.0) -> int:
        """检查自选基金中跌幅超阈值的并推送预警。返回预警的基金数。"""
        watchlist = self._repo.get_watchlist()
        if not watchlist:
            return 0

        fund_codes = [w.fund_code for w in watchlist]
        estimates = self._repo.get_latest_estimates(fund_codes)

        alerts = []
        for est in estimates:
            if est.estimate_return is not None and float(est.estimate_return) <= threshold:
                alerts.append(est)

        if not alerts:
            return 0

        lines = []
        for a in alerts:
            lines.append(f"- **{a.fund_code}** 估算跌幅 {float(a.estimate_return):.2f}%")

        content = f"以下自选基金跌幅超过 {threshold}%：\n" + "\n".join(lines)
        self._sender.send("大跌预警", content)
        return len(alerts)

    def check_rebalance(self) -> bool:
        """检查是否到调仓日并推送提醒。返回是否发送了提醒。"""
        today = date.today()
        messages = []
        if today.day <= 5:
            messages.append("卫星仓月度调仓窗口已到，请查看调仓建议")
            if today.month in (1, 4, 7, 10):
                messages.append("核心仓季度调仓窗口已到，请查看调仓建议")

        if not messages:
            return False

        content = "\n".join(f"- {m}" for m in messages)
        self._sender.send("调仓提醒", content)
        return True

    def check_all(self) -> dict:
        """执行所有启用的规则检查。"""
        results = {}
        rules = self._repo.get_notification_rules()

        for rule in rules:
            if not rule.enabled:
                continue
            params = rule.params if rule.params else {}

            if rule.rule_type == "dip_reminder":
                results["dip_reminder"] = self.check_dip_due()
            elif rule.rule_type == "drop_alert":
                threshold = params.get("threshold", -3.0)
                results["drop_alert"] = self.check_drop_alert(threshold)
            elif rule.rule_type == "rebalance_alert":
                results["rebalance_alert"] = self.check_rebalance()

        return results

    @staticmethod
    def _is_due(plan, today: date) -> bool:
        """判断定投计划今日是否到期。"""
        if plan.frequency == "weekly":
            return today.weekday() == plan.start_date.weekday()
        elif plan.frequency == "biweekly":
            delta = (today - plan.start_date).days
            return delta >= 0 and delta % 14 == 0
        elif plan.frequency == "monthly":
            return today.day == plan.start_date.day
        return False
