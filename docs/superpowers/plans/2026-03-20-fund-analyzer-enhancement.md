# 基金分析系统增强功能实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为基金分析系统新增6个功能：实时估值、自选关注列表、消息提醒、分红数据、费率差异化、风险测评。

**Architecture:** 每个功能按照现有分层架构实现：数据模型(models.py) → 数据访问(repository.py) → 数据采集(fetcher.py) → 同步(sync.py) → 业务逻辑 → UI(Streamlit) / CLI(Typer)。所有新表通过 `Base.metadata.create_all()` 自动创建，无需迁移工具。

**Tech Stack:** Python 3.11+, SQLAlchemy 2.0 (Mapped), akshare, Streamlit, Typer, PostgreSQL 16, pytest (SQLite内存数据库)

**设计文档:** `docs/superpowers/specs/2026-03-20-fund-analyzer-enhancement-design.md`

---

## 文件结构

### 新增文件
| 文件 | 职责 |
|------|------|
| `src/fund_analyzer/notification/__init__.py` | 通知模块包 |
| `src/fund_analyzer/notification/sender.py` | 企业微信Webhook发送器 |
| `src/fund_analyzer/notification/checker.py` | 通知规则检查器 |
| `src/fund_analyzer/risk/__init__.py` | 风险评估模块包 |
| `src/fund_analyzer/risk/questionnaire.py` | 风险问卷定义 |
| `src/fund_analyzer/risk/assessor.py` | 风险评估计算器 |
| `src/fund_analyzer/ui/views/watchlist.py` | 自选基金页面 |
| `src/fund_analyzer/ui/views/risk_assess.py` | 风险测评页面 |
| `tests/test_estimate.py` | 实时估值测试 |
| `tests/test_watchlist.py` | 自选列表测试 |
| `tests/test_notification.py` | 消息提醒测试 |
| `tests/test_dividend.py` | 分红数据测试 |
| `tests/test_fee_schedule.py` | 费率差异化测试 |
| `tests/test_risk.py` | 风险测评测试 |

### 修改文件
| 文件 | 变更内容 |
|------|---------|
| `src/fund_analyzer/data/models.py` | 新增7个ORM模型 |
| `src/fund_analyzer/data/repository.py` | 新增各功能的CRUD方法 |
| `src/fund_analyzer/data/fetcher.py` | 新增估值、分红、费率采集方法 |
| `src/fund_analyzer/data/sync.py` | 同步流程中加入分红和费率 |
| `src/fund_analyzer/config.py` | 新增 EstimateConfig，Settings增加字段 |
| `src/fund_analyzer/ui/app.py` | 侧边栏加入新页面 |
| `src/fund_analyzer/ui/session.py` | 新增会话辅助函数 |
| `src/fund_analyzer/ui/views/settings.py` | 加入通知配置区域 |
| `src/fund_analyzer/ui/views/screening.py` | 加入"加入自选"按钮 |
| `src/fund_analyzer/ui/views/dashboard.py` | 加入估值列和分红列 |
| `src/fund_analyzer/cli/app.py` | 新增 watchlist/notify 命令组 |
| `src/fund_analyzer/backtest/engine.py` | 费率查询改为动态 |
| `pyproject.toml` | 新增 requests 依赖 |

---

## 功能一：实时估值

### Task 1: 实时估值 — 数据模型与配置

**Files:**
- Modify: `src/fund_analyzer/data/models.py`
- Modify: `src/fund_analyzer/config.py`
- Test: `tests/test_estimate.py`

- [ ] **Step 1: 在 models.py 末尾新增 FundEstimate 模型**

在 `DipPlan` 类之后添加：

```python
# ---------------------------------------------------------------------------
# 10. FundEstimate — 基金实时估值
# ---------------------------------------------------------------------------

class FundEstimate(Base):
    """基金实时估值缓存表。

    复合主键：(fund_code, estimate_date)
    """

    __tablename__ = "fund_estimate"

    fund_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    estimate_date: Mapped[date] = mapped_column(Date, primary_key=True)
    estimate_nav: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(12, 4), nullable=True
    )
    estimate_return: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(8, 4), nullable=True
    )
    estimate_time: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<FundEstimate fund_code={self.fund_code!r} date={self.estimate_date}>"
```

- [ ] **Step 2: 在 config.py 新增 EstimateConfig**

在 `SmartDipConfig` 之后、`LoggingConfig` 之前添加：

```python
@dataclass
class EstimateConfig:
    primary_source: str = "akshare"
    fallback_enabled: bool = True
```

在 `Settings` dataclass 中添加字段：

```python
estimate: EstimateConfig = field(default_factory=EstimateConfig)
```

- [ ] **Step 3: 编写模型测试**

创建 `tests/test_estimate.py`：

```python
"""实时估值功能测试。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundEstimate
from fund_analyzer.data.repository import FundRepository


@pytest.fixture(scope="module")
def engine():
    _engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)
    _engine.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()


@pytest.fixture()
def repo(session):
    return FundRepository(session)


class TestFundEstimateModel:
    def test_create(self, session):
        est = FundEstimate(
            fund_code="110011",
            estimate_date=date(2026, 3, 20),
            estimate_nav=Decimal("2.3456"),
            estimate_return=Decimal("1.23"),
            estimate_time="14:30",
            source="akshare",
            updated_at=datetime.now(),
        )
        session.add(est)
        session.flush()
        result = session.get(FundEstimate, ("110011", date(2026, 3, 20)))
        assert result is not None
        assert result.estimate_nav == Decimal("2.3456")
```

- [ ] **Step 4: 运行测试验证模型创建**

Run: `poetry run pytest tests/test_estimate.py::TestFundEstimateModel::test_create -v`
Expected: PASS

---

### Task 2: 实时估值 — 数据访问层

**Files:**
- Modify: `src/fund_analyzer/data/repository.py`
- Test: `tests/test_estimate.py`

- [ ] **Step 1: 在 repository.py 中导入 FundEstimate**

在文件顶部的 imports 中添加 `FundEstimate`：

```python
from fund_analyzer.data.models import (
    Base,
    FundInfo,
    FundNav,
    IndexQuote,
    FundHolding,
    IndustryMapping,
    PortfolioPosition,
    PortfolioTransaction,
    StrategySignal,
    DipPlan,
    FundEstimate,
)
```

- [ ] **Step 2: 在 FundRepository 中新增估值方法**

在类末尾添加：

```python
    # -----------------------------------------------------------------------
    # FundEstimate — 实时估值
    # -----------------------------------------------------------------------

    def upsert_estimate(self, data: dict) -> FundEstimate:
        """插入或更新基金估值数据。

        参数
        ----
        data : dict
            必须包含 fund_code, estimate_date 键。

        返回
        ----
        FundEstimate 对象。
        """
        key = (data["fund_code"], data["estimate_date"])
        obj = self._session.get(FundEstimate, key)
        if obj is None:
            obj = FundEstimate(**data)
            self._session.add(obj)
        else:
            for k, v in data.items():
                if k not in ("fund_code", "estimate_date"):
                    setattr(obj, k, v)
        self._session.flush()
        return obj

    def get_latest_estimates(self, fund_codes: list[str]) -> list[FundEstimate]:
        """获取指定基金列表的最新估值记录。

        参数
        ----
        fund_codes : list[str]
            基金代码列表。

        返回
        ----
        每只基金最新日期的估值记录列表。
        """
        if not fund_codes:
            return []
        from sqlalchemy import func
        subq = (
            select(
                FundEstimate.fund_code,
                func.max(FundEstimate.estimate_date).label("max_date"),
            )
            .where(FundEstimate.fund_code.in_(fund_codes))
            .group_by(FundEstimate.fund_code)
            .subquery()
        )
        stmt = select(FundEstimate).join(
            subq,
            and_(
                FundEstimate.fund_code == subq.c.fund_code,
                FundEstimate.estimate_date == subq.c.max_date,
            ),
        )
        return list(self._session.execute(stmt).scalars().all())
```

- [ ] **Step 3: 编写 Repository 测试**

在 `tests/test_estimate.py` 中追加：

```python
class TestUpsertEstimate:
    def test_insert_new(self, repo, session):
        repo.upsert_estimate({
            "fund_code": "EST001",
            "estimate_date": date(2026, 3, 20),
            "estimate_nav": Decimal("1.5000"),
            "estimate_return": Decimal("0.50"),
            "estimate_time": "14:00",
            "source": "akshare",
        })
        result = session.get(FundEstimate, ("EST001", date(2026, 3, 20)))
        assert result is not None
        assert result.estimate_nav == Decimal("1.5000")

    def test_update_existing(self, repo, session):
        session.add(FundEstimate(
            fund_code="EST002",
            estimate_date=date(2026, 3, 20),
            estimate_nav=Decimal("1.0000"),
        ))
        session.flush()
        repo.upsert_estimate({
            "fund_code": "EST002",
            "estimate_date": date(2026, 3, 20),
            "estimate_nav": Decimal("1.1000"),
            "estimate_return": Decimal("10.00"),
        })
        session.expire_all()
        result = session.get(FundEstimate, ("EST002", date(2026, 3, 20)))
        assert result.estimate_nav == Decimal("1.1000")


class TestGetLatestEstimates:
    def test_returns_latest(self, repo, session):
        session.add_all([
            FundEstimate(fund_code="LAT001", estimate_date=date(2026, 3, 19), estimate_nav=Decimal("1.0")),
            FundEstimate(fund_code="LAT001", estimate_date=date(2026, 3, 20), estimate_nav=Decimal("1.1")),
        ])
        session.flush()
        results = repo.get_latest_estimates(["LAT001"])
        assert len(results) == 1
        assert results[0].estimate_date == date(2026, 3, 20)

    def test_empty_codes(self, repo):
        assert repo.get_latest_estimates([]) == []
```

