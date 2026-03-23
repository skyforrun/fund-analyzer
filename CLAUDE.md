# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Run Commands

```bash
# 依赖管理
poetry install              # 安装依赖
poetry lock                 # 更新 lock 文件

# 数据库
docker-compose up -d        # 启动 PostgreSQL 16 (localhost:5432, user/pass: postgres/postgres)

# 测试
poetry run pytest                                              # 运行全部测试 (363 cases)
poetry run pytest tests/test_factor.py                         # 运行单个测试文件
poetry run pytest tests/test_factor.py::test_score_batch       # 运行单个测试
poetry run pytest --cov=fund_analyzer --cov-report=term-missing  # 覆盖率报告

# CLI
poetry run fund-cli config show
poetry run fund-cli data sync
poetry run fund-cli portfolio show

# Web UI (Streamlit)
poetry run streamlit run src/fund_analyzer/ui/app.py
```

## Architecture

核心-卫星策略的基金量化分析系统。数据流向：**数据采集 → 策略评分 → 回测验证 → 组合管理**。

### 模块依赖关系

```
config.py / database.py          ← 全局配置与DB连接
        ↓
data/ (models → repository → fetcher → sync)   ← ORM模型、数据访问、akshare采集、同步调度
        ↓
strategy/ (factor/momentum/rotation/global_alloc → composite)  ← 4策略独立评分 → 综合加权
        ↓
backtest/ (engine + metrics)     ← 分仓回测、绩效指标计算
portfolio/ (manager/tracker/dip/rebalance)  ← 持仓交易、收益追踪、定投、调仓建议
        ↓
cli/app.py                       ← Typer CLI (4个命令组: data/portfolio/dip/config)
ui/app.py                        ← Streamlit Web UI (7页面)
```

### 策略双通道权重

- **核心仓** (30%): FactorStrategy(70%) + GlobalAllocStrategy(30%)
- **卫星仓** (70%): MomentumStrategy(40%) + RotationStrategy(35%) + GlobalAllocStrategy(25%)

权重在 `config/settings.yaml` 的 `strategy.core` / `strategy.satellite` 中配置。`CompositeStrategy` 负责加权聚合，不继承 `BaseStrategy`。

### 配置加载

`config/settings.yaml` → dataclass 层级映射，环境变量 `FUND_DB_PASSWORD` 可覆盖数据库密码。所有 dataclass 有完整默认值，可无配置文件运行。

### 数据库

9张表定义在 `data/models.py`，使用 SQLAlchemy 2.0 Mapped 注解。无 Alembic 迁移，表通过 `Base.metadata.create_all()` 创建。`FundRepository` 是统一数据访问层，所有业务模块通过它操作数据库。

### 测试

pytest，18个测试模块覆盖所有业务层。测试中广泛使用 `monkeypatch` mock 外部依赖（akshare、数据库），`tmp_path` 用于临时文件。pythonpath 配置为 `src`。
