"""
密码安全模块 —— 加盐哈希与校验。

数据库里不存明文密码，存的是 PBKDF2-HMAC-SHA256 的加盐哈希：

    pbkdf2_sha256$<迭代次数>$<盐十六进制>$<哈希十六进制>

盐保证同一个密码在不同账号下哈希值不同（彩虹表失效）；
迭代 20 万次是故意算得慢，提高暴力破解的成本。
"""

from __future__ import annotations

import hashlib
import os

ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 200_000
SALT_BYTES = 16


def hash_password(password: str) -> str:
    """把明文密码转换成可入库的加盐哈希字符串。"""
    if not password:
        raise ValueError("密码不能为空")

    salt = os.urandom(SALT_BYTES)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return f"{ALGORITHM}${ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验明文密码与库中哈希是否匹配。格式非法一律返回 False。"""
    if not password or not stored:
        return False

    try:
        algorithm, iterations, salt_hex, digest_hex = stored.split("$")
        if algorithm != ALGORITHM:
            return False
        iterations = int(iterations)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False

    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return actual == expected