- [ ] **Step 4: 运行测试**

Run: `poetry run pytest tests/test_estimate.py -v`
Expected: ALL PASS

---

### Task 3: 实时估值 — 数据采集

**Files:**
- Modify: `src/fund_analyzer/data/fetcher.py`
- Test: `tests/test_estimate.py`

- [ ] **Step 1: 在 FundFetcher 中新增估值采集方法**

在类末尾添加：

```python
    # ------------------------------------------------------------------
    # 实时估值采集
    # ------------------------------------------------------------------

    def fetch_fund_estimate(self, fund_code: str) -> dict | None:
        """获取基金盘中估值数据。

        优先使用 akshare，失败时回退到天天基金页面解析。

        Parameters
        ----------
        fund_code:
            基金代码。

        Returns
        -------
        dict | None
            包含 estimate_nav, estimate_return, estimate_time 的字典，
            失败时返回 None。
        """
        result = self._fetch_estimate_akshare(fund_code)
        if result is not None:
            result["source"] = "akshare"
            return result

        result = self._fetch_estimate_eastmoney(fund_code)
        if result is not None:
            result["source"] = "eastmoney"
            return result

        logger.warning("获取基金 %s 估值失败（两个数据源均不可用）", fund_code)
        return None

    def _fetch_estimate_akshare(self, fund_code: str) -> dict | None:
        """通过 akshare 获取基金盘中估值。"""
        try:
            df = self._call_with_retry(ak.fund_etf_fund_info_em, fund=fund_code)
            if df is None or df.empty:
                return None
            last_row = df.iloc[-1]
            nav_val = last_row.get("估算净值", last_row.get("单位净值", 0))
            ret_val = last_row.get("估算涨幅", last_row.get("日增长率", 0))
            time_val = last_row.get("估算时间", "")
            # 确保 estimate_time 格式为 HH:MM
            time_str = str(time_val)
            if len(time_str) > 5:
                time_str = time_str[11:16] if "T" in time_str or " " in time_str else time_str[:5]
            return {
                "estimate_nav": float(nav_val),
                "estimate_return": float(ret_val),
                "estimate_time": time_str,
            }
        except Exception as exc:
            logger.debug("akshare 估值获取失败(%s): %s", fund_code, exc)
            return None

    def _fetch_estimate_eastmoney(self, fund_code: str) -> dict | None:
        """通过天天基金估值 API 获取基金估值。"""
        import requests
        url = f"http://fundgz.1234567.com.cn/js/{fund_code}.js"
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            import re
            import json
            match = re.search(r"jsonpgz\((.+?)\)", resp.text)
            if not match:
                return None
            data = json.loads(match.group(1))
            return {
                "estimate_nav": float(data.get("gsz", 0)),
                "estimate_return": float(data.get("gszzl", 0)),
                "estimate_time": data.get("gztime", ""),
            }
        except Exception as exc:
            logger.debug("天天基金估值获取失败(%s): %s", fund_code, exc)
            return None

    def fetch_fund_estimate_batch(self, fund_codes: list[str]) -> list[dict]:
        """批量获取基金估值。

        Parameters
        ----------
        fund_codes:
            基金代码列表。

        Returns
        -------
        包含成功获取的估值数据的列表。
        """
        results = []
        for code in fund_codes:
            est = self.fetch_fund_estimate(code)
            if est is not None:
                est["fund_code"] = code
                results.append(est)
        return results
```

- [ ] **Step 2: 在 pyproject.toml 中添加 requests 依赖**

在 `dependencies` 列表中添加：

```toml
    "requests (>=2.31.0,<3.0.0)",
```

- [ ] **Step 3: 编写采集层测试（mock 外部 API）**

在 `tests/test_estimate.py` 中追加：

```python
from fund_analyzer.data.fetcher import FundFetcher


class TestFetchFundEstimate:
    def test_akshare_success(self, monkeypatch):
        import pandas as pd
        mock_df = pd.DataFrame([{
            "净值日期": "2026-03-20",
            "单位净值": 2.345,
            "日增长率": 1.23,
        }])
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_call_with_retry", lambda *a, **kw: mock_df)

        result = fetcher.fetch_fund_estimate("110011")
        assert result is not None
        assert result["source"] == "akshare"
        assert result["estimate_nav"] == 2.345

    def test_both_fail_returns_none(self, monkeypatch):
        fetcher = FundFetcher()
        monkeypatch.setattr(fetcher, "_fetch_estimate_akshare", lambda code: None)
        monkeypatch.setattr(fetcher, "_fetch_estimate_eastmoney", lambda code: None)

        result = fetcher.fetch_fund_estimate("999999")
        assert result is None

    def test_batch(self, monkeypatch):
        fetcher = FundFetcher()
        call_count = {"n": 0}

        def mock_fetch(code):
            call_count["n"] += 1
            if code == "A":
                return {"estimate_nav": 1.0, "estimate_return": 0.5, "estimate_time": "14:00", "source": "akshare"}
            return None

        monkeypatch.setattr(fetcher, "fetch_fund_estimate", mock_fetch)
        results = fetcher.fetch_fund_estimate_batch(["A", "B"])
        assert len(results) == 1
        assert results[0]["fund_code"] == "A"
```

- [ ] **Step 4: 运行测试**

Run: `poetry run pytest tests/test_estimate.py -v`
Expected: ALL PASS

---

### Task 4: 实时估值 — UI 页面

**Files:**
- Modify: `src/fund_analyzer/ui/session.py`
- Modify: `src/fund_analyzer/ui/views/dashboard.py`

- [ ] **Step 1: 在 session.py 中新增估值相关辅助函数**

在文件末尾 `init_session()` 之前添加：

```python
def get_fetcher() -> "FundFetcher":
    from fund_analyzer.data.fetcher import FundFetcher
    if "fetcher" not in st.session_state:
        st.session_state.fetcher = FundFetcher()
    return st.session_state.fetcher
```

- [ ] **Step 2: 在仪表盘页面加入估值展示**

在 `dashboard.py` 的持仓明细表格部分，查询持仓基金的估值数据并新增估值列。在 `render()` 函数中，持仓明细表格渲染前，添加估值数据获取逻辑：

```python
# 获取持仓基金的估值数据
from datetime import datetime as dt
holdings = summary.get("holdings", [])
if holdings:
    from fund_analyzer.ui.session import get_fetcher
    fund_codes_in_holdings = list({h["fund_code"] for h in holdings})
    estimates = {}
    # 仅在交易时段内获取估值
    now = dt.now()
    if 9 <= now.hour < 16:
        repo = get_repo()
        est_records = repo.get_latest_estimates(fund_codes_in_holdings)
        for e in est_records:
            estimates[e.fund_code] = {
                "估算净值": float(e.estimate_nav) if e.estimate_nav else "-",
                "估算涨跌": f"{float(e.estimate_return):.2f}%" if e.estimate_return else "-",
            }
    for h in holdings:
        est = estimates.get(h["fund_code"], {})
        h["估算净值"] = est.get("估算净值", "-")
        h["估算涨跌"] = est.get("估算涨跌", "-")
```

- [ ] **Step 3: 手动验证 UI（无自动化测试）**

Run: `poetry run streamlit run src/fund_analyzer/ui/app.py`
验证仪表盘页面是否正常显示估值列。

---

## 功能二：自选关注列表

### Task 5: 自选列表 — 数据模型与数据访问

**Files:**
- Modify: `src/fund_analyzer/data/models.py`
- Modify: `src/fund_analyzer/data/repository.py`
- Create: `tests/test_watchlist.py`

- [ ] **Step 1: 在 models.py 中新增 FundWatchlist 模型**

在 `FundEstimate` 类之后添加：

```python
# ---------------------------------------------------------------------------
# 11. FundWatchlist — 自选关注列表
# ---------------------------------------------------------------------------

class FundWatchlist(Base):
    """自选基金关注列表。

    主键：id（自增）
    唯一约束：(fund_code, group_name)
    """

    __tablename__ = "fund_watchlist"
    __table_args__ = (
        Index("uq_watchlist_fund_group", "fund_code", "group_name", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(String(20), nullable=False)
    fund_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    group_name: Mapped[str] = mapped_column(String(50), nullable=False, default="默认")
    notes: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    added_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<FundWatchlist fund_code={self.fund_code!r} group={self.group_name!r}>"
```

- [ ] **Step 2: 在 repository.py 中导入 FundWatchlist 并新增方法**

导入中添加 `FundWatchlist`，然后在类末尾添加：

