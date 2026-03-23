# 功能补齐设计文档

> 日期: 2026-03-20
> 状态: 待实现
> 范围: 补齐6大功能中的4项缺失

## 背景

基金量化分析系统新增的6个功能（实时估值、自选关注列表、消息提醒、分红数据、费率差异化、风险测评）核心实现已完成，但验证后发现4项缺失需要补齐：

1. 费率采集管道缺失（仅有存储和查询）
2. 实时估值未集成到数据同步流程
3. 分红数据无前端展示
4. 费率数据无前端展示

## 模块1：费率采集

### 文件变更
- `src/fund_analyzer/data/fetcher.py` — 新增 `fetch_fund_fee_schedule()`
- `src/fund_analyzer/data/sync.py` — 新增 `sync_fee_schedules()` + `sync_all()` 中添加调用
- `src/fund_analyzer/data/models.py` — 修改 `FundFeeSchedule` 唯一约束
- `src/fund_analyzer/data/repository.py` — 新增 `get_fee_schedules()` + 修改 `upsert_fee_schedule()` 查找逻辑
- `tests/test_fee_schedule.py` — 补充采集方法测试

### 数据库修复：唯一约束

**问题**：当前唯一约束 `(fund_code, fee_type, min_holding_days)` 无法区分不同金额区间的申购费率——所有申购费率 `min_holding_days` 默认为0，导致多条申购记录互相覆盖。

**修复**：将唯一索引改为 `(fund_code, fee_type, min_holding_days, min_amount)`，`min_amount` 使用 `coalesce(min_amount, 0)` 或改为 `nullable=False, default=0`。

```python
# models.py 修改
__table_args__ = (
    Index("uq_fee_schedule", "fund_code", "fee_type", "min_holding_days", "min_amount", unique=True),
    Index("ix_fee_fund_type", "fund_code", "fee_type"),
)
min_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
max_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
```

```python
# repository.py upsert_fee_schedule 修改查找条件
stmt = select(FundFeeSchedule).where(
    and_(
        FundFeeSchedule.fund_code == fund_code,
        FundFeeSchedule.fee_type == row["fee_type"],
        FundFeeSchedule.min_holding_days == row.get("min_holding_days", 0),
        FundFeeSchedule.min_amount == row.get("min_amount", 0),
    )
)
```

### 实现细节

#### `FundFetcher.fetch_fund_fee_schedule(fund_code: str) -> list[dict]`

从 akshare 采集基金费率阶梯数据。使用 `ak.fund_individual_detail_info_em(fund=fund_code, indicator="购买信息")` 返回的 DataFrame 包含多行键值对，从中解析申购费率和赎回费率。

```python
def fetch_fund_fee_schedule(self, fund_code: str) -> list[dict]:
    """采集基金申购/赎回费率阶梯。

    Returns
    -------
    list[dict]
        费率阶梯数据列表，空列表表示采集失败。
    """
    results = []
    try:
        df = self._call_with_retry(
            ak.fund_individual_detail_info_em, fund=fund_code, indicator="购买信息"
        )
        if df is None or df.empty:
            return results

        # DataFrame 列: ["项目", "数据"]
        # 解析申购费率行：匹配 "申购费率" 相关行
        # 格式示例: "小于100万元  0.15%"、"大于等于100万元,小于500万元  0.10%"
        # 解析赎回费率行：匹配 "赎回费率" 相关行
        # 格式示例: "小于7天  1.50%"、"大于等于7天,小于365天  0.50%"

        for _, row in df.iterrows():
            item, value = str(row.iloc[0]), str(row.iloc[1])
            # ... 正则解析金额区间/天数区间 → min/max值
            # ... 百分比字符串 → Decimal 费率值
    except Exception as exc:
        logger.warning("采集基金 %s 费率失败: %s", fund_code, exc)

    return results
```

**解析规则**：
- 金额区间正则：`r"(\d+)万元?"` 提取金额（单位：万元→乘10000）
- 天数区间正则：`r"(\d+)天"` 提取天数
- 费率正则：`r"(\d+\.?\d*)%"` 提取百分比→除100转Decimal
- "小于X" → max 设为 X
- "大于等于X" → min 设为 X
- "大于等于X,小于Y" → min=X, max=Y

返回格式（每条记录包含完整字段）：
```python
[
    {"fee_type": "purchase", "min_amount": Decimal("0"), "max_amount": Decimal("1000000"),
     "fee_rate": Decimal("0.0015"), "min_holding_days": 0, "max_holding_days": 999999},
    {"fee_type": "redemption", "min_holding_days": 0, "max_holding_days": 7,
     "fee_rate": Decimal("0.015"), "min_amount": Decimal("0")},
    {"fee_type": "redemption", "min_holding_days": 7, "max_holding_days": 365,
     "fee_rate": Decimal("0.005"), "min_amount": Decimal("0")},
]
```

