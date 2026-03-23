"""RecommendationService 单元测试。"""
from datetime import date
from unittest.mock import MagicMock, patch

from fund_analyzer.notification.recommendation import (
    FundRecommendation,
    RecommendationService,
)
from fund_analyzer.strategy.base import Signal


def _make_service(
    positions=None,
    watchlist=None,
    core_scores=None,
    satellite_scores=None,
    estimates=None,
    fund_infos=None,
):
    """创建带 mock 依赖的 RecommendationService。"""
    repo = MagicMock()
    composite = MagicMock()

    # 持仓
    if positions is None:
        positions = []
    repo.get_active_positions.return_value = positions

    # 自选
    if watchlist is None:
        watchlist = []
    repo.get_watchlist.return_value = watchlist

    # 评分
    if core_scores is None:
        core_scores = {}
    if satellite_scores is None:
        satellite_scores = {}
    composite.score_core.return_value = core_scores
    composite.score_satellite.return_value = satellite_scores

    # 估值
    if estimates is None:
        estimates = []
    repo.get_latest_estimates.return_value = estimates

    # 基金信息
    def _get_info(code):
        if fund_infos and code in fund_infos:
            info = MagicMock()
            info.fund_name = fund_infos[code]
            return info
        return None

    repo.get_fund_info.side_effect = _get_info

    return RecommendationService(repo=repo, composite=composite)


class TestGetTargetFundCodes:
    """测试 get_target_fund_codes。"""

    def test_empty(self):
        service = _make_service()
        assert service.get_target_fund_codes() == {}

    def test_positions_only(self):
        pos = MagicMock()
        pos.fund_code = "000001"
        pos.position_type = "core"
        service = _make_service(positions=[pos])
        result = service.get_target_fund_codes()
        assert result == {"000001": "core"}

    def test_watchlist_only(self):
        item = MagicMock()
        item.fund_code = "000002"
        item.fund_name = "测试基金"
        service = _make_service(watchlist=[item])
        result = service.get_target_fund_codes()
        assert result == {"000002": "watchlist"}

    def test_dedup_position_priority(self):
        """同一基金在持仓和自选中，以持仓类型为准。"""
        pos = MagicMock()
        pos.fund_code = "000001"
        pos.position_type = "satellite"
        item = MagicMock()
        item.fund_code = "000001"
        item.fund_name = "测试"
        service = _make_service(positions=[pos], watchlist=[item])
        result = service.get_target_fund_codes()
        assert result == {"000001": "satellite"}


class TestGenerateRecommendations:
    """测试 generate_recommendations。"""

    def test_empty_funds(self):
        service = _make_service()
        result = service.generate_recommendations(as_of=date(2024, 1, 1))
        assert result == []

    def test_filter_buy_only(self):
        """只返回 BUY 信号的基金。"""
        item1 = MagicMock()
        item1.fund_code = "000001"
        item1.fund_name = "高分基金"
        item2 = MagicMock()
        item2.fund_code = "000002"
        item2.fund_name = "低分基金"

        service = _make_service(
            watchlist=[item1, item2],
            satellite_scores={"000001": 85.0, "000002": 50.0},
            fund_infos={"000001": "高分基金", "000002": "低分基金"},
        )
        result = service.generate_recommendations(as_of=date(2024, 1, 1))
        assert len(result) == 1
        assert result[0].fund_code == "000001"
        assert result[0].score == 85.0

    def test_sorted_by_score_desc(self):
        """结果应按评分降序排列。"""
        items = []
        for code in ["000001", "000002", "000003"]:
            item = MagicMock()
            item.fund_code = code
            item.fund_name = f"基金{code}"
            items.append(item)

        service = _make_service(
            watchlist=items,
            satellite_scores={"000001": 82.0, "000002": 95.0, "000003": 88.0},
            fund_infos={"000001": "基金1", "000002": "基金2", "000003": "基金3"},
        )
        result = service.generate_recommendations(as_of=date(2024, 1, 1))
        scores = [r.score for r in result]
        assert scores == [95.0, 88.0, 82.0]

    def test_core_uses_core_scoring(self):
        """核心仓基金应使用 core 权重评分。"""
        pos = MagicMock()
        pos.fund_code = "000001"
        pos.position_type = "core"

        service = _make_service(
            positions=[pos],
            core_scores={"000001": 90.0},
            fund_infos={"000001": "核心基金"},
        )
        result = service.generate_recommendations(as_of=date(2024, 1, 1))
        assert len(result) == 1
        assert result[0].position_type == "core"
        service._composite.score_core.assert_called_once()


class TestRenderHtml:
    """测试 render_html。"""

    def test_empty_recommendations(self):
        service = _make_service()
        html = service.render_html([])
        assert "今日无加仓建议" in html

    def test_with_recommendations(self):
        service = _make_service()
        recs = [
            FundRecommendation(
                fund_code="000001",
                fund_name="测试基金",
                score=85.0,
                signal=Signal(action="buy", confidence=0.25, reason="score 85.00 >= buy_threshold 80"),
                estimate_nav=1.5678,
                estimate_return=-1.23,
                position_type="satellite",
            )
        ]
        html = service.render_html(recs)
        assert "000001" in html
        assert "测试基金" in html
        assert "85.0" in html
        assert "1.5678" in html
        assert "-1.23%" in html
        assert "卫星仓" in html

    def test_html_contains_disclaimer(self):
        service = _make_service()
        recs = [
            FundRecommendation(
                fund_code="000001",
                fund_name="测试",
                score=85.0,
                signal=Signal(action="buy", confidence=0.25, reason="test"),
            )
        ]
        html = service.render_html(recs)
        assert "不构成投资建议" in html
