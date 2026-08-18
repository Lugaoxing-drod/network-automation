"""
database.py
SQLite 数据库操作模块（第6课核心产出）
职责：封装所有数据库操作，让业务脚本只调用、不写SQL
"""

import sqlite3
import datetime
import os
from typing import List, Dict, Optional
from logger_config import setup_logger

logger = setup_logger(__name__)

DB_FILE = "network.db"


# ========== 初始化 ==========

def init_db():
    """
    初始化数据库：如果表不存在则创建
    这个函数应该在项目启动时调用一次
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()

    # 1. 设备台账表
    c.execute('''
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            device_type TEXT NOT NULL,
            host TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            role TEXT,
            dept TEXT,
            vlan_id TEXT,
            vlan_name TEXT,
            interface TEXT,
            ip_address TEXT,
            subnet_mask TEXT,
            uplink TEXT,
            mgmt_ip TEXT,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            updated_at TEXT
        )
    ''')

    # 2. 操作审计表 —— 解决"谁、什么时候、改了什么"
    c.execute('''
        CREATE TABLE IF NOT EXISTS operations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host TEXT NOT NULL,
            operation_type TEXT NOT NULL,
            status TEXT NOT NULL,
            detail TEXT,
            operator TEXT DEFAULT 'system',
            created_at TEXT
        )
    ''')

    # 3. 备份记录表
    c.execute('''
        CREATE TABLE IF NOT EXISTS backups (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            created_at TEXT
        )
    ''')

    # 4. 巡检记录表
    c.execute('''
        CREATE TABLE IF NOT EXISTS inspections (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            host TEXT NOT NULL,
            cpu_usage TEXT,
            memory_usage TEXT,
            intf_down_count TEXT,
            status TEXT,
            created_at TEXT
        )
    ''')

    conn.commit()
    conn.close()
    logger.info("[DB] 数据库初始化完成")


# ========== 设备台账 CRUD ==========

def add_device(device: dict) -> bool:
    """
    添加单台设备到数据库
    :param device: 字典，键名和表字段对应
    :return: True成功, False失败（如IP已存在）
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    try:
        c.execute('''
            INSERT INTO devices 
            (device_type, host, username, password, role, dept, vlan_id, vlan_name,
             interface, ip_address, subnet_mask, uplink, mgmt_ip, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            device.get('device_type', ''),
            device.get('host', '').strip(),
            device.get('username', ''),
            device.get('password', ''),
            device.get('role', ''),
            device.get('dept', ''),
            device.get('vlan_id', ''),
            device.get('vlan_name', ''),
            device.get('interface', ''),
            device.get('ip_address', ''),
            device.get('subnet_mask', ''),
            device.get('uplink', ''),
            device.get('mgmt_ip', ''),
            now, now
        ))
        conn.commit()
        logger.info(f"[DB] 设备 {device.get('host', '')} 入库成功")
        return True
    except sqlite3.IntegrityError:
        logger.warning(f"[DB] 设备 {device.get('host', '')} 已存在，跳过")
        return False
    except Exception as e:
        logger.error(f"[DB] 添加设备失败: {e}")
        return False
    finally:
        conn.close()


def get_all_devices(role: str = None) -> List[Dict]:
    """
    查询所有设备，或按角色筛选
    :param role: 如 'router' / 'core' / 'agg'，None表示全部
    :return: 设备字典列表
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # 让查询结果可以通过列名访问
    c = conn.cursor()

    if role:
        c.execute("SELECT * FROM devices WHERE role = ? AND status = 'active'", (role,))
    else:
        c.execute("SELECT * FROM devices WHERE status = 'active'")

    rows = c.fetchall()
    conn.close()

    # 把 sqlite3.Row 转成普通字典，兼容现有代码
    devices = [dict(row) for row in rows]
    logger.debug(f"[DB] 查询到 {len(devices)} 台设备" + (f" (role={role})" if role else ""))
    return devices


def get_device_by_host(host: str) -> Optional[Dict]:
    """按IP查单台设备"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute("SELECT * FROM devices WHERE host = ?", (host.strip(),))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def update_device_status(host: str, status: str):
    """更新设备状态（如标记为inactive）"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c.execute("UPDATE devices SET status = ?, updated_at = ? WHERE host = ?",
              (status, now, host.strip()))
    conn.commit()
    conn.close()
    logger.info(f"[DB] 设备 {host} 状态更新为 {status}")


# ========== 操作审计（核心：谁、什么时候、改了什么）==========

def log_operation(host: str, operation_type: str, status: str, detail: str = "", operator: str = "system"):
    """
    记录一次操作日志
    这是本课最核心的函数，所有业务脚本都应在关键节点调用它

    用法示例：
        log_operation("192.168.1.254", "backup", "success", "文件: backup_xxx.txt")
        log_operation("192.168.1.254", "config_push", "failed", "连接超时")
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute('''
        INSERT INTO operations (host, operation_type, status, detail, operator, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (host.strip(), operation_type, status, detail, operator, now))

    conn.commit()
    conn.close()
    logger.debug(f"[DB] 操作记录: {host} | {operation_type} | {status}")


def get_recent_operations(days: int = 7, status: str = None) -> List[Dict]:
    """
    查询最近N天的操作记录
    :param days: 最近几天
    :param status: 筛选状态，如 'failed'，None表示全部
    :return: 操作记录列表
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    if status:
        c.execute('''
            SELECT * FROM operations 
            WHERE created_at >= ? AND status = ?
            ORDER BY created_at DESC
        ''', (since, status))
    else:
        c.execute('''
            SELECT * FROM operations 
            WHERE created_at >= ?
            ORDER BY created_at DESC
        ''', (since,))

    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_failure_stats(days: int = 7) -> List[Dict]:
    """
    统计最近N天每台设备的失败次数
    这是Excel很难做、SQL很容易做的查询

    返回示例：
        [{'host': '192.168.1.13', 'fail_count': 3}, ...]
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    c.execute('''
        SELECT host, COUNT(*) as fail_count 
        FROM operations 
        WHERE created_at >= ? AND status = 'failed'
        GROUP BY host
        HAVING fail_count >= 1
        ORDER BY fail_count DESC
    ''', (since,))

    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ========== 备份记录 ==========

def log_backup(host: str, file_path: str):
    """记录一次备份"""
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute('''
        INSERT INTO backups (host, file_path, file_size, created_at)
        VALUES (?, ?, ?, ?)
    ''', (host.strip(), file_path, file_size, now))

    conn.commit()
    conn.close()
    logger.info(f"[DB] 备份记录入库: {host} -> {file_path}")


def get_latest_backup(host: str) -> Optional[Dict]:
    """查某台设备最近一次备份"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT * FROM backups WHERE host = ? ORDER BY created_at DESC LIMIT 1
    ''', (host.strip(),))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


# ========== 巡检记录 ==========

def log_inspection(host: str, cpu: str, memory: str, intf_down: str, status: str):
    """记录一次巡检结果"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    c.execute('''
        INSERT INTO inspections (host, cpu_usage, memory_usage, intf_down_count, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (host.strip(), cpu, memory, intf_down, status, now))

    conn.commit()
    conn.close()
    logger.debug(f"[DB] 巡检记录入库: {host} | CPU:{cpu} 内存:{memory}")


def get_inspection_history(host: str, limit: int = 10) -> List[Dict]:
    """查某台设备最近N次巡检历史（用于画趋势图）"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()
    c.execute('''
        SELECT * FROM inspections WHERE host = ? ORDER BY created_at DESC LIMIT ?
    ''', (host.strip(), limit))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]


# ========== 快捷查询（演示SQL威力）==========

def get_devices_never_backed_up(days: int = 7) -> List[str]:
    """
    查询最近N天从未备份过的设备
    这是Excel几乎不可能做到的查询
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    c.execute('''
        SELECT host FROM devices WHERE status = 'active'
        EXCEPT
        SELECT DISTINCT host FROM backups WHERE created_at >= ?
    ''', (since,))

    rows = c.fetchall()
    conn.close()
    return [row[0] for row in rows]


def get_operation_summary(days: int = 7) -> Dict:
    """
    最近N天操作汇总统计
    返回: {'total': 100, 'success': 95, 'failed': 5, 'success_rate': 95.0}
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    c.execute("SELECT COUNT(*) FROM operations WHERE created_at >= ?", (since,))
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM operations WHERE created_at >= ? AND status = 'success'", (since,))
    success = c.fetchone()[0]

    conn.close()

    failed = total - success
    rate = (success / total * 100) if total > 0 else 0
    return {
        "total": total,
        "success": success,
        "failed": failed,
        "success_rate": round(rate, 2)
    }


# 模块被导入时自动初始化（可选，看你喜欢显式调用还是自动）
# init_db()
