# 功能补齐实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 补齐基金量化分析系统中费率采集、估值同步、分红UI、费率UI四项缺失功能。

**Architecture:** 遵循现有的 fetcher → sync → repository → UI 数据流模式。所有新增代码复用已有的重试机制、Session管理和Streamlit组件模式。数据库表结构需修复唯一约束。

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, akshare, Streamlit, pytest

---

### Task 1: 修复 FundFeeSchedule 唯一约束

**Files:**
- Modify: `src/fund_analyzer/data/models.py:433-445`
- Modify: `src/fund_analyzer/data/repository.py:624-629`
- Modify: `tests/test_fee_schedule.py`

- [ ] **Step 1: 写测试验证多条申购费率不互相覆盖**

在 `tests/test_fee_schedule.py` 的 `TestUpsertFeeSchedule` 类中追加：

```python
def test_upsert_purchase_multiple_amounts(self, repo, session):
    """多条不同金额区间的申购费率不应互相覆盖。"""
    repo.upsert_fee_schedule("FEE_P01", [
        {"fee_type": "purchase", "min_holding_days": 0, "min_amount": Decimal("0"),
         "max_amount": Decimal("1000000"), "fee_rate": Decimal("0.001500")},
        {"fee_type": "purchase", "min_holding_days": 0, "min_amount": Decimal("1000000"),
         "max_amount": Decimal("5000000"), "fee_rate": Decimal("0.001000")},
    ])
    stmt = select(FundFeeSchedule).where(
        FundFeeSchedule.fund_code == "FEE_P01",
        FundFeeSchedule.fee_type == "purchase",
    )
    results = list(session.execute(stmt).scalars().all())
    assert len(results) == 2
```

- [ ] **Step 2: 运行测试确认失败**

运行: `poetry run pytest tests/test_fee_schedule.py::TestUpsertFeeSchedule::test_upsert_purchase_multiple_amounts -v`
预期: FAIL（唯一约束导致第二条记录覆盖第一条，只剩1条）

- [ ] **Step 3: 修改 models.py 唯一约束**

修改 `src/fund_analyzer/data/models.py:433-445`：

```python
__table_args__ = (
    Index("uq_fee_schedule", "fund_code", "fee_type", "min_holding_days", "min_amount", unique=True),
    Index("ix_fee_fund_type", "fund_code", "fee_type"),
)

id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
fund_code: Mapped[str] = mapped_column(String(20), nullable=False)
fee_type: Mapped[str] = mapped_column(String(20), nullable=False)
min_holding_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
max_holding_days: Mapped[int] = mapped_column(Integer, nullable=False, default=999999)
fee_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
min_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False, default=0)
max_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
```

- [ ] **Step 4: 修改 repository.py upsert 查找条件**

修改 `src/fund_analyzer/data/repository.py:624-629`，在查找条件中增加 `min_amount`：

```python
stmt = select(FundFeeSchedule).where(
    and_(
        FundFeeSchedule.fund_code == fund_code,
        FundFeeSchedule.fee_type == row["fee_type"],
        FundFeeSchedule.min_holding_days == row.get("min_holding_days", 0),
        FundFeeSchedule.min_amount == row.get("min_amount", 0),
    )
)
```

- [ ] **Step 5: 运行测试验证通过**

运行: `poetry run pytest tests/test_fee_schedule.py -v`
预期: 全部 PASS

---

### Task 2: 新增 `get_fee_schedules()` 方法

**Files:**
- Modify: `src/fund_analyzer/data/repository.py`（在 `get_fee_rate` 方法之后、风险评估注释之前插入）
- Modify: `tests/test_fee_schedule.py`

- [ ] **Step 1: 写测试**

在 `tests/test_fee_schedule.py` 追加：

```python
class TestGetFeeSchedules:
    def test_returns_ordered_list(self, repo, session):
        repo.upsert_fee_schedule("SCHED01", [
            {"fee_type": "redemption", "min_holding_days": 7, "max_holding_days": 365, "fee_rate": Decimal("0.005000")},
            {"fee_type": "redemption", "min_holding_days": 0, "max_holding_days": 7, "fee_rate": Decimal("0.015000")},
            {"fee_type": "purchase", "min_holding_days": 0, "min_amount": Decimal("0"),
             "max_amount": Decimal("1000000"), "fee_rate": Decimal("0.001500")},
        ])
        schedules = repo.get_fee_schedules("SCHED01")
        assert len(schedules) == 3
        # 按 fee_type 排序: purchase 在前, redemption 在后
        assert schedules[0].fee_type == "purchase"
        assert schedules[1].fee_type == "redemption"
        assert schedules[1].min_holding_days == 0

    def test_empty_returns_empty_list(self, repo):
        assert repo.get_fee_schedules("NONEXIST") == []
```

