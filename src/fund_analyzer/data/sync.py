"""数据同步调度模块。

封装 FundFetcher 与 FundRepository，提供统一的数据同步入口。
支持基金列表、净值历史、指数行情的增量/全量同步。
"""
from __future__ import annotations

import datetime
import logging
from decimal import Decimal, InvalidOperation
from typing import Optional

from fund_analyzer.data.fetcher import FundFetcher
from fund_analyzer.data.repository import FundRepository

logger = logging.getLogger(__name__)

# 关键指数代码
_KEY_INDICES = ["000688", "000300"]

# NAV 异常跳变阈值（绝对涨跌幅超过此值时发出警告）
_NAV_JUMP_THRESHOLD = Decimal("0.15")


def _to_date(value: object) -> Optional[datetime.date]:
    """将字符串或 date-like 对象转换为 datetime.date。

    支持以下格式：
    - ``datetime.date`` / ``datetime.datetime``
    - ``"YYYY-MM-DD"``
    - ``"YYYYMMDD"``

    转换失败时返回 None 并记录警告。
    """
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.date()
    if isinstance(value, datetime.date):
        return value
    s = str(value).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    logger.warning("无法解析日期：%r", value)
    return None


def _to_decimal(value: object) -> Optional[Decimal]:
    """将数值转换为 Decimal，转换失败时返回 None。"""
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


