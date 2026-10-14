"""
统计与看板查询。
"""

from __future__ import annotations

from datetime import date

from app.db import Database


def overview(db: Database, day: date | None = None) -> dict:
    """首页概览指标：今日各业务预约量、房间使用、注册用户数。"""
    today = day or date.today()

    return {
        "today": today,
        "arrivals": db.query_value(
            "SELECT COUNT(*) FROM room_order "
            "WHERE check_in_date = %s AND status IN ('confirmed','checked_in')",
            (today,), 0),
        "in_house": db.query_value(
            "SELECT COUNT(*) FROM room_order "
            "WHERE status = 'checked_in' AND check_in_date <= %s AND check_out_date > %s",
            (today, today), 0),
        "departures": db.query_value(
            "SELECT COUNT(*) FROM room_order "
            "WHERE check_out_date = %s AND status = 'checked_in'", (today,), 0),
        "rooms_total": db.query_value("SELECT COUNT(*) FROM room", None, 0),
        "rooms_available": db.query_value(
            "SELECT COUNT(*) FROM room WHERE status = 'available'", None, 0),
        "rooms_occupied": db.query_value(
            "SELECT COUNT(*) FROM room WHERE status = 'occupied'", None, 0),
        "rooms_cleaning": db.query_value(
            "SELECT COUNT(*) FROM room WHERE status = 'cleaning'", None, 0),
        "rooms_maintenance": db.query_value(
            "SELECT COUNT(*) FROM room WHERE status = 'maintenance'", None, 0),
        "users_total": db.query_value("SELECT COUNT(*) FROM `user`", None, 0),
        "pending_payment": db.query_value(
            "SELECT COUNT(*) FROM v_all_orders o "
            "WHERE o.status_category <> '已取消' AND o.total_price > 0 "
            "  AND NOT EXISTS (SELECT 1 FROM payment p "
            "                  WHERE p.order_type = o.order_type "
            "                    AND p.order_id = o.order_id AND p.status = 'paid')",
            None, 0),
    }


def revenue_summary(db: Database, start: date | None = None,
                    end: date | None = None) -> dict:
    """
    营收汇总（只统计已支付的流水）。
    """
    where = ["status = 'paid'"]
    params: list = []
    if start:
        where.append("paid_at >= %s")
        params.append(start)
    if end:
        where.append("paid_at < DATE_ADD(%s, INTERVAL 1 DAY)")
        params.append(end)

    condition = " AND ".join(where)
    total = float(db.query_value(
        f"SELECT COALESCE(SUM(amount), 0) FROM payment WHERE {condition}", params, 0) or 0)
    refunded = float(db.query_value(
        "SELECT COALESCE(SUM(amount), 0) FROM payment WHERE status = 'refunded'", None, 0) or 0)

    by_type = db.query(
        f"SELECT order_type, "
        f"       CASE order_type WHEN 'room' THEN '客房' END AS type_label, "
        f"       COUNT(*) AS payment_count, COALESCE(SUM(amount), 0) AS amount "
        f"FROM payment WHERE {condition} GROUP BY order_type ORDER BY amount DESC",
        params,
    )

    by_method = db.query(
        f"SELECT method, "
        f"       CASE method WHEN 'cash' THEN '现金' WHEN 'card' THEN '银行卡' "
        f"            WHEN 'wechat' THEN '微信' WHEN 'alipay' THEN '支付宝' "
        f"            WHEN 'room_charge' THEN '挂房账' END AS method_label, "
        f"       COUNT(*) AS payment_count, COALESCE(SUM(amount), 0) AS amount "
        f"FROM payment WHERE {condition} GROUP BY method ORDER BY amount DESC",
        params,
    )

    by_day = db.query(
        f"SELECT DATE(paid_at) AS pay_date, COALESCE(SUM(amount), 0) AS amount, "
        f"       COUNT(*) AS payment_count "
        f"FROM payment WHERE {condition} GROUP BY DATE(paid_at) ORDER BY pay_date DESC LIMIT 30",
        params,
    )

    return {
        "total": total,
        "refunded": refunded,
        "net": total - refunded,
        "by_type": by_type,
        "by_method": by_method,
        "by_day": by_day,
    }


def service_stats(db: Database) -> list[dict]:
    """各业务线的订单量、状态分布与订单金额（来自 v_service_stats 视图）。"""
    return db.query("SELECT * FROM v_service_stats ORDER BY order_count DESC")


def order_status_distribution(db: Database) -> list[dict]:
    return db.query(
        "SELECT type_label, status_category, COUNT(*) AS cnt "
        "FROM v_all_orders GROUP BY type_label, status_category "
        "ORDER BY type_label, status_category"
    )


def room_usage(db: Database) -> list[dict]:
    """按房型统计房间状态分布，用于管理端看板。"""
    return db.query(
        "SELECT rt.type_name, rt.price, COUNT(*) AS room_count, "
        "       SUM(CASE WHEN r.status = 'available' THEN 1 ELSE 0 END) AS available, "
        "       SUM(CASE WHEN r.status = 'occupied' THEN 1 ELSE 0 END) AS occupied, "
        "       SUM(CASE WHEN r.status = 'cleaning' THEN 1 ELSE 0 END) AS cleaning, "
        "       SUM(CASE WHEN r.status = 'maintenance' THEN 1 ELSE 0 END) AS maintenance "
        "FROM room r JOIN room_type rt ON rt.type_id = r.type_id "
        "GROUP BY rt.type_id, rt.type_name, rt.price ORDER BY rt.price"
    )


