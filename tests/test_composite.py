"""CompositeStrategy 单元测试。

使用 MagicMock 隔离子策略依赖，验证：
1. 加权评分计算正确性（score_core / score_satellite）
2. 交易信号生成合法性（signal）
3. 推荐结果数量与排序正确性（recommend）
"""
from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock

import pytest

from fund_analyzer.strategy.base import Signal
from fund_analyzer.strategy.composite import CompositeStrategy


# ---------------------------------------------------------------------------
# 辅助工厂函数
# ---------------------------------------------------------------------------


def _make_strategy(scores: dict[str, float]) -> MagicMock:
    """构造一个 score_batch 返回固定值的模拟策略。"""
    strategy = MagicMock()
    strategy.score_batch.return_value = scores
    return strategy


AS_OF = date(2024, 1, 1)
FUND_CODES = ["F001", "F002"]


# ---------------------------------------------------------------------------
# test_score_core：验证核心仓位加权计算
# ---------------------------------------------------------------------------


class TestScoreCore:
    """验证 score_core 使用 core_weights 正确计算加权平均分。"""

    def test_weighted_average_calculation(self):
        """F001: 85*70/100 + 50*30/100 = 74.5；F002: 60*70/100 + 75*30/100 = 64.5。"""
        factor = _make_strategy({"F001": 85.0, "F002": 60.0})
        global_alloc = _make_strategy({"F001": 50.0, "F002": 75.0})

        composite = CompositeStrategy(
            strategies={"factor": factor, "global_alloc": global_alloc},
            core_weights={"factor": 70, "global_alloc": 30},
            satellite_weights={"factor": 50, "global_alloc": 50},
        )

        scores = composite.score_core(FUND_CODES, AS_OF)

        assert scores["F001"] == pytest.approx(74.5)
        assert scores["F002"] == pytest.approx(64.5)

    def test_score_batch_called_with_correct_args(self):
        """score_batch 应以传入的 fund_codes 和 as_of 被调用。"""
        factor = _make_strategy({"F001": 80.0})
        global_alloc = _make_strategy({"F001": 60.0})

        composite = CompositeStrategy(
            strategies={"factor": factor, "global_alloc": global_alloc},
            core_weights={"factor": 60, "global_alloc": 40},
            satellite_weights={},
        )

        composite.score_core(["F001"], AS_OF)

        factor.score_batch.assert_called_once_with(["F001"], AS_OF)
        global_alloc.score_batch.assert_called_once_with(["F001"], AS_OF)

    def test_single_strategy_weight_returns_that_strategy_score(self):
        """仅使用单一策略权重时，结果应等于该策略的得分。"""
        factor = _make_strategy({"F001": 77.0, "F002": 55.0})

        composite = CompositeStrategy(
            strategies={"factor": factor},
            core_weights={"factor": 100},
            satellite_weights={},
        )

        scores = composite.score_core(FUND_CODES, AS_OF)

        assert scores["F001"] == pytest.approx(77.0)
        assert scores["F002"] == pytest.approx(55.0)


# ---------------------------------------------------------------------------
# test_score_satellite：验证卫星仓位加权计算
# ---------------------------------------------------------------------------


class TestScoreSatellite:
    """验证 score_satellite 使用 satellite_weights 正确计算加权平均分。"""

    def test_weighted_average_calculation(self):
        """使用不同于 core_weights 的 satellite_weights 进行验证。"""
        factor = _make_strategy({"F001": 70.0, "F002": 90.0})
        global_alloc = _make_strategy({"F001": 40.0, "F002": 60.0})

        # satellite_weights: factor=40, global_alloc=60
        # F001: 70*40/100 + 40*60/100 = 28 + 24 = 52.0
        # F002: 90*40/100 + 60*60/100 = 36 + 36 = 72.0
        composite = CompositeStrategy(
            strategies={"factor": factor, "global_alloc": global_alloc},
            core_weights={"factor": 50, "global_alloc": 50},
            satellite_weights={"factor": 40, "global_alloc": 60},
        )

        scores = composite.score_satellite(FUND_CODES, AS_OF)

        assert scores["F001"] == pytest.approx(52.0)
        assert scores["F002"] == pytest.approx(72.0)

    def test_satellite_independent_from_core(self):
        """score_satellite 应使用 satellite_weights，而非 core_weights。"""
        factor = _make_strategy({"F001": 80.0})
        global_alloc = _make_strategy({"F001": 20.0})

        # core: 80*100/100=80；satellite: 20*100/100=20
        composite = CompositeStrategy(
            strategies={"factor": factor, "global_alloc": global_alloc},
            core_weights={"factor": 100},
            satellite_weights={"global_alloc": 100},
        )

        core_score = composite.score_core(["F001"], AS_OF)["F001"]
        sat_score = composite.score_satellite(["F001"], AS_OF)["F001"]

        assert core_score == pytest.approx(80.0)
        assert sat_score == pytest.approx(20.0)


