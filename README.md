# 宾馆客房管理系统

数据库课程设计 · 选题 19 · Tkinter + MySQL 8.0

一套面向宾馆客房业务的桌面管理系统，围绕**客房预订**这一条主线，
含客人 / 前台 / 管理员三种角色的客户端。

按课程题目（选题 19 宾馆客房管理系统）的要求，系统做了三件事：

1. **收敛业务线** —— 删除餐饮 / 健身 / SPA / 洗衣四条与选题无关的业务线，
   只保留客房主线；
2. **补齐题目要求的功能** —— 团体登记与团体结账（要求 1）、结账单与结账报表
   （要求 1、5）、多手段查询客人信息（要求 3）、房价与房型变更的密码支持与
   审计留痕（要求 4）；
3. **把数据库结构收敛为唯一来源**（`sql/*.sql`），补齐视图、触发器、
   索引、约束与事务边界。

---

## 一、快速开始

```bash
# 1. 安装依赖（仅需 PyMySQL）
pip install -r requirements.txt

# 2. 配置数据库连接（二选一）
#    方式 A：复制模板并修改密码（注意目标文件名是 config_local.py，下划线）
copy config.local.example.py config_local.py
#    方式 B：设置环境变量
set HOTEL_DB_PASSWORD=你的密码

# 3. 启动（首次运行会自动建库、建表、建视图/触发器并写入基础数据）
python main.py
```

其他常用命令：

```bash
python tools/init_db.py --yes         # 手动重建数据库（会清空数据）
python tools/seed_demo_orders.py      # 生成客房订单 / 团体单 / 结账单 / 支付流水演示数据
python tools/smoke_test.py            # 端到端自检
```

### 演示账号

| 角色 | 用户名 | 密码 |
|---|---|---|
| 管理员 | `admin` | `admin123` |
| 前台 | `reception` | `recep123` |
| 客人 | `guest01` | `guest123` |

> 登录窗口底部列出了这三个账号，**鼠标点一下即可自动填入用户名和密码**，
> 光标会停在密码框，直接按回车就能登录。
>
> 密码在数据库中存的是 `PBKDF2-HMAC-SHA256` 加盐哈希，不是明文。

### 界面说明

三种角色的主窗口初始尺寸为 `1000x820`，最小尺寸 `960x750`
（定义在 `app/config.py` 的 `WINDOW_SIZE` 与 `app/ui/base.py` 的 `minsize`），
保证客房预订页左侧表单底部的「确认预订」按钮一进入就能看到，无需手动拉长窗口。
所有页面支持 `F5` 刷新当前标签页。

---

## 二、项目结构

```
hotel_system/
├── main.py                     程序入口（含首次运行自动初始化）
├── requirements.txt
├── config.local.example.py     本地配置模板（复制为 config_local.py）
├── config_local.py             本机数据库口令（已在 .gitignore 中，不提交）
├── README.md
├── LICENSE
├── .gitignore
├── 六课完整讲义.md              课程讲义（本地参考，已在 .gitignore 中）
├── 题目.png                     课程题目截图
│
├── sql/                        ★ 数据库结构唯一来源
│   ├── 01_schema.sql           9 张表 + 索引 + 主外键 + CHECK 约束
│   ├── 02_views.sql            7 个视图
│   ├── 03_triggers.sql         5 个触发器
│   └── 04_seed.sql             基础数据（三角色账号 / 4 种房型 / 16 间客房）
│
├── app/
│   ├── config.py               配置（环境变量 > config_local.py > 默认值）
│   ├── db.py                   数据访问层：连接、事务、回滚、异常封装
│   ├── security.py             密码加盐哈希与校验
│   ├── ids.py                  业务单号生成（抗碰撞 + 兜底重试）
│   ├── bootstrap.py            执行 sql/*.sql（含 MySQL DELIMITER 解析）
│   ├── service.py              ★ 业务规则层：状态机、冲突复查、并发控制
│   ├── stats.py                统计与看板查询
│   └── ui/
│       ├── widgets.py          通用控件与对话框
│       ├── base.py             窗口基类（统一异常处理、状态栏）
│       ├── login.py            登录 / 注册 / 修改密码
│       ├── guest.py            客人端主窗口
│       ├── guest_tabs.py       客人端两个标签页（客房预订 / 我的订单）
│       ├── reception.py        前台端主窗口
│       ├── reception_tabs.py   前台端七个标签页（概览/客房/团体登记/入住退房/
│       │                        客人查询/订单/评价）
│       ├── admin.py            管理端主窗口
│       └── admin_tabs.py       管理端六个标签页（含结账报表、变更记录）
│
└── tools/
    ├── init_db.py              建库工具
    ├── seed_demo_orders.py     客房订单 / 团体单 / 结账单演示数据生成
    └── smoke_test.py           端到端自检
```

