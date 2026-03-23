"""加仓推荐服务。

收集持仓 + 自选基金并集，基于综合策略评分生成加仓建议，渲染 HTML 邮件。
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from typing import Optional

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.base import Signal, score_to_signal
from fund_analyzer.strategy.composite import CompositeStrategy

logger = logging.getLogger(__name__)


@dataclass
class FundRecommendation:
    """单只基金的加仓推荐。"""
    fund_code: str
    fund_name: str
    score: float
    signal: Signal
    estimate_nav: Optional[float] = None
    estimate_return: Optional[float] = None
    position_type: str = "watchlist"


class RecommendationService:
    """每日加仓推荐服务。"""

    def __init__(
        self,
        repo: FundRepository,
        composite: CompositeStrategy,
        buy_threshold: float = 80,
        sell_threshold: float = 60,
    ) -> None:
        self._repo = repo
        self._composite = composite
        self._buy_threshold = buy_threshold
        self._sell_threshold = sell_threshold

    def get_target_fund_codes(self) -> dict[str, str]:
        """获取持仓 + 自选基金并集，返回 {fund_code: position_type} 映射。

        持仓基金标记为 core/satellite，自选基金标记为 watchlist。
        如果同一基金既在持仓又在自选，以持仓类型为准。
        """
        result: dict[str, str] = {}

        # 持仓基金
        positions = self._repo.get_active_positions()
        for pos in positions:
            result[pos.fund_code] = pos.position_type

        # 自选基金（不覆盖已有持仓类型）
        watchlist = self._repo.get_watchlist()
        for item in watchlist:
            if item.fund_code not in result:
                result[item.fund_code] = "watchlist"

        return result

    def generate_recommendations(
        self, as_of: Optional[date] = None,
    ) -> list[FundRecommendation]:
        """生成加仓推荐列表。

        流程：
        1. 获取持仓 + 自选基金并集
        2. 按 position_type 分别用核心/卫星权重评分
        3. 过滤出 BUY 信号的基金
        4. 获取实时估值
        5. 按评分降序排列返回
        """
        if as_of is None:
            as_of = date.today()

        fund_map = self.get_target_fund_codes()
        if not fund_map:
            logger.info("无持仓或自选基金，跳过推荐")
            return []

        all_codes = list(fund_map.keys())

        # 分组评分
        core_codes = [c for c, t in fund_map.items() if t == "core"]
        other_codes = [c for c, t in fund_map.items() if t != "core"]

        scores: dict[str, float] = {}
        if core_codes:
            scores.update(self._composite.score_core(core_codes, as_of))
        if other_codes:
            scores.update(self._composite.score_satellite(other_codes, as_of))

        # 过滤 BUY 信号
        recommendations: list[FundRecommendation] = []
        for code in all_codes:
            score = scores.get(code, 0.0)
            signal = score_to_signal(score, self._buy_threshold, self._sell_threshold)
            if signal.action != "buy":
                continue

            fund_info = self._repo.get_fund_info(code)
            fund_name = fund_info.fund_name if fund_info else code

            recommendations.append(FundRecommendation(
                fund_code=code,
                fund_name=fund_name,
                score=score,
                signal=signal,
                position_type=fund_map[code],
            ))

        # 获取估值数据
        if recommendations:
            rec_codes = [r.fund_code for r in recommendations]
            estimates = self._repo.get_latest_estimates(rec_codes)
            est_map = {e.fund_code: e for e in estimates}
            for rec in recommendations:
                est = est_map.get(rec.fund_code)
                if est:
                    rec.estimate_nav = float(est.estimate_nav) if est.estimate_nav else None
                    rec.estimate_return = float(est.estimate_return) if est.estimate_return else None

        # 按评分降序排列
        recommendations.sort(key=lambda r: r.score, reverse=True)

        logger.info("生成 %d 条加仓建议", len(recommendations))
        return recommendations

    def render_html(self, recommendations: list[FundRecommendation]) -> str:
        """将推荐列表渲染为 HTML 邮件内容。"""
        today = date.today().strftime("%Y-%m-%d")

        if not recommendations:
            return f"""
            <div style="font-family: 'Microsoft YaHei', Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 8px 8px 0 0;">
                    <h2 style="color: #fff; margin: 0; font-size: 20px;">📊 基金加仓建议</h2>
                    <p style="color: rgba(255,255,255,0.8); margin: 5px 0 0; font-size: 14px;">{today}</p>
                </div>
                <div style="background: #f8f9fa; padding: 30px; text-align: center; border-radius: 0 0 8px 8px; border: 1px solid #e9ecef;">
                    <p style="color: #6c757d; font-size: 16px; margin: 0;">今日无加仓建议，请耐心等待时机。</p>
                </div>
            </div>
            """

        # 构建表格行
        rows_html = ""
        for i, rec in enumerate(recommendations):
            bg = "#ffffff" if i % 2 == 0 else "#f8f9fa"
            score_color = "#27ae60" if rec.score >= 90 else "#2ecc71"

            est_nav_str = f"{rec.estimate_nav:.4f}" if rec.estimate_nav else "N/A"

            if rec.estimate_return is not None:
                ret_color = "#e74c3c" if rec.estimate_return >= 0 else "#27ae60"
                ret_str = f'<span style="color: {ret_color};">{rec.estimate_return:+.2f}%</span>'
            else:
                ret_str = "N/A"

            type_labels = {"core": "核心仓", "satellite": "卫星仓", "watchlist": "自选"}
            type_label = type_labels.get(rec.position_type, rec.position_type)

            rows_html += f"""
            <tr style="background: {bg};">
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef;">{rec.fund_code}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef;">{rec.fund_name}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; text-align: center;">
                    <span style="background: {score_color}; color: #fff; padding: 2px 8px; border-radius: 12px; font-size: 13px;">
                        {rec.score:.1f}
                    </span>
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; text-align: center;">
                    {rec.signal.confidence:.0%}
                </td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; text-align: right;">{est_nav_str}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; text-align: right;">{ret_str}</td>
                <td style="padding: 12px; border-bottom: 1px solid #e9ecef; text-align: center;">
                    <span style="background: #eee; padding: 2px 6px; border-radius: 4px; font-size: 12px;">{type_label}</span>
                </td>
            </tr>
            <tr style="background: {bg};">
                <td colspan="7" style="padding: 4px 12px 12px; border-bottom: 1px solid #dee2e6; color: #6c757d; font-size: 12px;">
                    💡 {rec.signal.reason}
                </td>
            </tr>
            """

        return f"""
        <div style="font-family: 'Microsoft YaHei', Arial, sans-serif; max-width: 700px; margin: 0 auto; padding: 20px;">
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; border-radius: 8px 8px 0 0;">
                <h2 style="color: #fff; margin: 0; font-size: 20px;">📊 基金加仓建议</h2>
                <p style="color: rgba(255,255,255,0.8); margin: 5px 0 0; font-size: 14px;">{today} · 共 {len(recommendations)} 只基金</p>
            </div>
            <div style="border: 1px solid #e9ecef; border-top: none; border-radius: 0 0 8px 8px; overflow: hidden;">
                <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
                    <thead>
                        <tr style="background: #2c3e50; color: #fff;">
                            <th style="padding: 10px 12px; text-align: left;">代码</th>
                            <th style="padding: 10px 12px; text-align: left;">名称</th>
                            <th style="padding: 10px 12px; text-align: center;">评分</th>
                            <th style="padding: 10px 12px; text-align: center;">置信度</th>
                            <th style="padding: 10px 12px; text-align: right;">估值</th>
                            <th style="padding: 10px 12px; text-align: right;">涨跌幅</th>
                            <th style="padding: 10px 12px; text-align: center;">仓位</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows_html}
                    </tbody>
                </table>
            </div>
            <div style="margin-top: 16px; padding: 12px; background: #fff3cd; border-radius: 6px; border: 1px solid #ffc107;">
                <p style="margin: 0; font-size: 12px; color: #856404;">
                    ⚠️ 以上数据基于实时估值，仅供参考，不构成投资建议。实际净值以基金公司公布为准。
                </p>
            </div>
        </div>
        """
