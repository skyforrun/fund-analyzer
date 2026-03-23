"""风险评估计算器。"""
from __future__ import annotations


RISK_LEVEL_MAP: dict[int, dict] = {
    1: {"label": "保守型", "core_ratio": 70, "satellite_ratio": 30},
    2: {"label": "稳健型", "core_ratio": 50, "satellite_ratio": 50},
    3: {"label": "平衡型", "core_ratio": 30, "satellite_ratio": 70},
    4: {"label": "进取型", "core_ratio": 20, "satellite_ratio": 80},
    5: {"label": "激进型", "core_ratio": 10, "satellite_ratio": 90},
}


class RiskAssessor:
    """风险评估计算器。"""

    def calculate_score(self, answers: dict[str, int]) -> int:
        """根据问卷答案计算总分（0-100）。"""
        return sum(answers.values())

    def score_to_level(self, score: int) -> int:
        """将分数映射到风险等级（1-5）。"""
        if score <= 25:
            return 1
        elif score <= 45:
            return 2
        elif score <= 65:
            return 3
        elif score <= 85:
            return 4
        else:
            return 5

    def get_recommended_ratios(self, level: int) -> tuple[int, int]:
        """获取建议的仓位比例。返回 (core_ratio, satellite_ratio)。"""
        info = RISK_LEVEL_MAP.get(level, RISK_LEVEL_MAP[3])
        return info["core_ratio"], info["satellite_ratio"]

    def get_level_label(self, level: int) -> str:
        """获取风险等级标签。"""
        info = RISK_LEVEL_MAP.get(level, RISK_LEVEL_MAP[3])
        return info["label"]