- [ ] **Step 2: 运行测试确认失败**

运行: `poetry run pytest tests/test_fee_schedule.py::TestGetFeeSchedules -v`
预期: FAIL（AttributeError: 'FundRepository' object has no attribute 'get_fee_schedules'）

- [ ] **Step 3: 实现 get_fee_schedules**

在 `src/fund_analyzer/data/repository.py` 的 `get_fee_rate` 方法之后（约第696行）插入：

```python
def get_fee_schedules(self, fund_code: str) -> list[FundFeeSchedule]:
    """获取基金的完整费率阶梯列表。"""
    stmt = (
        select(FundFeeSchedule)
        .where(FundFeeSchedule.fund_code == fund_code)
        .order_by(FundFeeSchedule.fee_type, FundFeeSchedule.min_holding_days)
    )
    return list(self._session.execute(stmt).scalars().all())
```

- [ ] **Step 4: 运行测试验证通过**

运行: `poetry run pytest tests/test_fee_schedule.py -v`
预期: 全部 PASS

---

### Task 3: 实现费率采集 `fetch_fund_fee_schedule()`

**Files:**
- Modify: `src/fund_analyzer/data/fetcher.py`（在 `fetch_fund_dividend` 方法之前插入，约第385行）
- Modify: `tests/test_fee_schedule.py`

- [ ] **Step 1: 写测试**

在 `tests/test_fee_schedule.py` 追加：

```python
from fund_analyzer.data.fetcher import FundFetcher


class TestFetchFundFeeSchedule:
    def test_fetch_success(self, monkeypatch):
        import pandas as pd
        mock_df = pd.DataFrame([
            {"项目": "适用金额", "数据": "适用金额"},
            {"项目": "小于100万元", "数据": "0.15%"},
            {"项目": "大于等于100万元，小于500万元", "数据": "0.12%"},
            {"项目": "适用期限", "数据": "适用期限"},
            {"项目": "小于7天", "数据": "1.50%"},
            {"项目": "大于等于7天，小于365天", "数据": "0.50%"},
            {"项目": "大于等于365天", "数据": "0.00%"},
        ])
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_call_with_retry", lambda *a, **kw: mock_df)
        result = fetcher.fetch_fund_fee_schedule("110011")
        purchase = [r for r in result if r["fee_type"] == "purchase"]
        redemption = [r for r in result if r["fee_type"] == "redemption"]
        assert len(purchase) == 2
        assert len(redemption) == 3
        assert purchase[0]["fee_rate"] == Decimal("0.001500")

    def test_fetch_empty(self, monkeypatch):
        import pandas as pd
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_call_with_retry", lambda *a, **kw: pd.DataFrame())
        result = fetcher.fetch_fund_fee_schedule("999999")
        assert result == []

    def test_fetch_api_error(self, monkeypatch):
        def raise_error(*a, **kw):
            raise Exception("API error")
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_call_with_retry", raise_error)
        result = fetcher.fetch_fund_fee_schedule("999999")
        assert result == []

    def test_fetch_partial_parse_error(self, monkeypatch):
        """部分行解析失败时跳过，不影响其他行。"""
        import pandas as pd
        mock_df = pd.DataFrame([
            {"项目": "适用期限", "数据": "适用期限"},
            {"项目": "小于7天", "数据": "1.50%"},
            {"项目": "无法解析的行", "数据": "无效数据"},
            {"项目": "大于等于7天", "数据": "0.00%"},
        ])
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_call_with_retry", lambda *a, **kw: mock_df)
        result = fetcher.fetch_fund_fee_schedule("110011")
        # 无效行被跳过，仍返回可解析的2条
        assert len(result) == 2
```

- [ ] **Step 2: 运行测试确认失败**

运行: `poetry run pytest tests/test_fee_schedule.py::TestFetchFundFeeSchedule -v`
预期: FAIL（AttributeError: 'FundFetcher' object has no attribute 'fetch_fund_fee_schedule'）

- [ ] **Step 3: 实现 fetch_fund_fee_schedule**

在 `src/fund_analyzer/data/fetcher.py` 第385行（分红采集注释之前）插入：

