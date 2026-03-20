"""CLI 命令行接口模块。

基于 Typer 框架，提供数据管理、组合管理、定投管理、配置管理等命令组。
使用 Rich 库进行表格和格式化输出。
"""
from __future__ import annotations

import sys
from decimal import Decimal
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

# -----------------------------------------------------------------------
# 全局 Console 实例
# -----------------------------------------------------------------------

console = Console()

# -----------------------------------------------------------------------
# 配置路径常量
# -----------------------------------------------------------------------

_DEFAULT_CONFIG_PATH = "config/settings.yaml"

# -----------------------------------------------------------------------
# 辅助函数（私有，便于测试时 mock）
# -----------------------------------------------------------------------


def _load_settings(config_path: str = _DEFAULT_CONFIG_PATH):
    """从指定路径加载配置文件，若文件不存在则打印错误并退出。

    Parameters
    ----------
    config_path : str
        配置文件路径，默认为 config/settings.yaml。

    Returns
    -------
    Settings
        已加载的配置对象。
    """
    from fund_analyzer.config import load_config

    if not Path(config_path).exists():
        console.print(f"[red]错误：配置文件不存在：{config_path}[/red]")
        raise typer.Exit(code=1)
    try:
        return load_config(config_path)
    except Exception as exc:
        console.print(f"[red]错误：加载配置文件失败：{exc}[/red]")
        raise typer.Exit(code=1)


def _get_session(settings=None):
    """根据配置创建数据库 Session。

    Parameters
    ----------
    settings : Settings, optional
        配置对象，未提供则自动加载。

    Returns
    -------
    Session
        SQLAlchemy Session 实例。
    """
    from fund_analyzer.database import create_session_factory

    if settings is None:
        settings = _load_settings()
    session_factory = create_session_factory(settings)
    return session_factory()


def _get_repo(session=None):
    """创建 FundRepository 实例。

    Parameters
    ----------
    session : Session, optional
        数据库 Session，未提供则自动创建。

    Returns
    -------
    FundRepository
        数据仓储对象。
    """
    from fund_analyzer.data.repository import FundRepository

    if session is None:
        session = _get_session()
    return FundRepository(session)


def _get_syncer(repo=None):
    """创建 DataSyncer 实例（包含 FundFetcher）。

    Parameters
    ----------
    repo : FundRepository, optional
        数据仓储，未提供则自动创建。

    Returns
    -------
    DataSyncer
        数据同步器对象。
    """
    from fund_analyzer.data.fetcher import FundFetcher
    from fund_analyzer.data.sync import DataSyncer

    if repo is None:
        repo = _get_repo()
    settings = _load_settings()
    fetcher = FundFetcher(
        request_interval=settings.data.sync_interval_seconds,
        retry_count=settings.data.retry_count,
    )
    return DataSyncer(repo=repo, fetcher=fetcher)


def _get_tracker(repo=None):
    """创建 PortfolioTracker 实例。

    Parameters
    ----------
    repo : FundRepository, optional
        数据仓储，未提供则自动创建。

    Returns
    -------
    PortfolioTracker
        组合收益追踪器对象。
    """
    from fund_analyzer.portfolio.tracker import PortfolioTracker

    if repo is None:
        repo = _get_repo()
    return PortfolioTracker(repo=repo)


# -----------------------------------------------------------------------
# 主 App
# -----------------------------------------------------------------------

app = typer.Typer(
    name="fund-analyzer",
    help="基金分析工具 — 数据同步、组合管理、定投管理",
    add_completion=False,
)

# -----------------------------------------------------------------------
# Sub-apps
# -----------------------------------------------------------------------

data_app = typer.Typer(name="data", help="数据管理")
portfolio_app = typer.Typer(name="portfolio", help="组合管理")
dip_app = typer.Typer(name="dip", help="定投管理")
config_app = typer.Typer(name="config", help="配置管理")

app.add_typer(data_app)
app.add_typer(portfolio_app)
app.add_typer(dip_app)
app.add_typer(config_app)

