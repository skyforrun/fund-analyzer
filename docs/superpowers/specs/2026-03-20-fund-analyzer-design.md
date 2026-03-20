# 基金理财量化分析系统 — 设计文档（v2）

## 1. 项目概述

### 1.1 目标
构建个人基金理财量化分析系统，采用**核心+卫星**配置策略，通过少数板块精选+全球化配置（以美股QDII为主），实现**年组合总收益率 > 10%**，同时追求卫星仓位中单只基金 50%+ 的高弹性收益。

### 1.2 投资理念
- **核心仓位（30%）**：稳健底仓，长期持有，提供基础收益和抗跌能力
- **卫星仓位（70%）**：进攻仓位，集中少数强势板块，追求高弹性收益
- 接受单只基金亏损，但要求组合整体年收益率 > 10%
- 偏向长期持有，非频繁交易

### 1.3 核心功能
- **基金筛选推荐**：多策略（因子筛选、动量、行业轮动、全球配置）综合打分，区分核心/卫星仓位推荐
- **投资组合管理**：持仓记录、定投计划、调仓信号、收益追踪
- **回测验证**：历史数据回测策略有效性，验证组合能否达到10%+年化目标

### 1.4 约束条件
- 交互形式：先CLI，后期加Web界面
- 数据来源：akshare等免费API
- 数据存储：PostgreSQL
- 用户背景：有经验的基金投资者，已持有组合
- 技术栈：Python 3.11+

---

## 2. 系统架构

### 2.1 模块划分

```
数据采集 → 数据存储 → 策略引擎 → 回测引擎 → 组合管理
  (akshare)  (PostgreSQL)  (多策略)    (历史验证)   (持仓/调仓)
                                            ↓
                                       CLI展示层
                                   (报表/图表/信号)
```

### 2.2 项目结构

```
finance/
├── pyproject.toml
├── config/
│   └── settings.yaml          # 数据库配置、策略参数等
├── src/
│   └── fund_analyzer/
│       ├── __init__.py
│       ├── data/              # 数据采集与存储
│       │   ├── __init__.py
│       │   ├── fetcher.py     # akshare数据拉取
│       │   ├── models.py      # SQLAlchemy ORM模型
│       │   └── sync.py        # 数据同步调度
│       ├── strategy/          # 策略引擎
│       │   ├── __init__.py
│       │   ├── base.py        # 策略基类与Signal定义
│       │   ├── factor.py      # 因子筛选策略（核心仓位）
│       │   ├── momentum.py    # 动量策略（卫星仓位）
│       │   ├── rotation.py    # 行业轮动策略（卫星仓位）
│       │   ├── global_alloc.py # 全球配置策略
│       │   └── composite.py   # 多策略综合打分（含动态权重）
│       ├── backtest/          # 回测引擎
│       │   ├── __init__.py
│       │   ├── engine.py      # 回测核心
│       │   └── metrics.py     # 绩效指标计算
│       ├── portfolio/         # 组合管理
│       │   ├── __init__.py
│       │   ├── manager.py     # 持仓管理
│       │   ├── rebalance.py   # 调仓逻辑
│       │   └── tracker.py     # 收益追踪
│       └── cli/               # 命令行接口
│           ├── __init__.py
│           └── app.py         # Typer CLI
├── tests/
└── docs/
```

### 2.3 技术栈
- **语言**：Python 3.11+
- **ORM**：SQLAlchemy 2.0
- **数据库**：PostgreSQL
- **数据源**：akshare
- **数据处理**：pandas, numpy
- **CLI框架**：Typer
- **可视化**：matplotlib / plotly
- **依赖管理**：Poetry
- **配置管理**：PyYAML（settings.yaml）

### 2.4 模块间依赖关系

```
cli → composite(策略引擎) → factor / momentum / rotation / global_alloc
cli → backtest(回测引擎) → composite(策略引擎)
cli → portfolio(组合管理)
策略引擎 → data(数据层，通过Repository模式访问)
回测引擎 → data(数据层)
组合管理 → data(数据层)
```

