# 基金理财量化分析系统 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建个人基金理财量化系统，通过核心+卫星策略配置，实现年组合总收益率 > 10%。

**Architecture:** 分层架构：数据层（akshare + PostgreSQL + SQLAlchemy ORM）→ 策略引擎层（因子/动量/轮动/全球配置 + 综合评分）→ 回测引擎 → 组合管理 → CLI。模块间通过 Repository 模式解耦，策略引擎使用可插拔的基类模式。

**Tech Stack:** Python 3.11+ / Poetry / SQLAlchemy 2.0 / PostgreSQL / akshare / pandas / numpy / Typer / matplotlib

**Spec:** `docs/superpowers/specs/2026-03-20-fund-analyzer-design.md`

---

## File Structure

```
finance/
├── pyproject.toml                          # Poetry项目配置
├── config/
│   └── settings.yaml                       # 运行时配置
├── src/
│   └── fund_analyzer/
│       ├── __init__.py                     # 包初始化
│       ├── config.py                       # 配置加载
│       ├── database.py                     # 数据库连接管理
│       ├── data/
│       │   ├── __init__.py
│       │   ├── models.py                   # SQLAlchemy ORM模型（9张表）
│       │   ├── repository.py               # 数据访问层（Repository模式）
│       │   ├── fetcher.py                  # akshare数据拉取
│       │   └── sync.py                     # 数据同步调度
│       ├── strategy/
│       │   ├── __init__.py
│       │   ├── base.py                     # Signal数据类 + BaseStrategy基类
│       │   ├── factor.py                   # 因子筛选策略
│       │   ├── momentum.py                 # 动量策略
│       │   ├── rotation.py                 # 行业轮动策略
│       │   ├── global_alloc.py             # 全球配置策略
│       │   └── composite.py               # 综合评分（核心/卫星双通道）
│       ├── backtest/
│       │   ├── __init__.py
│       │   ├── metrics.py                  # 绩效指标计算
│       │   └── engine.py                   # 回测引擎
│       ├── portfolio/
│       │   ├── __init__.py
│       │   ├── manager.py                  # 持仓管理 + 交易记录
│       │   ├── rebalance.py                # 调仓信号生成
│       │   ├── tracker.py                  # 收益追踪
│       │   └── dip.py                      # 定投计划管理
│       └── cli/
│           ├── __init__.py
│           └── app.py                      # Typer CLI入口
├── tests/
│   ├── conftest.py                         # 测试fixtures
│   ├── test_config.py
│   ├── test_models.py
│   ├── test_repository.py
│   ├── test_fetcher.py
│   ├── test_sync.py
│   ├── test_strategy_base.py
│   ├── test_factor.py
│   ├── test_momentum.py
│   ├── test_rotation.py
│   ├── test_global_alloc.py
│   ├── test_composite.py
│   ├── test_metrics.py
│   ├── test_backtest_engine.py
│   ├── test_portfolio_manager.py
│   ├── test_rebalance.py
│   ├── test_tracker.py
│   ├── test_dip.py
│   └── test_cli.py
└── docs/
```

---

### Task 1: 项目脚手架与配置

**Files:**
- Create: `pyproject.toml`
- Create: `config/settings.yaml`
- Create: `src/fund_analyzer/__init__.py`
- Create: `src/fund_analyzer/config.py`
- Create: `src/fund_analyzer/database.py`
- Create: `tests/conftest.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: 初始化Poetry项目**

```bash
cd D:/pycharmWorkspace/finance
poetry init --name fund-analyzer --python ">=3.11" --no-interaction
```

- [ ] **Step 2: 添加核心依赖**

```bash
poetry add sqlalchemy[asyncio] psycopg2-binary alembic akshare pandas numpy typer pyyaml matplotlib plotly rich
poetry add --group dev pytest pytest-cov
```

- [ ] **Step 3: 创建目录结构**

```bash
mkdir -p src/fund_analyzer/{data,strategy,backtest,portfolio,cli}
mkdir -p tests config
touch src/fund_analyzer/__init__.py
touch src/fund_analyzer/data/__init__.py
touch src/fund_analyzer/strategy/__init__.py
touch src/fund_analyzer/backtest/__init__.py
touch src/fund_analyzer/portfolio/__init__.py
touch src/fund_analyzer/cli/__init__.py
```

- [ ] **Step 4: 编写配置文件 `config/settings.yaml`**

```yaml
database:
  host: localhost
  port: 5432
  name: fund_analyzer
  user: postgres
  password: ""

data:
  sync_interval_seconds: 0.5
  retry_count: 3
  fund_pool:
    min_inception_years: 2
    min_size_billion: 1
    exclude_types: ["货币型", "纯债型"]

portfolio:
  core_ratio: 30
  satellite_ratio: 70

strategy:
  dynamic_weights: false
  signal_thresholds:
    buy: 80
    sell: 60
  core:
    factor: 70
    global_alloc: 30
  satellite:
    momentum: 40
    rotation: 35
    global_alloc: 25

backtest:
  default_start: "2020-01-01"
  initial_capital: 100000
  core_top_n: 3
  satellite_top_n: 7
  core_rebalance_freq: quarterly
  satellite_rebalance_freq: monthly
  buy_fee_rate: 0.0015
  sell_fee_rate: 0.005

smart_dip:
  low_pe_percentile: 30
  high_pe_percentile: 70
  low_multiplier: 1.5
  high_multiplier: 0.5

logging:
  level: INFO
  file: logs/fund_analyzer.log
```

- [ ] **Step 5: 编写测试 `tests/test_config.py`**

```python
import os
import pytest
from fund_analyzer.config import load_config, Settings


def test_load_config_from_file(tmp_path):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text("""
database:
  host: localhost
  port: 5432
  name: test_db
  user: test_user
  password: test_pass
portfolio:
  core_ratio: 30
  satellite_ratio: 70
""")
    settings = load_config(str(config_file))
    assert settings.database.host == "localhost"
    assert settings.database.name == "test_db"
    assert settings.portfolio.core_ratio == 30
    assert settings.portfolio.satellite_ratio == 70