```python
    # -----------------------------------------------------------------------
    # FundWatchlist — 自选关注
    # -----------------------------------------------------------------------

    def add_to_watchlist(
        self,
        fund_code: str,
        fund_name: str = "",
        group_name: str = "默认",
        notes: str = "",
    ) -> FundWatchlist:
        """添加基金到自选列表。若已存在则更新备注。"""
        from datetime import datetime as dt
        stmt = select(FundWatchlist).where(
            and_(
                FundWatchlist.fund_code == fund_code,
                FundWatchlist.group_name == group_name,
            )
        )
        obj = self._session.execute(stmt).scalar_one_or_none()
        if obj is None:
            obj = FundWatchlist(
                fund_code=fund_code,
                fund_name=fund_name,
                group_name=group_name,
                notes=notes,
                added_at=dt.now(),
            )
            self._session.add(obj)
        else:
            obj.notes = notes
            if fund_name:
                obj.fund_name = fund_name
        self._session.flush()
        return obj

    def remove_from_watchlist(
        self, fund_code: str, group_name: str | None = None
    ) -> int:
        """从自选列表移除基金。

        参数
        ----
        fund_code : str
            基金代码。
        group_name : str | None
            分组名。None 时删除该基金在所有分组的记录。

        返回
        ----
        删除的记录数。
        """
        conditions = [FundWatchlist.fund_code == fund_code]
        if group_name is not None:
            conditions.append(FundWatchlist.group_name == group_name)
        stmt = select(FundWatchlist).where(and_(*conditions))
        items = list(self._session.execute(stmt).scalars().all())
        for item in items:
            self._session.delete(item)
        self._session.flush()
        return len(items)

    def get_watchlist(self, group_name: str | None = None) -> list[FundWatchlist]:
        """获取自选列表，可按分组过滤。"""
        stmt = select(FundWatchlist)
        if group_name is not None:
            stmt = stmt.where(FundWatchlist.group_name == group_name)
        stmt = stmt.order_by(FundWatchlist.added_at.desc())
        return list(self._session.execute(stmt).scalars().all())

    def get_watchlist_groups(self) -> list[str]:
        """获取所有自选分组名。"""
        from sqlalchemy import func, distinct
        stmt = select(distinct(FundWatchlist.group_name))
        return list(self._session.execute(stmt).scalars().all())
```

- [ ] **Step 3: 编写测试**

创建 `tests/test_watchlist.py`：

```python
"""自选关注列表测试。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundWatchlist
from fund_analyzer.data.repository import FundRepository


@pytest.fixture(scope="module")
def engine():
    _engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)
    _engine.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()


@pytest.fixture()
def repo(session):
    return FundRepository(session)


class TestAddToWatchlist:
    def test_add_new(self, repo, session):
        result = repo.add_to_watchlist("110011", "易方达蓝筹精选")
        assert result.fund_code == "110011"
        assert result.group_name == "默认"

    def test_duplicate_updates_notes(self, repo):
        repo.add_to_watchlist("DUP001", "基金A", notes="旧备注")
        repo.add_to_watchlist("DUP001", "基金A", notes="新备注")
        items = repo.get_watchlist()
        matching = [w for w in items if w.fund_code == "DUP001"]
        assert len(matching) == 1
        assert matching[0].notes == "新备注"

    def test_different_groups(self, repo):
        repo.add_to_watchlist("GRP001", "基金B", group_name="核心观察")
        repo.add_to_watchlist("GRP001", "基金B", group_name="待买入")
        items = repo.get_watchlist()
        matching = [w for w in items if w.fund_code == "GRP001"]
        assert len(matching) == 2


class TestRemoveFromWatchlist:
    def test_remove_all_groups(self, repo):
        repo.add_to_watchlist("RM001", "基金C", group_name="A")
        repo.add_to_watchlist("RM001", "基金C", group_name="B")
        count = repo.remove_from_watchlist("RM001")
        assert count == 2

    def test_remove_specific_group(self, repo):
        repo.add_to_watchlist("RM002", "基金D", group_name="A")
        repo.add_to_watchlist("RM002", "基金D", group_name="B")
        count = repo.remove_from_watchlist("RM002", group_name="A")
        assert count == 1
        remaining = repo.get_watchlist()
        matching = [w for w in remaining if w.fund_code == "RM002"]
        assert len(matching) == 1
        assert matching[0].group_name == "B"


class TestGetWatchlistGroups:
    def test_returns_groups(self, repo):
        repo.add_to_watchlist("G001", "基金", group_name="核心")
        repo.add_to_watchlist("G002", "基金", group_name="卫星")
        groups = repo.get_watchlist_groups()
        assert "核心" in groups
        assert "卫星" in groups
```

- [ ] **Step 4: 运行测试**

Run: `poetry run pytest tests/test_watchlist.py -v`
Expected: ALL PASS

---

### Task 6: 自选列表 — UI 页面与 CLI

**Files:**
- Create: `src/fund_analyzer/ui/views/watchlist.py`
- Modify: `src/fund_analyzer/ui/app.py`
- Modify: `src/fund_analyzer/ui/views/screening.py`
- Modify: `src/fund_analyzer/cli/app.py`

- [ ] **Step 1: 创建自选基金页面**

创建 `src/fund_analyzer/ui/views/watchlist.py`：

```python
"""自选基金页面。"""
from __future__ import annotations

import pandas as pd
import streamlit as st

from fund_analyzer.ui.session import get_repo, commit


def render() -> None:
    st.header("自选基金")

    repo = get_repo()

    # 添加基金表单
    with st.expander("添加基金到自选", expanded=False):
        col1, col2, col3 = st.columns([2, 2, 3])
        with col1:
            add_code = st.text_input("基金代码", key="wl_add_code")
        with col2:
            add_group = st.text_input("分组", value="默认", key="wl_add_group")
        with col3:
            add_notes = st.text_input("备注", key="wl_add_notes")
        if st.button("添加", type="primary"):
            if add_code.strip():
                fund_info = repo.get_fund_info(add_code.strip())
                fund_name = fund_info.fund_name if fund_info else ""
                repo.add_to_watchlist(
                    add_code.strip(), fund_name, add_group, add_notes
                )
                commit()
                st.success(f"已添加 {add_code.strip()} 到自选列表")
                st.rerun()
            else:
                st.warning("请输入基金代码")

    # 分组筛选
    groups = repo.get_watchlist_groups()
    selected_group = None
    if groups:
        filter_options = ["全部"] + groups
        selected = st.selectbox("分组筛选", filter_options)
        if selected != "全部":
            selected_group = selected

    # 自选列表
    items = repo.get_watchlist(group_name=selected_group)
    if not items:
        st.info("自选列表为空，请添加基金")
        return

    data = []
    for item in items:
        data.append({
            "基金代码": item.fund_code,
            "基金名称": item.fund_name or "-",
            "分组": item.group_name,
            "备注": item.notes or "",
            "添加时间": item.added_at.strftime("%Y-%m-%d %H:%M") if item.added_at else "-",
        })

    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # 移除功能
    st.divider()
    remove_code = st.selectbox(
        "选择要移除的基金",
        [item.fund_code for item in items],
        format_func=lambda c: f"{c} - {next((i.fund_name for i in items if i.fund_code == c), '')}",
    )
    if st.button("移除", type="secondary"):
        repo.remove_from_watchlist(remove_code, group_name=selected_group)
        commit()
        st.success(f"已移除 {remove_code}")
        st.rerun()
```

- [ ] **Step 2: 在 app.py 中注册新页面**

在 `src/fund_analyzer/ui/app.py` 的 imports 中添加：

```python
from fund_analyzer.ui.views import watchlist
```

在 `PAGES` 字典中，在 `"🔍 基金筛选"` 之后添加：

```python
    "⭐ 自选基金": watchlist.render,
```

- [ ] **Step 3: 在筛选页面添加"加入自选"按钮**

在 `screening.py` 的筛选结果表格下方，添加快速加入自选的功能。在显示筛选结果 DataFrame 之后添加：

```python
# 快速加入自选
st.divider()
add_col1, add_col2 = st.columns([3, 1])
with add_col1:
    selected_code = st.selectbox(
        "加入自选",
        fund_codes[:top_n],
        format_func=lambda c: f"{c} - {next((f.fund_name for f in funds if f.fund_code == c), '')}",
        key="screening_add_watchlist",
    )
with add_col2:
    if st.button("加入自选", key="screening_add_btn"):
        fund_info = repo.get_fund_info(selected_code)
        fund_name = fund_info.fund_name if fund_info else ""
        repo.add_to_watchlist(selected_code, fund_name)
        from fund_analyzer.ui.session import commit
        commit()
        st.success(f"已将 {selected_code} 加入自选")
```

- [ ] **Step 4: 在 CLI 中添加 watchlist 命令组**

在 `src/fund_analyzer/cli/app.py` 中添加：

```python
watchlist_app = typer.Typer(name="watchlist", help="自选基金管理")
app.add_typer(watchlist_app)


@watchlist_app.command("add")
def watchlist_add(
    code: str = typer.Argument(..., help="基金代码"),
    group: str = typer.Option("默认", "--group", "-g", help="分组名称"),
):
    """添加基金到自选列表。"""
    session = _get_session()
    repo = _get_repo(session)
    fund_info = repo.get_fund_info(code)
    fund_name = fund_info.fund_name if fund_info else ""
    repo.add_to_watchlist(code, fund_name, group)
    session.commit()
    console.print(f"[green]已添加 {code} ({fund_name}) 到分组「{group}」[/green]")


@watchlist_app.command("list")
def watchlist_list(
    group: str = typer.Option(None, "--group", "-g", help="按分组过滤"),
):
    """显示自选列表。"""
    session = _get_session()
    repo = _get_repo(session)
    items = repo.get_watchlist(group_name=group)
    if not items:
        console.print("[yellow]自选列表为空[/yellow]")
        return
    from rich.table import Table
    table = Table(title="自选基金")
    table.add_column("代码")
    table.add_column("名称")
    table.add_column("分组")
    table.add_column("备注")
    for item in items:
        table.add_row(item.fund_code, item.fund_name or "-", item.group_name, item.notes or "")
    console.print(table)


@watchlist_app.command("remove")
def watchlist_remove(
    code: str = typer.Argument(..., help="基金代码"),
):
    """从自选列表移除基金。"""
    session = _get_session()
    repo = _get_repo(session)
    count = repo.remove_from_watchlist(code)
    session.commit()
    if count > 0:
        console.print(f"[green]已移除 {code}（{count}条记录）[/green]")
    else:
        console.print(f"[yellow]未找到 {code} 的自选记录[/yellow]")
```