# -----------------------------------------------------------------------
# config 命令组
# -----------------------------------------------------------------------


@config_app.command("show")
def config_show():
    """显示当前配置信息（数据库、比例、权重）。"""
    settings = _load_settings()

    console.print("[bold cyan]当前配置[/bold cyan]")

    # 数据库配置
    db_table = Table(title="数据库配置", show_header=True, header_style="bold magenta")
    db_table.add_column("参数", style="dim")
    db_table.add_column("值")
    db_table.add_row("主机", settings.database.host)
    db_table.add_row("端口", str(settings.database.port))
    db_table.add_row("数据库名", settings.database.name)
    db_table.add_row("用户名", settings.database.user)
    console.print(db_table)

    # 组合配置
    portfolio_table = Table(title="组合配置", show_header=True, header_style="bold magenta")
    portfolio_table.add_column("参数", style="dim")
    portfolio_table.add_column("值")
    portfolio_table.add_row("核心仓比例", f"{settings.portfolio.core_ratio}%")
    portfolio_table.add_row("卫星仓比例", f"{settings.portfolio.satellite_ratio}%")
    console.print(portfolio_table)

    # 策略权重
    weights_table = Table(title="策略权重", show_header=True, header_style="bold magenta")
    weights_table.add_column("类别", style="dim")
    weights_table.add_column("权重配置")
    for key, val in settings.strategy.core.items():
        weights_table.add_row(f"核心/{key}", str(val))
    for key, val in settings.strategy.satellite.items():
        weights_table.add_row(f"卫星/{key}", str(val))
    console.print(weights_table)


# -----------------------------------------------------------------------
# data 命令组
# -----------------------------------------------------------------------


@data_app.command("sync")
def data_sync(
    full: bool = typer.Option(False, "--full", help="是否全量同步（重刷所有历史数据）"),
):
    """运行数据同步，打印同步摘要。"""
    console.print("[bold]开始同步数据...[/bold]")
    syncer = _get_syncer()
    result = syncer.sync_all(full=full)

    summary_table = Table(title="同步摘要", show_header=True, header_style="bold green")
    summary_table.add_column("类型", style="dim")
    summary_table.add_column("数量", justify="right")
    summary_table.add_row("基金列表", str(result.get("funds", 0)))
    summary_table.add_row("净值记录（基金数）", str(result.get("navs", 0)))
    summary_table.add_row("指数行情", str(result.get("indices", 0)))
    summary_table.add_row("警告数量", str(len(result.get("warnings", []))))
    console.print(summary_table)

    warnings = result.get("warnings", [])
    if warnings:
        console.print("[yellow]同步警告：[/yellow]")
        for w in warnings:
            console.print(f"  [yellow]⚠[/yellow] {w}")

    console.print("[green]同步完成。[/green]")


# -----------------------------------------------------------------------
# portfolio 命令组
# -----------------------------------------------------------------------