所有模块通过数据层的 Repository 模式访问数据库，策略引擎不直接执行SQL查询。

---

## 3. 数据模型

### 3.1 fund_info — 基金基本信息

| 字段 | 类型 | 说明 |
|------|------|------|
| fund_code | VARCHAR(10) PK | 基金代码 |
| fund_name | VARCHAR(100) | 基金名称 |
| fund_type | VARCHAR(20) | 基金类型（股票型/混合型/指数型/QDII等） |
| market | VARCHAR(10) | 投向市场（a_share/us/hk/global） |
| manager | VARCHAR(50) | 基金经理 |
| manager_start_date | DATE | 当前经理任职起始日期 |
| company | VARCHAR(50) | 基金公司 |
| inception_date | DATE | 成立日期 |
| fund_size | DECIMAL(14,2) | 基金规模（亿元） |
| benchmark | VARCHAR(200) | 业绩比较基准 |
| updated_at | TIMESTAMP | 最后更新时间 |

### 3.2 fund_nav — 基金净值历史

| 字段 | 类型 | 说明 |
|------|------|------|
| fund_code | VARCHAR(10) PK | 基金代码 |
| date | DATE PK | 日期 |
| nav | DECIMAL(10,4) | 单位净值 |
| acc_nav | DECIMAL(10,4) | 累计净值 |
| daily_return | DECIMAL(10,6) | 日收益率 |

索引：联合主键 (fund_code, date) 已隐含索引。

### 3.3 index_quote — 指数行情

| 字段 | 类型 | 说明 |
|------|------|------|
| index_code | VARCHAR(10) PK | 指数代码 |
| date | DATE PK | 日期 |
| close | DECIMAL(10,4) | 收盘价 |
| daily_return | DECIMAL(10,6) | 日收益率 |

存储的指数包括：科创50（000688）、纳斯达克100、标普500、申万一级行业指数等。

### 3.4 fund_holding — 基金持仓（季报）

| 字段 | 类型 | 说明 |
|------|------|------|
| fund_code | VARCHAR(10) PK | 基金代码 |
| report_date | DATE PK | 报告日期 |
| stock_code | VARCHAR(10) PK | 股票代码 |
| stock_name | VARCHAR(50) | 股票名称 |
| industry | VARCHAR(30) | 所属行业（申万一级） |
| weight | DECIMAL(6,2) | 持仓权重（百分比，如 9.85 表示 9.85%） |

### 3.5 industry_mapping — 股票行业映射

| 字段 | 类型 | 说明 |
|------|------|------|
| stock_code | VARCHAR(10) PK | 股票代码 |
| stock_name | VARCHAR(50) | 股票名称 |
| industry_l1 | VARCHAR(30) | 申万一级行业 |
| industry_l2 | VARCHAR(30) | 申万二级行业 |
| updated_at | TIMESTAMP | 最后更新时间 |

### 3.6 portfolio_position — 用户持仓

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 主键 |
| fund_code | VARCHAR(10) | 基金代码 |
| position_type | VARCHAR(10) | 仓位类型（core/satellite） |
| buy_date | DATE | 买入日期 |
| shares | DECIMAL(12,4) | 持有份额 |
| cost_price | DECIMAL(10,4) | 成本价（净值） |
| status | VARCHAR(10) | 状态（holding/cleared） |
| sell_date | DATE | 清仓日期（可为空） |
| sell_price | DECIMAL(10,4) | 卖出净值（可为空） |

### 3.7 portfolio_transaction — 交易记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 主键 |
| fund_code | VARCHAR(10) | 基金代码 |
| date | DATE | 交易日期 |
| type | VARCHAR(10) | 交易类型（buy/sell/dip） |
| amount | DECIMAL(12,2) | 交易金额 |
| shares | DECIMAL(12,4) | 交易份额 |
| nav | DECIMAL(10,4) | 交易净值 |
| position_type | VARCHAR(10) | 仓位类型（core/satellite） |
| dip_plan_id | INTEGER | 关联定投计划ID（可为空） |