- [ ] **Step 5: 手动验证**

Run: `poetry run pytest tests/test_watchlist.py -v && poetry run fund-cli watchlist list`
Expected: 测试通过，CLI 正常输出

---

## 功能三：消息提醒

### Task 7: 消息提醒 — 数据模型

**Files:**
- Modify: `src/fund_analyzer/data/models.py`
- Modify: `src/fund_analyzer/data/repository.py`

- [ ] **Step 1: 在 models.py 中新增通知相关模型**

在 `FundWatchlist` 之后添加：

```python
# ---------------------------------------------------------------------------
# 12. NotificationConfig — 通知配置
# ---------------------------------------------------------------------------

class NotificationConfig(Base):
    """通知渠道配置表。"""

    __tablename__ = "notification_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False, default="wechat")
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    def __repr__(self) -> str:
        return f"<NotificationConfig channel={self.channel!r} enabled={self.enabled}>"


# ---------------------------------------------------------------------------
# 13. NotificationRule — 通知规则
# ---------------------------------------------------------------------------

class NotificationRule(Base):
    """通知规则表。"""

    __tablename__ = "notification_rule"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rule_type: Mapped[str] = mapped_column(String(30), nullable=False)
    params: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<NotificationRule type={self.rule_type!r} enabled={self.enabled}>"
```

> 注：`params` 使用 SQLAlchemy `JSON` 类型，PostgreSQL 上自动映射为 JSONB，SQLite 上映射为 TEXT（JSON 序列化），无需手动 `json.loads/dumps`。需在 models.py 顶部导入中添加 `JSON`：`from sqlalchemy import ..., JSON`。

- [ ] **Step 2: 在 repository.py 中新增通知相关方法**

导入 `NotificationConfig, NotificationRule`，然后添加：

```python
    # -----------------------------------------------------------------------
    # NotificationConfig / NotificationRule — 通知管理
    # -----------------------------------------------------------------------

    def get_notification_config(self) -> NotificationConfig | None:
        """获取当前通知配置（仅支持单渠道）。"""
        stmt = select(NotificationConfig).where(NotificationConfig.enabled == True).limit(1)
        return self._session.execute(stmt).scalar_one_or_none()

    def save_notification_config(self, webhook_url: str, enabled: bool = True) -> NotificationConfig:
        """保存通知配置。若已有配置则更新，否则新建。"""
        from datetime import datetime as dt
        stmt = select(NotificationConfig).limit(1)
        obj = self._session.execute(stmt).scalar_one_or_none()
        if obj is None:
            obj = NotificationConfig(
                channel="wechat",
                webhook_url=webhook_url,
                enabled=enabled,
                updated_at=dt.now(),
            )
            self._session.add(obj)
        else:
            obj.webhook_url = webhook_url
            obj.enabled = enabled
            obj.updated_at = dt.now()
        self._session.flush()
        return obj

    def get_notification_rules(self) -> list[NotificationRule]:
        """获取所有通知规则。"""
        stmt = select(NotificationRule)
        return list(self._session.execute(stmt).scalars().all())

    def save_notification_rule(self, rule_type: str, params: dict | None, enabled: bool = True) -> NotificationRule:
        """保存通知规则。同类型规则存在则更新。"""
        stmt = select(NotificationRule).where(NotificationRule.rule_type == rule_type)
        obj = self._session.execute(stmt).scalar_one_or_none()
        if obj is None:
            obj = NotificationRule(rule_type=rule_type, params=params, enabled=enabled)
            self._session.add(obj)
        else:
            obj.params = params
            obj.enabled = enabled
        self._session.flush()
        return obj
```

---

### Task 8: 消息提醒 — 发送器与检查器

**Files:**
- Create: `src/fund_analyzer/notification/__init__.py`
- Create: `src/fund_analyzer/notification/sender.py`
- Create: `src/fund_analyzer/notification/checker.py`
- Create: `tests/test_notification.py`

- [ ] **Step 1: 创建通知模块**

创建 `src/fund_analyzer/notification/__init__.py`：

```python
"""通知模块：企业微信推送。"""
```

创建 `src/fund_analyzer/notification/sender.py`：

```python
"""企业微信 Webhook 消息发送器。"""
from __future__ import annotations

import logging

import requests

logger = logging.getLogger(__name__)


class WeChatSender:
    """企业微信机器人 Webhook 发送器。

    Parameters
    ----------
    webhook_url : str
        企业微信机器人的 Webhook 地址。
    """

    def __init__(self, webhook_url: str) -> None:
        self._url = webhook_url

    def send(self, title: str, content: str) -> bool:
        """发送 Markdown 格式消息。

        Parameters
        ----------
        title : str
            消息标题。
        content : str
            消息正文（Markdown）。

        Returns
        -------
        bool
            发送成功返回 True，失败返回 False。
        """
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": f"## {title}\n{content}",
            },
        }
        try:
            resp = requests.post(self._url, json=payload, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("errcode") != 0:
                logger.warning("微信推送返回错误: %s", data)
                return False
            return True
        except Exception as exc:
            logger.warning("微信推送失败: %s", exc)
            return False

    def test(self) -> bool:
        """发送测试消息。"""
        return self.send("测试通知", "Fund Analyzer 通知功能配置成功！")
```

创建 `src/fund_analyzer/notification/checker.py`：

```python
"""通知规则检查器。"""
from __future__ import annotations

import json
import logging
from datetime import date

from fund_analyzer.data.repository import FundRepository
from fund_analyzer.notification.sender import WeChatSender

logger = logging.getLogger(__name__)


class NotificationChecker:
    """检查通知规则并发送提醒。

    Parameters
    ----------
    repo : FundRepository
        数据访问仓储。
    sender : WeChatSender
        消息发送器。
    """

    def __init__(self, repo: FundRepository, sender: WeChatSender) -> None:
        self._repo = repo
        self._sender = sender

    def check_dip_due(self) -> int:
        """检查今日到期的定投计划并推送提醒。

        Returns
        -------
        int
            推送的提醒数。
        """
        plans = self._repo.get_active_dip_plans()
        today = date.today()
        due_plans = []

        for plan in plans:
            if self._is_due(plan, today):
                due_plans.append(plan)

        if not due_plans:
            return 0

        lines = []
        for p in due_plans:
            lines.append(f"- 基金 **{p.fund_code}**，金额 ¥{float(p.amount):,.2f}，频率 {p.frequency}")

        content = f"今日有 {len(due_plans)} 个定投计划到期：\n" + "\n".join(lines)
        self._sender.send("定投提醒", content)
        return len(due_plans)

    def check_drop_alert(self, threshold: float = -3.0) -> int:
        """检查自选基金中跌幅超阈值的并推送预警。

        Parameters
        ----------
        threshold : float
            跌幅阈值（百分比，如 -3.0 表示 -3%）。

        Returns
        -------
        int
            预警的基金数。
        """
        watchlist = self._repo.get_watchlist()
        if not watchlist:
            return 0

        fund_codes = [w.fund_code for w in watchlist]
        estimates = self._repo.get_latest_estimates(fund_codes)

        alerts = []
        for est in estimates:
            if est.estimate_return is not None and float(est.estimate_return) <= threshold:
                alerts.append(est)

        if not alerts:
            return 0

        lines = []
        for a in alerts:
            lines.append(f"- **{a.fund_code}** 估算跌幅 {float(a.estimate_return):.2f}%")

        content = f"以下自选基金跌幅超过 {threshold}%：\n" + "\n".join(lines)
        self._sender.send("大跌预警", content)
        return len(alerts)

    def check_rebalance(self) -> bool:
        """检查是否到调仓日并推送提醒。

        Returns
        -------
        bool
            是否发送了提醒。
        """
        from dateutil.relativedelta import relativedelta
        today = date.today()
        # 简单判断：每月第一个交易日或每季度首月
        # 核心仓季度调仓（1/4/7/10月），卫星仓月度调仓
        messages = []
        if today.day <= 5:
            messages.append("卫星仓月度调仓窗口已到，请查看调仓建议")
            if today.month in (1, 4, 7, 10):
                messages.append("核心仓季度调仓窗口已到，请查看调仓建议")

        if not messages:
            return False

        content = "\n".join(f"- {m}" for m in messages)
        self._sender.send("调仓提醒", content)
        return True

    def check_all(self) -> dict:
        """执行所有启用的规则检查。"""
        results = {}
        rules = self._repo.get_notification_rules()

        for rule in rules:
            if not rule.enabled:
                continue
            params = rule.params if rule.params else {}

            if rule.rule_type == "dip_reminder":
                results["dip_reminder"] = self.check_dip_due()
            elif rule.rule_type == "drop_alert":
                threshold = params.get("threshold", -3.0)
                results["drop_alert"] = self.check_drop_alert(threshold)
            elif rule.rule_type == "rebalance_alert":
                results["rebalance_alert"] = self.check_rebalance()

        return results

    @staticmethod
    def _is_due(plan, today: date) -> bool:
        """判断定投计划今日是否到期。"""
        if plan.frequency == "weekly":
            return today.weekday() == plan.start_date.weekday()
        elif plan.frequency == "biweekly":
            delta = (today - plan.start_date).days
            return delta >= 0 and delta % 14 == 0
        elif plan.frequency == "monthly":
            return today.day == plan.start_date.day
        return False
```