```python
    # ------------------------------------------------------------------
    # 费率数据采集
    # ------------------------------------------------------------------

    def fetch_fund_fee_schedule(self, fund_code: str) -> list[dict]:
        """采集基金申购/赎回费率阶梯。

        通过 akshare fund_individual_detail_info_em 接口获取费率信息，
        解析金额区间和持有天数区间。

        Returns
        -------
        list[dict]
            费率阶梯数据列表，空列表表示采集失败。
        """
        import re

        results: list[dict] = []
        try:
            df = self._call_with_retry(
                ak.fund_individual_detail_info_em,
                fund=fund_code,
                indicator="购买信息",
            )
            if df is None or df.empty:
                return results

            section = None  # "purchase" or "redemption"
            for _, row in df.iterrows():
                item = str(row.iloc[0]).strip()
                value = str(row.iloc[1]).strip()

                # 检测段落切换
                if "适用金额" in item:
                    section = "purchase"
                    continue
                if "适用期限" in item:
                    section = "redemption"
                    continue
                if section is None:
                    continue

                # 解析费率百分比
                rate_match = re.search(r"(\d+\.?\d*)%", value)
                if not rate_match:
                    continue
                fee_rate = Decimal(rate_match.group(1)) / Decimal("100")

                if section == "purchase":
                    # 解析金额区间（万元）
                    amounts = re.findall(r"(\d+)万", item)
                    min_amt = Decimal("0")
                    max_amt = None
                    if "小于" in item and "大于" not in item:
                        max_amt = Decimal(amounts[0]) * 10000 if amounts else None
                    elif "大于等于" in item and "小于" in item and len(amounts) >= 2:
                        min_amt = Decimal(amounts[0]) * 10000
                        max_amt = Decimal(amounts[1]) * 10000
                    elif "大于等于" in item and len(amounts) >= 1:
                        min_amt = Decimal(amounts[0]) * 10000

                    results.append({
                        "fee_type": "purchase",
                        "min_holding_days": 0,
                        "max_holding_days": 999999,
                        "fee_rate": fee_rate,
                        "min_amount": min_amt,
                        "max_amount": max_amt,
                    })

                elif section == "redemption":
                    # 解析持有天数区间
                    days = re.findall(r"(\d+)天", item)
                    min_days = 0
                    max_days = 999999
                    if "小于" in item and "大于" not in item:
                        max_days = int(days[0]) if days else 999999
                    elif "大于等于" in item and "小于" in item and len(days) >= 2:
                        min_days = int(days[0])
                        max_days = int(days[1])
                    elif "大于等于" in item and len(days) >= 1:
                        min_days = int(days[0])

                    results.append({
                        "fee_type": "redemption",
                        "min_holding_days": min_days,
                        "max_holding_days": max_days,
                        "fee_rate": fee_rate,
                        "min_amount": Decimal("0"),
                    })

        except Exception as exc:
            logger.warning("采集基金 %s 费率失败: %s", fund_code, exc)

        return results
```

- [ ] **Step 4: 运行测试验证通过**

运行: `poetry run pytest tests/test_fee_schedule.py -v`
预期: 全部 PASS

---

### Task 4: 实现估值同步 `sync_estimates()` + 费率同步 `sync_fee_schedules()`

**Files:**
- Modify: `src/fund_analyzer/data/sync.py:183-194`（在 `sync_fund_dividend` 方法之后插入两个新方法）
- Modify: `src/fund_analyzer/data/sync.py:255-366`（修改 `sync_all`）
- Modify: `tests/test_estimate.py`

- [ ] **Step 1: 写测试**

在 `tests/test_estimate.py` 末尾追加：