索引：(fund_code, date), (dip_plan_id)

### 3.8 strategy_signal — 策略信号记录

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 主键 |
| strategy_name | VARCHAR(30) | 策略名称 |
| date | DATE | 信号日期 |
| fund_code | VARCHAR(10) | 基金代码 |
| score | DECIMAL(6,2) | 策略评分（0-100） |
| action | VARCHAR(10) | 信号（buy/sell/hold） |
| position_type | VARCHAR(10) | 建议仓位类型（core/satellite） |

索引：(date, fund_code), (strategy_name, date)

### 3.9 dip_plan — 定投计划

| 字段 | 类型 | 说明 |
|------|------|------|
| id | SERIAL PK | 主键 |
| fund_code | VARCHAR(10) | 基金代码 |
| amount | DECIMAL(12,2) | 定投金额 |
| frequency | VARCHAR(10) | 频率（weekly/biweekly/monthly） |
| start_date | DATE | 开始日期 |
| status | VARCHAR(10) | 状态（active/paused/stopped） |
| smart_dip | BOOLEAN | 是否启用智慧定投 |

---

## 4. 数据采集

### 4.1 数据源

通过 akshare 获取以下数据：
- 全市场开放式基金列表与基本信息（含QDII基金）
- 基金历史净值（日频），使用 `fund_open_fund_info_em` 等接口
- 指数日线行情：科创50（000688，使用 `stock_zh_index_daily_em`）、纳斯达克100、标普500、申万一级行业指数
- 基金季报持仓数据
- 股票行业分类（申万行业映射）

### 4.2 候选基金池预筛选

在策略评分之前，先过滤基金池：
- 成立满2年
- 基金规模 > 1亿元
- 排除货币基金、纯债基金
- 保留：股票型、混合型、指数型、QDII、LOF、ETF联接基金

### 4.3 同步策略
- **增量同步**：每日收盘后同步当日数据（默认模式）
- **全量同步**：重新拉取全部历史数据（用于初始化或数据修复）
- **触发方式**：CLI手动触发 或 配置cron定时任务
- **请求限流**：每次API请求间隔 0.5 秒，避免被限流
- **错误处理**：请求失败时自动重试3次（指数退避），失败记入日志，不中断整体同步
- **数据校验**：净值跳变检测（单日涨跌幅 > 15% 标记异常）、缺失日期检测
- **QDII净值延迟**：QDII基金净值通常延迟1-2个交易日公布，系统使用最新可用净值，回测中做日期对齐（以净值公布日为准）
- **收益计算**：统一使用累计净值（acc_nav）计算收益，已包含分红再投资
- **交易费率**：回测使用统一的默认费率（配置文件中设定），不区分A/C类

---

## 5. 策略引擎

### 5.1 策略基类与数据类型

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class Signal:
    action: Literal["buy", "sell", "hold"]
    confidence: float  # 0-1，信号置信度
    reason: str  # 信号理由

class BaseStrategy:
    def score_batch(self, fund_codes: list[str], date: date) -> dict[str, float]:
        """对一批基金打分（0-100），支持横向比较"""
        ...

    def signal(self, fund_code: str, date: date, universe: list[str] | None = None) -> Signal:
        """返回买入/卖出/持有信号，universe为可选的全市场基金列表（用于排名）"""
        ...