- [ ] **Step 2: 编写测试**

创建 `tests/test_notification.py`：

```python
"""消息提醒测试。"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import (
    Base, DipPlan, FundEstimate, FundWatchlist,
    NotificationConfig, NotificationRule,
)
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.notification.sender import WeChatSender
from fund_analyzer.notification.checker import NotificationChecker


@pytest.fixture(scope="module")
def engine():
    _engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)
    _engine.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()


@pytest.fixture()
def repo(session):
    return FundRepository(session)


class TestWeChatSender:
    def test_send_success(self, monkeypatch):
        sender = WeChatSender("https://example.com/webhook")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"errcode": 0}
        mock_resp.raise_for_status = MagicMock()
        monkeypatch.setattr("fund_analyzer.notification.sender.requests.post", lambda *a, **kw: mock_resp)

        assert sender.send("标题", "内容") is True

    def test_send_failure(self, monkeypatch):
        sender = WeChatSender("https://example.com/webhook")
        monkeypatch.setattr(
            "fund_analyzer.notification.sender.requests.post",
            MagicMock(side_effect=Exception("network error")),
        )
        assert sender.send("标题", "内容") is False


class TestNotificationChecker:
    def test_check_dip_due(self, repo, session):
        today = date.today()
        session.add(DipPlan(
            fund_code="DIP001",
            amount=Decimal("1000"),
            frequency="weekly",
            start_date=today,
            status="active",
            smart_dip=False,
        ))
        session.flush()

        sender = MagicMock()
        sender.send = MagicMock(return_value=True)
        checker = NotificationChecker(repo, sender)
        count = checker.check_dip_due()
        assert count == 1
        sender.send.assert_called_once()

    def test_check_drop_alert(self, repo, session):
        session.add(FundWatchlist(
            fund_code="DROP001", fund_name="跌基", group_name="默认",
            added_at=datetime.now(),
        ))
        session.add(FundEstimate(
            fund_code="DROP001", estimate_date=date.today(),
            estimate_return=Decimal("-5.00"),
        ))
        session.flush()

        sender = MagicMock()
        sender.send = MagicMock(return_value=True)
        checker = NotificationChecker(repo, sender)
        count = checker.check_drop_alert(threshold=-3.0)
        assert count == 1
        sender.send.assert_called_once()
```

- [ ] **Step 3: 运行测试**

Run: `poetry run pytest tests/test_notification.py -v`
Expected: ALL PASS

---

### Task 9: 消息提醒 — UI 与 CLI

**Files:**
- Modify: `src/fund_analyzer/ui/views/settings.py`
- Modify: `src/fund_analyzer/cli/app.py`

- [ ] **Step 1: 在设置页面添加通知配置区域**

在 `settings.py` 的 `render()` 函数中，在数据同步部分之后添加：

```python
    st.divider()
    st.subheader("通知设置")

    repo = get_repo()
    config = repo.get_notification_config()
    current_url = config.webhook_url if config else ""
    current_enabled = config.enabled if config else False

    webhook_url = st.text_input("企业微信 Webhook URL", value=current_url)
    notify_enabled = st.checkbox("启用通知", value=current_enabled)

    col_save, col_test = st.columns(2)
    with col_save:
        if st.button("保存通知配置"):
            repo.save_notification_config(webhook_url, notify_enabled)
            commit()
            st.success("通知配置已保存")

    with col_test:
        if st.button("发送测试消息"):
            if webhook_url:
                from fund_analyzer.notification.sender import WeChatSender
                sender = WeChatSender(webhook_url)
                if sender.test():
                    st.success("测试消息发送成功！")
                else:
                    st.error("测试消息发送失败，请检查 Webhook URL")
            else:
                st.warning("请先输入 Webhook URL")

    # 通知规则配置
    st.subheader("通知规则")
    import json

    rules = repo.get_notification_rules()
    rule_map = {r.rule_type: r for r in rules}

    dip_rule = rule_map.get("dip_reminder")
    dip_enabled = st.checkbox("定投到期提醒", value=dip_rule.enabled if dip_rule else True)

    drop_rule = rule_map.get("drop_alert")
    drop_enabled = st.checkbox("大跌预警", value=drop_rule.enabled if drop_rule else True)
    drop_threshold = st.number_input(
        "跌幅阈值(%)",
        value=float(drop_rule.params.get("threshold", -3)) if drop_rule and drop_rule.params else -3.0,
        step=0.5,
    )

    rebalance_rule = rule_map.get("rebalance_alert")
    rebalance_enabled = st.checkbox("调仓提醒", value=rebalance_rule.enabled if rebalance_rule else True)

    if st.button("保存规则"):
        repo.save_notification_rule("dip_reminder", {}, dip_enabled)
        repo.save_notification_rule("drop_alert", {"threshold": drop_threshold}, drop_enabled)
        repo.save_notification_rule("rebalance_alert", {}, rebalance_enabled)
        commit()
        st.success("通知规则已保存")
```

- [ ] **Step 2: 在 CLI 中添加 notify 命令组**

```python
notify_app = typer.Typer(name="notify", help="通知管理")
app.add_typer(notify_app)


@notify_app.command("test")
def notify_test():
    """发送测试通知。"""
    session = _get_session()
    repo = _get_repo(session)
    config = repo.get_notification_config()
    if not config or not config.webhook_url:
        console.print("[red]未配置通知 Webhook URL[/red]")
        raise typer.Exit(code=1)

    from fund_analyzer.notification.sender import WeChatSender
    sender = WeChatSender(config.webhook_url)
    if sender.test():
        console.print("[green]测试消息发送成功！[/green]")
    else:
        console.print("[red]测试消息发送失败[/red]")


@notify_app.command("check")
def notify_check():
    """执行通知规则检查。"""
    session = _get_session()
    repo = _get_repo(session)
    config = repo.get_notification_config()
    if not config or not config.webhook_url:
        console.print("[red]未配置通知 Webhook URL[/red]")
        raise typer.Exit(code=1)

    from fund_analyzer.notification.sender import WeChatSender
    from fund_analyzer.notification.checker import NotificationChecker
    sender = WeChatSender(config.webhook_url)
    checker = NotificationChecker(repo, sender)
    results = checker.check_all()

    for rule_type, count in results.items():
        console.print(f"  {rule_type}: 推送 {count} 条")
    console.print("[green]通知检查完成[/green]")
```

---

## 功能四：分红数据

### Task 10: 分红数据 — 数据模型与数据访问

**Files:**
- Modify: `src/fund_analyzer/data/models.py`
- Modify: `src/fund_analyzer/data/repository.py`
- Create: `tests/test_dividend.py`

- [ ] **Step 1: 在 models.py 新增 FundDividend 模型**

在 `NotificationRule` 之后添加：

```python
# ---------------------------------------------------------------------------
# 14. FundDividend — 基金分红记录
# ---------------------------------------------------------------------------

class FundDividend(Base):
    """基金分红记录表。

    复合主键：(fund_code, ex_date)
    """

    __tablename__ = "fund_dividend"

    fund_code: Mapped[str] = mapped_column(String(20), primary_key=True)
    ex_date: Mapped[date] = mapped_column(Date, primary_key=True)
    dividend_per_unit: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4), nullable=True
    )
    record_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    pay_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    dividend_type: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    def __repr__(self) -> str:
        return f"<FundDividend fund_code={self.fund_code!r} ex_date={self.ex_date}>"
```

- [ ] **Step 2: 在 repository.py 中新增分红方法**

导入 `FundDividend`，然后添加：

```python
    # -----------------------------------------------------------------------
    # FundDividend — 分红记录
    # -----------------------------------------------------------------------

    def upsert_dividends(self, fund_code: str, rows: list[dict]) -> None:
        """批量插入或更新分红记录。"""
        for row in rows:
            key = (fund_code, row["ex_date"])
            obj = self._session.get(FundDividend, key)
            if obj is None:
                obj = FundDividend(fund_code=fund_code, **row)
                self._session.add(obj)
            else:
                for k, v in row.items():
                    if k != "ex_date":
                        setattr(obj, k, v)
        self._session.flush()

    def get_dividends(
        self, fund_code: str, start_date: date | None = None
    ) -> list[FundDividend]:
        """查询基金分红历史。"""
        stmt = select(FundDividend).where(FundDividend.fund_code == fund_code)
        if start_date is not None:
            stmt = stmt.where(FundDividend.ex_date >= start_date)
        stmt = stmt.order_by(FundDividend.ex_date.desc())
        return list(self._session.execute(stmt).scalars().all())
```

- [ ] **Step 3: 编写测试**

创建 `tests/test_dividend.py`：

