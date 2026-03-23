# 基金分析系统增强功能设计文档

**日期**: 2026-03-20
**范围**: 6个新功能，按优先级逐功能串行实现
**方案**: 方案A — 逐功能串行实现，每个功能贯穿数据层→业务层→UI层

---

## 功能一：实时估值（双数据源）

### 需求
盘中提供基金估算净值和涨跌幅，支持 akshare 和天天基金两个数据源，akshare 为主、天天基金为回退。

### 数据层

**新增表 `fund_estimate`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| fund_code | String(20), PK | 基金代码 |
| estimate_date | Date, PK | 估值日期 |
| estimate_nav | Numeric(12,4) | 估算净值 |
| estimate_return | Numeric(8,4) | 估算涨跌幅(%) |
| estimate_time | String(10) | 估值时间点，格式 HH:MM，如"15:00" |
| source | String(20) | 数据源："akshare" 或 "eastmoney" |
| updated_at | DateTime | 更新时间 |

**FundFetcher 新增方法：**
- `fetch_fund_estimate(fund_code: str) -> dict | None` — 主用 `ak.fund_open_fund_info_em()`，失败回退天天基金爬虫
- `fetch_fund_estimate_batch(fund_codes: list[str]) -> list[dict]` — 批量获取，带限速

**FundRepository 新增方法：**
- `upsert_estimate(fund_code, date, nav, return_, time, source)`
- `get_latest_estimates(fund_codes: list[str]) -> list[FundEstimate]`

### 配置层

`config.py` 新增：
```python
@dataclass
class EstimateConfig:
    primary_source: str = "akshare"
    fallback_enabled: bool = True
```

`Settings` 新增 `estimate: EstimateConfig` 字段。

### UI层
- 仪表盘和筛选页面的基金列表中加入估值列（估算净值、估算涨跌幅）
- 盘中（9:30-15:00）显示估值数据，收盘后显示实际净值
- 使用 `st.metric` 卡片展示涨跌幅，红涨绿跌配色
- **刷新机制**：自选基金页面提供"刷新估值"按钮手动触发，不做自动轮询（Streamlit 架构限制）

> **索引说明**：`fund_estimate` 以 `(fund_code, estimate_date)` 为复合主键，天然为 `get_latest_estimates` 的查询提供索引覆盖。

---

## 功能二：自选关注列表

### 需求
用户可收藏基金到自选列表，支持分组管理和备注。

### 数据层

**新增表 `fund_watchlist`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| fund_code | String(20) | 基金代码 |
| fund_name | String(100) | 基金名称（冗余，查询时JOIN fund_info 可获取最新名称） |
| group_name | String(50) | 分组标签，默认"默认" |
| notes | String(500) | 备注 |
| added_at | DateTime | 添加时间 |

**唯一约束**：`(fund_code, group_name)` — 同一只基金在同一分组中不可重复添加。

**FundRepository 新增方法：**
- `add_to_watchlist(fund_code, fund_name, group_name="默认", notes="")`
- `remove_from_watchlist(fund_code, group_name=None)` — `group_name=None` 时删除该基金在所有分组的记录
- `get_watchlist(group_name=None) -> list[FundWatchlist]`
- `get_watchlist_groups() -> list[str]`

### UI层
- 侧边栏新增「⭐ 自选基金」页面
  - 自选列表表格：代码、名称、最新净值、日涨跌、估值、分组
  - 分组筛选下拉框
  - 添加基金表单（输入代码，自动填充名称）
  - 每行一键移除按钮
- 筛选页面每只基金旁增加"加入自选"按钮

### CLI层
- `fund-cli watchlist add <code> [--group 默认]`
- `fund-cli watchlist list [--group]`
- `fund-cli watchlist remove <code>`

---

## 功能三：消息提醒（微信推送）

### 需求
通过企业微信机器人Webhook推送消息，支持定投提醒、大跌预警、调仓提醒。

### 数据层

**新增表 `notification_config`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| channel | String(20) | 通知渠道，固定"wechat" |
| webhook_url | String(500) | Webhook地址 |
| enabled | Boolean | 是否启用 |
| updated_at | DateTime | 更新时间 |

**新增表 `notification_rule`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| rule_type | String(30) | 规则类型：dip_reminder / drop_alert / rebalance_alert |
| params | JSONB | 规则参数，如 {"threshold": -3} |
| enabled | Boolean | 是否启用 |

> **渠道关联说明**：当前版本仅支持单渠道（微信），所有规则默认使用唯一启用的 `notification_config` 记录。未来若扩展多渠道，可在 `notification_rule` 中增加 `config_id` 外键。

### 业务层

**新增 `notification/` 模块：**

`sender.py` — `WeChatSender` 类：
- `__init__(webhook_url: str)`
- `send(title: str, content: str)` — 发送Markdown格式消息到企业微信
- `test()` — 发送测试消息

`checker.py` — `NotificationChecker` 类：
- `__init__(repo: FundRepository, sender: WeChatSender)`
- `check_dip_due()` — 检查今日到期的定投计划，推送提醒
- `check_drop_alert(threshold: float)` — 检查自选基金中跌幅超阈值的，推送预警
- `check_rebalance()` — 检查是否到调仓日，推送提醒

> **错误处理**：`WeChatSender.send()` 失败时记录 WARNING 日志并跳过，不重试。企业微信Webhook有每分钟20条限制，批量发送时需合并为单条消息。

### UI层
- 「系统配置」页面新增"通知设置"区域：
  - Webhook URL 输入框
  - 测试发送按钮
  - 三种提醒规则的开关和参数配置（如跌幅阈值）

### CLI层
- `fund-cli notify test` — 发送测试消息
- `fund-cli notify check` — 手动触发所有规则检查（可配合系统cron定时执行）