@portfolio_app.command("show")
def portfolio_show():
    """显示当前持仓表格（核心仓/卫星仓分组）。"""
    tracker = _get_tracker()
    summary = tracker.summary()

    holdings = summary.get("holdings", [])
    if not holdings:
        console.print("[dim]当前无持仓记录。[/dim]")
        return

    # 按 position_type 分组
    core_holdings = [h for h in holdings if h["position_type"] == "core"]
    satellite_holdings = [h for h in holdings if h["position_type"] != "core"]

    def _make_table(title: str, rows: list[dict]) -> Table:
        table = Table(title=title, show_header=True, header_style="bold blue")
        table.add_column("基金代码", style="dim")
        table.add_column("份额", justify="right")
        table.add_column("成本价", justify="right")
        table.add_column("当前净值", justify="right")
        table.add_column("市值", justify="right")
        table.add_column("盈亏", justify="right")
        table.add_column("收益率", justify="right")

        for h in rows:
            return_pct = h.get("return_pct")
            return_str = f"{return_pct:.2f}%" if return_pct is not None else "N/A"
            pnl = h.get("pnl", Decimal("0"))
            pnl_color = "green" if pnl >= 0 else "red"

            table.add_row(
                h["fund_code"],
                str(h["shares"]),
                str(h["cost_price"]),
                str(h["current_nav"]) if h["current_nav"] is not None else "N/A",
                f"{h['market_value']:.2f}",
                f"[{pnl_color}]{pnl:.2f}[/{pnl_color}]",
                f"[{pnl_color}]{return_str}[/{pnl_color}]",
            )
        return table

    if core_holdings:
        console.print(_make_table("核心仓", core_holdings))
    if satellite_holdings:
        console.print(_make_table("卫星仓", satellite_holdings))

    # 汇总信息
    total_mv = summary.get("total_market_value", Decimal("0"))
    total_cost = summary.get("total_cost", Decimal("0"))
    total_pnl = summary.get("total_pnl", Decimal("0"))
    total_return = summary.get("total_return_pct")

    console.print(
        f"\n[bold]总市值：[/bold]{total_mv:.2f}  "
        f"[bold]总成本：[/bold]{total_cost:.2f}  "
        f"[bold]总盈亏：[/bold]{total_pnl:.2f}  "
        f"[bold]总收益率：[/bold]"
        + (f"{total_return:.2f}%" if total_return is not None else "N/A")
    )


@portfolio_app.command("buy")
def portfolio_buy(
    fund_code: str = typer.Argument(..., help="基金代码"),
    amount: float = typer.Option(..., "--amount", help="买入金额（元）"),
    position_type: str = typer.Option("satellite", "--type", help="持仓类型：core 或 satellite"),
):
    """记录买入操作（通过 PortfolioManager）。"""
    from fund_analyzer.portfolio.manager import PortfolioManager

    repo = _get_repo()
    manager = PortfolioManager(repo=repo)

    # 使用成本价 1.0 作为默认净值（实际使用时应传入当日净值）
    try:
        position = manager.buy(
            fund_code=fund_code,
            amount=amount,
            nav=1.0,
            position_type=position_type,
        )
        repo._session.commit()
        console.print(
            f"[green]买入成功：[/green]{fund_code}，"
            f"金额：{amount}，份额：{position.shares}，"
            f"类型：{position_type}"
        )
    except Exception as exc:
        console.print(f"[red]买入失败：{exc}[/red]")
        raise typer.Exit(code=1)


@portfolio_app.command("sell")
def portfolio_sell(
    fund_code: str = typer.Argument(..., help="基金代码"),
    shares: float = typer.Option(..., "--shares", help="卖出份额"),
):
    """记录卖出操作（通过 PortfolioManager）。"""
    from fund_analyzer.portfolio.manager import PortfolioManager

    repo = _get_repo()
    manager = PortfolioManager(repo=repo)

    try:
        manager.sell(
            fund_code=fund_code,
            shares=shares,
            nav=1.0,
        )
        repo._session.commit()
        console.print(f"[green]卖出成功：[/green]{fund_code}，份额：{shares}")
    except Exception as exc:
        console.print(f"[red]卖出失败：{exc}[/red]")
        raise typer.Exit(code=1)


# -----------------------------------------------------------------------
# 顶层命令（占位）
# -----------------------------------------------------------------------


@app.command("backtest")
def backtest(
    start: Optional[str] = typer.Option(None, "--start", help="回测开始日期，格式 YYYY-MM-DD"),
    end: Optional[str] = typer.Option(None, "--end", help="回测结束日期，格式 YYYY-MM-DD"),
    core_ratio: Optional[int] = typer.Option(None, "--core-ratio", help="核心仓比例（整数）"),
    satellite_ratio: Optional[int] = typer.Option(None, "--satellite-ratio", help="卫星仓比例（整数）"),
):
    """[占位] 回测功能，即将推出。"""
    console.print(
        "[yellow]回测功能尚未实现（占位命令）。[/yellow]\n"
        f"参数：start={start}, end={end}, "
        f"core_ratio={core_ratio}, satellite_ratio={satellite_ratio}"
    )