#### DataSyncer 集成

新增 `sync_fee_schedules()` 方法 + 在 `sync_all()` 分红同步之后调用：

```python
def sync_fee_schedules(self, fund_codes: list[str]) -> int:
    """同步基金费率阶梯数据。"""
    count = 0
    for code in fund_codes:
        schedules = self.fetcher.fetch_fund_fee_schedule(code)
        if schedules:
            self.repo.upsert_fee_schedule(code, schedules)
            count += 1
    return count

# sync_all() 中调用（仅 full 模式，费率变更频率低）
if full:
    if self._progress:
        self._progress(nav_done, nav_total, "同步费率数据...")
    fee_count = self.sync_fee_schedules(fund_codes)
    logger.info("费率同步完成: %d/%d", fee_count, len(fund_codes))
```

#### Repository 新增方法

```python
def get_fee_schedules(self, fund_code: str) -> list[FundFeeSchedule]:
    """获取基金的完整费率阶梯。"""
    return list(self._session.execute(
        select(FundFeeSchedule).where(
            FundFeeSchedule.fund_code == fund_code
        ).order_by(FundFeeSchedule.fee_type, FundFeeSchedule.min_holding_days)
    ).scalars().all())
```

### 错误处理
- akshare API 不可用时返回空列表，不阻塞同步流程
- 复用现有 `_call_with_retry()` 重试机制
- 解析失败的单行跳过，不影响其他行

## 模块2：估值同步

### 文件变更
- `src/fund_analyzer/data/sync.py` — 新增 `sync_estimates()` + 集成到 `sync_all()`
- `tests/test_estimate.py` — 补充同步测试

### 实现细节

#### `DataSyncer.sync_estimates(fund_codes: list[str]) -> int`

**关键修复**：`fetcher.fetch_fund_estimate()` 返回的字典不含 `estimate_date`，而 `repo.upsert_estimate()` 需要 `estimate_date` 作为复合主键。`sync_estimates` 必须补充此字段。

```python
from datetime import date as _date

def sync_estimates(self, fund_codes: list[str]) -> int:
    """批量同步基金实时估值。"""
    estimates = self.fetcher.fetch_fund_estimate_batch(fund_codes)
    today = _date.today()
    count = 0
    for est in estimates:
        if est:
            # 补充 estimate_date（fetcher 返回中不包含此字段）
            est["estimate_date"] = today
            self.repo.upsert_estimate(est)
            count += 1
    return count
```

#### sync_all 集成

在 `sync_all()` 末尾（指数同步之后），同时更新返回值：

```python
# 同步实时估值
if self._progress:
    self._progress(nav_done, nav_total, "同步实时估值...")
est_count = self.sync_estimates(fund_codes)
logger.info("估值同步完成: %d/%d", est_count, len(fund_codes))

# 返回值增加 estimates 字段
return {
    "funds": fund_count,
    "navs": nav_count,
    "indices": idx_count,
    "estimates": est_count,     # 新增
    "fee_schedules": fee_count, # 新增（如果 full 模式）
    "warnings": all_warnings,
}
```

## 模块3：分红数据UI

### 文件变更
- `src/fund_analyzer/ui/views/portfolio.py` — 添加分红记录展示区块

### 实现细节

在 `render()` 函数末尾添加折叠面板。使用 `tracker.summary()["holdings"]` 获取持仓基金列表（而非不存在的 `get_positions()`）。

```python
st.divider()
with st.expander("📊 分红记录", expanded=False):
    repo = get_repo()
    tracker = get_tracker()
    summary = tracker.summary()
    holdings = summary.get("holdings", [])
    if not holdings:
        st.info("暂无持仓，无法展示分红记录")
    else:
        all_dividends = []
        for h in holdings:
            divs = repo.get_dividends(h["fund_code"])
            for d in divs:
                all_dividends.append({
                    "基金代码": d.fund_code,
                    "除权日": d.ex_date,
                    "每份分红": float(d.dividend_per_unit),
                    "分红类型": d.dividend_type or "现金分红",
                })

        if all_dividends:
            import pandas as pd
            df = pd.DataFrame(all_dividends)
            st.dataframe(df, use_container_width=True)

            # 汇总统计
            summary_df = df.groupby("基金代码")["每份分红"].sum().reset_index()
            summary_df.columns = ["基金代码", "累计每份分红"]
            st.subheader("累计分红汇总")
            st.dataframe(summary_df, use_container_width=True)
        else:
            st.info("暂无分红记录")
```

