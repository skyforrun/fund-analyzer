"""数据采集模块：封装 akshare API 调用，提供重试与限速功能。"""
from __future__ import annotations

import logging
import math
import time
from typing import Any

import pandas as pd

import akshare as ak

logger = logging.getLogger(__name__)


class FundFetcher:
    """封装 akshare 数据采集，支持指数退避重试与请求间隔限速。

    Parameters
    ----------
    request_interval:
        每次 API 调用后的最短等待秒数，默认 0.5 秒。
    retry_count:
        最大重试次数（不含首次调用），默认 3 次。
    """

    def __init__(self, request_interval: float = 0.5, retry_count: int = 3) -> None:
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
            df: pd.DataFrame | None = self._call_with_retry(ak.fund_open_fund_info_em)
            if df is None or df.empty:
                return []
            result: list[dict] = []
            for _, row in df.iterrows():
                result.append({
                    "fund_code": str(row.iloc[0]),
                    "fund_name": str(row.iloc[1]),
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

        调用 ``ak.fund_open_fund_daily_em(fund=fund_code, indicator="单位净值走势")``。

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
                ak.fund_open_fund_daily_em,
                fund=fund_code,
                indicator="单位净值走势",
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
                # 解析 daily_return：第4列（索引3），百分比→小数，NaN→None
                raw_return: Any = values[3] if len(values) > 3 else float("nan")
                try:
                    daily_return_val = float(raw_return)
                    if math.isnan(daily_return_val):
                        daily_return: float | None = None
                    else:
                        daily_return = daily_return_val / 100.0
                except (TypeError, ValueError):
                    daily_return = None

                # nav / acc_nav：NaN → None
                def _safe_float(v: Any) -> float | None:
                    try:
                        fv = float(v)
                        return None if math.isnan(fv) else fv
                    except (TypeError, ValueError):
                        return None

                result.append({
                    "date": str(values[0]),
                    "nav": _safe_float(values[1]),
                    "acc_nav": _safe_float(values[2]) if len(values) > 2 else None,
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
        try:
            df: pd.DataFrame | None = self._call_with_retry(
                ak.stock_zh_index_daily_em,
                symbol=index_code,
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