class DataSyncer:
    """数据同步调度器。

    负责协调 FundFetcher（数据采集）与 FundRepository（数据持久化）之间的工作，
    提供基金列表、净值历史、指数行情的同步接口。

    Parameters
    ----------
    repo:
        数据仓储对象，负责数据库读写。
    fetcher:
        数据采集对象，负责从外部接口获取数据。
    """

    def __init__(self, repo: FundRepository, fetcher: FundFetcher) -> None:
        self._repo = repo
        self._fetcher = fetcher

    # ------------------------------------------------------------------
    # 公开同步方法
    # ------------------------------------------------------------------

    def sync_fund_list(self) -> int:
        """同步基金列表。

        通过 fetcher 获取开放式基金列表，逐条 upsert 到 repo，返回同步条数。

        Returns
        -------
        int
            成功 upsert 的基金数量。
        """
        funds = self._fetcher.fetch_fund_list()
        count = 0
        for fund in funds:
            try:
                self._repo.upsert_fund_info(fund)
                count += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "upsert_fund_info(%s) 失败：%s",
                    fund.get("fund_code", "?"),
                    exc,
                )
        logger.info("sync_fund_list 完成，共同步 %d 条", count)
        return count

    def sync_fund_nav(self, fund_code: str) -> list[str]:
        """同步指定基金的净值历史。

        1. 通过 fetcher 获取净值列表；
        2. 将 date 字符串解析为 datetime.date，nav/acc_nav/daily_return 转为 Decimal；
        3. 对连续净值做异常跳变检测（|涨跌幅| > 15% → 生成警告）；
        4. 批量 upsert 到 repo。

        Parameters
        ----------
        fund_code:
            基金代码。

        Returns
        -------
        list[str]
            警告信息列表（每条包含"异常"字样）。
        """
        raw_rows = self._fetcher.fetch_fund_nav(fund_code)
        if not raw_rows:
            logger.info("sync_fund_nav(%s)：未获取到数据", fund_code)
            return []

        warnings: list[str] = []
        parsed_rows: list[dict] = []

        prev_nav: Optional[Decimal] = None

        for raw in raw_rows:
            nav_date = _to_date(raw.get("date"))
            if nav_date is None:
                logger.warning("sync_fund_nav(%s)：跳过无效日期记录 %r", fund_code, raw)
                continue

            nav = _to_decimal(raw.get("nav"))
            acc_nav = _to_decimal(raw.get("acc_nav"))
            daily_return = _to_decimal(raw.get("daily_return"))

            # 异常跳变检测：与前一日净值相比
            if nav is not None and prev_nav is not None and prev_nav > Decimal("0"):
                jump = abs((nav - prev_nav) / prev_nav)
                if jump > _NAV_JUMP_THRESHOLD:
                    msg = (
                        f"[{fund_code}] {nav_date} 净值异常跳变："
                        f"前值={prev_nav}，当前={nav}，"
                        f"涨跌幅={jump:.2%}"
                    )
                    warnings.append(msg)
                    logger.warning(msg)

            prev_nav = nav

            parsed_rows.append(
                {
                    "date": nav_date,
                    "nav": nav,
                    "acc_nav": acc_nav,
                    "daily_return": daily_return,
                }
            )

        if parsed_rows:
            try:
                self._repo.upsert_fund_navs(fund_code, parsed_rows)
            except Exception as exc:  # noqa: BLE001
                logger.error("upsert_fund_navs(%s) 失败：%s", fund_code, exc)

        logger.info(
            "sync_fund_nav(%s) 完成，%d 条记录，%d 条警告",
            fund_code,
            len(parsed_rows),
            len(warnings),
        )
        return warnings

    def sync_index(self, index_code: str) -> int:
        """同步指定指数的行情数据。

        1. 通过 fetcher 获取指数日行情；
        2. 将 date 解析为 datetime.date，close 转为 Decimal；
        3. 基于相邻收盘价计算 daily_return（= (close_t / close_{t-1}) - 1）；
        4. 批量 upsert 到 repo。

        Parameters
        ----------
        index_code:
            指数代码，如 ``"000300"``。

        Returns
        -------
        int
            成功 upsert 的行情条数。
        """
        raw_rows = self._fetcher.fetch_index_daily(index_code)
        if not raw_rows:
            logger.info("sync_index(%s)：未获取到数据", index_code)
            return 0

        parsed_rows: list[dict] = []
        prev_close: Optional[Decimal] = None

        for raw in raw_rows:
            quote_date = _to_date(raw.get("date"))
            if quote_date is None:
                logger.warning("sync_index(%s)：跳过无效日期记录 %r", index_code, raw)
                continue

            close = _to_decimal(raw.get("close"))

            # 计算日涨跌幅
            daily_return: Optional[Decimal] = None
            if close is not None and prev_close is not None and prev_close > Decimal("0"):
                daily_return = (close / prev_close) - Decimal("1")

            prev_close = close

            parsed_rows.append(
                {
                    "date": quote_date,
                    "close": close,
                    "daily_return": daily_return,
                }
            )

        if parsed_rows:
            try:
                self._repo.upsert_index_quotes(index_code, parsed_rows)
            except Exception as exc:  # noqa: BLE001
                logger.error("upsert_index_quotes(%s) 失败：%s", index_code, exc)
                return 0

        logger.info("sync_index(%s) 完成，共同步 %d 条", index_code, len(parsed_rows))
        return len(parsed_rows)

    def sync_all(
        self,
        fund_codes: Optional[list[str]] = None,
        full: bool = False,
    ) -> dict:
        """全量/增量同步编排入口。

        执行顺序：
        1. 同步基金列表；
        2. 若 ``fund_codes`` 未指定，则从 repo 查询符合条件的基金；
           否则直接使用 ``fund_codes``；
        3. 逐基金同步净值；
        4. 同步关键指数（000688、000300）。

        Parameters
        ----------
        fund_codes:
            指定要同步净值的基金代码列表；``None`` 表示自动筛选符合条件的基金。
        full:
            保留参数，供未来实现全量重刷逻辑使用，当前版本不影响行为。

        Returns
        -------
        dict
            ``{"funds": int, "navs": int, "indices": int, "warnings": list}``
        """
        result: dict = {
            "funds": 0,
            "navs": 0,
            "indices": 0,
            "warnings": [],
        }

        # 1. 同步基金列表
        result["funds"] = self.sync_fund_list()

        # 2. 确定需要同步净值的基金代码
        if fund_codes is not None:
            codes_to_sync = list(fund_codes)
        else:
            try:
                eligible = self._repo.get_eligible_funds(
                    min_inception_years=3,
                    min_size_billion=1,
                    exclude_types=["货币型"],
                    as_of=datetime.date.today(),
                )
                codes_to_sync = [f.fund_code for f in eligible]
            except Exception as exc:  # noqa: BLE001
                logger.warning("get_eligible_funds 失败，跳过净值同步：%s", exc)
                codes_to_sync = []

        # 3. 逐基金同步净值
        total_nav_count = 0
        all_warnings: list[str] = []
        for code in codes_to_sync:
            try:
                warns = self.sync_fund_nav(code)
                all_warnings.extend(warns)
                total_nav_count += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("sync_fund_nav(%s) 出错：%s", code, exc)

        result["navs"] = total_nav_count

        # 4. 同步关键指数
        total_index_count = 0
        for idx_code in _KEY_INDICES:
            try:
                total_index_count += self.sync_index(idx_code)
            except Exception as exc:  # noqa: BLE001
                logger.warning("sync_index(%s) 出错：%s", idx_code, exc)

        result["indices"] = total_index_count
        result["warnings"] = all_warnings

        logger.info(
            "sync_all 完成：funds=%d, navs=%d, indices=%d, warnings=%d",
            result["funds"],
            result["navs"],
            result["indices"],
            len(all_warnings),
        )
        return result