# 评分到信号的映射规则（由 CompositeStrategy 统一执行）：
# - score >= 80: buy（强烈推荐买入）
# - 60 <= score < 80: hold（持有/观望）
# - score < 60: sell（建议卖出/回避）
# 阈值可在 settings.yaml 中配置
```

### 5.2 因子筛选策略（FactorStrategy）— 核心仓位选基

侧重长期稳健指标，用于筛选核心仓位基金：
- **收益因子**：近1年/3年年化收益率
- **风险因子**：最大回撤、年化波动率
- **风险调整因子**：夏普比率、Calmar比率、Sortino比率（核心权重最高）
- **基金经理因子**：任职年限（基于 `manager_start_date` 计算）
- **规模因子**：基金规模 2-200亿 为宜，过大/过小扣分

各因子加权求和得到综合评分，权重可在 `settings.yaml` 中调整。

### 5.3 动量策略（MomentumStrategy）— 卫星仓位选基

侧重短中期爆发力，用于筛选卫星仓位基金：
- 计算近20/60/120日收益动量
- 用相对强度排名（在同类基金中的百分位，通过 `score_batch` 实现横向比较）
- 短中长期动量加权组合
- 动量反转检测：短期动量急剧下降时发出预警

### 5.4 行业轮动策略（RotationStrategy）— 发现强势板块

辅助卫星仓位调整，发现新的进攻方向：
- 基于基金季报持仓 + `industry_mapping` 表，分析基金实际的行业暴露
- 跟踪申万一级行业指数的相对强弱（数据来自 `index_quote` 表）
- 偏好当前配置在强势行业的基金
- 行业动量窗口：60日

### 5.5 全球配置策略（GlobalAllocStrategy）— 市场分配

分析不同市场的相对强弱，建议全球配置比例：
- 跟踪A股（科创50/沪深300）与美股（纳指/标普500）的相对趋势
- 计算各市场的风险收益比
- 输出建议的A股/美股配置比例
- 当美股QDII处于强势时，提高QDII基金的推荐权重

### 5.6 综合评分（CompositeStrategy）

分核心和卫星两个评分通道：

**核心仓位评分**：
- 因子筛选策略权重高（70%）、全球配置（30%）
- 偏好稳健、长期业绩好的基金

**卫星仓位评分**：
- 动量策略（40%）、行业轮动（35%）、全球配置（25%）
- 偏好高弹性、当前趋势强势的基金

**动态自适应权重**（可选开启）：
- 每月回看过去3-6个月各策略推荐基金的实际收益
- 用指数加权移动平均，近期表现权重更大
- 单策略权重上下限：15%-60%，防止过度集中
- 冷启动期（不足3个月数据）使用默认静态权重
- 在配置中通过 `dynamic_weights: true` 开启

---

## 6. 回测引擎

### 6.1 回测流程

```
选择策略 → 设定回测区间 → 模拟历史信号 → 模拟交易 → 计算绩效 → 对比基准
```

### 6.2 回测参数
- 回测区间：自定义起止日期
- 初始资金：可配置
- 核心/卫星仓位比例：默认 30%/70%
- 调仓频率：核心仓位季度、卫星仓位月度
- 交易成本：申购费率、赎回费率（按实际费率）
- 基准：可选科创50（000688）或自定义
- 组合基金数量：核心仓位 Top 3，卫星仓位 Top 7（默认，可配置）
- 资金分配：核心仓位等权，卫星仓位按评分加权

### 6.3 绩效指标
- 年化收益率
- 年化波动率
- 最大回撤
- 夏普比率 / Sortino比率 / Calmar比率
- 超额收益（Alpha，vs 基准）
- 信息比率
- 胜率（月度正收益的比例）
- 单只基金最高年收益率（验证50%+目标）
- 核心/卫星仓位分别的收益贡献

### 6.4 输出
- 净值曲线图（组合 vs 基准）
- 回撤曲线图
- 月度收益热力图
- 绩效指标对比表
- 核心/卫星仓位收益归因

---

## 7. 组合管理

### 7.1 持仓管理
- 记录买入/卖出交易，自动计算持仓成本、收益率
- 区分核心仓位和卫星仓位（`position_type` 字段）
- 持仓概览：当前持有基金、市值、收益率、占比，按核心/卫星分组展示

### 7.2 定投计划
- 设定定投基金、频率（周/双周/月）、金额
- 系统每日检查是否触发定投，生成提醒（不自动执行真实交易）
- 支持智慧定投：基于指数PE百分位判断估值高低
  - PE百分位 < 30%（低估）：定投金额 × 1.5
  - PE百分位 30%-70%（正常）：正常定投
  - PE百分位 > 70%（高估）：定投金额 × 0.5

### 7.3 调仓信号
- 核心仓位：季度检视，非必要不调仓
- 卫星仓位：月度检视，跟踪板块趋势变化
- 输出：建议买入/卖出/加仓/减仓的基金、建议仓位类型、理由
- 用户手动确认执行后，录入实际交易

### 7.4 收益追踪
- 每日自动更新持仓市值
- 对比基准的超额收益
- 按核心/卫星仓位分别追踪
- 按周/月/年维度汇总

---

## 8. CLI命令设计

使用 Typer 框架，命令结构如下：

```bash
# 数据管理
fund-cli data sync              # 增量同步最新数据
fund-cli data sync --full       # 全量重新同步