@app.command("screen")
def screen(
    type_: Optional[str] = typer.Option(None, "--type", help="筛选类型"),
    top: Optional[int] = typer.Option(10, "--top", help="返回前 N 条结果"),
):
    """[占位] 基金筛选功能，即将推出。"""
    console.print(
        f"[yellow]基金筛选功能尚未实现（占位命令）。[/yellow]\n"
        f"参数：type={type_}, top={top}"
    )


@app.command("rebalance")
def rebalance():
    """[占位] 再平衡功能，即将推出。"""
    console.print("[yellow]再平衡功能尚未实现（占位命令）。[/yellow]")


# -----------------------------------------------------------------------
# dip 命令组
# -----------------------------------------------------------------------


@dip_app.command("create")
def dip_create(
    fund_code: str = typer.Argument(..., help="基金代码"),
    amount: float = typer.Option(..., "--amount", help="每期定投金额（元）"),
    freq: str = typer.Option("monthly", "--freq", help="定投频率：weekly / biweekly / monthly"),
    smart: bool = typer.Option(False, "--smart", help="是否启用智能定投"),
):
    """创建定投计划。"""
    from fund_analyzer.portfolio.dip import DipManager

    repo = _get_repo()
    manager = DipManager(repo=repo)

    try:
        plan = manager.create_plan(
            fund_code=fund_code,
            amount=Decimal(str(amount)),
            frequency=freq,
            smart=smart,
        )
        repo._session.commit()
        console.print(
            f"[green]定投计划创建成功：[/green]\n"
            f"  ID：{plan.id}\n"
            f"  基金代码：{fund_code}\n"
            f"  金额：{amount}\n"
            f"  频率：{freq}\n"
            f"  智能定投：{'是' if smart else '否'}"
        )
    except Exception as exc:
        console.print(f"[red]创建定投计划失败：{exc}[/red]")
        raise typer.Exit(code=1)


@dip_app.command("list")
def dip_list():
    """列出所有活跃的定投计划。"""
    from fund_analyzer.portfolio.dip import DipManager

    repo = _get_repo()
    manager = DipManager(repo=repo)

    plans = manager.list_plans()

    if not plans:
        console.print("[dim]当前无活跃的定投计划。[/dim]")
        return

    table = Table(title="定投计划列表", show_header=True, header_style="bold cyan")
    table.add_column("ID", justify="right", style="dim")
    table.add_column("基金代码")
    table.add_column("金额", justify="right")
    table.add_column("频率")
    table.add_column("起始日期")
    table.add_column("状态")
    table.add_column("智能定投")

    for plan in plans:
        table.add_row(
            str(plan["id"]),
            plan["fund_code"],
            str(plan["amount"]),
            plan["frequency"],
            str(plan["start_date"]),
            plan["status"],
            "是" if plan["smart_dip"] else "否",
        )

    console.print(table)


@dip_app.command("check")
def dip_check():
    """检查今日到期的定投计划。"""
    from fund_analyzer.portfolio.dip import DipManager

    repo = _get_repo()
    manager = DipManager(repo=repo)

    due_plans = manager.check_due()

    if not due_plans:
        console.print("[dim]今日无到期的定投计划。[/dim]")
        return

    table = Table(title="今日到期定投计划", show_header=True, header_style="bold yellow")
    table.add_column("计划 ID", justify="right", style="dim")
    table.add_column("基金代码")
    table.add_column("金额", justify="right")
    table.add_column("智能定投")

    for plan in due_plans:
        table.add_row(
            str(plan["plan_id"]),
            plan["fund_code"],
            str(plan["amount"]),
            "是" if plan["smart_dip"] else "否",
        )

    console.print(table)
    console.print(f"[bold]共 {len(due_plans)} 条计划今日应执行。[/bold]")


# -----------------------------------------------------------------------
# 入口
# -----------------------------------------------------------------------

if __name__ == "__main__":
    app()
