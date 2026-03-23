"""数据采集模块：封装 akshare API 调用，提供重试与限速功能。"""
from __future__ import annotations

import logging
import math
import threading
import time
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import Any

import pandas as pd

import akshare as ak

logger = logging.getLogger(__name__)

# akshare 内部使用 py_mini_racer（V8 引擎），不支持多线程并发调用
_akshare_lock = threading.Lock()


def _to_date(value: object) -> date_type | None:
    """将多种格式转为 date 对象。"""
    if isinstance(value, date_type):
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


class FundFetcher:
    """封装 akshare 数据采集，支持指数退避重试与请求间隔限速。

    Parameters
    ----------
    request_interval:
        每次 API 调用后的最短等待秒数，默认 0.5 秒。
    retry_count:
        最大重试次数（不含首次调用），默认 3 次。
    """

    def __init__(self, request_interval: float = 0.1, retry_count: int = 1) -> None:
        self.request_interval = request_interval
        self.retry_count = retry_count

    # ------------------------------------------------------------------
    # 内部工具方法
    # ------------------------------------------------------------------

    def _call_with_retry(self, func, *args, **kwargs) -> pd.DataFrame | None:
        """调用 akshare 函数，失败时以指数退避策略重试。

        Parameters
        ----------
        func:
            要调用的函数对象。
        *args / **kwargs:
            传递给 ``func`` 的位置参数与关键字参数。

        Returns
        -------
        pd.DataFrame | None
            成功时返回 DataFrame，所有重试均失败后返回 None。
        """
        last_exc: Exception | None = None
        for attempt in range(self.retry_count + 1):
            try:
                with _akshare_lock:
                    result = func(*args, **kwargs)
                # 请求成功后等待限速间隔
                time.sleep(self.request_interval)
                return result
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                if attempt < self.retry_count:
                    wait = self.request_interval * math.pow(2, attempt)
                    logger.warning(
                        "调用 %s 失败（第 %d 次），%.1f 秒后重试。原因：%s",
                        getattr(func, "__name__", str(func)),
                        attempt + 1,
                        wait,
                        exc,
                    )
                    time.sleep(wait)
                else:
                    logger.error(
                        "调用 %s 最终失败（共 %d 次尝试）。原因：%s",
                        getattr(func, "__name__", str(func)),
                        self.retry_count + 1,
                        exc,
                    )
        return None

    # ------------------------------------------------------------------
    # 公开数据采集方法
    # ------------------------------------------------------------------

    def fetch_fund_list(self) -> list[dict]:
        """获取开放式基金列表。

        调用 ``ak.fund_open_fund_info_em()``，返回包含
        ``fund_code`` 与 ``fund_name`` 的字典列表。

        Returns
        -------
        list[dict]
            例：``[{"fund_code": "110011", "fund_name": "易方达蓝筹精选"}, ...]``
            失败时返回空列表。
        """
        try:
            df: pd.DataFrame | None = self._call_with_retry(ak.fund_name_em)
            if df is None or df.empty:
                return []
            result: list[dict] = []
            for _, row in df.iterrows():
                result.append({
                    "fund_code": str(row.iloc[0]),
                    "fund_name": str(row.iloc[2]),
                    "fund_type": str(row.iloc[3]) if len(row) > 3 else None,
                })
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_fund_list 异常：%s", exc)
            return []

    def fetch_fund_nav(
        self,
        fund_code: str,
        start_date: str | None = None,
    ) -> list[dict]:
        """获取基金单位净值历史。

        调用 ``ak.fund_open_fund_info_em(symbol=fund_code, indicator="单位净值走势", period="成立来")``。

        Parameters
        ----------
        fund_code:
            基金代码，如 ``"110011"``。
        start_date:
            起始日期字符串（``"YYYY-MM-DD"``），``None`` 表示取全部历史。

        Returns
        -------
        list[dict]
            字段：``date``（str）、``nav``（float）、``acc_nav``（float）、
            ``daily_return``（float，已由百分比转为小数）。
            失败时返回空列表。
        """
        try:
            df: pd.DataFrame | None = self._call_with_retry(
                ak.fund_open_fund_info_em,
                symbol=fund_code,
                indicator="单位净值走势",
                period="成立来",
            )
            if df is None or df.empty:
                return []

            # 若提供了起始日期，则过滤
            if start_date is not None:
                date_col = df.columns[0]
                df = df[df[date_col].astype(str) >= start_date]

            result: list[dict] = []
            for _, row in df.iterrows():
                values = row.tolist()
                # 解析 daily_return：第3列（索引2），百分比→小数，NaN→None
                raw_return: Any = values[2] if len(values) > 2 else float("nan")
                try:
                    daily_return_val = float(raw_return)
                    if math.isnan(daily_return_val):
                        daily_return: float | None = None
                    else:
                        daily_return = daily_return_val / 100.0
                except (TypeError, ValueError):
                    daily_return = None

                # nav：NaN → None
                def _safe_float(v: Any) -> float | None:
                    try:
                        fv = float(v)
                        return None if math.isnan(fv) else fv
                    except (TypeError, ValueError):
                        return None

                result.append({
                    "date": str(values[0]),
                    "nav": _safe_float(values[1]),
                    "acc_nav": None,
                    "daily_return": daily_return,
                })
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_fund_nav(%s) 异常：%s", fund_code, exc)
            return []

    def fetch_index_daily(
        self,
        index_code: str,
        start_date: str = "20100101",
    ) -> list[dict]:
        """获取指数日行情。

        调用 ``ak.stock_zh_index_daily_em(symbol=index_code, start_date=start_date)``。

        Parameters
        ----------
        index_code:
            指数代码，如 ``"sh000300"``。
        start_date:
            起始日期字符串（``"YYYYMMDD"``），默认 ``"20100101"``。

        Returns
        -------
        list[dict]
            字段：``date``（str）、``close``（float）。
            失败时返回空列表。
        """
        # akshare 要求指数代码带市场前缀
        _index_prefix_map = {
            "000300": "sh000300",
            "000688": "sh000688",
            "000001": "sh000001",
            "399001": "sz399001",
            "399006": "sz399006",
        }
        symbol = _index_prefix_map.get(index_code, f"sh{index_code}")

        try:
            df: pd.DataFrame | None = self._call_with_retry(
                ak.stock_zh_index_daily_em,
                symbol=symbol,
                start_date=start_date,
            )
            if df is None or df.empty:
                return []

            result: list[dict] = []
            for _, row in df.iterrows():
                values = row.tolist()
                try:
                    close_val = float(values[1]) if len(values) > 1 else None
                except (TypeError, ValueError):
                    close_val = None
                result.append({
                    "date": str(values[0]),
                    "close": close_val,
                })
            return result
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_index_daily(%s) 异常：%s", index_code, exc)
            return []

    def fetch_fund_holding(self, fund_code: str, year: str) -> list[dict]:
        """获取基金持仓数据。

        调用 ``ak.fund_portfolio_hold_em(symbol=fund_code, date=year)``。

        Parameters
        ----------
        fund_code:
            基金代码。
        year:
            报告期年份，如 ``"2023"``。

        Returns
        -------
        list[dict]
            每行持仓数据对应一个字典，列名为键。
            失败时返回空列表。
        """
        try:
            df: pd.DataFrame | None = self._call_with_retry(
                ak.fund_portfolio_hold_em,
                symbol=fund_code,
                date=year,
            )
            if df is None or df.empty:
                return []
            return df.to_dict(orient="records")
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_fund_holding(%s, %s) 异常：%s", fund_code, year, exc)
            return []

    def fetch_industry_classification(self) -> list[dict]:
        """获取行业分类数据。

        调用 ``ak.stock_board_industry_name_em()``。

        Returns
        -------
        list[dict]
            每行行业数据对应一个字典，列名为键。
            失败时返回空列表。
        """
        try:
            df: pd.DataFrame | None = self._call_with_retry(
                ak.stock_board_industry_name_em
            )
            if df is None or df.empty:
                return []
            return df.to_dict(orient="records")
        except Exception as exc:  # noqa: BLE001
            logger.warning("fetch_industry_classification 异常：%s", exc)
            return []

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

        def _fetch_detail(**kwargs):
            return ak.fund_individual_detail_info_em(**kwargs)

        try:
            df = self._call_with_retry(
                _fetch_detail,
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
                if ex_date_val is None:
                    continue
                parsed_date = _to_date(ex_date_val)
                if parsed_date is None:
                    continue
                record["ex_date"] = parsed_date

                div_val = row.get("每份分红", row.get("每10份分红"))
                if div_val is not None:
                    col_name = "每份分红" if "每份分红" in row.index else "每10份分红"
                    divisor = 1 if col_name == "每份分红" else 10
                    decimal_val = _to_decimal(div_val)
                    record["dividend_per_unit"] = decimal_val / divisor if decimal_val else None

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