# ---------------------------------------------------------------------------
# test_signal_from_composite：验证 signal 方法返回合法 Signal
# ---------------------------------------------------------------------------


class TestSignalFromComposite:
    """验证 signal 方法能根据综合评分生成合法的 Signal 实例。"""

    def test_buy_signal_when_score_above_threshold(self):
        """评分高于 buy_threshold（默认 80）时应返回 buy 信号。"""
        factor = _make_strategy({"F001": 90.0})

        composite = CompositeStrategy(
            strategies={"factor": factor},
            core_weights={"factor": 100},
            satellite_weights={"factor": 100},
        )

        sig = composite.signal("F001", AS_OF, position_type="satellite")

        assert isinstance(sig, Signal)
        assert sig.action == "buy"
        assert 0.0 <= sig.confidence <= 1.0

    def test_sell_signal_when_score_below_threshold(self):
        """评分低于 sell_threshold（默认 60）时应返回 sell 信号。"""
        factor = _make_strategy({"F001": 40.0})

        composite = CompositeStrategy(
            strategies={"factor": factor},
            core_weights={"factor": 100},
            satellite_weights={"factor": 100},
        )

        sig = composite.signal("F001", AS_OF, position_type="satellite")

        assert isinstance(sig, Signal)
        assert sig.action == "sell"

    def test_hold_signal_when_score_in_between(self):
        """评分在 [sell_threshold, buy_threshold) 区间时应返回 hold 信号。"""
        factor = _make_strategy({"F001": 70.0})

        composite = CompositeStrategy(
            strategies={"factor": factor},
            core_weights={"factor": 100},
            satellite_weights={"factor": 100},
        )

        sig = composite.signal("F001", AS_OF)

        assert isinstance(sig, Signal)
        assert sig.action == "hold"

    def test_core_position_type_uses_core_weights(self):
        """position_type='core' 时应使用 core_weights 评分。"""
        factor = _make_strategy({"F001": 85.0})
        global_alloc = _make_strategy({"F001": 30.0})

        # core: 85*100/100=85 -> buy；satellite: 30*100/100=30 -> sell
        composite = CompositeStrategy(
            strategies={"factor": factor, "global_alloc": global_alloc},
            core_weights={"factor": 100},
            satellite_weights={"global_alloc": 100},
        )

        core_sig = composite.signal("F001", AS_OF, position_type="core")
        sat_sig = composite.signal("F001", AS_OF, position_type="satellite")

        assert core_sig.action == "buy"
        assert sat_sig.action == "sell"

    def test_custom_thresholds_respected(self):
        """自定义阈值应被正确应用。"""
        factor = _make_strategy({"F001": 55.0})

        # buy_threshold=50，score=55 应触发 buy
        composite = CompositeStrategy(
            strategies={"factor": factor},
            core_weights={"factor": 100},
            satellite_weights={"factor": 100},
            buy_threshold=50,
            sell_threshold=30,
        )

        sig = composite.signal("F001", AS_OF)

        assert sig.action == "buy"

    def test_signal_reason_is_non_empty_string(self):
        """Signal 的 reason 字段应为非空字符串。"""
        factor = _make_strategy({"F001": 75.0})

        composite = CompositeStrategy(
            strategies={"factor": factor},
            core_weights={"factor": 100},
            satellite_weights={"factor": 100},
        )

        sig = composite.signal("F001", AS_OF)

        assert isinstance(sig.reason, str)
        assert len(sig.reason) > 0


