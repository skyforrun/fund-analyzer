"""通用 API 响应模型。"""
from __future__ import annotations

from typing import Generic, Optional, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应包装器。

    Attributes
    ----------
    code : int
        业务状态码，0 表示成功。
    message : str
        状态描述信息。
    data : T | None
        业务数据载荷。
    """

    code: int = 0
    message: str = "success"
    data: Optional[T] = None
