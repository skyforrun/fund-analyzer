"""调仓建议模块（RebalanceAdvisor）单元测试。

测试覆盖：
- test_generate_advice：generate() 返回包含 "actions" 键的字典
- test_advice_suggests_sells_and_buys：旧持仓被新推荐替代时，同时出现 sell 和 buy 行动
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from fund_analyzer.portfolio.rebalance import RebalanceAdvisor


# ---------------------------------------------------------------------------
# 测试常量
# ---------------------------------------------------------------------------

OLD_CORE = "OLD_CORE_FUND"
OLD_SAT = "OLD_SAT_FUND"
NEW_CORE = "NEW_CORE_FUND"
NEW_SAT = "NEW_SAT_FUND"

AS_OF = date(2024, 6, 30)
FUND_UNIVERSE = [OLD_CORE, OLD_SAT, NEW_CORE, NEW_SAT]


# ---------------------------------------------------------------------------
# 测试辅助函数
# ---------------------------------------------------------------------------


def make_position(fund_code: str, position_type: str) -> MagicMock:
    """创建模拟持仓对象。"""
    pos = MagicMock()
    pos.fund_code = fund_code
    pos.position_type = position_type
    return pos


def make_repo(core_codes: list[str], satellite_codes: list[str]) -> MagicMock:
    """创建模拟 FundRepository，get_active_positions 返回指定持仓列表。"""
    repo = MagicMock()
    positions = [make_position(c, "core") for c in core_codes] + [
        make_position(c, "satellite") for c in satellite_codes
    ]
    repo.get_active_positions.return_value = positions
    return repo


def make_composite(
    core_picks: list[tuple[str, float]],
    satellite_picks: list[tuple[str, float]],
) -> MagicMock:
    """创建模拟 CompositeStrategy。

    - recommend() 返回 (core_picks, satellite_picks)
    - signal() 返回 action="sell" 的 MagicMock Signal
    """
    composite = MagicMock()
    composite.recommend.return_value = (core_picks, satellite_picks)

    signal_mock = MagicMock()
    signal_mock.action = "sell"
    signal_mock.reason = "mocked signal reason"
    composite.signal.return_value = signal_mock

    return composite


# ---------------------------------------------------------------------------
# 测试类
# ---------------------------------------------------------------------------


class TestGenerateAdvice:
    """test_generate_advice：generate() 应返回包含 "actions" 键的字典。"""

    def test_returns_dict_with_actions_key(self):
        """generate() 必须返回字典且包含 'actions' 键。"""
        repo = make_repo(core_codes=[OLD_CORE], satellite_codes=[OLD_SAT])
        composite = make_composite(
            core_picks=[(NEW_CORE, 90.0)],
            satellite_picks=[(NEW_SAT, 85.0)],
        )
        advisor = RebalanceAdvisor(repo=repo, composite=composite)

        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        assert isinstance(result, dict)
        assert "actions" in result

    def test_returns_dict_with_all_required_keys(self):
        """generate() 返回的字典应包含 as_of、actions、core_picks、satellite_picks 四个键。"""
        repo = make_repo(core_codes=[OLD_CORE], satellite_codes=[OLD_SAT])
        composite = make_composite(
            core_picks=[(NEW_CORE, 90.0)],
            satellite_picks=[(NEW_SAT, 85.0)],
        )
        advisor = RebalanceAdvisor(repo=repo, composite=composite)

        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        assert "as_of" in result
        assert "actions" in result
        assert "core_picks" in result
        assert "satellite_picks" in result

    def test_as_of_value_matches_input(self):
        """返回结果中的 as_of 应与传入的日期一致。"""
        repo = make_repo(core_codes=[], satellite_codes=[])
        composite = make_composite(core_picks=[], satellite_picks=[])
        advisor = RebalanceAdvisor(repo=repo, composite=composite)

        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        assert result["as_of"] == AS_OF

    def test_actions_is_list(self):
        """返回结果中的 actions 应为列表类型。"""
        repo = make_repo(core_codes=[OLD_CORE], satellite_codes=[OLD_SAT])
        composite = make_composite(
            core_picks=[(NEW_CORE, 90.0)],
            satellite_picks=[(NEW_SAT, 85.0)],
        )
        advisor = RebalanceAdvisor(repo=repo, composite=composite)

        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        assert isinstance(result["actions"], list)

    def test_no_change_produces_no_actions(self):
        """当持仓与推荐完全一致时，不应产生任何调仓行动。"""
        repo = make_repo(core_codes=[OLD_CORE], satellite_codes=[OLD_SAT])
        composite = make_composite(
            core_picks=[(OLD_CORE, 90.0)],
            satellite_picks=[(OLD_SAT, 85.0)],
        )
        advisor = RebalanceAdvisor(repo=repo, composite=composite)

        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        assert result["actions"] == []

    def test_core_picks_and_satellite_picks_returned(self):
        """返回结果中的 core_picks 和 satellite_picks 应与推荐列表一致。"""
        expected_core = [(NEW_CORE, 90.0)]
        expected_satellite = [(NEW_SAT, 85.0)]

        repo = make_repo(core_codes=[], satellite_codes=[])
        composite = make_composite(
            core_picks=expected_core,
            satellite_picks=expected_satellite,
        )
        advisor = RebalanceAdvisor(repo=repo, composite=composite)

        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        assert result["core_picks"] == expected_core
        assert result["satellite_picks"] == expected_satellite

    def test_generate_with_default_as_of_uses_today(self):
        """不传 as_of 时，as_of 应默认为今日日期。"""
        repo = make_repo(core_codes=[], satellite_codes=[])
        composite = make_composite(core_picks=[], satellite_picks=[])
        advisor = RebalanceAdvisor(repo=repo, composite=composite)

        result = advisor.generate(FUND_UNIVERSE)

        assert result["as_of"] == date.today()


class TestAdviceSuggestsSellsAndBuys:
    """test_advice_suggests_sells_and_buys：旧持仓被新推荐替代时应同时出现 sell 和 buy。"""

    def _make_advisor(self) -> RebalanceAdvisor:
        """构造场景：当前持仓为 OLD_CORE（核心）和 OLD_SAT（卫星），
        新推荐为 NEW_CORE（核心）和 NEW_SAT（卫星）。"""
        repo = make_repo(core_codes=[OLD_CORE], satellite_codes=[OLD_SAT])
        composite = make_composite(
            core_picks=[(NEW_CORE, 90.0)],
            satellite_picks=[(NEW_SAT, 85.0)],
        )
        return RebalanceAdvisor(repo=repo, composite=composite)

    def test_sell_actions_present(self):
        """旧持仓未出现在新推荐中，应包含 sell 行动。"""
        advisor = self._make_advisor()
        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        sell_codes = {a["fund_code"] for a in result["actions"] if a["action"] == "sell"}
        assert OLD_CORE in sell_codes or OLD_SAT in sell_codes

    def test_buy_actions_present(self):
        """新推荐中未出现在当前持仓，应包含 buy 行动。"""
        advisor = self._make_advisor()
        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        buy_codes = {a["fund_code"] for a in result["actions"] if a["action"] == "buy"}
        assert NEW_CORE in buy_codes or NEW_SAT in buy_codes

    def test_old_core_gets_sell_action(self):
        """OLD_CORE 持仓不在新推荐核心列表中，应产生 sell 行动。"""
        advisor = self._make_advisor()
        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        sell_actions = [
            a for a in result["actions"]
            if a["fund_code"] == OLD_CORE and a["action"] == "sell"
        ]
        assert len(sell_actions) == 1
        assert sell_actions[0]["position_type"] == "core"

    def test_old_sat_gets_sell_action(self):
        """OLD_SAT 持仓不在新推荐卫星列表中，应产生 sell 行动。"""
        advisor = self._make_advisor()
        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        sell_actions = [
            a for a in result["actions"]
            if a["fund_code"] == OLD_SAT and a["action"] == "sell"
        ]
        assert len(sell_actions) == 1
        assert sell_actions[0]["position_type"] == "satellite"

    def test_new_core_gets_buy_action(self):
        """NEW_CORE 在新推荐核心列表中但不在当前持仓，应产生 buy 行动。"""
        advisor = self._make_advisor()
        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        buy_actions = [
            a for a in result["actions"]
            if a["fund_code"] == NEW_CORE and a["action"] == "buy"
        ]
        assert len(buy_actions) == 1
        assert buy_actions[0]["position_type"] == "core"

    def test_new_sat_gets_buy_action(self):
        """NEW_SAT 在新推荐卫星列表中但不在当前持仓，应产生 buy 行动。"""
        advisor = self._make_advisor()
        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        buy_actions = [
            a for a in result["actions"]
            if a["fund_code"] == NEW_SAT and a["action"] == "buy"
        ]
        assert len(buy_actions) == 1
        assert buy_actions[0]["position_type"] == "satellite"

    def test_each_action_has_required_fields(self):
        """每个行动应包含 fund_code、position_type、action、reason 四个字段。"""
        advisor = self._make_advisor()
        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        for action in result["actions"]:
            assert "fund_code" in action
            assert "position_type" in action
            assert "action" in action
            assert "reason" in action

    def test_action_values_are_valid(self):
        """action 字段的值只能是 'buy' 或 'sell'。"""
        advisor = self._make_advisor()
        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        for action in result["actions"]:
            assert action["action"] in ("buy", "sell")

    def test_total_actions_count(self):
        """场景：2 个旧持仓全部替换为 2 个新推荐，应产生 4 个行动（2 sell + 2 buy）。"""
        advisor = self._make_advisor()
        result = advisor.generate(FUND_UNIVERSE, as_of=AS_OF)

        sell_count = sum(1 for a in result["actions"] if a["action"] == "sell")
        buy_count = sum(1 for a in result["actions"] if a["action"] == "buy")

        assert sell_count == 2
        assert buy_count == 2
        assert len(result["actions"]) == 4
