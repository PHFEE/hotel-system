"""
业务单号生成。
"""

from __future__ import annotations

import secrets
import string
from datetime import datetime
from typing import Callable, TypeVar

# 排除易混淆字符（0/O、1/I），便于口头报单号
_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
_PREFIXES = {
    "room": "RM",
    "settlement": "JS",
    "payment": "PY",
}

T = TypeVar("T")


def new_order_id(order_type: str, *, moment: datetime | None = None) -> str:
    """
    生成业务单号，格式：<类型前缀><YYYYMMDD><HHMMSS><毫秒3位><随机4位>

    例：RM20260510143012345A7K2  —— 共 2 + 8 + 6 + 3 + 4 = 23 字符
    """
    prefix = _PREFIXES.get(order_type, "XX")
    now = moment or datetime.now()
    tail = "".join(secrets.choice(_ALPHABET) for _ in range(4))
    return f"{prefix}{now.strftime('%Y%m%d%H%M%S')}{now.microsecond // 1000:03d}{tail}"


def uniqueness_guard(factory: Callable[[], str],
                     exists: Callable[[str], bool],
                     *, attempts: int = 8) -> str:
    """
    反复生成单号直到数据库确认不存在，最多尝试 attempts 次。

    factory: 生成候选单号的函数
    exists : 判断单号是否已存在的回调（通常是一次 COUNT 查询）
    """
    for _ in range(attempts):
        candidate = factory()
        if not exists(candidate):
            return candidate
    raise RuntimeError(f"连续 {attempts} 次生成的单号都发生碰撞，请检查系统时钟是否异常")