```python
"""分红数据测试。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundDividend
from fund_analyzer.data.repository import FundRepository


@pytest.fixture(scope="module")
def engine():
    _engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)
    _engine.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()


@pytest.fixture()
def repo(session):
    return FundRepository(session)


class TestUpsertDividends:
    def test_insert(self, repo, session):
        repo.upsert_dividends("DIV001", [
            {"ex_date": date(2025, 6, 15), "dividend_per_unit": Decimal("0.50"), "dividend_type": "现金分红"},
        ])
        result = session.get(FundDividend, ("DIV001", date(2025, 6, 15)))
        assert result is not None
        assert result.dividend_per_unit == Decimal("0.50")

    def test_update(self, repo, session):
        session.add(FundDividend(fund_code="DIV002", ex_date=date(2025, 1, 1), dividend_per_unit=Decimal("0.10")))
        session.flush()
        repo.upsert_dividends("DIV002", [
            {"ex_date": date(2025, 1, 1), "dividend_per_unit": Decimal("0.20")},
        ])
        session.expire_all()
        result = session.get(FundDividend, ("DIV002", date(2025, 1, 1)))
        assert result.dividend_per_unit == Decimal("0.20")


class TestGetDividends:
    def test_returns_ordered(self, repo, session):
        session.add_all([
            FundDividend(fund_code="DIV003", ex_date=date(2025, 1, 1), dividend_per_unit=Decimal("0.10")),
            FundDividend(fund_code="DIV003", ex_date=date(2025, 6, 1), dividend_per_unit=Decimal("0.20")),
        ])
        session.flush()
        results = repo.get_dividends("DIV003")
        assert len(results) == 2
        assert results[0].ex_date > results[1].ex_date

    def test_filter_by_start_date(self, repo, session):
        session.add_all([
            FundDividend(fund_code="DIV004", ex_date=date(2024, 1, 1)),
            FundDividend(fund_code="DIV004", ex_date=date(2025, 6, 1)),
        ])
        session.flush()
        results = repo.get_dividends("DIV004", start_date=date(2025, 1, 1))
        assert len(results) == 1
```

- [ ] **Step 4: 运行测试**

Run: `poetry run pytest tests/test_dividend.py -v`
Expected: ALL PASS

---

### Task 11: 分红数据 — 采集与同步

**Files:**
- Modify: `src/fund_analyzer/data/fetcher.py`
- Modify: `src/fund_analyzer/data/sync.py`

- [ ] **Step 0: 提取日期和数值转换工具函数到 fetcher.py**

将 `sync.py` 中的 `_to_date` 和 `_to_decimal` 函数复制到 `fetcher.py` 中作为模块级私有函数（或提取到 `data/utils.py` 供两个模块共享）：

```python
def _to_date(value: object) -> date | None:
    """将多种格式转为 date 对象。"""
    if isinstance(value, date):
        return value
    if isinstance(value, datetime):
        return value.date()
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None

def _to_decimal(value: object) -> Decimal | None:
    """将数值转为 Decimal。"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None
```

- [ ] **Step 1: 在 FundFetcher 中新增分红采集方法**

```python
    # ------------------------------------------------------------------
    # 分红数据采集
    # ------------------------------------------------------------------

    def fetch_fund_dividend(self, fund_code: str) -> list[dict] | None:
        """获取基金历史分红记录。

        Parameters
        ----------
        fund_code:
            基金代码。

        Returns
        -------
        list[dict] | None
            分红记录列表，失败时返回 None。
        """
        df = self._call_with_retry(ak.fund_open_fund_info_em, symbol=fund_code, indicator="分红送配详情")
        if df is None or df.empty:
            return None

        results = []
        for _, row in df.iterrows():
            try:
                record = {}
                ex_date_val = row.get("除息日", row.get("权益登记日"))
                if ex_date_val is not None:
                    record["ex_date"] = _to_date(ex_date_val) if not isinstance(ex_date_val, date) else ex_date_val
                else:
                    continue

                div_val = row.get("每份分红", row.get("每10份分红"))
                if div_val is not None:
                    # akshare 返回的可能是"每10份分红"，需要除以10
                    col_name = "每份分红" if "每份分红" in row.index else "每10份分红"
                    divisor = 1 if col_name == "每份分红" else 10
                    record["dividend_per_unit"] = _to_decimal(div_val) / divisor if _to_decimal(div_val) else None

                record_date = row.get("权益登记日")
                if record_date is not None:
                    record["record_date"] = _to_date(record_date)

                pay_date = row.get("红利发放日")
                if pay_date is not None:
                    record["pay_date"] = _to_date(pay_date)

                record["dividend_type"] = "现金分红"
                results.append(record)
            except Exception as exc:
                logger.debug("解析分红记录失败(%s): %s", fund_code, exc)
                continue

        return results if results else None
```

> 注：`_to_date` 和 `_to_decimal` 函数需要从 `sync.py` 中提取到公共位置，或者在 fetcher.py 中重新实现简单版本。

- [ ] **Step 2: 在 sync.py 的 sync_all 中加入分红同步**

在 `sync_fund_nav` 调用之后，添加分红同步逻辑：

```python
    def sync_fund_dividend(self, fund_code: str) -> int:
        """同步基金分红记录。

        Returns
        -------
        同步的分红记录数。
        """
        records = self._fetcher.fetch_fund_dividend(fund_code)
        if not records:
            return 0
        self._repo.upsert_dividends(fund_code, records)
        return len(records)
```

在 `sync_all` 方法中，净值同步循环内，在 `sync_fund_nav` 之后添加：

```python
            # 顺带同步分红记录
            try:
                self.sync_fund_dividend(code)
            except Exception as exc:
                warnings.append(f"分红同步失败 {code}: {exc}")
```

---

## 功能五：费率差异化

### Task 12: 费率差异化 — 数据模型与数据访问

**Files:**
- Modify: `src/fund_analyzer/data/models.py`
- Modify: `src/fund_analyzer/data/repository.py`
- Create: `tests/test_fee_schedule.py`

- [ ] **Step 1: 在 models.py 新增 FundFeeSchedule 模型**

```python
# ---------------------------------------------------------------------------
# 15. FundFeeSchedule — 基金费率阶梯表
# ---------------------------------------------------------------------------

class FundFeeSchedule(Base):
    """基金申购/赎回费率阶梯表。

    主键：id（自增）
    唯一约束：(fund_code, fee_type, min_holding_days)
    """

    __tablename__ = "fund_fee_schedule"
    __table_args__ = (
        Index("uq_fee_schedule", "fund_code", "fee_type", "min_holding_days", unique=True),
        Index("ix_fee_fund_type", "fund_code", "fee_type"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fund_code: Mapped[str] = mapped_column(String(20), nullable=False)
    fee_type: Mapped[str] = mapped_column(String(20), nullable=False)
    min_holding_days: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_holding_days: Mapped[int] = mapped_column(Integer, nullable=False, default=999999)
    fee_rate: Mapped[Decimal] = mapped_column(Numeric(8, 6), nullable=False)
    min_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)
    max_amount: Mapped[Optional[Decimal]] = mapped_column(Numeric(14, 2), nullable=True)

    def __repr__(self) -> str:
        return f"<FundFeeSchedule fund_code={self.fund_code!r} {self.fee_type} rate={self.fee_rate}>"
```

- [ ] **Step 2: 在 repository.py 新增费率方法**

导入 `FundFeeSchedule`，然后添加：

```python
    # -----------------------------------------------------------------------
    # FundFeeSchedule — 费率阶梯
    # -----------------------------------------------------------------------

    def upsert_fee_schedule(self, fund_code: str, schedules: list[dict]) -> None:
        """批量插入或更新费率阶梯。"""
        for row in schedules:
            stmt = select(FundFeeSchedule).where(
                and_(
                    FundFeeSchedule.fund_code == fund_code,
                    FundFeeSchedule.fee_type == row["fee_type"],
                    FundFeeSchedule.min_holding_days == row.get("min_holding_days", 0),
                )
            )
            obj = self._session.execute(stmt).scalar_one_or_none()
            if obj is None:
                obj = FundFeeSchedule(fund_code=fund_code, **row)
                self._session.add(obj)
            else:
                for k, v in row.items():
                    setattr(obj, k, v)
        self._session.flush()

    def get_fee_rate(
        self,
        fund_code: str,
        fee_type: str,
        holding_days: int | None = None,
        amount: float | None = None,
    ) -> Decimal | None:
        """查询实际适用费率。

        Parameters
        ----------
        fund_code : str
            基金代码。
        fee_type : str
            "purchase" 或 "redemption"。
        holding_days : int | None
            持有天数（赎回费用时使用）。
        amount : float | None
            申购金额（申购费用时使用）。

        Returns
        -------
        Decimal | None
            适用费率，无数据时返回 None。
        """
        stmt = select(FundFeeSchedule).where(
            and_(
                FundFeeSchedule.fund_code == fund_code,
                FundFeeSchedule.fee_type == fee_type,
            )
        )

        if fee_type == "redemption" and holding_days is not None:
            stmt = stmt.where(
                and_(
                    FundFeeSchedule.min_holding_days <= holding_days,
                    FundFeeSchedule.max_holding_days > holding_days,
                )
            )
        elif fee_type == "purchase" and amount is not None:
            stmt = stmt.where(
                or_(
                    FundFeeSchedule.min_amount.is_(None),
                    and_(
                        FundFeeSchedule.min_amount <= amount,
                        or_(
                            FundFeeSchedule.max_amount.is_(None),
                            FundFeeSchedule.max_amount > amount,
                        ),
                    ),
                )
            )

        stmt = stmt.order_by(FundFeeSchedule.min_holding_days.asc()).limit(1)
        result = self._session.execute(stmt).scalar_one_or_none()
        return result.fee_rate if result else None
```

- [ ] **Step 3: 编写测试**

创建 `tests/test_fee_schedule.py`：

