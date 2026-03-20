# Fund Analyzer — 基金理财量化分析系统

个人基金理财量化分析系统，采用**核心+卫星**配置策略，通过多策略组合筛选基金，目标年组合总收益率 > 10%。

## 投资理念

- **核心仓位（30%）**：稳健底仓，长期持有，配置美股QDII和A股宽基
- **卫星仓位（70%）**：进攻仓位，集中少数强势板块，追求高弹性收益
- 接受单只基金亏损，但组合整体保持正收益

## 功能特性

- **多策略筛选**：因子筛选、动量策略、行业轮动、全球配置，综合评分
- **回测引擎**：核心/卫星分仓回测，含交易费用，输出完整绩效指标
- **组合管理**：持仓记录、收益追踪、定投计划、调仓建议
- **CLI工具**：命令行操作，数据同步/筛选/回测/持仓管理一站式完成

## 技术栈

- Python 3.11+ / Poetry
- SQLAlchemy 2.0 + PostgreSQL
- akshare（免费数据源）
- Typer + Rich（CLI）
- pandas / numpy / matplotlib

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/skyforrun/fund-analyzer.git
cd fund-analyzer
poetry install
```

### 2. 启动数据库

```bash
docker-compose up -d
```

默认连接：`localhost:5432`，数据库 `fund_analyzer`，用户/密码 `postgres/postgres`。

### 3. 同步数据

```bash
poetry run fund-cli data sync
```

### 4. 常用命令

```bash
# 查看配置
poetry run fund-cli config show

# 基金筛选
poetry run fund-cli screen --top 20
poetry run fund-cli screen --type core        # 仅核心仓位候选
poetry run fund-cli screen --type satellite   # 仅卫星仓位候选

# 回测
poetry run fund-cli backtest --start 2022-01-01 --end 2025-12-31

# 查看持仓
poetry run fund-cli portfolio show

# 买入/卖出
poetry run fund-cli portfolio buy 000001 --amount 10000 --type satellite
poetry run fund-cli portfolio sell 000001 --shares 1000

# 定投管理
poetry run fund-cli dip create 000001 --amount 1000 --freq monthly --smart
poetry run fund-cli dip list
poetry run fund-cli dip check

# 调仓建议
poetry run fund-cli rebalance
```

## 项目结构

```
src/fund_analyzer/
├── config.py              # 配置加载
├── database.py            # 数据库连接
├── data/
│   ├── models.py          # ORM模型（9张表）
│   ├── repository.py      # 数据访问层
│   ├── fetcher.py         # akshare数据采集
│   └── sync.py            # 数据同步调度
├── strategy/
│   ├── base.py            # 策略基类与Signal
│   ├── factor.py          # 因子筛选（核心仓位）
│   ├── momentum.py        # 动量策略（卫星仓位）
│   ├── rotation.py        # 行业轮动
│   ├── global_alloc.py    # 全球配置
│   └── composite.py       # 综合评分（双通道）
├── backtest/
│   ├── engine.py          # 回测引擎
│   └── metrics.py         # 绩效指标（夏普/最大回撤等）
├── portfolio/
│   ├── manager.py         # 持仓管理
│   ├── tracker.py         # 收益追踪
│   ├── dip.py             # 定投计划
│   └── rebalance.py       # 调仓建议
└── cli/
    └── app.py             # CLI入口
```

## 策略说明

### 核心仓位评分权重

| 策略 | 权重 |
|------|------|
| 因子筛选 | 70% |
| 全球配置 | 30% |

### 卫星仓位评分权重

| 策略 | 权重 |
|------|------|
| 动量策略 | 40% |
| 行业轮动 | 35% |
| 全球配置 | 25% |

### 因子筛选维度

夏普比率（25%）、收益率（20%）、最大回撤（10%）、波动率（5%）、Calmar/Sortino比率（20%）、基金经理任期（10%）、基金规模（10%）

## 测试

```bash
# 运行全部测试
poetry run pytest

# 带覆盖率
poetry run pytest --cov=fund_analyzer --cov-report=term-missing

# 363个测试，覆盖率88%
```

## 配置文件

配置位于 `config/settings.yaml`，支持修改：

- 数据库连接（或通过 `FUND_DB_PASSWORD` 环境变量设置密码）
- 核心/卫星仓位比例
- 策略权重
- 回测参数（初始资金、调仓频率、交易费率）
- 智慧定投阈值

## License

MIT