## 模块4：费率UI

### 文件变更
- `src/fund_analyzer/ui/views/screening.py` — 在筛选结果区块内添加费率查看
- `src/fund_analyzer/ui/views/portfolio.py` — 添加持仓费率展示

### 实现细节

#### 筛选页（screening.py）

在基金筛选结果展示区块**内部**（`if st.button(...)` 块内），添加费率查看功能：

```python
# 在筛选结果表格之后
if ranked_funds:
    fund_codes = [f.fund_code for f in ranked_funds]
    selected_fund = st.selectbox("查看基金费率", fund_codes)
    if selected_fund:
        with st.expander("💰 费率详情", expanded=True):
            schedules = repo.get_fee_schedules(selected_fund)
            if schedules:
                purchase = [s for s in schedules if s.fee_type == "purchase"]
                redemption = [s for s in schedules if s.fee_type == "redemption"]
                col1, col2 = st.columns(2)
                with col1:
                    st.caption("申购费率")
                    if purchase:
                        import pandas as pd
                        pdf = pd.DataFrame([{
                            "金额下限": f"{float(s.min_amount):,.0f}",
                            "金额上限": f"{float(s.max_amount):,.0f}" if s.max_amount else "无上限",
                            "费率": f"{float(s.fee_rate)*100:.2f}%",
                        } for s in purchase])
                        st.dataframe(pdf, use_container_width=True, hide_index=True)
                with col2:
                    st.caption("赎回费率")
                    if redemption:
                        rdf = pd.DataFrame([{
                            "最少持有天数": s.min_holding_days,
                            "最多持有天数": s.max_holding_days if s.max_holding_days < 999999 else "无上限",
                            "费率": f"{float(s.fee_rate)*100:.2f}%",
                        } for s in redemption])
                        st.dataframe(rdf, use_container_width=True, hide_index=True)
            else:
                st.info("暂无费率数据（请先执行全量同步）")
```

#### 持仓页（portfolio.py）

在持仓列表区块添加费率信息，根据买入日期计算持有天数，高亮显示当前适用赎回费率：

```python
with st.expander("💰 持仓费率", expanded=False):
    repo = get_repo()
    holdings = summary.get("holdings", [])
    if holdings:
        fee_data = []
        today = date.today()
        for h in holdings:
            code = h["fund_code"]
            # 持有天数 = today - buy_date（从 position 记录获取）
            holding_days = h.get("holding_days", 0)
            fee_rate = repo.get_fee_rate(code, "redemption", holding_days=holding_days)
            fee_data.append({
                "基金代码": code,
                "持有天数": holding_days,
                "当前赎回费率": f"{float(fee_rate)*100:.2f}%" if fee_rate else "无数据",
            })
        import pandas as pd
        df = pd.DataFrame(fee_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("暂无持仓")
```

**注意**：`holdings` 列表中目前没有 `holding_days` 字段，需要在 `tracker.summary()` 中补充（从 `PortfolioPosition.buy_date` 计算 `(today - buy_date).days`）。这是一个小改动，在 `tracker.py` 的 `summary()` 方法中为每条 holding 增加 `"holding_days"` 和 `"buy_date"` 字段。

## 测试计划

| 测试文件 | 新增用例 | 覆盖内容 |
|---------|---------|---------|
| test_fee_schedule.py | test_fetch_success | 正常采集返回解析后的费率列表 |
| test_fee_schedule.py | test_fetch_empty | akshare 返回空DataFrame时返回空列表 |
| test_fee_schedule.py | test_fetch_parse_error | 部分行解析失败时跳过、不影响其他行 |
| test_fee_schedule.py | test_upsert_purchase_multiple | 多条申购费率不互相覆盖（验证唯一约束修复） |
| test_estimate.py | test_sync_estimates | sync_estimates 补充 estimate_date 字段 |
| test_estimate.py | test_sync_all_includes_estimates | sync_all 返回值包含 estimates 字段 |

手动验证：UI 部分（分红记录、费率详情、持仓费率展示）通过 `poetry run streamlit run src/fund_analyzer/ui/app.py` 启动后手动检查。

## 影响范围

- **数据库变更**：`fund_fee_schedule` 表唯一约束从3列扩展为4列（需删除旧索引重建，或通过 `create_all` 自动处理）
- **向后兼容**：`min_amount` 默认值从 `None` 改为 `0`，已有数据中 `min_amount IS NULL` 的记录需更新为 `0`
- **无新依赖**：复用 akshare、pandas
- **返回值变更**：`sync_all()` 返回字典新增 `estimates` 和 `fee_schedules` 键