```python
"""费率差异化测试。"""
from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, FundFeeSchedule
from fund_analyzer.data.repository import FundRepository


@pytest.fixture(scope="module")
def engine():
    _engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)
    _engine.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()


@pytest.fixture()
def repo(session):
    return FundRepository(session)


class TestUpsertFeeSchedule:
    def test_insert(self, repo, session):
        repo.upsert_fee_schedule("FEE001", [
            {"fee_type": "redemption", "min_holding_days": 0, "max_holding_days": 7, "fee_rate": Decimal("0.015000")},
            {"fee_type": "redemption", "min_holding_days": 7, "max_holding_days": 365, "fee_rate": Decimal("0.005000")},
            {"fee_type": "redemption", "min_holding_days": 365, "max_holding_days": 999999, "fee_rate": Decimal("0.000000")},
        ])
        from sqlalchemy import select
        stmt = select(FundFeeSchedule).where(FundFeeSchedule.fund_code == "FEE001")
        results = list(session.execute(stmt).scalars().all())
        assert len(results) == 3


class TestGetFeeRate:
    def test_redemption_by_holding_days(self, repo, session):
        repo.upsert_fee_schedule("FEE002", [
            {"fee_type": "redemption", "min_holding_days": 0, "max_holding_days": 7, "fee_rate": Decimal("0.015000")},
            {"fee_type": "redemption", "min_holding_days": 7, "max_holding_days": 365, "fee_rate": Decimal("0.005000")},
            {"fee_type": "redemption", "min_holding_days": 365, "max_holding_days": 999999, "fee_rate": Decimal("0.000000")},
        ])

        rate_3d = repo.get_fee_rate("FEE002", "redemption", holding_days=3)
        assert rate_3d == Decimal("0.015000")

        rate_30d = repo.get_fee_rate("FEE002", "redemption", holding_days=30)
        assert rate_30d == Decimal("0.005000")

        rate_400d = repo.get_fee_rate("FEE002", "redemption", holding_days=400)
        assert rate_400d == Decimal("0.000000")

    def test_not_found_returns_none(self, repo):
        result = repo.get_fee_rate("NONEXIST", "purchase")
        assert result is None
```

- [ ] **Step 4: 运行测试**

Run: `poetry run pytest tests/test_fee_schedule.py -v`
Expected: ALL PASS

---

### Task 13: 费率差异化 — 回测引擎集成

**Files:**
- Modify: `src/fund_analyzer/backtest/engine.py`

- [ ] **Step 1: 修改 BacktestEngine 的费率计算逻辑**

在 `BacktestEngine.__init__` 中保留 `buy_fee` 和 `sell_fee` 作为默认 fallback 值。

在调仓逻辑中（卖出部分），将固定费率改为动态查询：

```python
def _get_sell_fee_rate(self, fund_code: str, holding_days: int) -> float:
    """获取卖出费率，优先查数据库，无数据时使用默认值。"""
    rate = self._repo.get_fee_rate(fund_code, "redemption", holding_days=holding_days)
    if rate is not None:
        return float(rate)
    return self.sell_fee

def _get_buy_fee_rate(self, fund_code: str, amount: float) -> float:
    """获取买入费率，优先查数据库，无数据时使用默认值。"""
    rate = self._repo.get_fee_rate(fund_code, "purchase", amount=amount)
    if rate is not None:
        return float(rate)
    return self.buy_fee
```

在现有调仓方法中，将 `self.sell_fee` 替换为 `self._get_sell_fee_rate(fund_code, holding_days)`，将 `self.buy_fee` 替换为 `self._get_buy_fee_rate(fund_code, amount)`。

- [ ] **Step 2: 在 test_fee_schedule.py 中添加回测集成测试**

```python
class TestBacktestFeeIntegration:
    def test_get_sell_fee_rate_with_data(self, repo, session):
        """有费率数据时使用实际费率。"""
        repo.upsert_fee_schedule("BT001", [
            {"fee_type": "redemption", "min_holding_days": 0, "max_holding_days": 7, "fee_rate": Decimal("0.015000")},
            {"fee_type": "redemption", "min_holding_days": 7, "max_holding_days": 999999, "fee_rate": Decimal("0.001000")},
        ])
        rate = repo.get_fee_rate("BT001", "redemption", holding_days=3)
        assert rate == Decimal("0.015000")
        rate = repo.get_fee_rate("BT001", "redemption", holding_days=30)
        assert rate == Decimal("0.001000")

    def test_get_fee_rate_fallback(self, repo):
        """无费率数据时返回 None，由调用方使用默认值。"""
        rate = repo.get_fee_rate("NO_DATA", "redemption", holding_days=30)
        assert rate is None
```

- [ ] **Step 3: 运行测试**

Run: `poetry run pytest tests/test_fee_schedule.py -v`
Expected: ALL PASS

---

## 功能六：风险测评

### Task 14: 风险测评 — 数据模型

**Files:**
- Modify: `src/fund_analyzer/data/models.py`
- Modify: `src/fund_analyzer/data/repository.py`

- [ ] **Step 1: 在 models.py 新增 RiskProfile 模型**

```python
# ---------------------------------------------------------------------------
# 16. RiskProfile — 风险评估记录
# ---------------------------------------------------------------------------

class RiskProfile(Base):
    """用户风险评估记录表。"""

    __tablename__ = "risk_profile"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    risk_level: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_label: Mapped[str] = mapped_column(String(20), nullable=False)
    core_ratio: Mapped[int] = mapped_column(Integer, nullable=False)
    satellite_ratio: Mapped[int] = mapped_column(Integer, nullable=False)
    assessment_date: Mapped[date] = mapped_column(Date, nullable=False)
    answers: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    def __repr__(self) -> str:
        return f"<RiskProfile level={self.risk_level} label={self.risk_label!r}>"
```

- [ ] **Step 2: 在 repository.py 新增风险评估方法**

导入 `RiskProfile`，然后添加：

```python
    # -----------------------------------------------------------------------
    # RiskProfile — 风险评估
    # -----------------------------------------------------------------------

    def save_risk_profile(self, data: dict) -> RiskProfile:
        """保存风险评估结果。"""
        obj = RiskProfile(**data)
        self._session.add(obj)
        self._session.flush()
        return obj

    def get_latest_risk_profile(self) -> RiskProfile | None:
        """获取最新的风险评估结果。"""
        stmt = select(RiskProfile).order_by(RiskProfile.assessment_date.desc()).limit(1)
        return self._session.execute(stmt).scalar_one_or_none()
```

---

### Task 15: 风险测评 — 问卷与评估器

**Files:**
- Create: `src/fund_analyzer/risk/__init__.py`
- Create: `src/fund_analyzer/risk/questionnaire.py`
- Create: `src/fund_analyzer/risk/assessor.py`
- Create: `tests/test_risk.py`

- [ ] **Step 1: 创建风险模块**

创建 `src/fund_analyzer/risk/__init__.py`：

```python
"""风险评估模块。"""
```

创建 `src/fund_analyzer/risk/questionnaire.py`：

```python
"""风险评估问卷定义。"""
from __future__ import annotations

QUESTIONS: list[dict] = [
    {
        "id": "experience",
        "text": "您的投资经验有多长？",
        "options": [
            {"label": "没有投资经验", "score": 5},
            {"label": "1-3年", "score": 10},
            {"label": "3-5年", "score": 15},
            {"label": "5年以上", "score": 20},
        ],
    },
    {
        "id": "loss_tolerance",
        "text": "您能承受的最大投资亏损是多少？",
        "options": [
            {"label": "不能接受任何亏损", "score": 5},
            {"label": "亏损10%以内", "score": 10},
            {"label": "亏损20%以内", "score": 15},
            {"label": "亏损30%以内", "score": 18},
            {"label": "亏损30%以上也能接受", "score": 20},
        ],
    },
    {
        "id": "investment_horizon",
        "text": "您的投资期限预期是多长？",
        "options": [
            {"label": "1年以内", "score": 5},
            {"label": "1-3年", "score": 10},
            {"label": "3-5年", "score": 15},
            {"label": "5年以上", "score": 20},
        ],
    },
    {
        "id": "income_stability",
        "text": "您的收入来源稳定程度如何？",
        "options": [
            {"label": "不太稳定", "score": 5},
            {"label": "比较稳定", "score": 10},
            {"label": "非常稳定，且有较多储蓄", "score": 20},
        ],
    },
    {
        "id": "investment_goal",
        "text": "您的主要投资目标是什么？",
        "options": [
            {"label": "保值，跑赢通胀即可", "score": 5},
            {"label": "稳健增值，追求中等收益", "score": 10},
            {"label": "积极增值，愿意承担较大波动", "score": 15},
            {"label": "追求高收益，能承受大幅波动", "score": 20},
        ],
    },
]
```

创建 `src/fund_analyzer/risk/assessor.py`：

```python
"""风险评估计算器。"""
from __future__ import annotations


# 风险等级到仓位比例映射
RISK_LEVEL_MAP: dict[int, dict] = {
    1: {"label": "保守型", "core_ratio": 70, "satellite_ratio": 30},
    2: {"label": "稳健型", "core_ratio": 50, "satellite_ratio": 50},
    3: {"label": "平衡型", "core_ratio": 30, "satellite_ratio": 70},
    4: {"label": "进取型", "core_ratio": 20, "satellite_ratio": 80},
    5: {"label": "激进型", "core_ratio": 10, "satellite_ratio": 90},
}


class RiskAssessor:
    """风险评估计算器。"""

    def calculate_score(self, answers: dict[str, int]) -> int:
        """根据问卷答案计算总分。

        Parameters
        ----------
        answers : dict[str, int]
            题目ID到选择分数的映射。

        Returns
        -------
        int
            总分（0-100）。
        """
        return sum(answers.values())

    def score_to_level(self, score: int) -> int:
        """将分数映射到风险等级（1-5）。

        Parameters
        ----------
        score : int
            总分（0-100）。

        Returns
        -------
        int
            风险等级 1-5。
        """
        if score <= 25:
            return 1
        elif score <= 45:
            return 2
        elif score <= 65:
            return 3
        elif score <= 85:
            return 4
        else:
            return 5

    def get_recommended_ratios(self, level: int) -> tuple[int, int]:
        """获取建议的仓位比例。

        Parameters
        ----------
        level : int
            风险等级 1-5。

        Returns
        -------
        tuple[int, int]
            (core_ratio, satellite_ratio)。
        """
        info = RISK_LEVEL_MAP.get(level, RISK_LEVEL_MAP[3])
        return info["core_ratio"], info["satellite_ratio"]

    def get_level_label(self, level: int) -> str:
        """获取风险等级标签。"""
        info = RISK_LEVEL_MAP.get(level, RISK_LEVEL_MAP[3])
        return info["label"]
```