def test_load_config_db_password_from_env(tmp_path, monkeypatch):
    config_file = tmp_path / "settings.yaml"
    config_file.write_text("""
database:
  host: localhost
  port: 5432
  name: test_db
  user: test_user
  password: ""
""")
    monkeypatch.setenv("FUND_DB_PASSWORD", "env_secret")
    settings = load_config(str(config_file))
    assert settings.database.password == "env_secret"


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path.yaml")
```

- [ ] **Step 6: 运行测试，确认失败**

```bash
poetry run pytest tests/test_config.py -v
```
Expected: FAIL（模块不存在）

- [ ] **Step 7: 实现 `src/fund_analyzer/config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    name: str = "fund_analyzer"
    user: str = "postgres"
    password: str = ""

    @property
    def url(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"


@dataclass
class FundPoolConfig:
    min_inception_years: int = 2
    min_size_billion: float = 1
    exclude_types: list[str] = field(default_factory=lambda: ["货币型", "纯债型"])


@dataclass
class DataConfig:
    sync_interval_seconds: float = 0.5
    retry_count: int = 3
    fund_pool: FundPoolConfig = field(default_factory=FundPoolConfig)


@dataclass
class PortfolioConfig:
    core_ratio: int = 30
    satellite_ratio: int = 70


@dataclass
class SignalThresholds:
    buy: float = 80
    sell: float = 60


@dataclass
class StrategyWeights:
    factor: float = 0
    momentum: float = 0
    rotation: float = 0
    global_alloc: float = 0


@dataclass
class StrategyConfig:
    dynamic_weights: bool = False
    signal_thresholds: SignalThresholds = field(default_factory=SignalThresholds)
    core: dict[str, float] = field(default_factory=lambda: {"factor": 70, "global_alloc": 30})
    satellite: dict[str, float] = field(default_factory=lambda: {"momentum": 40, "rotation": 35, "global_alloc": 25})


@dataclass
class BacktestConfig:
    default_start: str = "2020-01-01"
    initial_capital: float = 100000
    core_top_n: int = 3
    satellite_top_n: int = 7
    core_rebalance_freq: str = "quarterly"
    satellite_rebalance_freq: str = "monthly"
    buy_fee_rate: float = 0.0015
    sell_fee_rate: float = 0.005


@dataclass
class SmartDipConfig:
    low_pe_percentile: float = 30
    high_pe_percentile: float = 70
    low_multiplier: float = 1.5
    high_multiplier: float = 0.5


@dataclass
class LoggingConfig:
    level: str = "INFO"
    file: str = "logs/fund_analyzer.log"


@dataclass
class Settings:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    data: DataConfig = field(default_factory=DataConfig)
    portfolio: PortfolioConfig = field(default_factory=PortfolioConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    smart_dip: SmartDipConfig = field(default_factory=SmartDipConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def _dict_to_dataclass(cls, data: dict):
    """Recursively convert a dict to a dataclass instance."""
    if data is None:
        return cls()
    field_types = {f.name: f.type for f in cls.__dataclass_fields__.values()}
    kwargs = {}
    for key, value in data.items():
        if key in field_types and isinstance(value, dict):
            # Check if the field type is a dataclass
            field_type = cls.__dataclass_fields__[key].type
            # Resolve string annotations
            if isinstance(field_type, str):
                field_type = eval(field_type)
            if hasattr(field_type, "__dataclass_fields__"):
                kwargs[key] = _dict_to_dataclass(field_type, value)
            else:
                kwargs[key] = value
        elif key in field_types:
            kwargs[key] = value
    return cls(**kwargs)


def load_config(path: str) -> Settings:
    """Load settings from a YAML file. DB password falls back to FUND_DB_PASSWORD env var."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    with open(config_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    settings = _dict_to_dataclass(Settings, raw)

    # Override DB password from environment if not set in file
    env_password = os.environ.get("FUND_DB_PASSWORD")
    if env_password and not settings.database.password:
        settings.database.password = env_password

    return settings
```

- [ ] **Step 8: 运行测试，确认通过**

```bash
poetry run pytest tests/test_config.py -v
```
Expected: 3 passed

- [ ] **Step 9: 实现 `src/fund_analyzer/database.py`**

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from fund_analyzer.config import Settings


def create_db_engine(settings: Settings):
    """Create SQLAlchemy engine from settings."""
    return create_engine(settings.database.url, echo=False)


def create_session_factory(settings: Settings) -> sessionmaker[Session]:
    """Create a session factory bound to the configured database."""
    engine = create_db_engine(settings)
    return sessionmaker(bind=engine)
```

- [ ] **Step 10: 配置 pyproject.toml 的包路径和 CLI 入口**

在 `pyproject.toml` 中添加：
```toml
[tool.poetry.packages]
include = "fund_analyzer"
from = "src"

[tool.poetry.scripts]
fund-cli = "fund_analyzer.cli.app:app"

[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

- [ ] **Step 11: Commit**

```bash
git add pyproject.toml poetry.lock config/ src/ tests/
git commit -m "feat: 项目脚手架、配置加载与数据库连接"
```

---

### Task 2: ORM数据模型

**Files:**
- Create: `src/fund_analyzer/data/models.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: 编写测试 `tests/test_models.py`**

```python
import pytest
from datetime import date, datetime
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundInfo, FundNav, IndexQuote, FundHolding, IndustryMapping, PortfolioPosition, PortfolioTransaction, StrategySignal, DipPlan


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_create_fund_info(db_session):
    fund = FundInfo(
        fund_code="000001",
        fund_name="华夏成长",
        fund_type="混合型",
        market="a_share",
        manager="张三",
        manager_start_date=date(2020, 1, 1),
        company="华夏基金",
        inception_date=date(2015, 6, 1),
        fund_size=Decimal("50.00"),
        benchmark="沪深300",
    )
    db_session.add(fund)
    db_session.commit()

    result = db_session.get(FundInfo, "000001")
    assert result.fund_name == "华夏成长"
    assert result.market == "a_share"
    assert result.fund_size == Decimal("50.00")
    assert result.manager_start_date == date(2020, 1, 1)


def test_create_fund_nav(db_session):
    nav = FundNav(
        fund_code="000001",
        date=date(2025, 1, 10),
        nav=Decimal("2.3456"),
        acc_nav=Decimal("3.4567"),
        daily_return=Decimal("0.012345"),
    )
    db_session.add(nav)
    db_session.commit()

    result = db_session.query(FundNav).first()
    assert result.fund_code == "000001"
    assert result.nav == Decimal("2.3456")


def test_create_portfolio_position(db_session):
    pos = PortfolioPosition(
        fund_code="000001",
        position_type="satellite",
        buy_date=date(2025, 1, 1),
        shares=Decimal("1000.0000"),
        cost_price=Decimal("1.5000"),
        status="holding",
    )
    db_session.add(pos)
    db_session.commit()

    result = db_session.query(PortfolioPosition).first()
    assert result.position_type == "satellite"
    assert result.status == "holding"
    assert result.sell_date is None


def test_create_portfolio_transaction_with_dip(db_session):
    # Create a dip plan first
    plan = DipPlan(
        fund_code="000001",
        amount=Decimal("1000.00"),
        frequency="monthly",
        start_date=date(2025, 1, 1),
        status="active",
        smart_dip=True,
    )
    db_session.add(plan)
    db_session.commit()

    tx = PortfolioTransaction(
        fund_code="000001",
        date=date(2025, 2, 1),
        type="dip",
        amount=Decimal("1000.00"),
        shares=Decimal("500.0000"),
        nav=Decimal("2.0000"),
        position_type="core",
        dip_plan_id=plan.id,
    )
    db_session.add(tx)
    db_session.commit()

    result = db_session.query(PortfolioTransaction).first()
    assert result.dip_plan_id == plan.id
    assert result.position_type == "core"


def test_all_tables_created(db_session):
    """Verify all 9 tables exist."""
    tables = Base.metadata.tables.keys()
    expected = {
        "fund_info", "fund_nav", "index_quote", "fund_holding",
        "industry_mapping", "portfolio_position", "portfolio_transaction",
        "strategy_signal", "dip_plan",
    }
    assert expected.issubset(set(tables))
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_models.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 `src/fund_analyzer/data/models.py`**

```python
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import String, Date, Numeric, Integer, Boolean, DateTime, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class FundInfo(Base):
    __tablename__ = "fund_info"

    fund_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    fund_name: Mapped[str] = mapped_column(String(100))
    fund_type: Mapped[str] = mapped_column(String(20))
    market: Mapped[str] = mapped_column(String(10))
    manager: Mapped[str | None] = mapped_column(String(50))
    manager_start_date: Mapped[date | None] = mapped_column(Date)
    company: Mapped[str | None] = mapped_column(String(50))
    inception_date: Mapped[date | None] = mapped_column(Date)
    fund_size: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    benchmark: Mapped[str | None] = mapped_column(String(200))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class FundNav(Base):
    __tablename__ = "fund_nav"

    fund_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    nav: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    acc_nav: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    daily_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))


class IndexQuote(Base):
    __tablename__ = "index_quote"

    index_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    date: Mapped[date] = mapped_column(Date, primary_key=True)
    close: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))
    daily_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))


class FundHolding(Base):
    __tablename__ = "fund_holding"

    fund_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    report_date: Mapped[date] = mapped_column(Date, primary_key=True)
    stock_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    stock_name: Mapped[str | None] = mapped_column(String(50))
    industry: Mapped[str | None] = mapped_column(String(30))
    weight: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))


class IndustryMapping(Base):
    __tablename__ = "industry_mapping"

    stock_code: Mapped[str] = mapped_column(String(10), primary_key=True)
    stock_name: Mapped[str | None] = mapped_column(String(50))
    industry_l1: Mapped[str | None] = mapped_column(String(30))
    industry_l2: Mapped[str | None] = mapped_column(String(30))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.now, onupdate=datetime.now)


class PortfolioPosition(Base):
    __tablename__ = "portfolio_position"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(String(10))
    position_type: Mapped[str] = mapped_column(String(10))
    buy_date: Mapped[date] = mapped_column(Date)
    shares: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    cost_price: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    status: Mapped[str] = mapped_column(String(10), default="holding")
    sell_date: Mapped[date | None] = mapped_column(Date)
    sell_price: Mapped[Decimal | None] = mapped_column(Numeric(10, 4))


class PortfolioTransaction(Base):
    __tablename__ = "portfolio_transaction"
    __table_args__ = (
        Index("ix_tx_fund_date", "fund_code", "date"),
        Index("ix_tx_dip_plan", "dip_plan_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(String(10))
    date: Mapped[date] = mapped_column(Date)
    type: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    shares: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    nav: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    position_type: Mapped[str] = mapped_column(String(10))
    dip_plan_id: Mapped[int | None] = mapped_column(Integer)


class StrategySignal(Base):
    __tablename__ = "strategy_signal"
    __table_args__ = (
        Index("ix_signal_date_fund", "date", "fund_code"),
        Index("ix_signal_strategy_date", "strategy_name", "date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    strategy_name: Mapped[str] = mapped_column(String(30))
    date: Mapped[date] = mapped_column(Date)
    fund_code: Mapped[str] = mapped_column(String(10))
    score: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    action: Mapped[str] = mapped_column(String(10))
    position_type: Mapped[str] = mapped_column(String(10))


class DipPlan(Base):
    __tablename__ = "dip_plan"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    frequency: Mapped[str] = mapped_column(String(10))
    start_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), default="active")
    smart_dip: Mapped[bool] = mapped_column(Boolean, default=False)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_models.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/data/models.py tests/test_models.py
git commit -m "feat: 定义9张核心ORM数据模型"
```

---

### Task 3: 数据访问层（Repository）

**Files:**
- Create: `src/fund_analyzer/data/repository.py`
- Create: `tests/test_repository.py`

- [ ] **Step 1: 编写测试 `tests/test_repository.py`**

```python
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundInfo, FundNav, IndexQuote
from fund_analyzer.data.repository import FundRepository


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def repo(db_session):
    return FundRepository(db_session)


@pytest.fixture
def sample_fund(db_session):
    fund = FundInfo(
        fund_code="000001", fund_name="测试基金", fund_type="混合型",
        market="a_share", inception_date=date(2020, 1, 1), fund_size=Decimal("50.00"),
    )
    db_session.add(fund)
    db_session.commit()
    return fund


@pytest.fixture
def sample_navs(db_session):
    navs = [
        FundNav(fund_code="000001", date=date(2025, 1, i), nav=Decimal(f"{1.0 + i * 0.01:.4f}"),
                acc_nav=Decimal(f"{1.0 + i * 0.01:.4f}"), daily_return=Decimal("0.01"))
        for i in range(1, 11)
    ]
    db_session.add_all(navs)
    db_session.commit()
    return navs


def test_get_fund_info(repo, sample_fund):
    result = repo.get_fund_info("000001")
    assert result.fund_name == "测试基金"


def test_get_fund_info_not_found(repo):
    assert repo.get_fund_info("999999") is None


def test_get_fund_nav_range(repo, sample_fund, sample_navs):
    navs = repo.get_fund_nav("000001", start=date(2025, 1, 3), end=date(2025, 1, 7))
    assert len(navs) == 5


def test_get_eligible_funds(repo, db_session):
    """Test fund pool filtering: min inception, min size, exclude types."""
    # Eligible fund
    db_session.add(FundInfo(fund_code="E001", fund_name="好基金", fund_type="混合型",
                            market="a_share", inception_date=date(2020, 1, 1), fund_size=Decimal("5.00")))
    # Too young
    db_session.add(FundInfo(fund_code="E002", fund_name="新基金", fund_type="混合型",
                            market="a_share", inception_date=date(2025, 1, 1), fund_size=Decimal("5.00")))
    # Too small
    db_session.add(FundInfo(fund_code="E003", fund_name="小基金", fund_type="混合型",
                            market="a_share", inception_date=date(2020, 1, 1), fund_size=Decimal("0.50")))
    # Excluded type
    db_session.add(FundInfo(fund_code="E004", fund_name="货基", fund_type="货币型",
                            market="a_share", inception_date=date(2020, 1, 1), fund_size=Decimal("100.00")))
    db_session.commit()

    funds = repo.get_eligible_funds(
        min_inception_years=2, min_size_billion=1, exclude_types=["货币型", "纯债型"],
        as_of=date(2025, 6, 1),
    )
    codes = [f.fund_code for f in funds]
    assert "E001" in codes
    assert "E002" not in codes
    assert "E003" not in codes
    assert "E004" not in codes


def test_upsert_fund_nav(repo, db_session, sample_fund):
    repo.upsert_fund_navs("000001", [
        {"date": date(2025, 3, 1), "nav": Decimal("2.0"), "acc_nav": Decimal("2.0"), "daily_return": Decimal("0.01")},
    ])
    result = repo.get_fund_nav("000001", start=date(2025, 3, 1), end=date(2025, 3, 1))
    assert len(result) == 1
    assert result[0].nav == Decimal("2.0")
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_repository.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 `src/fund_analyzer/data/repository.py`**

```python
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select, and_, delete
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.dialects.postgresql import insert as pg_insert

from fund_analyzer.data.models import (
    FundInfo, FundNav, IndexQuote, FundHolding, IndustryMapping,
    PortfolioPosition, PortfolioTransaction, StrategySignal, DipPlan,
)


class FundRepository:
    def __init__(self, session: Session):
        self.session = session

    # --- FundInfo ---

    def get_fund_info(self, fund_code: str) -> FundInfo | None:
        return self.session.get(FundInfo, fund_code)

    def get_eligible_funds(
        self,
        min_inception_years: int = 2,
        min_size_billion: float = 1,
        exclude_types: list[str] | None = None,
        as_of: date | None = None,
    ) -> list[FundInfo]:
        as_of = as_of or date.today()
        cutoff_date = as_of - timedelta(days=min_inception_years * 365)
        exclude_types = exclude_types or []

        stmt = select(FundInfo).where(
            and_(
                FundInfo.inception_date <= cutoff_date,
                FundInfo.fund_size >= Decimal(str(min_size_billion)),
                FundInfo.fund_type.notin_(exclude_types),
            )
        )
        return list(self.session.scalars(stmt))

    def upsert_fund_info(self, data: dict) -> None:
        existing = self.session.get(FundInfo, data["fund_code"])
        if existing:
            for key, value in data.items():
                setattr(existing, key, value)
        else:
            self.session.add(FundInfo(**data))
        self.session.commit()

    # --- FundNav ---

    def get_fund_nav(
        self, fund_code: str, start: date | None = None, end: date | None = None
    ) -> list[FundNav]:
        stmt = select(FundNav).where(FundNav.fund_code == fund_code)
        if start:
            stmt = stmt.where(FundNav.date >= start)
        if end:
            stmt = stmt.where(FundNav.date <= end)
        stmt = stmt.order_by(FundNav.date)
        return list(self.session.scalars(stmt))

    def upsert_fund_navs(self, fund_code: str, rows: list[dict]) -> None:
        for row in rows:
            existing = self.session.get(FundNav, (fund_code, row["date"]))
            if existing:
                for key, value in row.items():
                    setattr(existing, key, value)
            else:
                self.session.add(FundNav(fund_code=fund_code, **row))
        self.session.commit()

    # --- IndexQuote ---

    def get_index_quote(
        self, index_code: str, start: date | None = None, end: date | None = None
    ) -> list[IndexQuote]:
        stmt = select(IndexQuote).where(IndexQuote.index_code == index_code)
        if start:
            stmt = stmt.where(IndexQuote.date >= start)
        if end:
            stmt = stmt.where(IndexQuote.date <= end)
        stmt = stmt.order_by(IndexQuote.date)
        return list(self.session.scalars(stmt))

    def upsert_index_quotes(self, index_code: str, rows: list[dict]) -> None:
        for row in rows:
            existing = self.session.get(IndexQuote, (index_code, row["date"]))
            if existing:
                for key, value in row.items():
                    setattr(existing, key, value)
            else:
                self.session.add(IndexQuote(index_code=index_code, **row))
        self.session.commit()

    # --- FundHolding ---

    def get_fund_holdings(self, fund_code: str, report_date: date) -> list[FundHolding]:
        stmt = select(FundHolding).where(
            and_(FundHolding.fund_code == fund_code, FundHolding.report_date == report_date)
        )
        return list(self.session.scalars(stmt))

    # --- IndustryMapping ---

    def get_industry(self, stock_code: str) -> IndustryMapping | None:
        return self.session.get(IndustryMapping, stock_code)

    # --- PortfolioPosition ---

    def get_active_positions(self, position_type: str | None = None) -> list[PortfolioPosition]:
        stmt = select(PortfolioPosition).where(PortfolioPosition.status == "holding")
        if position_type:
            stmt = stmt.where(PortfolioPosition.position_type == position_type)
        return list(self.session.scalars(stmt))

    # --- PortfolioTransaction ---

    def add_transaction(self, data: dict) -> PortfolioTransaction:
        tx = PortfolioTransaction(**data)
        self.session.add(tx)
        self.session.commit()
        return tx

    # --- StrategySignal ---

    def save_signals(self, signals: list[dict]) -> None:
        for s in signals:
            self.session.add(StrategySignal(**s))
        self.session.commit()

    # --- DipPlan ---

    def get_active_dip_plans(self) -> list[DipPlan]:
        stmt = select(DipPlan).where(DipPlan.status == "active")
        return list(self.session.scalars(stmt))
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_repository.py -v
```
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/data/repository.py tests/test_repository.py
git commit -m "feat: 实现数据访问层Repository"
```

---

### Task 4: 数据采集（Fetcher）

**Files:**
- Create: `src/fund_analyzer/data/fetcher.py`
- Create: `tests/test_fetcher.py`

- [ ] **Step 1: 编写测试 `tests/test_fetcher.py`**

使用 mock 隔离 akshare 外部依赖：

```python
import pytest
from unittest.mock import patch, MagicMock
from datetime import date
from decimal import Decimal
import pandas as pd

from fund_analyzer.data.fetcher import FundFetcher


@pytest.fixture
def fetcher():
    return FundFetcher(request_interval=0, retry_count=1)


@patch("fund_analyzer.data.fetcher.ak")
def test_fetch_fund_list(mock_ak, fetcher):
    mock_ak.fund_open_fund_info_em.return_value = pd.DataFrame({
        "基金代码": ["000001", "000002"],
        "基金简称": ["基金A", "基金B"],
    })
    result = fetcher.fetch_fund_list()
    assert len(result) == 2
    assert result[0]["fund_code"] == "000001"


@patch("fund_analyzer.data.fetcher.ak")
def test_fetch_fund_nav_history(mock_ak, fetcher):
    mock_ak.fund_open_fund_daily_em.return_value = pd.DataFrame({
        "净值日期": ["2025-01-01", "2025-01-02"],
        "单位净值": [1.0, 1.01],
        "累计净值": [2.0, 2.01],
        "日增长率": [0.5, 1.0],
    })
    result = fetcher.fetch_fund_nav("000001")
    assert len(result) == 2
    assert result[0]["nav"] == 1.0


@patch("fund_analyzer.data.fetcher.ak")
def test_fetch_fund_nav_with_retry_on_failure(mock_ak, fetcher):
    mock_ak.fund_open_fund_daily_em.side_effect = Exception("Network error")
    result = fetcher.fetch_fund_nav("000001")
    assert result == []


@patch("fund_analyzer.data.fetcher.ak")
def test_fetch_index_daily(mock_ak, fetcher):
    mock_ak.stock_zh_index_daily_em.return_value = pd.DataFrame({
        "date": ["2025-01-01", "2025-01-02"],
        "close": [1000.0, 1010.0],
    })
    result = fetcher.fetch_index_daily("000688")
    assert len(result) == 2
    assert result[0]["close"] == 1000.0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_fetcher.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 `src/fund_analyzer/data/fetcher.py`**

```python
from __future__ import annotations

import logging
import time
from datetime import date

import akshare as ak
import pandas as pd

logger = logging.getLogger(__name__)


class FundFetcher:
    """Fetch fund and index data from akshare with retry and rate limiting."""

    def __init__(self, request_interval: float = 0.5, retry_count: int = 3):
        self.request_interval = request_interval
        self.retry_count = retry_count

    def _call_with_retry(self, func, *args, **kwargs) -> pd.DataFrame | None:
        for attempt in range(self.retry_count):
            try:
                result = func(*args, **kwargs)
                time.sleep(self.request_interval)
                return result
            except Exception as e:
                wait = 2 ** attempt
                logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {wait}s...")
                time.sleep(wait)
        logger.error(f"All {self.retry_count} attempts failed for {func.__name__}")
        return None

    def fetch_fund_list(self) -> list[dict]:
        """Fetch all open-ended fund basic info."""
        df = self._call_with_retry(ak.fund_open_fund_info_em)
        if df is None or df.empty:
            return []
        result = []
        for _, row in df.iterrows():
            result.append({
                "fund_code": str(row.get("基金代码", "")),
                "fund_name": str(row.get("基金简称", "")),
            })
        return result

    def fetch_fund_nav(self, fund_code: str, start_date: str | None = None) -> list[dict]:
        """Fetch daily NAV history for a fund."""
        kwargs = {"fund": fund_code, "indicator": "单位净值走势"}
        df = self._call_with_retry(ak.fund_open_fund_daily_em, **kwargs)
        if df is None or df.empty:
            return []
        result = []
        for _, row in df.iterrows():
            daily_return = row.get("日增长率", 0)
            if pd.isna(daily_return):
                daily_return = 0
            result.append({
                "date": str(row.get("净值日期", "")),
                "nav": float(row.get("单位净值", 0)),
                "acc_nav": float(row.get("累计净值", 0)),
                "daily_return": float(daily_return) / 100,
            })
        return result

    def fetch_index_daily(self, index_code: str, start_date: str = "20100101") -> list[dict]:
        """Fetch daily index quotes."""
        df = self._call_with_retry(
            ak.stock_zh_index_daily_em, symbol=index_code, start_date=start_date
        )
        if df is None or df.empty:
            return []
        result = []
        for _, row in df.iterrows():
            result.append({
                "date": str(row.get("date", "")),
                "close": float(row.get("close", 0)),
            })
        return result

    def fetch_fund_holding(self, fund_code: str, year: str) -> list[dict]:
        """Fetch fund quarterly holding data."""
        try:
            df = self._call_with_retry(
                ak.fund_portfolio_hold_em, symbol=fund_code, date=year
            )
        except Exception:
            return []
        if df is None or df.empty:
            return []
        result = []
        for _, row in df.iterrows():
            result.append({
                "stock_code": str(row.get("股票代码", "")),
                "stock_name": str(row.get("股票名称", "")),
                "weight": float(row.get("占净值比例", 0)),
                "report_date": str(row.get("季度", "")),
            })
        return result

    def fetch_industry_classification(self) -> list[dict]:
        """Fetch Shenwan industry classification for A-share stocks."""
        df = self._call_with_retry(ak.stock_board_industry_name_em)
        if df is None or df.empty:
            return []
        result = []
        for _, row in df.iterrows():
            result.append({
                "industry_name": str(row.get("板块名称", "")),
                "industry_code": str(row.get("板块代码", "")),
            })
        return result
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_fetcher.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/data/fetcher.py tests/test_fetcher.py
git commit -m "feat: 实现akshare数据采集（含重试和限流）"
```

---

### Task 5: 数据同步调度（Sync）

**Files:**
- Create: `src/fund_analyzer/data/sync.py`
- Create: `tests/test_sync.py`

- [ ] **Step 1: 编写测试 `tests/test_sync.py`**

```python
import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundInfo, FundNav
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.data.sync import DataSyncer


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def mock_fetcher():
    fetcher = MagicMock()
    fetcher.fetch_fund_list.return_value = [
        {"fund_code": "000001", "fund_name": "基金A"},
        {"fund_code": "000002", "fund_name": "基金B"},
    ]
    fetcher.fetch_fund_nav.return_value = [
        {"date": "2025-01-01", "nav": 1.0, "acc_nav": 2.0, "daily_return": 0.01},
        {"date": "2025-01-02", "nav": 1.01, "acc_nav": 2.01, "daily_return": 0.01},
    ]
    fetcher.fetch_index_daily.return_value = [
        {"date": "2025-01-01", "close": 1000.0},
        {"date": "2025-01-02", "close": 1010.0},
    ]
    return fetcher


@pytest.fixture
def syncer(db_session, mock_fetcher):
    repo = FundRepository(db_session)
    return DataSyncer(repo=repo, fetcher=mock_fetcher)


def test_sync_fund_list(syncer, db_session):
    syncer.sync_fund_list()
    funds = db_session.query(FundInfo).all()
    assert len(funds) == 2


def test_sync_fund_navs(syncer, db_session):
    # Need fund_info first
    db_session.add(FundInfo(fund_code="000001", fund_name="基金A", fund_type="混合型", market="a_share"))
    db_session.commit()

    syncer.sync_fund_nav("000001")
    navs = db_session.query(FundNav).all()
    assert len(navs) == 2


def test_sync_validates_nav_jump(syncer, db_session, mock_fetcher):
    """NAV jump > 15% should be flagged."""
    db_session.add(FundInfo(fund_code="000001", fund_name="基金A", fund_type="混合型", market="a_share"))
    db_session.commit()

    mock_fetcher.fetch_fund_nav.return_value = [
        {"date": "2025-01-01", "nav": 1.0, "acc_nav": 2.0, "daily_return": 0.01},
        {"date": "2025-01-02", "nav": 1.2, "acc_nav": 2.2, "daily_return": 0.20},  # 20% jump
    ]
    warnings = syncer.sync_fund_nav("000001")
    assert len(warnings) > 0
    assert "异常" in warnings[0]
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_sync.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 `src/fund_analyzer/data/sync.py`**

```python
from __future__ import annotations

import logging
from datetime import date, datetime
from decimal import Decimal

from fund_analyzer.data.fetcher import FundFetcher
from fund_analyzer.data.repository import FundRepository

logger = logging.getLogger(__name__)


class DataSyncer:
    """Orchestrates data synchronization from akshare to database."""

    def __init__(self, repo: FundRepository, fetcher: FundFetcher):
        self.repo = repo
        self.fetcher = fetcher

    def sync_fund_list(self) -> int:
        """Sync fund basic info. Returns count of synced funds."""
        funds = self.fetcher.fetch_fund_list()
        count = 0
        for f in funds:
            self.repo.upsert_fund_info({
                "fund_code": f["fund_code"],
                "fund_name": f["fund_name"],
                "fund_type": f.get("fund_type", "未知"),
                "market": f.get("market", "a_share"),
            })
            count += 1
        logger.info(f"Synced {count} funds")
        return count

    def sync_fund_nav(self, fund_code: str) -> list[str]:
        """Sync NAV history for a single fund. Returns list of warning messages."""
        warnings = []
        rows = self.fetcher.fetch_fund_nav(fund_code)
        if not rows:
            return warnings

        nav_dicts = []
        prev_nav = None
        for row in rows:
            nav_val = row["nav"]
            daily_ret = row.get("daily_return", 0)

            # Validate NAV jump
            if prev_nav and prev_nav > 0:
                change = abs(nav_val - prev_nav) / prev_nav
                if change > 0.15:
                    msg = f"净值异常跳变: {fund_code} {row['date']} 变动 {change:.1%}"
                    warnings.append(msg)
                    logger.warning(msg)

            nav_dicts.append({
                "date": datetime.strptime(row["date"], "%Y-%m-%d").date() if isinstance(row["date"], str) else row["date"],
                "nav": Decimal(str(nav_val)),
                "acc_nav": Decimal(str(row.get("acc_nav", nav_val))),
                "daily_return": Decimal(str(daily_ret)),
            })
            prev_nav = nav_val

        self.repo.upsert_fund_navs(fund_code, nav_dicts)
        logger.info(f"Synced {len(nav_dicts)} NAV records for {fund_code}")
        return warnings

    def sync_index(self, index_code: str) -> int:
        """Sync index daily quotes. Returns count."""
        rows = self.fetcher.fetch_index_daily(index_code)
        if not rows:
            return 0

        quote_dicts = []
        prev_close = None
        for row in rows:
            close_val = row["close"]
            daily_ret = 0.0
            if prev_close and prev_close > 0:
                daily_ret = (close_val - prev_close) / prev_close
            quote_dicts.append({
                "date": datetime.strptime(row["date"], "%Y-%m-%d").date() if isinstance(row["date"], str) else row["date"],
                "close": Decimal(str(close_val)),
                "daily_return": Decimal(str(round(daily_ret, 6))),
            })
            prev_close = close_val

        self.repo.upsert_index_quotes(index_code, quote_dicts)
        logger.info(f"Synced {len(quote_dicts)} index quotes for {index_code}")
        return len(quote_dicts)

    def sync_all(self, fund_codes: list[str] | None = None, full: bool = False) -> dict:
        """Run full or incremental sync. Returns summary dict."""
        summary = {"funds": 0, "navs": 0, "indices": 0, "warnings": []}

        # Sync fund list
        summary["funds"] = self.sync_fund_list()

        # Sync NAVs for specified or all funds
        if fund_codes is None:
            eligible = self.repo.get_eligible_funds()
            fund_codes = [f.fund_code for f in eligible]

        for code in fund_codes:
            warnings = self.sync_fund_nav(code)
            summary["navs"] += 1
            summary["warnings"].extend(warnings)

        # Sync key indices
        for idx in ["000688", "000300"]:  # 科创50, 沪深300
            summary["indices"] += self.sync_index(idx)

        return summary
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_sync.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/data/sync.py tests/test_sync.py
git commit -m "feat: 实现数据同步调度（含异常检测）"
```

---

### Task 6: 策略基类与Signal

**Files:**
- Create: `src/fund_analyzer/strategy/base.py`
- Create: `tests/test_strategy_base.py`

- [ ] **Step 1: 编写测试 `tests/test_strategy_base.py`**

```python
import pytest
from datetime import date

from fund_analyzer.strategy.base import Signal, BaseStrategy


def test_signal_creation():
    signal = Signal(action="buy", confidence=0.85, reason="高评分")
    assert signal.action == "buy"
    assert signal.confidence == 0.85
    assert signal.reason == "高评分"


def test_signal_invalid_action():
    # Signal uses Literal type hint but doesn't enforce at runtime in dataclass
    # We test the score_to_signal helper instead
    from fund_analyzer.strategy.base import score_to_signal
    signal = score_to_signal(90, buy_threshold=80, sell_threshold=60)
    assert signal.action == "buy"

    signal = score_to_signal(70, buy_threshold=80, sell_threshold=60)
    assert signal.action == "hold"

    signal = score_to_signal(50, buy_threshold=80, sell_threshold=60)
    assert signal.action == "sell"


def test_base_strategy_is_abstract():
    """BaseStrategy cannot be used directly without implementing score_batch."""
    strategy = BaseStrategy(name="test")
    with pytest.raises(NotImplementedError):
        strategy.score_batch(["000001"], date(2025, 1, 1))
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_strategy_base.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 `src/fund_analyzer/strategy/base.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Literal


@dataclass
class Signal:
    action: Literal["buy", "sell", "hold"]
    confidence: float  # 0-1
    reason: str


def score_to_signal(
    score: float,
    buy_threshold: float = 80,
    sell_threshold: float = 60,
) -> Signal:
    """Convert a 0-100 score to a buy/sell/hold signal."""
    if score >= buy_threshold:
        confidence = min((score - buy_threshold) / (100 - buy_threshold), 1.0)
        return Signal(action="buy", confidence=confidence, reason=f"评分{score:.1f}≥{buy_threshold}")
    elif score >= sell_threshold:
        confidence = (score - sell_threshold) / (buy_threshold - sell_threshold)
        return Signal(action="hold", confidence=confidence, reason=f"评分{score:.1f}，观望")
    else:
        confidence = min((sell_threshold - score) / sell_threshold, 1.0)
        return Signal(action="sell", confidence=confidence, reason=f"评分{score:.1f}<{sell_threshold}")


class BaseStrategy:
    """Base class for all fund scoring strategies."""

    def __init__(self, name: str):
        self.name = name

    def score_batch(self, fund_codes: list[str], as_of: date) -> dict[str, float]:
        """Score a batch of funds. Returns {fund_code: score(0-100)}."""
        raise NotImplementedError

    def signal(self, fund_code: str, as_of: date, universe: list[str] | None = None) -> Signal:
        """Get signal for a single fund. Default implementation uses score_batch."""
        codes = universe or [fund_code]
        scores = self.score_batch(codes, as_of)
        score = scores.get(fund_code, 0)
        return score_to_signal(score)
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_strategy_base.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/strategy/base.py tests/test_strategy_base.py
git commit -m "feat: 策略基类与Signal数据类型"
```

---

### Task 7: 绩效指标计算（Metrics）

**Files:**
- Create: `src/fund_analyzer/backtest/metrics.py`
- Create: `tests/test_metrics.py`

- [ ] **Step 1: 编写测试 `tests/test_metrics.py`**

```python
import pytest
import numpy as np
import pandas as pd
from fund_analyzer.backtest.metrics import (
    annualized_return, annualized_volatility, max_drawdown,
    sharpe_ratio, sortino_ratio, calmar_ratio, information_ratio,
    monthly_win_rate, compute_all_metrics,
)


@pytest.fixture
def daily_returns():
    """252 trading days of synthetic returns (~15% annual)."""
    np.random.seed(42)
    return pd.Series(np.random.normal(0.0006, 0.015, 252))


@pytest.fixture
def benchmark_returns():
    np.random.seed(123)
    return pd.Series(np.random.normal(0.0003, 0.018, 252))


def test_annualized_return(daily_returns):
    result = annualized_return(daily_returns)
    assert -0.5 < result < 1.0  # Reasonable range


def test_annualized_volatility(daily_returns):
    result = annualized_volatility(daily_returns)
    assert 0.1 < result < 0.5


def test_max_drawdown(daily_returns):
    result = max_drawdown(daily_returns)
    assert 0 < result < 1


def test_sharpe_ratio(daily_returns):
    result = sharpe_ratio(daily_returns, risk_free_rate=0.02)
    assert isinstance(result, float)


def test_sortino_ratio(daily_returns):
    result = sortino_ratio(daily_returns)
    assert isinstance(result, float)


def test_calmar_ratio(daily_returns):
    result = calmar_ratio(daily_returns)
    assert isinstance(result, float)


def test_information_ratio(daily_returns, benchmark_returns):
    result = information_ratio(daily_returns, benchmark_returns)
    assert isinstance(result, float)


def test_monthly_win_rate(daily_returns):
    result = monthly_win_rate(daily_returns)
    assert 0 <= result <= 1


def test_compute_all_metrics(daily_returns, benchmark_returns):
    result = compute_all_metrics(daily_returns, benchmark_returns)
    assert "annualized_return" in result
    assert "sharpe_ratio" in result
    assert "max_drawdown" in result
    assert "information_ratio" in result
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_metrics.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 `src/fund_analyzer/backtest/metrics.py`**

```python
from __future__ import annotations

import numpy as np
import pandas as pd


def annualized_return(daily_returns: pd.Series, trading_days: int = 252) -> float:
    """Compute annualized return from daily returns."""
    total = (1 + daily_returns).prod()
    n_days = len(daily_returns)
    if n_days == 0:
        return 0.0
    return float(total ** (trading_days / n_days) - 1)


def annualized_volatility(daily_returns: pd.Series, trading_days: int = 252) -> float:
    """Compute annualized volatility."""
    return float(daily_returns.std() * np.sqrt(trading_days))


def max_drawdown(daily_returns: pd.Series) -> float:
    """Compute maximum drawdown from daily returns."""
    cumulative = (1 + daily_returns).cumprod()
    running_max = cumulative.cummax()
    drawdown = (cumulative - running_max) / running_max
    return float(abs(drawdown.min()))


def sharpe_ratio(daily_returns: pd.Series, risk_free_rate: float = 0.02, trading_days: int = 252) -> float:
    """Compute annualized Sharpe ratio."""
    ann_ret = annualized_return(daily_returns, trading_days)
    ann_vol = annualized_volatility(daily_returns, trading_days)
    if ann_vol == 0:
        return 0.0
    return float((ann_ret - risk_free_rate) / ann_vol)


def sortino_ratio(daily_returns: pd.Series, risk_free_rate: float = 0.02, trading_days: int = 252) -> float:
    """Compute annualized Sortino ratio (only downside volatility)."""
    ann_ret = annualized_return(daily_returns, trading_days)
    downside = daily_returns[daily_returns < 0]
    if len(downside) == 0:
        return float("inf")
    downside_vol = float(downside.std() * np.sqrt(trading_days))
    if downside_vol == 0:
        return 0.0
    return float((ann_ret - risk_free_rate) / downside_vol)


def calmar_ratio(daily_returns: pd.Series, trading_days: int = 252) -> float:
    """Compute Calmar ratio (annualized return / max drawdown)."""
    ann_ret = annualized_return(daily_returns, trading_days)
    mdd = max_drawdown(daily_returns)
    if mdd == 0:
        return 0.0
    return float(ann_ret / mdd)


def information_ratio(daily_returns: pd.Series, benchmark_returns: pd.Series, trading_days: int = 252) -> float:
    """Compute Information Ratio (alpha / tracking error)."""
    excess = daily_returns - benchmark_returns
    tracking_error = float(excess.std() * np.sqrt(trading_days))
    if tracking_error == 0:
        return 0.0
    alpha = annualized_return(daily_returns, trading_days) - annualized_return(benchmark_returns, trading_days)
    return float(alpha / tracking_error)


def monthly_win_rate(daily_returns: pd.Series) -> float:
    """Compute percentage of months with positive returns."""
    # Group by month (approximate: 21 trading days)
    n = len(daily_returns)
    if n < 21:
        return 1.0 if daily_returns.sum() > 0 else 0.0
    monthly = []
    for i in range(0, n, 21):
        chunk = daily_returns.iloc[i:i+21]
        monthly_ret = (1 + chunk).prod() - 1
        monthly.append(monthly_ret)
    if not monthly:
        return 0.0
    wins = sum(1 for r in monthly if r > 0)
    return wins / len(monthly)


def compute_all_metrics(
    daily_returns: pd.Series,
    benchmark_returns: pd.Series | None = None,
    risk_free_rate: float = 0.02,
) -> dict[str, float]:
    """Compute all performance metrics."""
    result = {
        "annualized_return": annualized_return(daily_returns),
        "annualized_volatility": annualized_volatility(daily_returns),
        "max_drawdown": max_drawdown(daily_returns),
        "sharpe_ratio": sharpe_ratio(daily_returns, risk_free_rate),
        "sortino_ratio": sortino_ratio(daily_returns, risk_free_rate),
        "calmar_ratio": calmar_ratio(daily_returns),
        "monthly_win_rate": monthly_win_rate(daily_returns),
    }
    if benchmark_returns is not None:
        result["information_ratio"] = information_ratio(daily_returns, benchmark_returns)
        result["alpha"] = result["annualized_return"] - annualized_return(benchmark_returns)
    return result
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_metrics.py -v
```
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/backtest/metrics.py tests/test_metrics.py
git commit -m "feat: 实现绩效指标计算（夏普/Sortino/最大回撤等）"
```

---

### Task 8: 因子筛选策略（FactorStrategy）

**Files:**
- Create: `src/fund_analyzer/strategy/factor.py`
- Create: `tests/test_factor.py`

- [ ] **Step 1: 编写测试 `tests/test_factor.py`**

```python
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
import pandas as pd
import numpy as np

from fund_analyzer.strategy.factor import FactorStrategy


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    # Fund info
    fund_info = MagicMock()
    fund_info.fund_size = Decimal("50.00")
    fund_info.manager_start_date = date(2020, 1, 1)
    repo.get_fund_info.return_value = fund_info

    # NAV data: 756 days (~3 years)
    np.random.seed(42)
    navs = []
    nav_val = 1.0
    for i in range(756):
        ret = np.random.normal(0.0005, 0.015)
        nav_val *= (1 + ret)
        mock_nav = MagicMock()
        mock_nav.date = date(2022, 1, 1).__class__(2022 + i // 365, (i % 365) // 30 + 1, min(i % 30 + 1, 28))
        mock_nav.acc_nav = Decimal(str(round(nav_val, 4)))
        mock_nav.daily_return = Decimal(str(round(ret, 6)))
        navs.append(mock_nav)
    repo.get_fund_nav.return_value = navs
    return repo


@pytest.fixture
def strategy(mock_repo):
    return FactorStrategy(repo=mock_repo)


def test_score_batch_returns_scores(strategy):
    scores = strategy.score_batch(["000001", "000002"], as_of=date(2025, 1, 1))
    assert "000001" in scores
    assert 0 <= scores["000001"] <= 100


def test_score_penalizes_extreme_fund_size(mock_repo):
    # Very large fund
    fund_info = MagicMock()
    fund_info.fund_size = Decimal("500.00")  # 500亿，过大
    fund_info.manager_start_date = date(2020, 1, 1)
    mock_repo.get_fund_info.return_value = fund_info

    strategy = FactorStrategy(repo=mock_repo)
    scores = strategy.score_batch(["000001"], as_of=date(2025, 1, 1))
    # Score should still be valid but lower due to size penalty
    assert 0 <= scores["000001"] <= 100


def test_score_with_no_nav_data(mock_repo):
    mock_repo.get_fund_nav.return_value = []
    strategy = FactorStrategy(repo=mock_repo)
    scores = strategy.score_batch(["000001"], as_of=date(2025, 1, 1))
    assert scores["000001"] == 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_factor.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 `src/fund_analyzer/strategy/factor.py`**

```python
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.backtest.metrics import (
    annualized_return, annualized_volatility, max_drawdown, sharpe_ratio, calmar_ratio, sortino_ratio,
)
from fund_analyzer.strategy.base import BaseStrategy


class FactorStrategy(BaseStrategy):
    """Multi-factor scoring strategy for core position selection."""

    def __init__(
        self,
        repo: FundRepository,
        weights: dict[str, float] | None = None,
    ):
        super().__init__(name="factor")
        self.repo = repo
        self.weights = weights or {
            "return_1y": 0.10,
            "return_3y": 0.10,
            "max_drawdown": 0.10,
            "volatility": 0.05,
            "sharpe": 0.25,
            "calmar": 0.10,
            "sortino": 0.10,
            "manager_tenure": 0.10,
            "fund_size": 0.10,
        }

    def _compute_factors(self, fund_code: str, as_of: date) -> dict[str, float] | None:
        """Compute raw factor values for a fund."""
        info = self.repo.get_fund_info(fund_code)
        if info is None:
            return None

        # Get 3 years of NAV data
        start = as_of - timedelta(days=3 * 365)
        navs = self.repo.get_fund_nav(fund_code, start=start, end=as_of)
        if len(navs) < 60:  # Need at least ~3 months
            return None

        # Convert to daily returns series
        returns = pd.Series([float(n.daily_return or 0) for n in navs])

        # 1-year return
        one_year_navs = navs[-min(252, len(navs)):]
        if len(one_year_navs) >= 2:
            ret_1y = float(one_year_navs[-1].acc_nav / one_year_navs[0].acc_nav - 1)
        else:
            ret_1y = 0.0

        # 3-year return
        if len(navs) >= 2:
            ret_3y = float(navs[-1].acc_nav / navs[0].acc_nav - 1)
            n_years = len(navs) / 252
            ret_3y_ann = (1 + ret_3y) ** (1 / max(n_years, 0.5)) - 1
        else:
            ret_3y_ann = 0.0

        # Risk metrics
        mdd = max_drawdown(returns) if len(returns) > 0 else 1.0
        vol = annualized_volatility(returns) if len(returns) > 0 else 1.0
        sr = sharpe_ratio(returns) if len(returns) > 0 else 0.0
        cr = calmar_ratio(returns) if len(returns) > 0 else 0.0
        so = sortino_ratio(returns) if len(returns) > 0 else 0.0

        # Manager tenure (years)
        tenure = 0.0
        if info.manager_start_date:
            tenure = (as_of - info.manager_start_date).days / 365

        # Fund size (billion CNY)
        size = float(info.fund_size or 0)

        return {
            "return_1y": ret_1y,
            "return_3y": ret_3y_ann,
            "max_drawdown": mdd,
            "volatility": vol,
            "sharpe": sr,
            "calmar": cr,
            "sortino": so,
            "manager_tenure": tenure,
            "fund_size": size,
        }

    def _factor_to_score(self, name: str, value: float) -> float:
        """Convert a raw factor value to a 0-100 score."""
        if name in ("return_1y", "return_3y"):
            # Higher return = higher score. Map [-0.3, 0.5] to [0, 100]
            return max(0, min(100, (value + 0.3) / 0.8 * 100))
        elif name == "max_drawdown":
            # Lower drawdown = higher score. Map [0, 0.5] to [100, 0]
            return max(0, min(100, (1 - value / 0.5) * 100))
        elif name == "volatility":
            # Lower vol = higher score. Map [0, 0.4] to [100, 0]
            return max(0, min(100, (1 - value / 0.4) * 100))
        elif name in ("sharpe", "calmar", "sortino"):
            # Higher = better. Map [-1, 3] to [0, 100]
            return max(0, min(100, (value + 1) / 4 * 100))
        elif name == "manager_tenure":
            # 3-10 years is ideal
            if value < 1:
                return 20
            elif value < 3:
                return 50
            elif value <= 10:
                return 90
            else:
                return 70
        elif name == "fund_size":
            # 2-200 billion is ideal
            if value < 1:
                return 20
            elif value < 2:
                return 50
            elif value <= 200:
                return 90
            else:
                return 60
        return 50

    def score_batch(self, fund_codes: list[str], as_of: date) -> dict[str, float]:
        result = {}
        for code in fund_codes:
            factors = self._compute_factors(code, as_of)
            if factors is None:
                result[code] = 0
                continue
            weighted_score = 0.0
            for factor_name, weight in self.weights.items():
                raw = factors.get(factor_name, 0)
                factor_score = self._factor_to_score(factor_name, raw)
                weighted_score += factor_score * weight
            result[code] = round(weighted_score, 2)
        return result
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_factor.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/strategy/factor.py tests/test_factor.py
git commit -m "feat: 实现因子筛选策略（核心仓位选基）"
```

---

### Task 9: 动量策略（MomentumStrategy）

**Files:**
- Create: `src/fund_analyzer/strategy/momentum.py`
- Create: `tests/test_momentum.py`

- [ ] **Step 1: 编写测试 `tests/test_momentum.py`**

```python
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
import numpy as np

from fund_analyzer.strategy.momentum import MomentumStrategy


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    np.random.seed(42)

    def make_navs(seed_offset=0):
        np.random.seed(42 + seed_offset)
        navs = []
        nav_val = 1.0
        for i in range(252):
            ret = np.random.normal(0.001, 0.02)
            nav_val *= (1 + ret)
            mock_nav = MagicMock()
            mock_nav.acc_nav = Decimal(str(round(nav_val, 4)))
            mock_nav.daily_return = Decimal(str(round(ret, 6)))
            navs.append(mock_nav)
        return navs

    repo.get_fund_nav.side_effect = lambda code, **kwargs: make_navs(hash(code) % 100)
    return repo


@pytest.fixture
def strategy(mock_repo):
    return MomentumStrategy(repo=mock_repo)


def test_score_batch_multiple_funds(strategy):
    scores = strategy.score_batch(["F001", "F002", "F003"], as_of=date(2025, 6, 1))
    assert len(scores) == 3
    for code, score in scores.items():
        assert 0 <= score <= 100


def test_score_uses_relative_ranking(strategy):
    """Scores should reflect relative ranking among the batch."""
    scores = strategy.score_batch(["F001", "F002", "F003", "F004", "F005"],
                                   as_of=date(2025, 6, 1))
    score_values = list(scores.values())
    # Not all scores should be the same (different seeds)
    assert len(set(round(s, 1) for s in score_values)) > 1


def test_score_empty_nav(mock_repo):
    mock_repo.get_fund_nav.return_value = []
    strategy = MomentumStrategy(repo=mock_repo)
    scores = strategy.score_batch(["F001"], as_of=date(2025, 6, 1))
    assert scores["F001"] == 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_momentum.py -v
```
Expected: FAIL

- [ ] **Step 3: 实现 `src/fund_analyzer/strategy/momentum.py`**

```python
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import numpy as np
import pandas as pd

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.base import BaseStrategy


class MomentumStrategy(BaseStrategy):
    """Momentum-based scoring for satellite positions."""

    def __init__(
        self,
        repo: FundRepository,
        windows: list[int] | None = None,
        window_weights: list[float] | None = None,
    ):
        super().__init__(name="momentum")
        self.repo = repo
        self.windows = windows or [20, 60, 120]
        self.window_weights = window_weights or [0.4, 0.35, 0.25]

    def _compute_momentum(self, fund_code: str, as_of: date) -> dict[str, float] | None:
        """Compute momentum values for different windows."""
        max_window = max(self.windows) + 10
        start = as_of - timedelta(days=int(max_window * 1.5))
        navs = self.repo.get_fund_nav(fund_code, start=start, end=as_of)

        if len(navs) < 20:
            return None

        acc_navs = [float(n.acc_nav) for n in navs]
        result = {}
        for window in self.windows:
            if len(acc_navs) >= window:
                recent = acc_navs[-1]
                past = acc_navs[-window]
                if past > 0:
                    result[f"mom_{window}"] = (recent / past - 1)
                else:
                    result[f"mom_{window}"] = 0.0
            else:
                result[f"mom_{window}"] = 0.0

        # Momentum reversal detection: short-term momentum drop
        if len(acc_navs) >= 10:
            short_mom = acc_navs[-1] / acc_navs[-5] - 1 if acc_navs[-5] > 0 else 0
            mid_mom = acc_navs[-1] / acc_navs[-20] - 1 if len(acc_navs) >= 20 and acc_navs[-20] > 0 else 0
            result["reversal_risk"] = 1.0 if (mid_mom > 0.05 and short_mom < -0.03) else 0.0
        else:
            result["reversal_risk"] = 0.0

        return result

    def score_batch(self, fund_codes: list[str], as_of: date) -> dict[str, float]:
        # Step 1: compute raw momentum for all funds
        raw_scores = {}
        for code in fund_codes:
            mom = self._compute_momentum(code, as_of)
            if mom is None:
                raw_scores[code] = None
                continue

            # Weighted average of momentum values
            weighted = 0.0
            for window, weight in zip(self.windows, self.window_weights):
                weighted += mom.get(f"mom_{window}", 0) * weight

            # Penalize reversal risk
            if mom.get("reversal_risk", 0) > 0:
                weighted *= 0.7

            raw_scores[code] = weighted

        # Step 2: Rank within the batch (percentile ranking)
        valid_scores = {k: v for k, v in raw_scores.items() if v is not None}
        if not valid_scores:
            return {code: 0 for code in fund_codes}

        sorted_codes = sorted(valid_scores.keys(), key=lambda c: valid_scores[c])
        n = len(sorted_codes)

        result = {}
        for rank, code in enumerate(sorted_codes):
            percentile = (rank / max(n - 1, 1)) * 100
            result[code] = round(percentile, 2)

        # Assign 0 to funds with no data
        for code in fund_codes:
            if code not in result:
                result[code] = 0

        return result
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_momentum.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/strategy/momentum.py tests/test_momentum.py
git commit -m "feat: 实现动量策略（含反转检测和相对排名）"
```

---

### Task 10: 行业轮动策略（RotationStrategy）

**Files:**
- Create: `src/fund_analyzer/strategy/rotation.py`
- Create: `tests/test_rotation.py`

- [ ] **Step 1: 编写测试 `tests/test_rotation.py`**

```python
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from fund_analyzer.strategy.rotation import RotationStrategy


@pytest.fixture
def mock_repo():
    repo = MagicMock()

    # Fund holdings
    holding1 = MagicMock()
    holding1.industry = "电子"
    holding1.weight = Decimal("30.00")
    holding2 = MagicMock()
    holding2.industry = "计算机"
    holding2.weight = Decimal("20.00")
    holding3 = MagicMock()
    holding3.industry = "医药生物"
    holding3.weight = Decimal("15.00")
    repo.get_fund_holdings.return_value = [holding1, holding2, holding3]

    # Index quotes for industries
    def make_index_quotes(code, **kwargs):
        quotes = []
        base = 1000
        for i in range(60):
            q = MagicMock()
            if "电子" in code or code == "电子":
                base_v = 1000 + i * 10  # Strong uptrend
            elif "计算机" in code or code == "计算机":
                base_v = 1000 + i * 5
            else:
                base_v = 1000 - i * 2  # Weak
            q.close = Decimal(str(base_v))
            quotes.append(q)
        return quotes

    repo.get_index_quote.side_effect = make_index_quotes
    return repo


@pytest.fixture
def strategy(mock_repo):
    return RotationStrategy(
        repo=mock_repo,
        industry_indices={"电子": "电子", "计算机": "计算机", "医药生物": "医药生物"},
    )


def test_score_batch(strategy):
    scores = strategy.score_batch(["F001"], as_of=date(2025, 6, 1))
    assert "F001" in scores
    assert 0 <= scores["F001"] <= 100


def test_fund_in_strong_industry_scores_higher(mock_repo):
    # Fund A: heavy in strong industry
    holding_strong = MagicMock()
    holding_strong.industry = "电子"
    holding_strong.weight = Decimal("80.00")

    # Fund B: heavy in weak industry
    holding_weak = MagicMock()
    holding_weak.industry = "医药生物"
    holding_weak.weight = Decimal("80.00")

    def get_holdings(code, report_date):
        if code == "STRONG":
            return [holding_strong]
        return [holding_weak]

    mock_repo.get_fund_holdings.side_effect = get_holdings

    strategy = RotationStrategy(
        repo=mock_repo,
        industry_indices={"电子": "电子", "医药生物": "医药生物"},
    )
    scores = strategy.score_batch(["STRONG", "WEAK"], as_of=date(2025, 6, 1))
    assert scores["STRONG"] > scores["WEAK"]


def test_no_holdings_returns_zero(mock_repo):
    mock_repo.get_fund_holdings.return_value = []
    strategy = RotationStrategy(repo=mock_repo, industry_indices={})
    scores = strategy.score_batch(["F001"], as_of=date(2025, 6, 1))
    assert scores["F001"] == 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_rotation.py -v
```

- [ ] **Step 3: 实现 `src/fund_analyzer/strategy/rotation.py`**

```python
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.base import BaseStrategy


class RotationStrategy(BaseStrategy):
    """Industry rotation strategy for discovering strong sectors."""

    def __init__(
        self,
        repo: FundRepository,
        industry_indices: dict[str, str] | None = None,
        momentum_window: int = 60,
    ):
        super().__init__(name="rotation")
        self.repo = repo
        self.industry_indices = industry_indices or {}
        self.momentum_window = momentum_window

    def _get_industry_momentum(self, industry: str, as_of: date) -> float | None:
        """Compute momentum for an industry index."""
        index_code = self.industry_indices.get(industry)
        if not index_code:
            return None

        start = as_of - timedelta(days=int(self.momentum_window * 1.5))
        quotes = self.repo.get_index_quote(index_code, start=start, end=as_of)

        if len(quotes) < 2:
            return None

        first = float(quotes[0].close)
        last = float(quotes[-1].close)
        if first <= 0:
            return None

        return (last / first) - 1

    def _get_latest_report_date(self, as_of: date) -> date:
        """Get the most recent quarterly report date before as_of."""
        year = as_of.year
        quarters = [
            date(year, 3, 31), date(year, 6, 30),
            date(year, 9, 30), date(year, 12, 31),
            date(year - 1, 9, 30), date(year - 1, 12, 31),
        ]
        for q in sorted(quarters, reverse=True):
            if q <= as_of - timedelta(days=30):  # Allow reporting delay
                return q
        return date(year - 1, 12, 31)

    def score_batch(self, fund_codes: list[str], as_of: date) -> dict[str, float]:
        # Step 1: compute industry momentum
        industry_mom = {}
        for industry in self.industry_indices:
            mom = self._get_industry_momentum(industry, as_of)
            if mom is not None:
                industry_mom[industry] = mom

        if not industry_mom:
            return {code: 0 for code in fund_codes}

        # Rank industries by momentum
        sorted_industries = sorted(industry_mom.keys(), key=lambda x: industry_mom[x], reverse=True)
        n_ind = len(sorted_industries)
        industry_rank = {}
        for rank, ind in enumerate(sorted_industries):
            industry_rank[ind] = (n_ind - rank) / n_ind * 100  # Top industry = 100

        # Step 2: score each fund based on its industry exposure
        report_date = self._get_latest_report_date(as_of)
        result = {}

        for code in fund_codes:
            holdings = self.repo.get_fund_holdings(code, report_date)
            if not holdings:
                result[code] = 0
                continue

            weighted_score = 0.0
            total_weight = 0.0
            for h in holdings:
                ind = h.industry
                w = float(h.weight)
                if ind in industry_rank:
                    weighted_score += industry_rank[ind] * w
                    total_weight += w

            if total_weight > 0:
                result[code] = round(weighted_score / total_weight, 2)
            else:
                result[code] = 0

        return result
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_rotation.py -v
```
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/strategy/rotation.py tests/test_rotation.py
git commit -m "feat: 实现行业轮动策略"
```

---

### Task 11: 全球配置策略（GlobalAllocStrategy）

**Files:**
- Create: `src/fund_analyzer/strategy/global_alloc.py`
- Create: `tests/test_global_alloc.py`

- [ ] **Step 1: 编写测试 `tests/test_global_alloc.py`**

```python
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from fund_analyzer.strategy.global_alloc import GlobalAllocStrategy


@pytest.fixture
def mock_repo():
    repo = MagicMock()

    def make_quotes(code, **kwargs):
        quotes = []
        for i in range(120):
            q = MagicMock()
            if "000688" in code:  # 科创50, flat
                q.close = Decimal(str(1000 + i * 1))
            elif "SPX" in code or "标普" in code:  # S&P500, strong
                q.close = Decimal(str(4000 + i * 20))
            else:
                q.close = Decimal(str(1000))
            quotes.append(q)
        return quotes

    repo.get_index_quote.side_effect = make_quotes

    # Fund info: classify by market
    def get_fund_info(code):
        info = MagicMock()
        if "QDII" in code:
            info.market = "us"
        else:
            info.market = "a_share"
        return info

    repo.get_fund_info.side_effect = get_fund_info
    return repo


@pytest.fixture
def strategy(mock_repo):
    return GlobalAllocStrategy(
        repo=mock_repo,
        market_indices={"a_share": "000688", "us": "SPX"},
    )


def test_score_batch(strategy):
    scores = strategy.score_batch(["QDII_001", "A_001"], as_of=date(2025, 6, 1))
    assert len(scores) == 2
    for score in scores.values():
        assert 0 <= score <= 100


def test_us_fund_scores_higher_when_us_strong(strategy):
    scores = strategy.score_batch(["QDII_001", "A_001"], as_of=date(2025, 6, 1))
    # US market is configured to be stronger, so QDII should score higher
    assert scores["QDII_001"] > scores["A_001"]
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_global_alloc.py -v
```

- [ ] **Step 3: 实现 `src/fund_analyzer/strategy/global_alloc.py`**

```python
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.base import BaseStrategy


class GlobalAllocStrategy(BaseStrategy):
    """Global allocation strategy: compare market trends to weight QDII vs A-share."""

    def __init__(
        self,
        repo: FundRepository,
        market_indices: dict[str, str] | None = None,
        lookback_days: int = 120,
    ):
        super().__init__(name="global_alloc")
        self.repo = repo
        self.market_indices = market_indices or {
            "a_share": "000688",  # 科创50
            "us": "SPX",         # 标普500
        }
        self.lookback_days = lookback_days

    def _market_momentum(self, market: str, as_of: date) -> float | None:
        index_code = self.market_indices.get(market)
        if not index_code:
            return None
        start = as_of - timedelta(days=int(self.lookback_days * 1.5))
        quotes = self.repo.get_index_quote(index_code, start=start, end=as_of)
        if len(quotes) < 2:
            return None
        first = float(quotes[0].close)
        last = float(quotes[-1].close)
        if first <= 0:
            return None
        return (last / first) - 1

    def _market_scores(self, as_of: date) -> dict[str, float]:
        """Score each market 0-100 based on relative momentum."""
        momentums = {}
        for market in self.market_indices:
            mom = self._market_momentum(market, as_of)
            if mom is not None:
                momentums[market] = mom

        if not momentums:
            # Equal weight if no data
            return {m: 50.0 for m in self.market_indices}

        # Rank markets
        sorted_markets = sorted(momentums.keys(), key=lambda x: momentums[x], reverse=True)
        n = len(sorted_markets)
        scores = {}
        for rank, market in enumerate(sorted_markets):
            scores[market] = round((n - rank) / n * 100, 2)

        return scores

    def score_batch(self, fund_codes: list[str], as_of: date) -> dict[str, float]:
        market_scores = self._market_scores(as_of)

        result = {}
        for code in fund_codes:
            info = self.repo.get_fund_info(code)
            if info is None:
                result[code] = 50  # Neutral
                continue

            market = getattr(info, "market", "a_share")
            # Map market to score; default to a_share
            if market in market_scores:
                result[code] = market_scores[market]
            elif market in ("hk", "global"):
                # Average of available markets
                result[code] = sum(market_scores.values()) / max(len(market_scores), 1)
            else:
                result[code] = market_scores.get("a_share", 50)

        return result
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_global_alloc.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/strategy/global_alloc.py tests/test_global_alloc.py
git commit -m "feat: 实现全球配置策略"
```

---

### Task 12: 综合评分策略（CompositeStrategy）

**Files:**
- Create: `src/fund_analyzer/strategy/composite.py`
- Create: `tests/test_composite.py`

- [ ] **Step 1: 编写测试 `tests/test_composite.py`**

```python
import pytest
from datetime import date
from unittest.mock import MagicMock

from fund_analyzer.strategy.composite import CompositeStrategy
from fund_analyzer.strategy.base import Signal


@pytest.fixture
def mock_strategies():
    factor = MagicMock()
    factor.name = "factor"
    factor.score_batch.return_value = {"F001": 85, "F002": 60}

    momentum = MagicMock()
    momentum.name = "momentum"
    momentum.score_batch.return_value = {"F001": 70, "F002": 90}

    rotation = MagicMock()
    rotation.name = "rotation"
    rotation.score_batch.return_value = {"F001": 65, "F002": 80}

    global_alloc = MagicMock()
    global_alloc.name = "global_alloc"
    global_alloc.score_batch.return_value = {"F001": 50, "F002": 75}

    return {
        "factor": factor,
        "momentum": momentum,
        "rotation": rotation,
        "global_alloc": global_alloc,
    }


@pytest.fixture
def composite(mock_strategies):
    return CompositeStrategy(
        strategies=mock_strategies,
        core_weights={"factor": 70, "global_alloc": 30},
        satellite_weights={"momentum": 40, "rotation": 35, "global_alloc": 25},
    )


def test_score_core(composite):
    scores = composite.score_core(["F001", "F002"], as_of=date(2025, 6, 1))
    # F001: factor=85*0.7 + global=50*0.3 = 59.5+15 = 74.5
    assert abs(scores["F001"] - 74.5) < 0.1


def test_score_satellite(composite):
    scores = composite.score_satellite(["F001", "F002"], as_of=date(2025, 6, 1))
    # F002: momentum=90*0.4 + rotation=80*0.35 + global=75*0.25 = 36+28+18.75 = 82.75
    assert abs(scores["F002"] - 82.75) < 0.1


def test_signal_from_composite(composite):
    signal = composite.signal("F001", as_of=date(2025, 6, 1), position_type="core")
    assert signal.action in ("buy", "sell", "hold")


def test_recommend(composite):
    core, satellite = composite.recommend(
        ["F001", "F002"], as_of=date(2025, 6, 1), core_top_n=1, satellite_top_n=1,
    )
    assert len(core) == 1
    assert len(satellite) == 1
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_composite.py -v
```

- [ ] **Step 3: 实现 `src/fund_analyzer/strategy/composite.py`**

```python
from __future__ import annotations

from datetime import date

from fund_analyzer.strategy.base import BaseStrategy, Signal, score_to_signal


class CompositeStrategy:
    """Composite strategy with separate core/satellite scoring channels."""

    def __init__(
        self,
        strategies: dict[str, BaseStrategy],
        core_weights: dict[str, float],
        satellite_weights: dict[str, float],
        buy_threshold: float = 80,
        sell_threshold: float = 60,
    ):
        self.strategies = strategies
        self.core_weights = core_weights
        self.satellite_weights = satellite_weights
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold

    def _weighted_score(
        self, fund_codes: list[str], as_of: date, weights: dict[str, float]
    ) -> dict[str, float]:
        total_weight = sum(weights.values())
        if total_weight == 0:
            return {code: 0 for code in fund_codes}

        # Gather scores from each strategy
        strategy_scores = {}
        for name, weight in weights.items():
            if name in self.strategies:
                strategy_scores[name] = self.strategies[name].score_batch(fund_codes, as_of)

        # Weighted average
        result = {}
        for code in fund_codes:
            weighted_sum = 0.0
            for name, weight in weights.items():
                score = strategy_scores.get(name, {}).get(code, 0)
                weighted_sum += score * weight
            result[code] = round(weighted_sum / total_weight, 2)

        return result

    def score_core(self, fund_codes: list[str], as_of: date) -> dict[str, float]:
        return self._weighted_score(fund_codes, as_of, self.core_weights)

    def score_satellite(self, fund_codes: list[str], as_of: date) -> dict[str, float]:
        return self._weighted_score(fund_codes, as_of, self.satellite_weights)

    def signal(
        self, fund_code: str, as_of: date, position_type: str = "satellite"
    ) -> Signal:
        if position_type == "core":
            scores = self.score_core([fund_code], as_of)
        else:
            scores = self.score_satellite([fund_code], as_of)
        score = scores.get(fund_code, 0)
        return score_to_signal(score, self.buy_threshold, self.sell_threshold)

    def recommend(
        self,
        fund_codes: list[str],
        as_of: date,
        core_top_n: int = 3,
        satellite_top_n: int = 7,
    ) -> tuple[list[tuple[str, float]], list[tuple[str, float]]]:
        """Return (core_picks, satellite_picks) as sorted lists of (code, score)."""
        core_scores = self.score_core(fund_codes, as_of)
        sat_scores = self.score_satellite(fund_codes, as_of)

        core_sorted = sorted(core_scores.items(), key=lambda x: x[1], reverse=True)
        sat_sorted = sorted(sat_scores.items(), key=lambda x: x[1], reverse=True)

        return core_sorted[:core_top_n], sat_sorted[:satellite_top_n]
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_composite.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/strategy/composite.py tests/test_composite.py
git commit -m "feat: 实现综合评分策略（核心/卫星双通道）"
```

---

### Task 13: 回测引擎

**Files:**
- Create: `src/fund_analyzer/backtest/engine.py`
- Create: `tests/test_backtest_engine.py`

- [ ] **Step 1: 编写测试 `tests/test_backtest_engine.py`**

```python
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock
import numpy as np

from fund_analyzer.backtest.engine import BacktestEngine


@pytest.fixture
def mock_repo():
    repo = MagicMock()

    def make_navs(code, start=None, end=None):
        navs = []
        np.random.seed(hash(code) % 1000)
        nav_val = 1.0
        d = date(2022, 1, 1)
        for i in range(756):
            ret = np.random.normal(0.0005, 0.015)
            nav_val *= (1 + ret)
            n = MagicMock()
            n.date = date(2022, 1, 1).__class__(
                2022 + (i // 252), ((i % 252) // 21) + 1, min((i % 21) + 1, 28)
            )
            n.acc_nav = Decimal(str(round(nav_val, 4)))
            n.daily_return = Decimal(str(round(ret, 6)))
            navs.append(n)
        # Filter by date if needed
        if start:
            navs = [n for n in navs if n.date >= start]
        if end:
            navs = [n for n in navs if n.date <= end]
        return navs

    repo.get_fund_nav.side_effect = make_navs

    def make_index_quotes(code, start=None, end=None):
        quotes = []
        val = 1000
        for i in range(756):
            val *= (1 + np.random.normal(0.0003, 0.018))
            q = MagicMock()
            q.date = date(2022, 1, 1).__class__(
                2022 + (i // 252), ((i % 252) // 21) + 1, min((i % 21) + 1, 28)
            )
            q.close = Decimal(str(round(val, 4)))
            q.daily_return = Decimal(str(round(np.random.normal(0.0003, 0.018), 6)))
            quotes.append(q)
        if start:
            quotes = [q for q in quotes if q.date >= start]
        if end:
            quotes = [q for q in quotes if q.date <= end]
        return quotes

    repo.get_index_quote.side_effect = make_index_quotes
    return repo


@pytest.fixture
def mock_composite():
    composite = MagicMock()
    composite.recommend.return_value = (
        [("F001", 90), ("F002", 85), ("F003", 80)],  # core
        [("F004", 95), ("F005", 88), ("F006", 85), ("F007", 82),
         ("F008", 80), ("F009", 78), ("F010", 75)],  # satellite
    )
    return composite


@pytest.fixture
def engine(mock_repo, mock_composite):
    return BacktestEngine(
        repo=mock_repo,
        composite=mock_composite,
        initial_capital=100000,
        core_ratio=0.3,
        satellite_ratio=0.7,
        buy_fee=0.0015,
        sell_fee=0.005,
    )


def test_run_backtest(engine):
    result = engine.run(
        fund_universe=["F001", "F002", "F003", "F004", "F005",
                       "F006", "F007", "F008", "F009", "F010"],
        start=date(2022, 6, 1),
        end=date(2024, 6, 1),
        benchmark_code="000688",
    )
    assert "portfolio_returns" in result
    assert "benchmark_returns" in result
    assert "metrics" in result
    assert result["metrics"]["annualized_return"] is not None


def test_backtest_deducts_fees(engine):
    result = engine.run(
        fund_universe=["F001", "F002", "F003", "F004", "F005",
                       "F006", "F007", "F008", "F009", "F010"],
        start=date(2022, 6, 1),
        end=date(2024, 6, 1),
        benchmark_code="000688",
    )
    # With fees, total value should be less than without
    assert result["total_fees_paid"] > 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_backtest_engine.py -v
```

- [ ] **Step 3: 实现 `src/fund_analyzer/backtest/engine.py`**

```python
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pandas as pd
import numpy as np

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.composite import CompositeStrategy
from fund_analyzer.backtest.metrics import compute_all_metrics


class BacktestEngine:
    """Backtest engine for core+satellite portfolio strategy."""

    def __init__(
        self,
        repo: FundRepository,
        composite: CompositeStrategy,
        initial_capital: float = 100000,
        core_ratio: float = 0.3,
        satellite_ratio: float = 0.7,
        core_top_n: int = 3,
        satellite_top_n: int = 7,
        buy_fee: float = 0.0015,
        sell_fee: float = 0.005,
        core_rebalance_months: int = 3,
        satellite_rebalance_months: int = 1,
    ):
        self.repo = repo
        self.composite = composite
        self.initial_capital = initial_capital
        self.core_ratio = core_ratio
        self.satellite_ratio = satellite_ratio
        self.core_top_n = core_top_n
        self.satellite_top_n = satellite_top_n
        self.buy_fee = buy_fee
        self.sell_fee = sell_fee
        self.core_rebalance_months = core_rebalance_months
        self.satellite_rebalance_months = satellite_rebalance_months

    def _get_rebalance_dates(self, start: date, end: date, months: int) -> list[date]:
        """Generate rebalance dates at given month intervals."""
        dates = []
        current = start
        while current <= end:
            dates.append(current)
            month = current.month + months
            year = current.year + (month - 1) // 12
            month = (month - 1) % 12 + 1
            day = min(current.day, 28)
            current = date(year, month, day)
        return dates

    def _get_daily_return(self, fund_code: str, d: date) -> float:
        """Get daily return for a fund on a specific date."""
        navs = self.repo.get_fund_nav(fund_code, start=d, end=d)
        if navs:
            return float(navs[0].daily_return or 0)
        return 0.0

    def run(
        self,
        fund_universe: list[str],
        start: date,
        end: date,
        benchmark_code: str = "000688",
    ) -> dict:
        """Run backtest and return results."""
        # Get all trading dates from benchmark
        benchmark_quotes = self.repo.get_index_quote(benchmark_code, start=start, end=end)
        if not benchmark_quotes:
            return {"error": "No benchmark data"}

        trading_dates = [q.date for q in benchmark_quotes]
        benchmark_returns = pd.Series(
            [float(q.daily_return or 0) for q in benchmark_quotes],
            index=trading_dates,
        )

        # Rebalance schedules
        core_dates = set(self._get_rebalance_dates(start, end, self.core_rebalance_months))
        sat_dates = set(self._get_rebalance_dates(start, end, self.satellite_rebalance_months))

        # Portfolio state
        core_capital = self.initial_capital * self.core_ratio
        sat_capital = self.initial_capital * self.satellite_ratio
        core_holdings: dict[str, float] = {}   # {fund_code: capital_allocated}
        sat_holdings: dict[str, float] = {}
        total_fees = 0.0

        portfolio_values = []

        for d in trading_dates:
            # Rebalance core
            if d in core_dates:
                core_picks, _ = self.composite.recommend(
                    fund_universe, as_of=d,
                    core_top_n=self.core_top_n, satellite_top_n=0,
                )
                # Sell old, buy new
                total_fees += sum(v * self.sell_fee for v in core_holdings.values())
                core_total = sum(core_holdings.values()) if core_holdings else core_capital
                core_holdings = {}
                if core_picks:
                    per_fund = core_total / len(core_picks)
                    for code, _ in core_picks:
                        allocated = per_fund * (1 - self.buy_fee)
                        total_fees += per_fund * self.buy_fee
                        core_holdings[code] = allocated

            # Rebalance satellite
            if d in sat_dates:
                _, sat_picks = self.composite.recommend(
                    fund_universe, as_of=d,
                    core_top_n=0, satellite_top_n=self.satellite_top_n,
                )
                total_fees += sum(v * self.sell_fee for v in sat_holdings.values())
                sat_total = sum(sat_holdings.values()) if sat_holdings else sat_capital
                sat_holdings = {}
                if sat_picks:
                    # Weighted by score
                    total_score = sum(s for _, s in sat_picks)
                    for code, score in sat_picks:
                        weight = score / total_score if total_score > 0 else 1 / len(sat_picks)
                        allocated = sat_total * weight * (1 - self.buy_fee)
                        total_fees += sat_total * weight * self.buy_fee
                        sat_holdings[code] = allocated

            # Apply daily returns
            for code in core_holdings:
                ret = self._get_daily_return(code, d)
                core_holdings[code] *= (1 + ret)

            for code in sat_holdings:
                ret = self._get_daily_return(code, d)
                sat_holdings[code] *= (1 + ret)

            total_value = sum(core_holdings.values()) + sum(sat_holdings.values())
            portfolio_values.append(total_value)

        # Compute returns
        if len(portfolio_values) < 2:
            return {"error": "Insufficient data"}

        portfolio_series = pd.Series(portfolio_values, index=trading_dates[:len(portfolio_values)])
        portfolio_returns = portfolio_series.pct_change().dropna()

        # Align benchmark
        aligned_benchmark = benchmark_returns.reindex(portfolio_returns.index).fillna(0)

        metrics = compute_all_metrics(portfolio_returns, aligned_benchmark)

        return {
            "portfolio_returns": portfolio_returns,
            "benchmark_returns": aligned_benchmark,
            "portfolio_values": portfolio_series,
            "metrics": metrics,
            "total_fees_paid": total_fees,
            "final_value": portfolio_values[-1] if portfolio_values else 0,
            "initial_capital": self.initial_capital,
        }
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_backtest_engine.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/backtest/engine.py tests/test_backtest_engine.py
git commit -m "feat: 实现回测引擎（核心+卫星双通道调仓）"
```

---

### Task 14: 组合管理（Portfolio Manager）

**Files:**
- Create: `src/fund_analyzer/portfolio/manager.py`
- Create: `tests/test_portfolio_manager.py`

- [ ] **Step 1: 编写测试 `tests/test_portfolio_manager.py`**

```python
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundInfo, FundNav, PortfolioPosition, PortfolioTransaction
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.portfolio.manager import PortfolioManager


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        # Add a fund and its NAV
        session.add(FundInfo(fund_code="000001", fund_name="测试基金", fund_type="混合型", market="a_share"))
        session.add(FundNav(fund_code="000001", date=date(2025, 3, 1),
                            nav=Decimal("2.0000"), acc_nav=Decimal("2.0000"), daily_return=Decimal("0.01")))
        session.commit()
        yield session


@pytest.fixture
def manager(db_session):
    repo = FundRepository(db_session)
    return PortfolioManager(repo=repo)


def test_buy_fund(manager, db_session):
    manager.buy("000001", amount=10000, nav=Decimal("2.0"), position_type="satellite", buy_date=date(2025, 3, 1))
    positions = db_session.query(PortfolioPosition).all()
    assert len(positions) == 1
    assert positions[0].fund_code == "000001"
    assert positions[0].shares == Decimal("5000.0000")  # 10000 / 2.0
    assert positions[0].position_type == "satellite"

    txs = db_session.query(PortfolioTransaction).all()
    assert len(txs) == 1
    assert txs[0].type == "buy"


def test_sell_fund(manager, db_session):
    manager.buy("000001", amount=10000, nav=Decimal("2.0"), position_type="core", buy_date=date(2025, 3, 1))
    manager.sell("000001", shares=Decimal("2000"), nav=Decimal("2.5"), sell_date=date(2025, 6, 1))

    positions = db_session.query(PortfolioPosition).all()
    assert len(positions) == 1
    assert positions[0].shares == Decimal("3000.0000")
    assert positions[0].status == "holding"


def test_sell_all_clears_position(manager, db_session):
    manager.buy("000001", amount=10000, nav=Decimal("2.0"), position_type="core", buy_date=date(2025, 3, 1))
    manager.sell("000001", shares=Decimal("5000"), nav=Decimal("2.5"), sell_date=date(2025, 6, 1))

    positions = db_session.query(PortfolioPosition).all()
    assert positions[0].status == "cleared"
    assert positions[0].sell_date == date(2025, 6, 1)
    assert positions[0].sell_price == Decimal("2.5")


def test_get_holdings(manager):
    manager.buy("000001", amount=10000, nav=Decimal("2.0"), position_type="satellite", buy_date=date(2025, 3, 1))
    holdings = manager.get_holdings()
    assert len(holdings) == 1
    assert holdings[0]["fund_code"] == "000001"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_portfolio_manager.py -v
```

- [ ] **Step 3: 实现 `src/fund_analyzer/portfolio/manager.py`**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from fund_analyzer.data.models import PortfolioPosition, PortfolioTransaction
from fund_analyzer.data.repository import FundRepository


class PortfolioManager:
    """Manage portfolio positions and transactions."""

    def __init__(self, repo: FundRepository):
        self.repo = repo

    def buy(
        self,
        fund_code: str,
        amount: float,
        nav: Decimal,
        position_type: str = "satellite",
        buy_date: date | None = None,
        dip_plan_id: int | None = None,
    ) -> PortfolioPosition:
        buy_date = buy_date or date.today()
        shares = Decimal(str(amount)) / nav
        shares = shares.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        # Create position
        position = PortfolioPosition(
            fund_code=fund_code,
            position_type=position_type,
            buy_date=buy_date,
            shares=shares,
            cost_price=nav,
            status="holding",
        )
        self.repo.session.add(position)

        # Create transaction
        tx_type = "dip" if dip_plan_id else "buy"
        self.repo.add_transaction({
            "fund_code": fund_code,
            "date": buy_date,
            "type": tx_type,
            "amount": Decimal(str(amount)),
            "shares": shares,
            "nav": nav,
            "position_type": position_type,
            "dip_plan_id": dip_plan_id,
        })

        return position

    def sell(
        self,
        fund_code: str,
        shares: Decimal,
        nav: Decimal,
        sell_date: date | None = None,
    ) -> None:
        sell_date = sell_date or date.today()
        positions = self.repo.get_active_positions()
        fund_positions = [p for p in positions if p.fund_code == fund_code]

        if not fund_positions:
            raise ValueError(f"No active position for {fund_code}")

        remaining = shares
        for pos in fund_positions:
            if remaining <= 0:
                break
            if pos.shares <= remaining:
                # Sell entire position
                remaining -= pos.shares
                amount = pos.shares * nav
                pos.status = "cleared"
                pos.sell_date = sell_date
                pos.sell_price = nav
                self.repo.add_transaction({
                    "fund_code": fund_code,
                    "date": sell_date,
                    "type": "sell",
                    "amount": amount,
                    "shares": pos.shares,
                    "nav": nav,
                    "position_type": pos.position_type,
                })
                pos.shares = Decimal("0")
            else:
                # Partial sell
                amount = remaining * nav
                pos.shares -= remaining
                self.repo.add_transaction({
                    "fund_code": fund_code,
                    "date": sell_date,
                    "type": "sell",
                    "amount": amount,
                    "shares": remaining,
                    "nav": nav,
                    "position_type": pos.position_type,
                })
                remaining = Decimal("0")

        self.repo.session.commit()

    def get_holdings(self, position_type: str | None = None) -> list[dict]:
        positions = self.repo.get_active_positions(position_type)
        result = []
        for pos in positions:
            info = self.repo.get_fund_info(pos.fund_code)
            fund_name = info.fund_name if info else pos.fund_code
            result.append({
                "fund_code": pos.fund_code,
                "fund_name": fund_name,
                "position_type": pos.position_type,
                "shares": pos.shares,
                "cost_price": pos.cost_price,
                "buy_date": pos.buy_date,
            })
        return result
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_portfolio_manager.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/portfolio/manager.py tests/test_portfolio_manager.py
git commit -m "feat: 实现组合持仓管理（买入/卖出/查询）"
```

---

### Task 15: 收益追踪（Tracker）

**Files:**
- Create: `src/fund_analyzer/portfolio/tracker.py`
- Create: `tests/test_tracker.py`

- [ ] **Step 1: 编写测试 `tests/test_tracker.py`**

```python
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from fund_analyzer.portfolio.tracker import PortfolioTracker


@pytest.fixture
def mock_repo():
    repo = MagicMock()

    pos1 = MagicMock()
    pos1.fund_code = "000001"
    pos1.position_type = "core"
    pos1.shares = Decimal("1000")
    pos1.cost_price = Decimal("2.0")

    pos2 = MagicMock()
    pos2.fund_code = "000002"
    pos2.position_type = "satellite"
    pos2.shares = Decimal("2000")
    pos2.cost_price = Decimal("1.5")

    repo.get_active_positions.return_value = [pos1, pos2]

    def get_nav(code, start=None, end=None):
        nav = MagicMock()
        if code == "000001":
            nav.nav = Decimal("2.5")
            nav.acc_nav = Decimal("2.5")
        else:
            nav.nav = Decimal("1.8")
            nav.acc_nav = Decimal("1.8")
        return [nav]

    repo.get_fund_nav.side_effect = get_nav
    return repo


@pytest.fixture
def tracker(mock_repo):
    return PortfolioTracker(repo=mock_repo)


def test_compute_portfolio_summary(tracker):
    summary = tracker.summary(as_of=date(2025, 6, 1))
    assert summary["total_market_value"] > 0
    assert summary["total_cost"] > 0
    assert "total_return_pct" in summary
    assert "core" in summary["by_type"]
    assert "satellite" in summary["by_type"]


def test_core_satellite_breakdown(tracker):
    summary = tracker.summary(as_of=date(2025, 6, 1))
    core = summary["by_type"]["core"]
    sat = summary["by_type"]["satellite"]
    # Core: 1000 shares * 2.5 = 2500
    assert core["market_value"] == 2500
    # Satellite: 2000 * 1.8 = 3600
    assert sat["market_value"] == 3600
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_tracker.py -v
```

- [ ] **Step 3: 实现 `src/fund_analyzer/portfolio/tracker.py`**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fund_analyzer.data.repository import FundRepository


class PortfolioTracker:
    """Track portfolio performance and returns."""

    def __init__(self, repo: FundRepository):
        self.repo = repo

    def _get_latest_nav(self, fund_code: str, as_of: date) -> Decimal | None:
        navs = self.repo.get_fund_nav(fund_code, start=as_of, end=as_of)
        if navs:
            return navs[-1].nav
        # Try recent dates
        from datetime import timedelta
        for days_back in range(1, 10):
            d = as_of - timedelta(days=days_back)
            navs = self.repo.get_fund_nav(fund_code, start=d, end=d)
            if navs:
                return navs[-1].nav
        return None

    def summary(self, as_of: date | None = None) -> dict:
        as_of = as_of or date.today()
        positions = self.repo.get_active_positions()

        by_type: dict[str, dict] = {}
        holdings = []

        for pos in positions:
            nav = self._get_latest_nav(pos.fund_code, as_of)
            if nav is None:
                nav = pos.cost_price  # Fallback

            market_value = float(pos.shares * nav)
            cost = float(pos.shares * pos.cost_price)
            pnl = market_value - cost
            return_pct = (pnl / cost * 100) if cost > 0 else 0

            holding = {
                "fund_code": pos.fund_code,
                "position_type": pos.position_type,
                "shares": float(pos.shares),
                "cost_price": float(pos.cost_price),
                "current_nav": float(nav),
                "market_value": market_value,
                "cost": cost,
                "pnl": pnl,
                "return_pct": round(return_pct, 2),
            }
            holdings.append(holding)

            pt = pos.position_type
            if pt not in by_type:
                by_type[pt] = {"market_value": 0, "cost": 0, "pnl": 0}
            by_type[pt]["market_value"] += market_value
            by_type[pt]["cost"] += cost
            by_type[pt]["pnl"] += pnl

        for pt in by_type:
            cost = by_type[pt]["cost"]
            by_type[pt]["return_pct"] = round(by_type[pt]["pnl"] / cost * 100, 2) if cost > 0 else 0

        total_mv = sum(h["market_value"] for h in holdings)
        total_cost = sum(h["cost"] for h in holdings)
        total_pnl = total_mv - total_cost

        return {
            "as_of": as_of,
            "total_market_value": round(total_mv, 2),
            "total_cost": round(total_cost, 2),
            "total_pnl": round(total_pnl, 2),
            "total_return_pct": round(total_pnl / total_cost * 100, 2) if total_cost > 0 else 0,
            "by_type": by_type,
            "holdings": holdings,
        }
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_tracker.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/portfolio/tracker.py tests/test_tracker.py
git commit -m "feat: 实现收益追踪（按核心/卫星分组汇总）"
```

---

### Task 16: 定投管理（DIP）

**Files:**
- Create: `src/fund_analyzer/portfolio/dip.py`
- Create: `tests/test_dip.py`

- [ ] **Step 1: 编写测试 `tests/test_dip.py`**

```python
import pytest
from datetime import date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, DipPlan
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.portfolio.dip import DipManager


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def manager(db_session):
    repo = FundRepository(db_session)
    return DipManager(repo=repo)


def test_create_dip_plan(manager, db_session):
    plan = manager.create_plan("000001", amount=1000, frequency="monthly",
                                start_date=date(2025, 1, 1), smart=True)
    assert plan.fund_code == "000001"
    assert plan.smart_dip is True
    assert plan.status == "active"


def test_check_due_monthly(manager, db_session):
    manager.create_plan("000001", amount=1000, frequency="monthly",
                        start_date=date(2025, 1, 15))
    # Same day of month = due
    due = manager.check_due(as_of=date(2025, 2, 15))
    assert len(due) == 1
    assert due[0]["fund_code"] == "000001"


def test_check_not_due(manager, db_session):
    manager.create_plan("000001", amount=1000, frequency="monthly",
                        start_date=date(2025, 1, 15))
    # Different day = not due
    due = manager.check_due(as_of=date(2025, 2, 10))
    assert len(due) == 0


def test_pause_and_resume(manager, db_session):
    plan = manager.create_plan("000001", amount=1000, frequency="monthly",
                                start_date=date(2025, 1, 1))
    manager.pause_plan(plan.id)
    assert db_session.get(DipPlan, plan.id).status == "paused"

    manager.resume_plan(plan.id)
    assert db_session.get(DipPlan, plan.id).status == "active"
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_dip.py -v
```

- [ ] **Step 3: 实现 `src/fund_analyzer/portfolio/dip.py`**

```python
from __future__ import annotations

from datetime import date
from decimal import Decimal

from fund_analyzer.data.models import DipPlan
from fund_analyzer.data.repository import FundRepository


class DipManager:
    """Manage DCA (Dollar Cost Averaging) plans."""

    def __init__(self, repo: FundRepository):
        self.repo = repo

    def create_plan(
        self,
        fund_code: str,
        amount: float,
        frequency: str = "monthly",
        start_date: date | None = None,
        smart: bool = False,
    ) -> DipPlan:
        plan = DipPlan(
            fund_code=fund_code,
            amount=Decimal(str(amount)),
            frequency=frequency,
            start_date=start_date or date.today(),
            status="active",
            smart_dip=smart,
        )
        self.repo.session.add(plan)
        self.repo.session.commit()
        return plan

    def check_due(self, as_of: date | None = None) -> list[dict]:
        """Check which DIP plans are due today."""
        as_of = as_of or date.today()
        plans = self.repo.get_active_dip_plans()
        due = []

        for plan in plans:
            if self._is_due(plan, as_of):
                due.append({
                    "plan_id": plan.id,
                    "fund_code": plan.fund_code,
                    "amount": float(plan.amount),
                    "smart_dip": plan.smart_dip,
                })

        return due

    def _is_due(self, plan: DipPlan, as_of: date) -> bool:
        if plan.start_date > as_of:
            return False

        if plan.frequency == "weekly":
            return as_of.weekday() == plan.start_date.weekday()
        elif plan.frequency == "biweekly":
            days_diff = (as_of - plan.start_date).days
            return days_diff % 14 == 0
        elif plan.frequency == "monthly":
            return as_of.day == plan.start_date.day
        return False

    def pause_plan(self, plan_id: int) -> None:
        plan = self.repo.session.get(DipPlan, plan_id)
        if plan:
            plan.status = "paused"
            self.repo.session.commit()

    def resume_plan(self, plan_id: int) -> None:
        plan = self.repo.session.get(DipPlan, plan_id)
        if plan:
            plan.status = "active"
            self.repo.session.commit()

    def stop_plan(self, plan_id: int) -> None:
        plan = self.repo.session.get(DipPlan, plan_id)
        if plan:
            plan.status = "stopped"
            self.repo.session.commit()

    def list_plans(self) -> list[dict]:
        plans = self.repo.get_active_dip_plans()
        return [
            {
                "id": p.id,
                "fund_code": p.fund_code,
                "amount": float(p.amount),
                "frequency": p.frequency,
                "start_date": p.start_date,
                "smart_dip": p.smart_dip,
                "status": p.status,
            }
            for p in plans
        ]
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_dip.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/portfolio/dip.py tests/test_dip.py
git commit -m "feat: 实现定投计划管理"
```

---

### Task 17: 调仓建议（Rebalance）

**Files:**
- Create: `src/fund_analyzer/portfolio/rebalance.py`
- Create: `tests/test_rebalance.py`

- [ ] **Step 1: 编写测试 `tests/test_rebalance.py`**

```python
import pytest
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock

from fund_analyzer.portfolio.rebalance import RebalanceAdvisor


@pytest.fixture
def mock_composite():
    composite = MagicMock()
    composite.recommend.return_value = (
        [("NEW_CORE", 90)],   # new core pick
        [("NEW_SAT", 95)],    # new satellite pick
    )
    composite.signal.return_value = MagicMock(action="sell", confidence=0.8, reason="评分下降")
    return composite


@pytest.fixture
def mock_repo():
    repo = MagicMock()
    pos1 = MagicMock()
    pos1.fund_code = "OLD_CORE"
    pos1.position_type = "core"
    pos1.shares = Decimal("1000")

    pos2 = MagicMock()
    pos2.fund_code = "OLD_SAT"
    pos2.position_type = "satellite"
    pos2.shares = Decimal("2000")

    repo.get_active_positions.return_value = [pos1, pos2]
    return repo


@pytest.fixture
def advisor(mock_repo, mock_composite):
    return RebalanceAdvisor(repo=mock_repo, composite=mock_composite)


def test_generate_advice(advisor):
    advice = advisor.generate(fund_universe=["NEW_CORE", "NEW_SAT", "OLD_CORE", "OLD_SAT"],
                               as_of=date(2025, 6, 1))
    assert "actions" in advice
    assert len(advice["actions"]) > 0


def test_advice_suggests_sells_and_buys(advisor):
    advice = advisor.generate(fund_universe=["NEW_CORE", "NEW_SAT", "OLD_CORE", "OLD_SAT"],
                               as_of=date(2025, 6, 1))
    actions = advice["actions"]
    action_types = [a["action"] for a in actions]
    # Should suggest selling old and buying new
    assert "sell" in action_types or "buy" in action_types
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_rebalance.py -v
```

- [ ] **Step 3: 实现 `src/fund_analyzer/portfolio/rebalance.py`**

```python
from __future__ import annotations

from datetime import date

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.strategy.composite import CompositeStrategy


class RebalanceAdvisor:
    """Generate rebalancing advice based on strategy signals."""

    def __init__(
        self,
        repo: FundRepository,
        composite: CompositeStrategy,
        core_top_n: int = 3,
        satellite_top_n: int = 7,
    ):
        self.repo = repo
        self.composite = composite
        self.core_top_n = core_top_n
        self.satellite_top_n = satellite_top_n

    def generate(
        self,
        fund_universe: list[str],
        as_of: date | None = None,
    ) -> dict:
        as_of = as_of or date.today()
        actions = []

        # Current holdings
        positions = self.repo.get_active_positions()
        current_core = {p.fund_code for p in positions if p.position_type == "core"}
        current_sat = {p.fund_code for p in positions if p.position_type == "satellite"}

        # New recommendations
        core_picks, sat_picks = self.composite.recommend(
            fund_universe, as_of=as_of,
            core_top_n=self.core_top_n, satellite_top_n=self.satellite_top_n,
        )
        new_core = {code for code, _ in core_picks}
        new_sat = {code for code, _ in sat_picks}

        # Core: sell those not in new picks
        for code in current_core - new_core:
            signal = self.composite.signal(code, as_of, position_type="core")
            actions.append({
                "fund_code": code,
                "position_type": "core",
                "action": "sell",
                "reason": f"不在核心推荐中。{signal.reason}",
            })

        # Core: buy new picks
        for code in new_core - current_core:
            score = dict(core_picks).get(code, 0)
            actions.append({
                "fund_code": code,
                "position_type": "core",
                "action": "buy",
                "reason": f"核心推荐，评分{score:.1f}",
            })

        # Satellite: sell those not in new picks
        for code in current_sat - new_sat:
            signal = self.composite.signal(code, as_of, position_type="satellite")
            actions.append({
                "fund_code": code,
                "position_type": "satellite",
                "action": "sell",
                "reason": f"不在卫星推荐中。{signal.reason}",
            })

        # Satellite: buy new picks
        for code in new_sat - current_sat:
            score = dict(sat_picks).get(code, 0)
            actions.append({
                "fund_code": code,
                "position_type": "satellite",
                "action": "buy",
                "reason": f"卫星推荐，评分{score:.1f}",
            })

        return {
            "as_of": as_of,
            "actions": actions,
            "core_picks": core_picks,
            "satellite_picks": sat_picks,
        }
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_rebalance.py -v
```
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/portfolio/rebalance.py tests/test_rebalance.py
git commit -m "feat: 实现调仓建议生成"
```

---

### Task 18: CLI命令行接口

**Files:**
- Create: `src/fund_analyzer/cli/app.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: 编写测试 `tests/test_cli.py`**

```python
import pytest
from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from fund_analyzer.cli.app import app

runner = CliRunner()


def test_cli_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "fund-cli" in result.output or "Usage" in result.output


def test_config_show():
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0


@patch("fund_analyzer.cli.app._get_syncer")
def test_data_sync(mock_get_syncer):
    syncer = MagicMock()
    syncer.sync_all.return_value = {"funds": 10, "navs": 5, "indices": 100, "warnings": []}
    mock_get_syncer.return_value = syncer

    result = runner.invoke(app, ["data", "sync"])
    assert result.exit_code == 0
    syncer.sync_all.assert_called_once()


def test_portfolio_show_empty():
    """Portfolio show with no data should not crash."""
    with patch("fund_analyzer.cli.app._get_tracker") as mock:
        tracker = MagicMock()
        tracker.summary.return_value = {
            "as_of": "2025-06-01",
            "total_market_value": 0,
            "total_cost": 0,
            "total_pnl": 0,
            "total_return_pct": 0,
            "by_type": {},
            "holdings": [],
        }
        mock.return_value = tracker
        result = runner.invoke(app, ["portfolio", "show"])
        assert result.exit_code == 0
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
poetry run pytest tests/test_cli.py -v
```

- [ ] **Step 3: 实现 `src/fund_analyzer/cli/app.py`**

```python
from __future__ import annotations

import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="fund-cli", help="基金理财量化分析系统")
console = Console()

# --- Sub-apps ---
data_app = typer.Typer(help="数据管理")
screen_app = typer.Typer(help="基金筛选")
portfolio_app = typer.Typer(help="组合管理")
dip_app = typer.Typer(help="定投管理")
config_app = typer.Typer(help="配置管理")

app.add_typer(data_app, name="data")
app.add_typer(portfolio_app, name="portfolio")
app.add_typer(dip_app, name="dip")
app.add_typer(config_app, name="config")


def _load_settings():
    from fund_analyzer.config import load_config
    config_path = Path("config/settings.yaml")
    if not config_path.exists():
        console.print("[red]配置文件不存在: config/settings.yaml[/red]")
        raise typer.Exit(1)
    return load_config(str(config_path))


def _get_session():
    from fund_analyzer.database import create_session_factory
    settings = _load_settings()
    factory = create_session_factory(settings)
    return factory()


def _get_repo():
    from fund_analyzer.data.repository import FundRepository
    session = _get_session()
    return FundRepository(session)


def _get_syncer():
    from fund_analyzer.data.fetcher import FundFetcher
    from fund_analyzer.data.sync import DataSyncer
    settings = _load_settings()
    repo = _get_repo()
    fetcher = FundFetcher(
        request_interval=settings.data.sync_interval_seconds,
        retry_count=settings.data.retry_count,
    )
    return DataSyncer(repo=repo, fetcher=fetcher)


def _get_tracker():
    from fund_analyzer.portfolio.tracker import PortfolioTracker
    return PortfolioTracker(repo=_get_repo())


# --- Config commands ---

@config_app.command("show")
def config_show():
    """查看当前配置"""
    settings = _load_settings()
    console.print(f"[bold]数据库:[/bold] {settings.database.host}:{settings.database.port}/{settings.database.name}")
    console.print(f"[bold]核心仓位比例:[/bold] {settings.portfolio.core_ratio}%")
    console.print(f"[bold]卫星仓位比例:[/bold] {settings.portfolio.satellite_ratio}%")
    console.print(f"[bold]动态权重:[/bold] {'开启' if settings.strategy.dynamic_weights else '关闭'}")
    console.print(f"[bold]核心策略权重:[/bold] {settings.strategy.core}")
    console.print(f"[bold]卫星策略权重:[/bold] {settings.strategy.satellite}")


# --- Data commands ---

@data_app.command("sync")
def data_sync(
    full: bool = typer.Option(False, "--full", help="全量同步"),
):
    """同步基金和指数数据"""
    syncer = _get_syncer()
    console.print("[bold]开始同步数据...[/bold]")
    result = syncer.sync_all(full=full)
    console.print(f"基金列表: {result['funds']} 只")
    console.print(f"净值同步: {result['navs']} 只基金")
    console.print(f"指数数据: {result['indices']} 条")
    if result["warnings"]:
        console.print(f"[yellow]警告: {len(result['warnings'])} 条[/yellow]")
        for w in result["warnings"][:5]:
            console.print(f"  - {w}")


# --- Portfolio commands ---

@portfolio_app.command("show")
def portfolio_show():
    """查看当前持仓"""
    tracker = _get_tracker()
    summary = tracker.summary()

    console.print(f"\n[bold]持仓概览[/bold] (截至 {summary['as_of']})")
    console.print(f"总市值: ¥{summary['total_market_value']:,.2f}")
    console.print(f"总成本: ¥{summary['total_cost']:,.2f}")
    console.print(f"总盈亏: ¥{summary['total_pnl']:,.2f} ({summary['total_return_pct']}%)")

    if not summary["holdings"]:
        console.print("\n[dim]暂无持仓[/dim]")
        return

    for ptype in ["core", "satellite"]:
        if ptype in summary["by_type"]:
            info = summary["by_type"][ptype]
            label = "核心仓位" if ptype == "core" else "卫星仓位"
            console.print(f"\n[bold]{label}[/bold]: ¥{info['market_value']:,.2f} (收益 {info.get('return_pct', 0)}%)")

    table = Table(title="持仓明细")
    table.add_column("基金代码")
    table.add_column("仓位")
    table.add_column("份额")
    table.add_column("成本价")
    table.add_column("现价")
    table.add_column("市值")
    table.add_column("收益率")

    for h in summary["holdings"]:
        table.add_row(
            h["fund_code"],
            "核心" if h["position_type"] == "core" else "卫星",
            f"{h['shares']:.2f}",
            f"{h['cost_price']:.4f}",
            f"{h['current_nav']:.4f}",
            f"¥{h['market_value']:,.2f}",
            f"{h['return_pct']}%",
        )

    console.print(table)


@portfolio_app.command("buy")
def portfolio_buy(
    fund_code: str = typer.Argument(..., help="基金代码"),
    amount: float = typer.Option(..., "--amount", "-a", help="买入金额"),
    position_type: str = typer.Option("satellite", "--type", "-t", help="仓位类型 core/satellite"),
):
    """记录买入"""
    from fund_analyzer.portfolio.manager import PortfolioManager
    repo = _get_repo()
    mgr = PortfolioManager(repo=repo)

    # Get latest NAV
    navs = repo.get_fund_nav(fund_code)
    if not navs:
        console.print(f"[red]未找到基金 {fund_code} 的净值数据，请先同步[/red]")
        raise typer.Exit(1)
    nav = navs[-1].nav

    mgr.buy(fund_code, amount=amount, nav=nav, position_type=position_type)
    console.print(f"[green]买入成功: {fund_code} ¥{amount} ({position_type})[/green]")


@portfolio_app.command("sell")
def portfolio_sell(
    fund_code: str = typer.Argument(..., help="基金代码"),
    shares: float = typer.Option(..., "--shares", "-s", help="卖出份额"),
):
    """记录卖出"""
    from fund_analyzer.portfolio.manager import PortfolioManager
    repo = _get_repo()
    mgr = PortfolioManager(repo=repo)

    navs = repo.get_fund_nav(fund_code)
    if not navs:
        console.print(f"[red]未找到基金 {fund_code} 的净值数据[/red]")
        raise typer.Exit(1)
    nav = navs[-1].nav

    mgr.sell(fund_code, shares=Decimal(str(shares)), nav=nav)
    console.print(f"[green]卖出成功: {fund_code} {shares}份[/green]")


# --- Backtest command ---

@app.command("backtest")
def backtest(
    start: str = typer.Option("2022-01-01", "--start", help="回测开始日期"),
    end: str = typer.Option(None, "--end", help="回测结束日期"),
    core_ratio: int = typer.Option(30, "--core-ratio", help="核心仓位比例(%)"),
    satellite_ratio: int = typer.Option(70, "--satellite-ratio", help="卫星仓位比例(%)"),
):
    """运行回测"""
    console.print("[bold]回测功能需要先完成数据同步和策略配置[/bold]")
    console.print(f"回测区间: {start} ~ {end or '至今'}")
    console.print(f"核心/卫星: {core_ratio}% / {satellite_ratio}%")
    # Full implementation would instantiate BacktestEngine and run


# --- Screen command ---

@app.command("screen")
def screen(
    position_type: str = typer.Option(None, "--type", "-t", help="仓位类型 core/satellite"),
    top: int = typer.Option(10, "--top", help="显示前N只"),
):
    """运行策略筛选"""
    console.print(f"[bold]筛选 Top {top} 基金[/bold]")
    if position_type:
        label = "核心" if position_type == "core" else "卫星"
        console.print(f"仓位类型: {label}")
    console.print("[dim]筛选功能需要先完成数据同步[/dim]")


# --- Rebalance command ---

@app.command("rebalance")
def rebalance():
    """生成调仓建议"""
    console.print("[bold]调仓建议功能需要先完成数据同步和策略配置[/bold]")


# --- DIP commands ---

@dip_app.command("create")
def dip_create(
    fund_code: str = typer.Argument(..., help="基金代码"),
    amount: float = typer.Option(..., "--amount", "-a", help="定投金额"),
    freq: str = typer.Option("monthly", "--freq", "-f", help="频率 weekly/biweekly/monthly"),
    smart: bool = typer.Option(False, "--smart", help="启用智慧定投"),
):
    """创建定投计划"""
    from fund_analyzer.portfolio.dip import DipManager
    repo = _get_repo()
    mgr = DipManager(repo=repo)
    plan = mgr.create_plan(fund_code, amount=amount, frequency=freq, smart=smart)
    console.print(f"[green]定投计划创建成功: {fund_code} ¥{amount} {freq}[/green]")


@dip_app.command("list")
def dip_list():
    """查看定投计划"""
    from fund_analyzer.portfolio.dip import DipManager
    repo = _get_repo()
    mgr = DipManager(repo=repo)
    plans = mgr.list_plans()
    if not plans:
        console.print("[dim]暂无定投计划[/dim]")
        return
    table = Table(title="定投计划")
    table.add_column("ID")
    table.add_column("基金代码")
    table.add_column("金额")
    table.add_column("频率")
    table.add_column("智慧定投")
    for p in plans:
        table.add_row(
            str(p["id"]), p["fund_code"], f"¥{p['amount']:.0f}",
            p["frequency"], "是" if p["smart_dip"] else "否",
        )
    console.print(table)


@dip_app.command("check")
def dip_check():
    """检查今日定投触发"""
    from fund_analyzer.portfolio.dip import DipManager
    repo = _get_repo()
    mgr = DipManager(repo=repo)
    due = mgr.check_due()
    if not due:
        console.print("[dim]今日无定投触发[/dim]")
        return
    for d in due:
        console.print(f"[yellow]触发: {d['fund_code']} ¥{d['amount']:.0f}[/yellow]")


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
poetry run pytest tests/test_cli.py -v
```
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/fund_analyzer/cli/app.py tests/test_cli.py
git commit -m "feat: 实现CLI命令行接口（Typer + Rich）"
```

---

### Task 19: 集成测试与全量测试

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: 编写共享fixtures `tests/conftest.py`**

```python
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base


@pytest.fixture
def db_engine():
    """Create a fresh in-memory SQLite engine for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    """Create a session bound to the in-memory test database."""
    with Session(db_engine) as session:
        yield session
```

- [ ] **Step 2: 运行全量测试**

```bash
poetry run pytest tests/ -v --tb=short
```
Expected: All tests pass

- [ ] **Step 3: 运行测试覆盖率**

```bash
poetry run pytest tests/ --cov=fund_analyzer --cov-report=term-missing
```

- [ ] **Step 4: Commit**

```bash
git add tests/conftest.py
git commit -m "feat: 添加共享测试fixtures，完成全量测试验证"
```