**分层原则**：界面只负责「收集输入 + 渲染结果」，所有业务规则集中在
`app/service.py`，所有 SQL 集中在 `app/db.py` / `app/service.py` / `app/stats.py`。
`app/ui/` 目录下**不含任何 SQL 语句**（可用
`rg "SELECT |INSERT INTO|UPDATE |DELETE FROM" app/ui` 验证，应无命中）。
基础资源维护这类需要动态表名的功能，也通过 `service.RESOURCE_CATALOG`
白名单注册表在服务层完成，界面不再直接触碰数据库。

---

## 三、数据库设计

### 3.1 数据表（9 张）

| 分组 | 表 |
|---|---|
| 用户 | `user` |
| 客房 | `room_type`、`room`、`room_order` |
| 团体与结账 | `guest_group`、`settlement` |
| 支付与评价 | `payment`、`review` |
| 操作审计 | `price_change_log` |

三条关键关系：

- `guest_group 1 ── N room_order`：**团体登记**一次为多间房生成订单
  （`room_order.group_id`），团体结账再按 `group_id` 汇总；
- `settlement 1 ── N room_order`：**结账单**一次结清多张订单
  （`room_order.settlement_no`）。团体结账生成一张覆盖多间房的账单，
  散客结账生成一张单间账单；账单金额是**快照**，不随后续改价而变化；
- `room_order.id_card` 支撑"多种手段查询客人信息"（要求 3）。

### 3.2 视图（7 个）

| 视图 | 作用 |
|---|---|
| `v_all_orders` | 客房订单的状态归一化与倒序列表（`status_group` / `status_label` / `status_category`），并带出团体名与结账单号。三端订单列表统一走它 |
| `v_room_availability` | 房间与房型信息（带 `room_id`，预订无需按房号反查） |
| `v_room_current_state` | 房间物理状态 + 有效订单数 + 在住客人，解决状态与订单脱节 |
| `v_daily_revenue` | 按日汇总 `payment` 中 `status='paid'` 的真实收款 |
| `v_service_stats` | 客房订单量与状态分布（供管理端看板） |
| `v_guest_profile` | 客人档案：以 `user` 为主体 LEFT JOIN 订单，**没下过单的客人也能查到**；支撑姓名/手机号/证件号/房间号/订单号/日期区间六种检索 |
| `v_settlement_detail` | 结账单明细：一张账单 → 多个房间 → 各自的收款流水，供查看结账单明细与导出报表 |

### 3.3 触发器（5 个）

| 触发器 | 保障的不变量 |
|---|---|
| `trg_room_order_before_insert` | 晚数与总金额由数据库按当前房价重算（界面无法篡改账目）；团体成员的入住/离店日期必须与团体单一致 |
| `trg_room_order_after_insert` | 当日到店的订单自动把房间置为「在住」 |
| `trg_room_order_after_update` | 入住→在住、退房→打扫中、取消→按剩余订单回置空闲 |
| `trg_room_order_before_update` | **已结账的订单不能直接取消** —— 必须先走「结账单退款」，否则结账单金额与订单状态会互相矛盾 |
| `trg_review_before_insert` | 被评价订单必须存在且属于该用户 |

`01_schema.sql` / `02_views.sql` / `03_triggers.sql` 开头都显式列出了
**已删除业务线的对象**的 `DROP ... IF EXISTS`（例如 `restaurant`、`dish`、
`spa_booking`、`laundry_order`、`v_tech_schedule_today` 等），
旧库升级后不会留下残留对象。

### 3.4 约束与索引

- **12 个外键**：订单/账单类表全部使用 `ON DELETE RESTRICT`，
  删除房型/房间/团体单不会连带删除历史订单与账单（原版是 `CASCADE`，
  误删即丢账目）。
- **9 个 CHECK 约束**：价格为正、入住人数上限、离店晚于入住、金额非负、
  评分 1–5，以及团体单的日期区间与结账单的房间数/金额取值域。
- **22 个显式非主键索引**；另有 5 个由 MySQL 为外键自动创建的索引，
  因此 `information_schema` 统计到的非主键索引总数为 **27** 个。
  唯一索引保证业务唯一性：`user(username/phone/email)`、`room_type(type_name)`、
  `room(room_number)`、`payment(payment_no)`、`review(user_id, order_id, order_type)`
  防重复评价，以及 `guest_group(group_name, check_in_date)` 防同名团体同日重复登记；
  普通索引服务高频查询，其中复合索引
  `room_order(room_id, status, check_in_date, check_out_date)`
  直接服务最高频的"查某时段可用房"查询，
  `room_order(group_id)` / `room_order(settlement_no)` 服务团体与结账单的汇总查询。

