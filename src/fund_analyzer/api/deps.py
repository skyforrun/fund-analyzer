"""FastAPI 依赖注入模块。

使用 @lru_cache 缓存应用级单例（Settings、SessionFactory），
使用 FastAPI Depends + yield 管理请求级 Session 生命周期。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from fund_analyzer.config import Settings, load_config
from fund_analyzer.database import create_session_factory
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.data.fetcher import FundFetcher
from fund_analyzer.data.sync import DataSyncer
from fund_analyzer.strategy.factor import FactorStrategy
from fund_analyzer.strategy.momentum import MomentumStrategy
from fund_analyzer.strategy.rotation import RotationStrategy
from fund_analyzer.strategy.global_alloc import GlobalAllocStrategy
from fund_analyzer.strategy.composite import CompositeStrategy
from fund_analyzer.portfolio.manager import PortfolioManager
from fund_analyzer.portfolio.tracker import PortfolioTracker
from fund_analyzer.portfolio.dip import DipManager
from fund_analyzer.portfolio.rebalance import RebalanceAdvisor
from fund_analyzer.backtest.engine import BacktestEngine

_CONFIG_CANDIDATES = ["settings.yaml", "config/settings.yaml"]


# ---------------------------------------------------------------------------
# 应用级单例（通过 lru_cache 实现）
# ---------------------------------------------------------------------------

@lru_cache
def get_settings() -> Settings:
    """加载并缓存全局配置。"""
    for p in _CONFIG_CANDIDATES:
        path = Path(p)
        if path.exists():
            return load_config(str(path))
    return Settings()


@lru_cache
def _session_factory():
    """创建并缓存 SQLAlchemy SessionFactory。"""
    return create_session_factory(get_settings())


# ---------------------------------------------------------------------------
# 请求级依赖（通过 Depends 注入）
# ---------------------------------------------------------------------------

def get_db_session() -> Generator[Session, None, None]:
    """每请求创建一个 DB Session，请求结束后关闭。"""
    factory = _session_factory()
    session = factory()
    try:
        yield session
    finally:
        session.close()


def get_repo(
    session: Session = Depends(get_db_session),
) -> FundRepository:
    """获取数据仓储实例。"""
    return FundRepository(session)


def get_fetcher() -> FundFetcher:
    """获取数据采集器实例。"""
    return FundFetcher()


def get_tracker(
    repo: FundRepository = Depends(get_repo),
) -> PortfolioTracker:
    """获取组合收益追踪器。"""
    return PortfolioTracker(repo)


def get_composite(
    repo: FundRepository = Depends(get_repo),
    settings: Settings = Depends(get_settings),
) -> CompositeStrategy:
    """获取综合策略引擎。"""
    strategies = {
        "factor": FactorStrategy(repo),
        "momentum": MomentumStrategy(repo),
        "rotation": RotationStrategy(repo),
        "global_alloc": GlobalAllocStrategy(repo),
    }
    return CompositeStrategy(
        strategies=strategies,
        core_weights=settings.strategy.core,
        satellite_weights=settings.strategy.satellite,
        buy_threshold=settings.strategy.signal_thresholds.buy,
        sell_threshold=settings.strategy.signal_thresholds.sell,
    )


def get_manager(
    repo: FundRepository = Depends(get_repo),
) -> PortfolioManager:
    """获取组合管理器。"""
    return PortfolioManager(repo)


def get_dip_manager(
    repo: FundRepository = Depends(get_repo),
) -> DipManager:
    """获取定投管理器。"""
    return DipManager(repo)


def get_rebalance_advisor(
    repo: FundRepository = Depends(get_repo),
    composite: CompositeStrategy = Depends(get_composite),
    settings: Settings = Depends(get_settings),
) -> RebalanceAdvisor:
    """获取调仓建议器。"""
    return RebalanceAdvisor(
        repo=repo,
        composite=composite,
        core_top_n=settings.backtest.core_top_n,
        satellite_top_n=settings.backtest.satellite_top_n,
    )


def get_syncer(
    repo: FundRepository = Depends(get_repo),
) -> DataSyncer:
    """获取数据同步器。"""
    return DataSyncer(repo=repo, fetcher=FundFetcher())


def get_backtest_engine(
    repo: FundRepository = Depends(get_repo),
    composite: CompositeStrategy = Depends(get_composite),
    settings: Settings = Depends(get_settings),
) -> BacktestEngine:
    """获取回测引擎。"""
    freq_map = {"quarterly": 3, "monthly": 1, "weekly": 1}
    return BacktestEngine(
        repo=repo,
        composite=composite,
        initial_capital=settings.backtest.initial_capital,
        core_ratio=settings.portfolio.core_ratio / 100,
        satellite_ratio=settings.portfolio.satellite_ratio / 100,
        core_top_n=settings.backtest.core_top_n,
        satellite_top_n=settings.backtest.satellite_top_n,
        buy_fee=settings.backtest.buy_fee_rate,
        sell_fee=settings.backtest.sell_fee_rate,
        core_rebalance_months=freq_map.get(settings.backtest.core_rebalance_freq, 3),
        satellite_rebalance_months=freq_map.get(settings.backtest.satellite_rebalance_freq, 1),
    )
