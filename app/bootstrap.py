"""
数据库初始化引导模块。

职责：把 sql/*.sql 按顺序执行到真实数据库中。
"""

from __future__ import annotations

import re
from pathlib import Path

import pymysql

SQL_DIR = Path(__file__).resolve().parent.parent / "sql"

DEFAULT_ORDER = ("01_schema.sql", "02_views.sql", "03_triggers.sql", "04_seed.sql")

DELIMITER_PATTERN = re.compile(r"^\s*DELIMITER\s+(\S+)\s*$", re.IGNORECASE)


def split_sql_statements(script: str) -> list[str]:
    """把 SQL 脚本切分成可逐条执行的语句"""
    normalized = script.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.split("\n")

    # 第一步：按 DELIMITER 指令分段
    segments: list[tuple[str, str]] = []
    current: list[str] = []
    delimiter = ";"

    for line in lines:
        match = DELIMITER_PATTERN.match(line)
        if match:
            if current:
                segments.append(("\n".join(current), delimiter))
                current = []
            delimiter = match.group(1)
            continue
        current.append(line)
    if current:
        segments.append(("\n".join(current), delimiter))

    # 第二步：按所在段的分隔符切分
    statements: list[str] = []
    for text, delim in segments:
        for piece in text.split(delim):
            cleaned = _strip_leading_comments(piece).strip()
            if cleaned:
                statements.append(cleaned)

    return statements


def _strip_leading_comments(text: str) -> str:
    """去掉行首的 -- / # 行注释与 /* */ 块注释，用于判断是否还有真实语句。"""
    lines: list[str] = []
    in_block = False
    for line in text.split("\n"):
        stripped = line.strip()
        if in_block:
            if "*/" in stripped:
                in_block = False
                stripped = stripped.split("*/", 1)[1].strip()
                if stripped:
                    lines.append(stripped)
            continue
        if stripped.startswith("/*"):
            if "*/" not in stripped:
                in_block = True
                continue
            stripped = stripped.split("*/", 1)[1].strip()
            if not stripped:
                continue
        if not stripped or stripped.startswith("--") or stripped.startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)


def _is_ignorable(statement: str) -> bool:
    """跳过纯注释与空语句。"""
    if not statement:
        return True
    if not _strip_leading_comments(statement).strip():
        return True
    without_trailing = re.sub(r"--[^\n]*", "", statement)
    without_trailing = re.sub(r"/\*.*?\*/", "", without_trailing, flags=re.DOTALL)
    return not without_trailing.strip()


def bootstrap(connection: pymysql.connections.Connection,
              files: tuple[str, ...] = DEFAULT_ORDER,
              *,
              verbose: bool = True) -> dict[str, int]:
    
    """按顺序执行 sql/ 下的脚本。"""
    
    report: dict[str, int] = {}
    cursor = connection.cursor()

    for filename in files:
        path = SQL_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"缺少数据库脚本：{path}")

        statements = split_sql_statements(path.read_text(encoding="utf-8"))
        executed = 0

        for index, statement in enumerate(statements, start=1):
            if _is_ignorable(statement):
                continue
            try:
                cursor.execute(statement)
                executed += 1
            except pymysql.Error as exc:
                preview = " ".join(statement.split())[:120]
                raise RuntimeError(
                    f"{filename} 第 {index} 条语句执行失败：{exc}\n  语句预览：{preview}..."
                ) from exc

        connection.commit()
        report[filename] = executed
        if verbose:
            print(f"  ✓ {filename:18s} 执行 {executed} 条语句")

    cursor.close()
    return report


if __name__ == "__main__":
    from app.config import DB_CONFIG

    print("正在初始化数据库（sql/*.sql）...")
    conn = pymysql.connect(
        host=DB_CONFIG["host"], user=DB_CONFIG["user"], password=DB_CONFIG["password"],
        port=DB_CONFIG["port"], charset="utf8mb4", autocommit=False,
    )
    try:
        bootstrap(conn)
        print("数据库初始化完成。")
    finally:
        conn.close()