### 3.5 关于 order_type 字段

`review.order_id` / `payment.order_id` 现在**只指向 `room_order`**，
不再跨多张订单表，因此不再需要多态引用所需的复杂校验。

`order_type` 列仍然保留为 `ENUM` 类型（当前取值只有 `'room'`），
这是**为后续扩展留位**的取舍：ENUM 是有约束的类型而不是普通字符串，
将来若重新接入其他业务线，只需扩展枚举取值、新增对应订单表，并在
`trg_review_before_insert` 中补一个 `CASE` 分支即可，不必改动表结构。
当前系统只会写入 `'room'`。

### 3.6 团体与结账的数据一致性

「一次操作涉及多行」的业务（团体登记、团体结账、整单退款），一致性由三层共同保证：

1. **事务**：`create_group_booking` 在同一事务里对每间房复查冲突
   （`SELECT ... FOR UPDATE`）后再插单；`settle_group` 先锁住待结账订单，
   再建账单、回填 `settlement_no`、逐单登记收款，任何一步失败整体回滚。
2. **外键**：订单指向团体单/结账单的外键都是 `RESTRICT`，
   仍被引用的账目凭据删不掉。
3. **触发器**：团体成员日期必须与团体单一致（`trg_room_order_before_insert`）；
   已结账单里的订单不能被直接取消（`trg_room_order_before_update`）。

**整单退款**（`refund_settlement`）的顺序是刻意设计的：
先把收款流水置为 `refunded`，再把成员订单的 `settlement_no` 置回 `NULL`
（订单回到"未结账"状态），之后才允许按状态机取消 ——
这正是 `trg_room_order_before_update` 放行的顺序，顺序反了会被数据库拦住。

---

## 四、重构要点（小结）

相比最初的版本，这次重构集中在四个方面：

**1. 结构收敛（致命问题）**

- 原系统 `setup_database.sql` 与代码内嵌 DDL 两份 schema 互相分叉，
  脚本与代码对不上会导致建表必然报错。现在表结构只存在于 `sql/*.sql`，
  Python 侧不再内嵌任何 DDL，并有自检断言锁定对象清单。

**2. 数据安全**

- 密码明文存库 → `PBKDF2-HMAC-SHA256` 加盐哈希（20 万次迭代，支持参数升级自动重算）；
- 全项目无 `rollback` → `Database.transaction()` 上下文管理器，多步操作原子化；
- 订单号主键碰撞无重试 → 毫秒级时间戳 + 4 位随机字符 + 冲突重试；
- 外键 `ON DELETE CASCADE` 会因删房型清空订单 → 订单类外键改 `RESTRICT`；
- 管理端「禁用用户」实际执行 `DELETE FROM user` → 改为 `is_active` 软禁用，
  历史订单完整保留。

**3. 业务正确性**

- 「我的订单」用秒级时间戳作排序键，同一秒的多单互相覆盖、静默丢单
  → 删除自建排序结构，统一走 `v_all_orders` 视图 + SQL `ORDER BY`，
  并加了"同一秒连开 5 单全部可见"的回归测试；
- 订房"先查后插"存在并发窗口 → 同一事务内 `SELECT ... FOR UPDATE` 复查冲突；
- 同一订单可无限重复评价 → 唯一约束 + 服务层校验 + 触发器校验三重拦截；
- `room.status` 与订单脱节 → 房态改由触发器随订单流转，「在住」不允许人工设置；
- 「收入」按订单状态求和（未收款也计入）→ 新增 `payment` 流水表，
  收入只统计 `status='paid'` 的真实收款；
- 日期手输格式错误直接抛 `ValueError` → `parse_date` 统一转友好提示，
  日期控件提供「前一天 / 后一天 / 今天」快捷按钮；
- 三端各自重复实现订单汇总与状态翻译 → 统一走 `service.list_orders()`；
- 自建的 `Queue` 零调用、`PriorityQueue` 同优先级顺序不稳定 → 移除无用结构。

**4. 补齐课程题目要求**

- **团体登记 / 团体结账**：新增 `guest_group` 表与 `room_order.group_id`，
  前台端一次登记多间房、整团入住退房，`settle_group` 生成一张覆盖全团的结账单；
- **结账单与结账报表**：新增 `settlement` 表（金额快照）+ `room_order.settlement_no`，
  报表支持账单数/房间数/金额/散客与团体/按结算方式/按日/按经手人，
  并支持 **CSV 导出** 与**整单退款**；
- **多种手段查询客人**：新增 `v_guest_profile` 与 `search_guest_profile()`，
  姓名/手机号/证件号/房间号/订单号/日期区间任意组合，没下过单的客人也能查到；
