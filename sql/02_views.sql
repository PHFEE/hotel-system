-- =====================================================================
--  酒店服务预约管理系统 —— 视图定义
--  ------------------------------------------------------------------
--  文件   : sql/02_views.sql
--  依赖   : 01_schema.sql
-- =====================================================================

USE `hotel_booking`;

DROP VIEW IF EXISTS `v_guest_profile`;
DROP VIEW IF EXISTS `v_settlement_detail`;
DROP VIEW IF EXISTS `v_all_orders`;
DROP VIEW IF EXISTS `v_room_availability`;
DROP VIEW IF EXISTS `v_room_current_state`;
DROP VIEW IF EXISTS `v_daily_revenue`;
DROP VIEW IF EXISTS `v_service_stats`;
-- 历史视图：属于已移除的 SPA 业务线，这里保留 DROP 以便旧库升级后不留残留
DROP VIEW IF EXISTS `v_tech_schedule_today`;


-- ---------------------------------------------------------------------
--  V1. 客房订单视图（状态归一化视图）
-- ---------------------------------------------------------------------
CREATE VIEW `v_all_orders` AS
SELECT
    ro.order_id                                     AS order_id,
    ro.user_id                                      AS user_id,
    u.username                                      AS username,
    'room'                                          AS order_type,
    '客房'                                          AS type_label,
    CONCAT(r.room_number, ' / ', DATE_FORMAT(ro.check_in_date, '%Y-%m-%d'),
           '~', DATE_FORMAT(ro.check_out_date, '%Y-%m-%d'),
           ' / ', ro.nights, '晚')                   AS detail,
    ro.total_price                                  AS total_price,
    ro.status                                       AS raw_status,
    CASE ro.status
        WHEN 'confirmed'   THEN 'pending'
        WHEN 'checked_in'  THEN 'active'
        WHEN 'checked_out' THEN 'completed'
        ELSE 'cancelled'
    END                                             AS status_group,
    CASE ro.status
        WHEN 'confirmed'   THEN '待入住'
        WHEN 'checked_in'  THEN '已入住'
        WHEN 'checked_out' THEN '已退房'
        ELSE '已取消'
    END                                             AS status_label,
    CASE ro.status
        WHEN 'confirmed'   THEN '进行中'
        WHEN 'checked_in'  THEN '进行中'
        WHEN 'checked_out' THEN '已完成'
        ELSE '已取消'
    END                                             AS status_category,
    ro.group_id                                     AS group_id,
    gg.group_name                                   AS group_name,
    ro.settlement_no                                AS settlement_no,
    ro.check_in_date                                AS service_date,
    ro.created_at                                   AS created_at
FROM room_order ro
JOIN `user` u ON u.user_id = ro.user_id
JOIN room   r ON r.room_id = ro.room_id
LEFT JOIN guest_group gg ON gg.group_id = ro.group_id;


-- ---------------------------------------------------------------------
--  V2. 房间与房型信息视图
--
--  用法：SELECT * FROM v_room_availability
--        WHERE status = 'available' AND type_name = %s
-- ---------------------------------------------------------------------
CREATE VIEW `v_room_availability` AS
SELECT
    r.room_id                                       AS room_id,
    r.room_number                                   AS room_number,
    rt.type_id                                      AS type_id,
    rt.type_name                                    AS type_name,
    rt.price                                        AS price,
    rt.max_occupancy                                AS max_occupancy,
    rt.facilities                                   AS facilities,
    r.floor                                         AS floor,
    r.status                                        AS status
FROM room r
JOIN room_type rt ON rt.type_id = r.type_id;


-- ---------------------------------------------------------------------
--  V3. 房间实时状态视图
-- ---------------------------------------------------------------------
CREATE VIEW `v_room_current_state` AS
SELECT
    r.room_id,
    r.room_number,
    rt.type_name,
    rt.price,
    r.floor,
    r.status                                        AS room_status,
    COALESCE(occ.active_orders, 0)                  AS active_orders,
    occ.current_guest,
    occ.nearest_check_in,
    occ.nearest_check_out,
    CASE
        WHEN r.status = 'maintenance' THEN '维护中'
        WHEN r.status = 'cleaning'    THEN '打扫中'
        WHEN occ.current_guest IS NOT NULL THEN '在住'
        WHEN COALESCE(occ.active_orders, 0) > 0 THEN '已预订'
        ELSE '空闲'
    END                                             AS state_label
