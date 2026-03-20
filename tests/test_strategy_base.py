"""策略基类与 Signal 的单元测试。"""
from __future__ import annotations

from datetime import date

import pytest

from fund_analyzer.strategy.base import BaseStrategy, Signal, score_to_signal


# ---------------------------------------------------------------------------
# Signal 数据类测试
# ---------------------------------------------------------------------------


class TestSignalCreation:
    """测试 Signal dataclass 的创建与属性访问。"""

    def test_signal_creation_buy(self):
        sig = Signal(action="buy", confidence=0.9, reason="测试买入信号")
        assert sig.action == "buy"
        assert sig.confidence == 0.9
        assert sig.reason == "测试买入信号"

    def test_signal_creation_sell(self):
        sig = Signal(action="sell", confidence=0.5, reason="测试卖出信号")
        assert sig.action == "sell"
        assert sig.confidence == 0.5

    def test_signal_creation_hold(self):
        sig = Signal(action="hold", confidence=0.0, reason="持有")
        assert sig.action == "hold"
        assert sig.confidence == 0.0

    def test_signal_is_dataclass(self):
        """Signal 应为 dataclass，支持相等比较。"""
        s1 = Signal(action="buy", confidence=0.8, reason="相同")
        s2 = Signal(action="buy", confidence=0.8, reason="相同")
        assert s1 == s2

    def test_signal_fields_are_accessible(self):
        sig = Signal(action="hold", confidence=0.0, reason="无操作")
        assert hasattr(sig, "action")
        assert hasattr(sig, "confidence")
        assert hasattr(sig, "reason")


# ---------------------------------------------------------------------------
# score_to_signal 函数测试
# ---------------------------------------------------------------------------


class TestScoreToSignal:
    """测试 score_to_signal 在各区间的行为。"""

    # --- 买入区间 ---

    def test_score_at_buy_threshold_returns_buy(self):
        sig = score_to_signal(80)
        assert sig.action == "buy"

    def test_score_above_buy_threshold_returns_buy(self):
        sig = score_to_signal(90)
        assert sig.action == "buy"

    def test_score_at_100_returns_buy_with_full_confidence(self):
        sig = score_to_signal(100)
        assert sig.action == "buy"
        assert sig.confidence == pytest.approx(1.0)

    def test_buy_confidence_formula(self):
        """confidence = (score - buy_threshold) / (100 - buy_threshold)"""
        score = 90
        buy_threshold = 80
        expected = (score - buy_threshold) / (100 - buy_threshold)
        sig = score_to_signal(score, buy_threshold=buy_threshold)
        assert sig.confidence == pytest.approx(expected)

    def test_buy_confidence_at_threshold_is_zero(self):
        sig = score_to_signal(80, buy_threshold=80)
        assert sig.confidence == pytest.approx(0.0)

    # --- 持有区间 ---

    def test_score_at_sell_threshold_returns_hold(self):
        sig = score_to_signal(60)
        assert sig.action == "hold"

    def test_score_between_thresholds_returns_hold(self):
        sig = score_to_signal(70)
        assert sig.action == "hold"

    def test_score_just_below_buy_threshold_returns_hold(self):
        sig = score_to_signal(79.9)
        assert sig.action == "hold"

    # --- 卖出区间 ---

    def test_score_below_sell_threshold_returns_sell(self):
        sig = score_to_signal(59)
        assert sig.action == "sell"

    def test_score_at_zero_returns_sell_with_full_confidence(self):
        sig = score_to_signal(0)
        assert sig.action == "sell"
        assert sig.confidence == pytest.approx(1.0)

    def test_sell_confidence_formula(self):
        """confidence = (sell_threshold - score) / sell_threshold"""
        score = 30
        sell_threshold = 60
        expected = (sell_threshold - score) / sell_threshold
        sig = score_to_signal(score, sell_threshold=sell_threshold)
        assert sig.confidence == pytest.approx(expected)

    def test_sell_confidence_just_below_threshold(self):
        score = 59
        sell_threshold = 60
        expected = (sell_threshold - score) / sell_threshold
        sig = score_to_signal(score, sell_threshold=sell_threshold)
        assert sig.confidence == pytest.approx(expected)

    # --- 自定义阈值 ---

    def test_custom_thresholds_buy(self):
        sig = score_to_signal(75, buy_threshold=70, sell_threshold=50)
        assert sig.action == "buy"

    def test_custom_thresholds_hold(self):
        sig = score_to_signal(60, buy_threshold=70, sell_threshold=50)
        assert sig.action == "hold"

    def test_custom_thresholds_sell(self):
        sig = score_to_signal(40, buy_threshold=70, sell_threshold=50)
        assert sig.action == "sell"

    # --- 返回类型 ---

    def test_returns_signal_instance(self):
        sig = score_to_signal(75)
        assert isinstance(sig, Signal)

    def test_reason_is_non_empty_string(self):
        for score in [20, 70, 90]:
            sig = score_to_signal(score)
            assert isinstance(sig.reason, str)
            assert len(sig.reason) > 0


# ---------------------------------------------------------------------------
# BaseStrategy 测试
# ---------------------------------------------------------------------------


class TestBaseStrategyIsAbstract:
    """测试 BaseStrategy 的抽象行为。"""

    def test_score_batch_raises_not_implemented(self):
        strategy = BaseStrategy(name="测试策略")
        with pytest.raises(NotImplementedError):
            strategy.score_batch(["000001"], date(2024, 1, 1))

    def test_signal_raises_not_implemented_via_score_batch(self):
        """signal() 默认调用 score_batch()，后者未实现时应传递 NotImplementedError。"""
        strategy = BaseStrategy(name="测试策略")
        with pytest.raises(NotImplementedError):
            strategy.signal("000001", date(2024, 1, 1))

    def test_name_is_set(self):
        strategy = BaseStrategy(name="我的策略")
        assert strategy.name == "我的策略"

    def test_subclass_can_override_score_batch(self):
        """子类正确实现 score_batch 后，signal() 应正常工作。"""

        class MockStrategy(BaseStrategy):
            def score_batch(
                self, fund_codes: list[str], as_of: date
            ) -> dict[str, float]:
                return {code: 85.0 for code in fund_codes}

        strategy = MockStrategy(name="Mock策略")
        sig = strategy.signal("000001", date(2024, 1, 1))
        assert isinstance(sig, Signal)
        assert sig.action == "buy"

    def test_signal_uses_universe_when_provided(self):
        """当传入 universe 时，score_batch 应接收整个 universe。"""
        received_codes: list[list[str]] = []

        class RecordingStrategy(BaseStrategy):
            def score_batch(
                self, fund_codes: list[str], as_of: date
            ) -> dict[str, float]:
                received_codes.append(list(fund_codes))
                return {code: 70.0 for code in fund_codes}

        strategy = RecordingStrategy(name="记录策略")
        universe = ["000001", "000002", "000003"]
        strategy.signal("000001", date(2024, 1, 1), universe=universe)
        assert received_codes[0] == universe

    def test_signal_uses_only_fund_code_when_universe_is_none(self):
        """universe 为 None 时，score_batch 仅接收目标基金代码。"""
        received_codes: list[list[str]] = []

        class RecordingStrategy(BaseStrategy):
            def score_batch(
                self, fund_codes: list[str], as_of: date
            ) -> dict[str, float]:
                received_codes.append(list(fund_codes))
                return {code: 70.0 for code in fund_codes}

        strategy = RecordingStrategy(name="记录策略")
        strategy.signal("000001", date(2024, 1, 1), universe=None)
        assert received_codes[0] == ["000001"]