def schema_objects(db: Database) -> dict:
    """
    统计数据库对象数量（表/视图/触发器/索引/外键）。
    """
    name = db.query_value("SELECT DATABASE()", None, "hotel_booking")
    counts = {
        "tables": db.query_value(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = %s AND table_type = 'BASE TABLE'", (name,), 0),
        "views": db.query_value(
            "SELECT COUNT(*) FROM information_schema.views WHERE table_schema = %s",
            (name,), 0),
        "triggers": db.query_value(
            "SELECT COUNT(*) FROM information_schema.triggers WHERE trigger_schema = %s",
            (name,), 0),
        "indexes": db.query_value(
            "SELECT COUNT(DISTINCT table_name, index_name) FROM information_schema.statistics "
            "WHERE table_schema = %s AND index_name <> 'PRIMARY'", (name,), 0),
        "foreign_keys": db.query_value(
            "SELECT COUNT(*) FROM information_schema.key_column_usage "
            "WHERE table_schema = %s AND referenced_table_name IS NOT NULL", (name,), 0),
        "check_constraints": db.query_value(
            "SELECT COUNT(*) FROM information_schema.check_constraints "
            "WHERE constraint_schema = %s", (name,), 0),
    }
    return counts


# =====================================================================
#  结账报表（题目要求 (5)）
# =====================================================================
def settlement_report(db: Database, start: date | None = None,
                      end: date | None = None) -> dict:
    """
    结账报表：以结账单（settlement）为主体做统计。
    """
    where = ["s.status = 'settled'"]
    params: list = []
    if start:
        where.append("s.settled_at >= %s")
        params.append(start)
    if end:
        where.append("s.settled_at < DATE_ADD(%s, INTERVAL 1 DAY)")
        params.append(end)
    cond = " AND ".join(where)
    date_cond = " AND ".join([c for c in where if not c.startswith("s.status")]) or "1 = 1"

    head = db.query_one(
        f"SELECT COUNT(*)                                        AS bill_count, "
        f"       COALESCE(SUM(s.room_count), 0)                   AS room_count, "
        f"       COALESCE(SUM(s.total_amount), 0)                 AS total_amount, "
        f"       COALESCE(SUM(CASE WHEN s.group_id IS NULL THEN 1 ELSE 0 END), 0) "
        f"                                                        AS walkin_count, "
        f"       COALESCE(SUM(CASE WHEN s.group_id IS NOT NULL THEN 1 ELSE 0 END), 0) "
        f"                                                        AS group_count "
        f"FROM settlement s WHERE {cond}", params) or {}

    refunded = db.query_one(
        f"SELECT COUNT(*) AS cnt, COALESCE(SUM(s.total_amount), 0) AS amount "
        f"FROM settlement s WHERE s.status = 'refunded' AND {date_cond}", params) or {}

    by_method = db.query(
        f"SELECT s.method, "
        f"       CASE s.method WHEN 'cash' THEN '现金' WHEN 'card' THEN '银行卡' "
        f"            WHEN 'wechat' THEN '微信' WHEN 'alipay' THEN '支付宝' "
        f"            WHEN 'room_charge' THEN '挂房账' END AS method_label, "
        f"       COUNT(*) AS bill_count, COALESCE(SUM(s.total_amount), 0) AS amount "
        f"FROM settlement s WHERE {cond} GROUP BY s.method ORDER BY amount DESC",
        params)

    by_day = db.query(
        f"SELECT DATE(s.settled_at) AS settle_date, COUNT(*) AS bill_count, "
        f"       COALESCE(SUM(s.room_count), 0) AS room_count, "
        f"       COALESCE(SUM(s.total_amount), 0) AS amount "
        f"FROM settlement s WHERE {cond} "
        f"GROUP BY DATE(s.settled_at) ORDER BY settle_date DESC LIMIT 60", params)

    by_operator = db.query(
        f"SELECT COALESCE(op.username, '—') AS operator_name, COUNT(*) AS bill_count, "
        f"       COALESCE(SUM(s.total_amount), 0) AS amount "
        f"FROM settlement s LEFT JOIN `user` op ON op.user_id = s.operator_id "
        f"WHERE {cond} GROUP BY s.operator_id, op.username ORDER BY amount DESC",
        params)

    by_type = db.query(
        f"SELECT CASE WHEN s.group_id IS NULL THEN '散客' ELSE '团体' END AS bill_type, "
        f"       COUNT(*) AS bill_count, COALESCE(SUM(s.room_count), 0) AS room_count, "
        f"       COALESCE(SUM(s.total_amount), 0) AS amount "
        f"FROM settlement s WHERE {cond} "
        f"GROUP BY CASE WHEN s.group_id IS NULL THEN '散客' ELSE '团体' END "
        f"ORDER BY amount DESC", params)

    unsettled = db.query_value(
        "SELECT COUNT(*) FROM room_order "
        "WHERE status <> 'cancelled' AND settlement_no IS NULL", None, 0)

    return {
        "bill_count": int(head.get("bill_count") or 0),
        "room_count": int(head.get("room_count") or 0),
        "total_amount": float(head.get("total_amount") or 0),
        "walkin_count": int(head.get("walkin_count") or 0),
        "group_count": int(head.get("group_count") or 0),
        "avg_bill": (round(float(head.get("total_amount") or 0)
                           / int(head.get("bill_count") or 1), 2)),
        "refunded_count": int(refunded.get("cnt") or 0),
        "refunded_amount": float(refunded.get("amount") or 0),
        "unsettled_orders": int(unsettled or 0),
        "by_method": by_method,
        "by_day": by_day,
        "by_operator": by_operator,
        "by_type": by_type,
    }