---

## 功能四：分红数据

### 需求
采集基金历史分红记录，收益计算统一使用累计净值。

### 数据层

**新增表 `fund_dividend`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| fund_code | String(20), PK | 基金代码 |
| ex_date | Date, PK | 除息日（复合主键） |
| dividend_per_unit | Numeric(10,4) | 每份分红金额 |
| record_date | Date | 权益登记日 |
| pay_date | Date | 发放日 |
| dividend_type | String(20) | "现金分红" 或 "红利再投" |

**FundFetcher 新增：**
- `fetch_fund_dividend(fund_code: str) -> pd.DataFrame | None` — 调用 `ak.fund_open_fund_dividend_em()`

**FundRepository 新增：**
- `upsert_dividends(fund_code: str, dividends: list[dict])` — 与现有 upsert 方法保持一致，接收 dict 列表
- `get_dividends(fund_code: str, start_date: date | None = None) -> list[FundDividend]`

### 业务层
- 收益计算统一使用 `acc_nav`（累计净值），已自然包含分红再投效果
- 仪表盘/持仓页面新增"累计分红"列

### 同步层
- `DataSync` 同步净值时顺带同步分红记录

---

## 功能五：费率差异化

### 需求
采集每只基金的申购/赎回阶梯费率表，回测和交易时使用实际费率。

### 数据层

**新增表 `fund_fee_schedule`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| fund_code | String(20) | 基金代码 |
| fee_type | String(20) | "purchase" 或 "redemption" |
| min_holding_days | Integer | 最少持有天数（含），申购费填0 |
| max_holding_days | Integer | 最多持有天数（不含），无上限用999999 |
| fee_rate | Numeric(8,6) | 费率 |
| min_amount | Numeric(14,2) | 申购费按金额阶梯时的最小金额（可null） |
| max_amount | Numeric(14,2) | 同上最大金额（可null） |

**唯一约束**：`(fund_code, fee_type, min_holding_days)` — 防止重复采集产生重复记录。
**索引**：`(fund_code, fee_type)` — 加速费率查询。

**FundFetcher 新增：**
- `fetch_fund_fee(fund_code: str) -> list[dict]` — 获取费率信息，解析阶梯费率表

**FundRepository 新增：**
- `upsert_fee_schedule(fund_code: str, schedules: list[dict])` — 与现有 upsert 方法保持一致
- `get_fee_rate(fund_code: str, fee_type: str, holding_days: int | None = None, amount: float | None = None) -> Decimal` — 查询实际适用费率

### 业务层影响
- `BacktestEngine`：调仓时根据持有天数查询实际赎回费率，申购费率按金额查询。**Fallback 逻辑**：优先查询 `fund_fee_schedule` 表，无数据时回退使用 `BacktestConfig` 中的固定费率（`buy_fee_rate=0.0015`，`sell_fee_rate=0.005`）。持有天数 = 卖出日期 - 买入日期的天数差。
- 持仓管理卖出时显示预估赎回费率和费用金额

---

## 功能六：风险测评

### 需求
用户填写风险问卷，根据评分自动调整核心/卫星仓比例。

### 数据层

**新增表 `risk_profile`：**

| 字段 | 类型 | 说明 |
|------|------|------|
| id | Integer, PK | 自增主键 |
| risk_level | Integer | 风险等级 1-5 |
| risk_label | String(20) | "保守型"/"稳健型"/"平衡型"/"进取型"/"激进型" |
| core_ratio | Integer | 建议核心仓比例 |
| satellite_ratio | Integer | 建议卫星仓比例 |
| assessment_date | Date | 评估日期 |
| answers | JSONB | 问卷原始回答 |

### 业务层

**新增 `risk/` 模块：**

`questionnaire.py` — 问卷定义：
- 5-8道题目（投资经验、可承受亏损、投资期限、收入稳定性、投资目标等）
- 每题2-5个选项，各有权重分值

`assessor.py` — `RiskAssessor` 类：
- `calculate_score(answers: dict) -> int` — 计算总分（0-100）
- `score_to_level(score: int) -> int` — 映射到1-5级
- `get_recommended_ratios(level: int) -> tuple[int, int]` — 返回 (core_ratio, satellite_ratio)

**风险等级与仓位映射：**

| 等级 | 标签 | 核心仓 | 卫星仓 |
|------|------|--------|--------|
| 1 | 保守型 | 70% | 30% |
| 2 | 稳健型 | 50% | 50% |
| 3 | 平衡型 | 30% | 70% |
| 4 | 进取型 | 20% | 80% |
| 5 | 激进型 | 10% | 90% |

### UI层
- 侧边栏新增「📋 风险测评」页面（或嵌入设置页面）
  - 问卷表单，逐题作答
  - 提交后显示：风险等级、标签、建议仓位比例
  - "应用建议"按钮 → 更新 `settings.yaml` 中 `portfolio.core_ratio / satellite_ratio`（需新增 `save_config()` 方法写回配置文件，操作前提示用户确认）

### CLI层
- `fund-cli config risk-assess` — 交互式问卷

---

## 数据库变更汇总

新增7张表：
1. `fund_estimate` — 实时估值缓存
2. `fund_watchlist` — 自选关注列表
3. `notification_config` — 通知配置
4. `notification_rule` — 通知规则
5. `fund_dividend` — 分红记录
6. `fund_fee_schedule` — 费率阶梯表
7. `risk_profile` — 风险评估

共7张新表（原有9张 → 总计16张），通过 `Base.metadata.create_all()` 自动创建，无需迁移工具。

## 实现顺序

1. 实时估值 → 2. 自选关注 → 3. 消息提醒 → 4. 分红数据 → 5. 费率差异化 → 6. 风险测评

每个功能完整实现后即可使用和验证。