```python
from unittest.mock import MagicMock
from fund_analyzer.data.sync import DataSyncer


class TestSyncEstimates:
    def test_sync_estimates_adds_date(self, monkeypatch):
        """sync_estimates 为每条估值补充 estimate_date。"""
        mock_repo = MagicMock()
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_fund_estimate_batch.return_value = [
            {"fund_code": "A", "estimate_nav": 1.5, "estimate_return": 0.5,
             "estimate_time": "14:00", "source": "akshare"},
        ]
        upserted_data = []
        mock_repo.upsert_estimate.side_effect = lambda d: upserted_data.append(d)

        syncer = DataSyncer(mock_repo, mock_fetcher)
        count = syncer.sync_estimates(["A"])

        assert count == 1
        assert "estimate_date" in upserted_data[0]
        assert upserted_data[0]["estimate_date"] == date.today()

    def test_sync_estimates_skips_none(self, monkeypatch):
        """防御性测试：即使 batch 返回含 None 的列表，sync 也能正确跳过。"""
        mock_repo = MagicMock()
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_fund_estimate_batch.return_value = [None, None]

        syncer = DataSyncer(mock_repo, mock_fetcher)
        count = syncer.sync_estimates(["A", "B"])
        assert count == 0
        mock_repo.upsert_estimate.assert_not_called()

    def test_sync_estimates_handles_upsert_error(self, monkeypatch):
        """upsert 失败时计数不增加，但继续处理后续数据。"""
        mock_repo = MagicMock()
        mock_fetcher = MagicMock()
        mock_fetcher.fetch_fund_estimate_batch.return_value = [
            {"fund_code": "FAIL", "estimate_nav": 1.0, "estimate_return": 0,
             "estimate_time": "14:00", "source": "akshare"},
            {"fund_code": "OK", "estimate_nav": 2.0, "estimate_return": 1.0,
             "estimate_time": "14:30", "source": "akshare"},
        ]
        call_count = {"n": 0}
        def mock_upsert(d):
            call_count["n"] += 1
            if d["fund_code"] == "FAIL":
                raise Exception("DB error")
        mock_repo.upsert_estimate.side_effect = mock_upsert

        syncer = DataSyncer(mock_repo, mock_fetcher)
        count = syncer.sync_estimates(["FAIL", "OK"])
        assert count == 1  # 只有 OK 成功
        assert call_count["n"] == 2  # 两次都尝试了
```

- [ ] **Step 2: 运行测试确认失败**

运行: `poetry run pytest tests/test_estimate.py::TestSyncEstimates -v`
预期: FAIL（AttributeError: 'DataSyncer' object has no attribute 'sync_estimates'）

- [ ] **Step 3: 在 sync.py 中实现 sync_estimates 和 sync_fee_schedules**

在 `src/fund_analyzer/data/sync.py` 第194行（`sync_fund_dividend` 之后）插入：

```python
    def sync_estimates(self, fund_codes: list[str]) -> int:
        """批量同步基金实时估值。

        为每条估值数据补充 estimate_date 字段（fetcher 返回中不包含）。

        Returns
        -------
        成功同步的估值数量。
        """
        import datetime as _dt

        estimates = self._fetcher.fetch_fund_estimate_batch(fund_codes)
        today = _dt.date.today()
        count = 0
        for est in estimates:
            if est is not None:
                est["estimate_date"] = today
                try:
                    self._repo.upsert_estimate(est)
                    count += 1
                except Exception as exc:
                    logger.warning("upsert_estimate(%s) 失败: %s", est.get("fund_code"), exc)
        return count

    def sync_fee_schedules(self, fund_codes: list[str]) -> int:
        """同步基金费率阶梯数据。

        Returns
        -------
        成功同步费率的基金数。
        """
        count = 0
        for code in fund_codes:
            try:
                schedules = self._fetcher.fetch_fund_fee_schedule(code)
                if schedules:
                    self._repo.upsert_fee_schedule(code, schedules)
                    count += 1
            except Exception as exc:
                logger.warning("sync_fee_schedule(%s) 失败: %s", code, exc)
        return count
```

- [ ] **Step 4: 修改 sync_all 集成估值同步和费率同步**

修改 `src/fund_analyzer/data/sync.py` 的 `sync_all` 方法：

1. 在返回值初始化（第290-295行）中增加字段：

```python
result: dict = {
    "funds": 0,
    "navs": 0,
    "indices": 0,
    "estimates": 0,
    "fee_schedules": 0,
    "warnings": [],
}
```

2. 在第356行 `result["indices"] = total_index_count` 之后、第357行 `result["warnings"] = all_warnings` 之前插入：

```python
        # 5. 同步实时估值
        _progress(nav_total, nav_total, "同步实时估值...")
        try:
            result["estimates"] = self.sync_estimates(codes_to_sync)
        except Exception as exc:
            logger.warning("sync_estimates 出错：%s", exc)

        # 6. 同步费率（仅 full 模式，费率变更频率低）
        if full:
            _progress(nav_total, nav_total, "同步费率数据...")
            try:
                result["fee_schedules"] = self.sync_fee_schedules(codes_to_sync)
            except Exception as exc:
                logger.warning("sync_fee_schedules 出错：%s", exc)
```