- **房价房型变更的密码支持与审计**：`Approval` 二次密码校验拦截房型/房间的
  新增、修改、删除，并把「旧值 → 新值 + 原因 + 操作人」写入 `price_change_log`。

---

## 五、操作流程速览

### 客人端（2 个标签页）

1. **客房预订** — 选日期 → 查询可用房 → 填入住人 → 确认预订
   （金额由数据库按当前房价计算）
2. **我的订单** — 统一列表，可查看详情、取消、支付、评价

### 前台端（7 个标签页）

- **今日概览** — 到店/在住/离店、房间状态、待收款
- **客房管理** — 按楼层/状态/房号筛选，查看预订日历，更改房间物理状态，
  **代客开单**（散客现场登记）
- **团体登记** — 填团体信息 → 查询可用房 → 多选房间一次登记 → 整团入住 /
  整团退房 / 团体结账（生成一张覆盖全团的结账单）
- **入住 / 退房** — 办理入住（房间自动转在住）、办理退房（自动转打扫）、
  **办理结账**（生成结账单）、登记收款
- **客人查询** — 关键字/姓名/手机号/证件号/房间号/订单号/入住日期区间组合查询，
  双击一行查看该客人的全部订单
- **订单管理** — 按状态机推进、取消、登记收款、查看详情
- **客户评价** — 查看评分与内容

### 管理端（6 个标签页）

- **数据统计** — 按时间范围统计实收/退款/净收入、按支付方式分布
- **结账报表** — 账单数/房间数/结账金额、散客与团体、按结算方式与按日流水、
  结账单明细，支持 **导出 CSV** 与 **整单退款**
- **用户管理** — 添加账号、重置密码、**软禁用**（不删数据）
- **资源管理** — 房型 / 房间增删改；每次改动都要**输入操作员密码**并填写原因，
  可随时查看「📜 变更记录」
- **订单总览** — 全量客房订单与支付流水
- **关于系统** — 直观展示数据库对象清单（表/视图/触发器/索引/外键/CHECK）

---

## 六、自检

`tools/smoke_test.py` 覆盖 **273 项**断言（脚本结束时清理自己写入的数据、并把
改动过的房价还原，可反复执行）：

```bash
python tools/smoke_test.py
```

输出末尾应显示：

```
通过 273 项，失败 0 项
```

覆盖范围：

- 数据库对象清单（9 表 / 7 视图 / 5 触发器 / 12 外键 / 9 CHECK，且对象名与期望集合完全相等）
- 密码：明文不入库、错误密码被拒、加盐生效、禁用账号无法登录
- 客房订单金额与日期：金额由触发器按房价重算（直插篡改也无效）、晚数由数据库计算、日期非法被拒
- 状态机与房态联动：非法流转被拒，入住/退房/取消自动改变房间状态
- **订单汇总回归测试**：同一秒连续创建 5 单，列表条数正确、5 单全部可见
- **团体登记**：一次登记多间房挂同一 `group_id`、同名团体同日被拒、成员日期与团体单不一致被触发器拒绝
- **团体结账 / 散客结账**：一张账单覆盖多间房、逐单登记收款、重复结账被拒
- **已结账订单不可取消**：业务层与触发器双重拦截；整单退款后流水置退款、订单解绑、可再按状态机取消
- **客人多手段查询**：姓名/手机号/证件号/房间号/订单号/日期区间六种手段，含没有订单的客人
- **密码支持与审计**：无密码 / 错密码改动被拒，正确密码通过并写入变更日志（旧值 → 新值 + 原因 + 操作人）
- **结账报表**：账单数/房间数/金额/团体与散客/按结算方式/按日，已退款账单单独计数
- 支付与退款：重复支付被拒、营收来自流水、未收款订单不计入营收
- 评价三重校验：订单存在性 / 归属 / 重复评价
- 资源维护白名单：拦截非法表、拒绝改主键、类型校验、外键 RESTRICT 保护

> **常见故障**：若「数据库对象数量」类断言失败，说明当前库与 `sql/*.sql` 不同步
> —— 通常是旧库残留了已删除业务线的表（`restaurant`、`dish`、`spa_booking`、
> `laundry_order` 等）。两种处理方式：
> 重新执行一次 `python tools/init_db.py --yes`（会清空数据重建），
> 或按 `sql/01_schema.sql` 开头的 `DROP TABLE IF EXISTS` 清单手工删除残留表。

---

## 七、环境要求

- Python 3.9+（开发环境 3.14）
- MySQL 8.0+（使用了 CHECK 约束与 `INSERT ... ON DUPLICATE KEY UPDATE`）
- PyMySQL 1.1+
- Tkinter（Python 官方安装包默认自带）
