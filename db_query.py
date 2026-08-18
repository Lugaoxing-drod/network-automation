"""
db_query.py
第6课辅助工具：演示 SQLite 的查询能力
用法：python db_query.py
"""

from database import (
    get_recent_operations, 
    get_failure_stats, 
    get_devices_never_backed_up,
    get_operation_summary,
    get_inspection_history,
    get_latest_backup
)
from logger_config import setup_logger

logger = setup_logger(__name__)


def print_section(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def main():
    # 1. 最近7天操作记录（最近10条）
    print_section("最近7天操作记录（最近10条）")
    ops = get_recent_operations(days=7)
    for op in ops[:10]:
        print(f"  {op['created_at']} | {op['host']} | {op['operation_type']:12} | {op['status']:8} | {op['detail']}")
    if not ops:
        print("  （暂无记录，先跑几次 backup_v2.py 再来查）")

    # 2. 最近7天失败统计
    print_section("最近7天失败统计（按设备）")
    fails = get_failure_stats(days=7)
    for f in fails:
        print(f"  {f['host']}: 失败 {f['fail_count']} 次")
    if not fails:
        print("  （最近7天没有失败记录，很好！）")

    # 3. 从未备份的设备
    print_section("最近7天从未备份过的设备")
    never = get_devices_never_backed_up(days=7)
    for ip in never:
        print(f"  {ip}")
    if not never:
        print("  （所有设备都有备份记录）")

    # 4. 操作汇总
    print_section("最近7天操作汇总")
    stats = get_operation_summary(days=7)
    print(f"  总操作: {stats['total']}")
    print(f"  成功:   {stats['success']}")
    print(f"  失败:   {stats['failed']}")
    print(f"  成功率: {stats['success_rate']}%")

    # 5. 单台设备巡检历史示例（如果有数据）
    print_section("示例：192.168.1.254 最近巡检历史")
    history = get_inspection_history("192.168.1.254", limit=5)
    for h in history:
        print(f"  {h['created_at']} | CPU:{h['cpu_usage']} | 内存:{h['memory_usage']} | 接口异常:{h['intf_down_count']}")
    if not history:
        print("  （暂无巡检记录，先跑改造后的巡检脚本）")

    # 6. 单台设备最新备份
    print_section("示例：192.168.1.254 最新备份")
    latest = get_latest_backup("192.168.1.254")
    if latest:
        print(f"  文件: {latest['file_path']}")
        print(f"  大小: {latest['file_size']} 字节")
        print(f"  时间: {latest['created_at']}")
    else:
        print("  （暂无备份记录）")


if __name__ == "__main__":
    main()