# ---------------------------------------------------------------------------
# test_recommend：验证 recommend 返回正确数量的推荐结果
# ---------------------------------------------------------------------------


class TestRecommend:
    """验证 recommend 返回按评分降序排列、数量正确的推荐列表。"""

    def _make_composite(self, factor_scores: dict[str, float]) -> CompositeStrategy:
        """构造仅使用 factor 策略的 CompositeStrategy。"""
        factor = _make_strategy(factor_scores)
        return CompositeStrategy(
            strategies={"factor": factor},
            core_weights={"factor": 100},
            satellite_weights={"factor": 100},
        )

    def test_returns_tuple_of_two_lists(self):
        """recommend 应返回包含两个列表的元组。"""
        codes = [f"F{i:03d}" for i in range(10)]
        scores = {code: float(i * 10) for i, code in enumerate(codes)}
        composite = self._make_composite(scores)

        result = composite.recommend(codes, AS_OF)

        assert isinstance(result, tuple)
        assert len(result) == 2
        core_picks, sat_picks = result
        assert isinstance(core_picks, list)
        assert isinstance(sat_picks, list)

    def test_core_top_n_correct_count(self):
        """core_picks 数量应等于 core_top_n。"""
        codes = [f"F{i:03d}" for i in range(10)]
        scores = {code: float(i * 10) for i, code in enumerate(codes)}
        composite = self._make_composite(scores)

        core_picks, _ = composite.recommend(codes, AS_OF, core_top_n=3)

        assert len(core_picks) == 3

    def test_satellite_top_n_correct_count(self):
        """satellite_picks 数量应等于 satellite_top_n。"""
        codes = [f"F{i:03d}" for i in range(10)]
        scores = {code: float(i * 10) for i, code in enumerate(codes)}
        composite = self._make_composite(scores)

        _, sat_picks = composite.recommend(codes, AS_OF, satellite_top_n=7)

        assert len(sat_picks) == 7

    def test_picks_sorted_by_score_descending(self):
        """推荐结果应按评分从高到低排列。"""
        scores = {"F001": 85.0, "F002": 60.0, "F003": 92.0, "F004": 70.0}
        composite = self._make_composite(scores)

        core_picks, sat_picks = composite.recommend(
            list(scores.keys()), AS_OF, core_top_n=2, satellite_top_n=3
        )

        core_score_values = [s for _, s in core_picks]
        assert core_score_values == sorted(core_score_values, reverse=True)

        sat_score_values = [s for _, s in sat_picks]
        assert sat_score_values == sorted(sat_score_values, reverse=True)

    def test_top_scored_fund_appears_first_in_core(self):
        """评分最高的基金应排在 core_picks 第一位。"""
        scores = {"F001": 85.0, "F002": 60.0, "F003": 92.0}
        composite = self._make_composite(scores)

        core_picks, _ = composite.recommend(list(scores.keys()), AS_OF, core_top_n=1)

        assert core_picks[0][0] == "F003"
        assert core_picks[0][1] == pytest.approx(92.0)

    def test_fewer_funds_than_top_n(self):
        """候选基金数少于 top_n 时，应返回全部基金（不报错）。"""
        scores = {"F001": 80.0, "F002": 70.0}
        composite = self._make_composite(scores)

        core_picks, sat_picks = composite.recommend(
            list(scores.keys()), AS_OF, core_top_n=5, satellite_top_n=5
        )

        assert len(core_picks) == 2
        assert len(sat_picks) == 2

    def test_picks_are_code_score_tuples(self):
        """推荐结果中每项应为 (str, float) 元组。"""
        scores = {"F001": 80.0, "F002": 70.0, "F003": 60.0}
        composite = self._make_composite(scores)

        core_picks, sat_picks = composite.recommend(
            list(scores.keys()), AS_OF, core_top_n=2, satellite_top_n=2
        )

        for item in core_picks + sat_picks:
            code, score = item
            assert isinstance(code, str)
            assert isinstance(score, float)