注意：`result["warnings"] = all_warnings` 行保持不变，新代码插入在它之前。

3. 更新日志行（第359-364行）：

```python
        logger.info(
            "sync_all 完成：funds=%d, navs=%d, indices=%d, estimates=%d, fee_schedules=%d, warnings=%d",
            result["funds"],
            result["navs"],
            result["indices"],
            result["estimates"],
            result["fee_schedules"],
            len(all_warnings),
        )
```

- [ ] **Step 5: 运行测试验证通过**

运行: `poetry run pytest tests/test_estimate.py tests/test_fee_schedule.py -v`
预期: 全部 PASS

---

### Task 5: tracker.summary() 增加 holding_days 和 buy_date 字段

**前置依赖:** 无（独立于 Task 1-4）

**Files:**
- Modify: `src/fund_analyzer/portfolio/tracker.py:117-145`

- [ ] **Step 1: 修改 tracker.summary() 中的 holdings 构建逻辑**

在 `src/fund_analyzer/portfolio/tracker.py` 第135-145行，为 holdings dict 增加 `buy_date` 和 `holding_days`：

```python
            buy_date_val = pos.buy_date if hasattr(pos, "buy_date") else None
            holding_days = (as_of - buy_date_val).days if buy_date_val else 0

            holdings.append({
                "fund_code": fund_code,
                "position_type": position_type,
                "shares": shares,
                "cost_price": cost_price,
                "current_nav": current_nav,
                "market_value": market_value,
                "cost": cost,
                "pnl": pnl,
                "return_pct": return_pct,
                "buy_date": buy_date_val,
                "holding_days": holding_days,
            })
```

- [ ] **Step 2: 运行现有测试确认无回归**

运行: `poetry run pytest tests/ -v --tb=short`
预期: 全部 PASS（新增字段为追加性变更，不影响现有测试）

注：`holding_days` 和 `buy_date` 字段的正确性将通过 Task 7 的持仓费率展示间接验证。由于 tracker 模块的测试通过 mock 驱动，新字段的计算逻辑（`(as_of - buy_date).days`）足够简单，无需额外单测。

---

### Task 6: 分红数据 UI

**Files:**
- Modify: `src/fund_analyzer/ui/views/portfolio.py`（在文件末尾追加）

- [ ] **Step 1: 在 portfolio.py render() 末尾添加分红展示区块**

在 `src/fund_analyzer/ui/views/portfolio.py` 文件末尾（第101行之后）追加分红展示逻辑。注意需要在 `render()` 函数内部、最外层缩进级别追加：

将现有 `render()` 函数改为在文件最后一行 `st.form_submit_button("确认卖出", disabled=True)` 之后追加：

```python

    # ---------------------------------------------------------------
    # 分红记录
    # ---------------------------------------------------------------
    st.divider()
    with st.expander("📊 分红记录", expanded=False):
        try:
            repo = get_repo()
            tracker = get_tracker()
            summary_data = tracker.summary()
            holdings_list = summary_data.get("holdings", [])
            if not holdings_list:
                st.info("暂无持仓，无法展示分红记录")
            else:
                import pandas as pd
                all_dividends = []
                for h in holdings_list:
                    divs = repo.get_dividends(h["fund_code"])
                    for d in divs:
                        all_dividends.append({
                            "基金代码": d.fund_code,
                            "除权日": d.ex_date,
                            "每份分红": float(d.dividend_per_unit) if d.dividend_per_unit else 0,
                            "分红类型": d.dividend_type or "现金分红",
                        })

                if all_dividends:
                    df = pd.DataFrame(all_dividends)
                    st.dataframe(df, use_container_width=True, hide_index=True)
                    summary_df = df.groupby("基金代码")["每份分红"].sum().reset_index()
                    summary_df.columns = ["基金代码", "累计每份分红"]
                    st.caption("累计分红汇总")
                    st.dataframe(summary_df, use_container_width=True, hide_index=True)
                else:
                    st.info("暂无分红记录")
        except Exception as e:
            st.error(f"获取分红记录失败：{e}")
```

- [ ] **Step 2: 运行现有测试确认无回归**

运行: `poetry run pytest tests/ -v --tb=short`
预期: 全部 PASS

---

### Task 7: 费率 UI — 持仓页

**前置依赖:** Task 2 (get_fee_schedules), Task 5 (holding_days 字段)

**Files:**
- Modify: `src/fund_analyzer/ui/views/portfolio.py`（在分红区块之后追加）

