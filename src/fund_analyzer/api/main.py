"""FastAPI 应用入口。

配置 CORS、路由挂载、生命周期管理。
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, time, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from fund_analyzer.api.routers.backtest import router as backtest_router
from fund_analyzer.api.routers.dashboard import router as dashboard_router
from fund_analyzer.api.routers.dip import router as dip_router
from fund_analyzer.api.routers.portfolio import router as portfolio_router
from fund_analyzer.api.routers.rebalance import router as rebalance_router
from fund_analyzer.api.routers.risk import router as risk_router
from fund_analyzer.api.routers.screening import router as screening_router
from fund_analyzer.api.routers.settings import router as settings_router
from fund_analyzer.api.routers.watchlist import router as watchlist_router

logger = logging.getLogger(__name__)

# 全局引用，供 settings router 查询/控制
scheduled_sync_task: asyncio.Task | None = None
scheduled_email_task: asyncio.Task | None = None


async def _scheduled_sync(sync_time_str: str, max_nav_funds: int) -> None:
    """后台定时同步协程。每天到达 sync_time 时执行一次 sync_all。"""
    while True:
        now = datetime.now()
        target_time = time.fromisoformat(sync_time_str)
        target = datetime.combine(now.date(), target_time)
        if target <= now:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        logger.info(
            "定时同步已调度，下次执行时间: %s（%.0f 秒后）",
            target.strftime("%Y-%m-%d %H:%M:%S"),
            wait_seconds,
        )
        await asyncio.sleep(wait_seconds)

        logger.info("定时同步开始执行...")
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None, _run_sync, max_nav_funds
            )
            logger.info("定时同步完成: %s", result)
        except Exception:
            logger.exception("定时同步执行失败")


def _run_sync(max_nav_funds: int) -> dict:
    """在线程池中执行同步（阻塞操作）。"""
    from fund_analyzer.api.deps import _session_factory, get_settings
    from fund_analyzer.data.fetcher import FundFetcher
    from fund_analyzer.data.repository import FundRepository
    from fund_analyzer.data.sync import DataSyncer

    factory = _session_factory()
    session = factory()
    try:
        repo = FundRepository(session)
        syncer = DataSyncer(repo=repo, fetcher=FundFetcher())
        result = syncer.sync_all(max_nav_funds=max_nav_funds)
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


async def _scheduled_email_recommendation(send_time_str: str) -> None:
    """后台定时邮件推送协程。每天到达 send_time 时执行一次加仓建议邮件。"""
    while True:
        now = datetime.now()
        target_time = time.fromisoformat(send_time_str)
        target = datetime.combine(now.date(), target_time)
        if target <= now:
            target += timedelta(days=1)

        wait_seconds = (target - now).total_seconds()
        logger.info(
            "邮件推送已调度，下次执行时间: %s（%.0f 秒后）",
            target.strftime("%Y-%m-%d %H:%M:%S"),
            wait_seconds,
        )
        await asyncio.sleep(wait_seconds)

        logger.info("开始生成加仓建议邮件...")
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, _run_email_recommendation)
            logger.info("邮件推送完成")
        except Exception:
            logger.exception("邮件推送失败")


def _run_email_recommendation() -> None:
    """在线程池中执行邮件推荐（阻塞操作）。"""
    from fund_analyzer.api.deps import _session_factory, get_settings
    from fund_analyzer.data.repository import FundRepository
    from fund_analyzer.strategy.factor import FactorStrategy
    from fund_analyzer.strategy.momentum import MomentumStrategy
    from fund_analyzer.strategy.rotation import RotationStrategy
    from fund_analyzer.strategy.global_alloc import GlobalAllocStrategy
    from fund_analyzer.strategy.composite import CompositeStrategy
    from fund_analyzer.notification.recommendation import RecommendationService
    from fund_analyzer.notification.email_sender import EmailSender
    from datetime import date

    settings = get_settings()
    factory = _session_factory()
    session = factory()
    try:
        repo = FundRepository(session)
        strategies = {
            "factor": FactorStrategy(repo),
            "momentum": MomentumStrategy(repo),
            "rotation": RotationStrategy(repo),
            "global_alloc": GlobalAllocStrategy(repo),
        }
        composite = CompositeStrategy(
            strategies=strategies,
            core_weights=settings.strategy.core,
            satellite_weights=settings.strategy.satellite,
            buy_threshold=settings.strategy.signal_thresholds.buy,
            sell_threshold=settings.strategy.signal_thresholds.sell,
        )
        service = RecommendationService(
            repo=repo,
            composite=composite,
            buy_threshold=settings.strategy.signal_thresholds.buy,
            sell_threshold=settings.strategy.signal_thresholds.sell,
        )
        recommendations = service.generate_recommendations()
        html = service.render_html(recommendations)

        sender = EmailSender(settings.email)
        title = f"基金加仓建议 - {date.today()}"
        sender.send(title, html)
    except Exception:
        raise
    finally:
        session.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理。"""
    global scheduled_sync_task
    global scheduled_email_task

    from fund_analyzer.api.deps import get_settings

    settings = get_settings()
    if settings.schedule.enabled:
        scheduled_sync_task = asyncio.create_task(
            _scheduled_sync(
                settings.schedule.sync_time,
                settings.schedule.max_nav_funds,
            )
        )
        logger.info(
            "定时同步任务已启动（每天 %s）", settings.schedule.sync_time
        )

    if settings.email.enabled:
        scheduled_email_task = asyncio.create_task(
            _scheduled_email_recommendation(settings.email.send_time)
        )
        logger.info(
            "邮件推送任务已启动（每天 %s）", settings.email.send_time
        )

    yield

    if scheduled_sync_task is not None:
        scheduled_sync_task.cancel()
        try:
            await scheduled_sync_task
        except asyncio.CancelledError:
            pass
        logger.info("定时同步任务已停止")

    if scheduled_email_task is not None:
        scheduled_email_task.cancel()
        try:
            await scheduled_email_task
        except asyncio.CancelledError:
            pass
        logger.info("邮件推送任务已停止")


app = FastAPI(
    title="Fund Analyzer API",
    description="基金量化分析系统 API",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS 配置：允许前端开发服务器访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载路由
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(portfolio_router, prefix="/api/portfolio", tags=["portfolio"])
app.include_router(watchlist_router, prefix="/api/watchlist", tags=["watchlist"])
app.include_router(screening_router, prefix="/api/screening", tags=["screening"])
app.include_router(backtest_router, prefix="/api/backtest", tags=["backtest"])
app.include_router(dip_router, prefix="/api/dip", tags=["dip"])
app.include_router(rebalance_router, prefix="/api/rebalance", tags=["rebalance"])
app.include_router(risk_router, prefix="/api/risk", tags=["risk"])
app.include_router(settings_router, prefix="/api/settings", tags=["settings"])