FROM room r
JOIN room_type rt ON rt.type_id = r.type_id
LEFT JOIN (
    SELECT
        ro.room_id,
        COUNT(*)                                    AS active_orders,
        MAX(CASE WHEN ro.status = 'checked_in' THEN ro.guest_name END) AS current_guest,
        MIN(CASE WHEN ro.status = 'confirmed'  THEN ro.check_in_date END)  AS nearest_check_in,
        MAX(CASE WHEN ro.status = 'checked_in' THEN ro.check_out_date END) AS nearest_check_out
    FROM room_order ro
    WHERE ro.status IN ('confirmed', 'checked_in')
    GROUP BY ro.room_id
) occ ON occ.room_id = r.room_id;


-- ---------------------------------------------------------------------
--  V4. 每日营收视图（按支付时间汇总真实收款）
-- ---------------------------------------------------------------------
CREATE VIEW `v_daily_revenue` AS
SELECT
    DATE(p.paid_at)                                 AS pay_date,
    p.order_type                                    AS order_type,
    CASE p.order_type
        WHEN 'room'    THEN '客房'
    END                                             AS type_label,
    COUNT(*)                                        AS payment_count,
    SUM(p.amount)                                   AS revenue
FROM payment p
WHERE p.status = 'paid'
GROUP BY DATE(p.paid_at), p.order_type;


-- ---------------------------------------------------------------------
--  V5. 订单统计视图（客房订单量与金额一览，供管理端看板）
-- ---------------------------------------------------------------------
CREATE VIEW `v_service_stats` AS
SELECT
    order_type,
    type_label,
    COUNT(*)                                        AS order_count,
    SUM(CASE WHEN status_category = '进行中' THEN 1 ELSE 0 END) AS active_count,
    SUM(CASE WHEN status_category = '已完成' THEN 1 ELSE 0 END) AS completed_count,
    SUM(CASE WHEN status_category = '已取消' THEN 1 ELSE 0 END) AS cancelled_count,
    SUM(CASE WHEN status_category <> '已取消' THEN total_price ELSE 0 END) AS order_amount
FROM v_all_orders
GROUP BY order_type, type_label;


-- ---------------------------------------------------------------------
--  V6. 客人档案视图（题目要求 (3)：提供多种手段查询客人的信息）
-- ---------------------------------------------------------------------
CREATE VIEW `v_guest_profile` AS
SELECT
    u.user_id,
    u.username,
    u.real_name,
    u.phone,
    u.email,
    u.role,
    u.is_active,
    ro.order_id,
    r.room_number,
    rt.type_name,
    rt.price,
    ro.check_in_date,
    ro.check_out_date,
    ro.nights,
    ro.total_price,
    ro.guest_name,
    ro.guest_phone,
    ro.id_card,
    ro.group_id,
    gg.group_name,
    ro.settlement_no,
    ro.status              AS raw_status,
    o.status_label,
    o.status_category
FROM `user` u
LEFT JOIN room_order ro ON ro.user_id = u.user_id
LEFT JOIN v_all_orders o ON o.order_type = 'room' AND o.order_id = ro.order_id
LEFT JOIN room r ON r.room_id = ro.room_id
LEFT JOIN room_type rt ON rt.type_id = r.type_id
LEFT JOIN guest_group gg ON gg.group_id = ro.group_id;


-- ---------------------------------------------------------------------
--  V7. 结账单明细视图（题目要求 (1)(5)：结账单与结账报表）
-- ---------------------------------------------------------------------
CREATE VIEW `v_settlement_detail` AS
SELECT
    s.settlement_no,
    s.group_id,
    gg.group_name,
    s.user_id,
    u.username,
    s.room_count,
    s.total_amount,
    s.method,
    CASE s.method
        WHEN 'cash'        THEN '现金'
        WHEN 'card'        THEN '银行卡'
        WHEN 'wechat'      THEN '微信'
        WHEN 'alipay'      THEN '支付宝'
        WHEN 'room_charge' THEN '挂房账'
    END                    AS method_label,
    s.operator_id,
    op.username            AS operator_name,
    s.status               AS settlement_status,
    s.status = 'settled'   AS is_settled,
    s.settled_at,
    s.remark,
    ro.order_id,
    ro.guest_name,
    ro.id_card,
    r.room_number,
    rt.type_name,
    ro.check_in_date,
    ro.check_out_date,
    ro.nights,
    ro.total_price,
    p.payment_no,
    p.amount               AS paid_amount,
    p.status               AS payment_status,
    p.paid_at
FROM settlement s
JOIN `user` u ON u.user_id = s.user_id
LEFT JOIN `user` op ON op.user_id = s.operator_id
LEFT JOIN guest_group gg ON gg.group_id = s.group_id
LEFT JOIN room_order ro ON ro.settlement_no = s.settlement_no
LEFT JOIN room r ON r.room_id = ro.room_id
LEFT JOIN room_type rt ON rt.type_id = r.type_id
LEFT JOIN payment p
       ON p.order_type = 'room' AND p.order_id = ro.order_id AND p.status = 'paid';


