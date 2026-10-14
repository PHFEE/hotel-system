"""
酒店服务预约管理系统 —— 应用包。

分层结构：
    app/config.py      配置（环境变量 > config.local.py > 默认值）
    app/db.py          数据访问层：连接管理、事务、回滚、防注入
    app/security.py    密码加盐哈希与校验
    app/ids.py         业务单号生成
    app/service.py     业务规则层：状态机、容量校验、并发控制
    app/stats.py       统计查询
    app/bootstrap.py   执行 sql/*.sql 完成建库
    app/ui/            Tkinter 界面
"""

# 真正导入子模块，使 __all__ 中列出的名字确实存在于包命名空间。
# 注意：这些模块只在导入时定义函数/类，不会建立数据库连接。
from . import bootstrap, config, db, ids, security, service, stats

__all__ = ["config", "db", "security", "ids", "service", "stats", "bootstrap"]