- [ ] **Step 1: 在 portfolio.py 分红区块之后添加费率展示**

在分红记录区块之后追加。注意：复用分红区块中已获取的 `repo`、`holdings_list`，无需重新获取：

```python

    # ---------------------------------------------------------------
    # 持仓费率
    # ---------------------------------------------------------------
    with st.expander("💰 持仓费率", expanded=False):
        try:
            repo = get_repo()
            tracker = get_tracker()
            summary_data2 = tracker.summary()
            holdings_list2 = summary_data2.get("holdings", [])
            if not holdings_list2:
                st.info("暂无持仓")
            else:
                import pandas as pd
                fee_rows = []
                for h in holdings_list2:
                    code = h["fund_code"]
                    holding_days = h.get("holding_days", 0)
                    fee_rate = repo.get_fee_rate(code, "redemption", holding_days=holding_days)
                    fee_rows.append({
                        "基金代码": code,
                        "持有天数": holding_days,
                        "当前赎回费率": f"{float(fee_rate)*100:.2f}%" if fee_rate is not None else "无数据",
                    })
                df = pd.DataFrame(fee_rows)
                st.dataframe(df, use_container_width=True, hide_index=True)
        except Exception as e:
            st.error(f"获取费率信息失败：{e}")
```

- [ ] **Step 2: 运行现有测试确认无回归**

运行: `poetry run pytest tests/ -v --tb=short`
预期: 全部 PASS

---

### Task 8: 费率 UI — 筛选页

**前置依赖:** Task 2 (get_fee_schedules)

**Files:**
- Modify: `src/fund_analyzer/ui/views/screening.py:100-118`（在"快速加入自选"区块之前插入）

- [ ] **Step 1: 在筛选结果区块内添加费率查看功能**

在 `src/fund_analyzer/ui/views/screening.py` 第99行（`st.dataframe(df, ...)` 之后）与第101行（`# 快速加入自选` 注释之前）之间插入。注意：`repo` 变量在第29行 `repo = get_repo()` 已定义，无需重新获取：

```python
                # 费率详情
                st.divider()
                selected_for_fee = st.selectbox(
                    "查看基金费率",
                    [r["基金代码"] for r in rows],
                    key="screening_fee_select",
                )
                if selected_for_fee:
                    schedules = repo.get_fee_schedules(selected_for_fee)
                    if schedules:
                        with st.expander("💰 费率详情", expanded=True):
                            purchase = [s for s in schedules if s.fee_type == "purchase"]
                            redemption = [s for s in schedules if s.fee_type == "redemption"]
                            col_p, col_r = st.columns(2)
                            with col_p:
                                st.caption("申购费率")
                                if purchase:
                                    pdf = pd.DataFrame([{
                                        "金额下限": f"¥{float(s.min_amount):,.0f}",
                                        "金额上限": f"¥{float(s.max_amount):,.0f}" if s.max_amount else "无上限",
                                        "费率": f"{float(s.fee_rate)*100:.2f}%",
                                    } for s in purchase])
                                    st.dataframe(pdf, use_container_width=True, hide_index=True)
                                else:
                                    st.info("暂无申购费率数据")
                            with col_r:
                                st.caption("赎回费率")
                                if redemption:
                                    rdf = pd.DataFrame([{
                                        "最少持有天数": s.min_holding_days,
                                        "最多持有天数": s.max_holding_days if s.max_holding_days < 999999 else "无上限",
                                        "费率": f"{float(s.fee_rate)*100:.2f}%",
                                    } for s in redemption])
                                    st.dataframe(rdf, use_container_width=True, hide_index=True)
                                else:
                                    st.info("暂无赎回费率数据")
                    else:
                        st.info("暂无费率数据（请先执行全量同步）")
```

- [ ] **Step 2: 运行全部测试确认无回归**

运行: `poetry run pytest tests/ -v --tb=short`
预期: 全部 PASS

---

### Task 9: 全量回归测试

**Files:** 无新增

- [ ] **Step 1: 运行全部测试套件**

运行: `poetry run pytest tests/ -v`
预期: 全部 PASS（包括新增的所有测试用例）

- [ ] **Step 2: 验证新增测试数量**

确认新增测试用例：
- `test_fee_schedule.py`: +7 用例（test_upsert_purchase_multiple_amounts ×1, TestGetFeeSchedules ×2, TestFetchFundFeeSchedule ×4）
- `test_estimate.py`: +3 用例（TestSyncEstimates ×3）
- 总计: +10 用例