- [ ] **Step 2: 编写测试**

创建 `tests/test_risk.py`：

```python
"""风险测评测试。"""
from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fund_analyzer.data.models import Base, RiskProfile
from fund_analyzer.data.repository import FundRepository
from fund_analyzer.risk.assessor import RiskAssessor
from fund_analyzer.risk.questionnaire import QUESTIONS


@pytest.fixture(scope="module")
def engine():
    _engine = create_engine("sqlite:///:memory:", echo=False)
    Base.metadata.create_all(_engine)
    yield _engine
    Base.metadata.drop_all(_engine)
    _engine.dispose()


@pytest.fixture()
def session(engine):
    with Session(engine) as s:
        yield s
        s.rollback()


@pytest.fixture()
def repo(session):
    return FundRepository(session)


class TestQuestionnaire:
    def test_has_questions(self):
        assert len(QUESTIONS) == 5

    def test_question_structure(self):
        for q in QUESTIONS:
            assert "id" in q
            assert "text" in q
            assert "options" in q
            assert len(q["options"]) >= 2
            for opt in q["options"]:
                assert "label" in opt
                assert "score" in opt


class TestRiskAssessor:
    def test_conservative_score(self):
        assessor = RiskAssessor()
        # 所有题选最低分
        answers = {q["id"]: q["options"][0]["score"] for q in QUESTIONS}
        score = assessor.calculate_score(answers)
        level = assessor.score_to_level(score)
        assert level == 1
        assert assessor.get_level_label(level) == "保守型"

    def test_aggressive_score(self):
        assessor = RiskAssessor()
        # 所有题选最高分
        answers = {q["id"]: q["options"][-1]["score"] for q in QUESTIONS}
        score = assessor.calculate_score(answers)
        level = assessor.score_to_level(score)
        assert level == 5
        assert assessor.get_level_label(level) == "激进型"

    def test_balanced_score(self):
        assessor = RiskAssessor()
        answers = {"experience": 10, "loss_tolerance": 15, "investment_horizon": 10, "income_stability": 10, "investment_goal": 10}
        score = assessor.calculate_score(answers)
        assert score == 55
        level = assessor.score_to_level(score)
        assert level == 3

    def test_get_recommended_ratios(self):
        assessor = RiskAssessor()
        core, sat = assessor.get_recommended_ratios(1)
        assert core == 70
        assert sat == 30
        core, sat = assessor.get_recommended_ratios(5)
        assert core == 10
        assert sat == 90


class TestRiskProfileRepository:
    def test_save_and_get(self, repo):
        repo.save_risk_profile({
            "risk_level": 3,
            "risk_label": "平衡型",
            "core_ratio": 30,
            "satellite_ratio": 70,
            "assessment_date": date(2026, 3, 20),
            "answers": {"experience": 10},
        })
        result = repo.get_latest_risk_profile()
        assert result is not None
        assert result.risk_level == 3
        assert result.risk_label == "平衡型"
```

- [ ] **Step 3: 运行测试**

Run: `poetry run pytest tests/test_risk.py -v`
Expected: ALL PASS

---

### Task 16: 风险测评 — UI 页面与配置写回

**Files:**
- Create: `src/fund_analyzer/ui/views/risk_assess.py`
- Modify: `src/fund_analyzer/ui/app.py`
- Modify: `src/fund_analyzer/config.py`

- [ ] **Step 1: 在 config.py 新增 save_config 函数**

在 `load_config` 之后添加：

```python
def save_config(path: str, settings: Settings) -> None:
    """将 Settings 写回 YAML 文件。"""
    from dataclasses import asdict
    config_path = Path(path)
    data = asdict(settings)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)
```

- [ ] **Step 2: 创建风险测评页面**

创建 `src/fund_analyzer/ui/views/risk_assess.py`：

```python
"""风险测评页面。"""
from __future__ import annotations

import json
from datetime import date

import streamlit as st

from fund_analyzer.risk.questionnaire import QUESTIONS
from fund_analyzer.risk.assessor import RiskAssessor, RISK_LEVEL_MAP
from fund_analyzer.ui.session import get_repo, get_settings, commit


def render() -> None:
    st.header("风险测评")

    repo = get_repo()

    # 显示历史评估结果
    latest = repo.get_latest_risk_profile()
    if latest:
        st.info(
            f"上次评估结果：**{latest.risk_label}**（等级{latest.risk_level}），"
            f"建议核心仓 {latest.core_ratio}% / 卫星仓 {latest.satellite_ratio}%，"
            f"评估日期 {latest.assessment_date}"
        )

    st.subheader("风险偏好问卷")
    st.caption("请根据您的实际情况选择最符合的选项")

    answers = {}
    for q in QUESTIONS:
        options = q["options"]
        labels = [opt["label"] for opt in options]
        selected = st.radio(q["text"], labels, key=f"risk_{q['id']}")
        selected_opt = next(opt for opt in options if opt["label"] == selected)
        answers[q["id"]] = selected_opt["score"]

    if st.button("提交评估", type="primary"):
        assessor = RiskAssessor()
        score = assessor.calculate_score(answers)
        level = assessor.score_to_level(score)
        label = assessor.get_level_label(level)
        core_ratio, satellite_ratio = assessor.get_recommended_ratios(level)

        # 保存评估结果
        repo.save_risk_profile({
            "risk_level": level,
            "risk_label": label,
            "core_ratio": core_ratio,
            "satellite_ratio": satellite_ratio,
            "assessment_date": date.today(),
            "answers": answers,
        })
        commit()

        # 展示结果
        st.success(f"评估完成！您的风险等级：**{label}**（得分 {score}）")

        col1, col2, col3 = st.columns(3)
        col1.metric("风险等级", f"{level}/5")
        col2.metric("建议核心仓", f"{core_ratio}%")
        col3.metric("建议卫星仓", f"{satellite_ratio}%")

        # 应用建议按钮
        settings = get_settings()
        current_core = settings.portfolio.core_ratio
        if core_ratio != current_core:
            st.warning(
                f"当前仓位配置为核心 {current_core}% / 卫星 {100 - current_core}%，"
                f"与建议不一致。"
            )
            if st.button("应用建议到配置"):
                from pathlib import Path
                from fund_analyzer.config import save_config
                settings.portfolio.core_ratio = core_ratio
                settings.portfolio.satellite_ratio = satellite_ratio
                for p in ["settings.yaml", "config/settings.yaml"]:
                    if Path(p).exists():
                        save_config(p, settings)
                        st.success(f"已更新配置文件 {p}")
                        st.cache_resource.clear()
                        break
```

- [ ] **Step 3: 在 app.py 中注册页面**

在 imports 中添加：

```python
from fund_analyzer.ui.views import risk_assess
```

在 `PAGES` 字典中添加：

```python
    "📋 风险测评": risk_assess.render,
```

---

### Task 17: 全量集成测试

**Files:**
- All test files

- [ ] **Step 1: 确保所有 models.py 导入一致**

确认 `repository.py` 的 import 语句包含所有新增模型：

```python
from fund_analyzer.data.models import (
    Base,
    FundInfo,
    FundNav,
    IndexQuote,
    FundHolding,
    IndustryMapping,
    PortfolioPosition,
    PortfolioTransaction,
    StrategySignal,
    DipPlan,
    FundEstimate,
    FundWatchlist,
    NotificationConfig,
    NotificationRule,
    FundDividend,
    FundFeeSchedule,
    RiskProfile,
)
```

- [ ] **Step 2: 运行全量测试**

Run: `poetry run pytest -v`
Expected: 所有现有测试（363 cases）+ 新增测试全部 PASS

- [ ] **Step 3: 运行覆盖率报告**

Run: `poetry run pytest --cov=fund_analyzer --cov-report=term-missing`
Expected: 覆盖率不低于现有水平

---

## 实现顺序总结

| 顺序 | 功能 | Tasks | 关键产出 |
|------|------|-------|---------|
| 1 | 实时估值 | Task 1-4 | FundEstimate 模型 + 双数据源采集 + 仪表盘估值列 |
| 2 | 自选关注 | Task 5-6 | FundWatchlist 模型 + 自选页面 + CLI |
| 3 | 消息提醒 | Task 7-9 | 通知配置/规则 + 微信发送器 + 检查器 + 设置页面 |
| 4 | 分红数据 | Task 10-11 | FundDividend 模型 + 采集同步 |
| 5 | 费率差异化 | Task 12-13 | FundFeeSchedule 模型 + 回测引擎动态费率 |
| 6 | 风险测评 | Task 14-16 | RiskProfile + 问卷 + 评估器 + UI |
| 7 | 集成验证 | Task 17 | 全量测试通过 |