# 基金筛选
fund-cli screen                 # 运行策略筛选，输出Top基金排名（核心+卫星）
fund-cli screen --type core     # 仅筛选核心仓位候选
fund-cli screen --type satellite # 仅筛选卫星仓位候选
fund-cli screen --strategy momentum  # 仅用动量策略筛选
fund-cli screen --top 20        # 输出前20只

# 回测
fund-cli backtest --start 2022-01-01 --end 2025-12-31
fund-cli backtest --core-ratio 30 --satellite-ratio 70

# 组合管理
fund-cli portfolio show         # 当前持仓概览（核心/卫星分组）
fund-cli portfolio buy 000001 --amount 10000 --type satellite  # 记录买入（卫星仓位）
fund-cli portfolio sell 000001 --shares 1000  # 记录卖出

# 定投
fund-cli dip create 000001 --amount 1000 --freq monthly --smart
fund-cli dip list               # 查看定投计划
fund-cli dip check              # 检查今日是否有定投触发

# 调仓建议
fund-cli rebalance              # 生成调仓建议（核心+卫星）

# 配置
fund-cli config show            # 查看当前配置
fund-cli config set-weights --core-factor 70 --core-global 30
fund-cli config set-weights --sat-momentum 40 --sat-rotation 35 --sat-global 25
```

---

## 9. 配置文件示例

```yaml
# config/settings.yaml

database:
  host: localhost
  port: 5432
  name: fund_analyzer
  user: postgres
  password: ""  # 建议使用环境变量 FUND_DB_PASSWORD

data:
  sync_interval_seconds: 0.5  # API请求间隔
  retry_count: 3
  fund_pool:
    min_inception_years: 2
    min_size_billion: 1
    exclude_types: ["货币型", "纯债型"]

portfolio:
  core_ratio: 30       # 核心仓位比例(%)
  satellite_ratio: 70   # 卫星仓位比例(%)

strategy:
  dynamic_weights: false  # 是否启用动态权重
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
  buy_fee_rate: 0.0015    # 申购费率 0.15%
  sell_fee_rate: 0.005     # 赎回费率 0.5%

smart_dip:
  low_pe_percentile: 30    # PE百分位低估阈值
  high_pe_percentile: 70   # PE百分位高估阈值
  low_multiplier: 1.5      # 低估时定投金额倍数
  high_multiplier: 0.5     # 高估时定投金额倍数
```

---

## 10. 成功标准

1. 回测中，组合在多个滚动3年窗口内年化收益率 > 10% 的概率 > 60%
2. 回测中，卫星仓位历史上存在单只基金年收益 > 50% 的情况
3. 组合在任意滚动1年窗口中总亏损概率 < 20%
4. 调仓建议可执行、可追踪，用户能基于系统信号做出投资决策
5. CLI操作流畅，核心操作（筛选、回测、查看持仓）响应在秒级
