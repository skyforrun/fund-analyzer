"""策略基类与信号定义。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass
class Signal:
    """交易信号。"""

    action: Literal["buy", "sell", "hold"]
    confidence: float  # 0-1
    reason: str


def score_to_signal(
    score: float,
    buy_threshold: float = 80,
    sell_threshold: float = 60,
) -> Signal:
    """将评分转换为交易信号。

    Args:
        score: 基金评分，范围 0-100。
        buy_threshold: 买入阈值，默认 80。
        sell_threshold: 卖出阈值，默认 60。

    Returns:
        Signal 实例。
    """
    if score >= buy_threshold:
        confidence = (score - buy_threshold) / (100 - buy_threshold)
        return Signal(
            action="buy",
            confidence=float(confidence),
            reason=f"score {score:.2f} >= buy_threshold {buy_threshold}",
        )
    elif score < sell_threshold:
        confidence = (sell_threshold - score) / sell_threshold
        return Signal(
            action="sell",
            confidence=float(confidence),
            reason=f"score {score:.2f} < sell_threshold {sell_threshold}",
        )
    else:
        return Signal(
            action="hold",
            confidence=0.0,
            reason=(
                f"score {score:.2f} in [{sell_threshold}, {buy_threshold})"
            ),
        )


class BaseStrategy:
    """策略基类，所有具体策略均应继承此类。"""

    def __init__(self, name: str) -> None:
        self.name = name

    def score_batch(
        self,
        fund_codes: list[str],
        as_of: date,
    ) -> dict[str, float]:
        """批量计算基金评分。子类必须实现此方法。

        Args:
            fund_codes: 基金代码列表。
            as_of: 评分基准日期。

        Returns:
            以基金代码为键、评分（0-100）为值的字典。
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} 必须实现 score_batch 方法"
        )

    def signal(
        self,
        fund_code: str,
        as_of: date,
        universe: list[str] | None = None,
    ) -> Signal:
        """生成单只基金的交易信号。

        默认实现：调用 score_batch 获取评分，再通过 score_to_signal 转换为信号。

        Args:
            fund_code: 基金代码。
            as_of: 信号基准日期。
            universe: 评分时使用的基金池（含 fund_code），为 None 时仅评分 fund_code。

        Returns:
            Signal 实例。
        """
        codes = universe if universe is not None else [fund_code]
        scores = self.score_batch(codes, as_of)
        score = scores[fund_code]
        return score_to_signal(score)
