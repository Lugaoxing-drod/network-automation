"""
backup_v2.py
第6课产物：改造后的并发备份脚本
核心变化：
  1. 从 SQLite 读取设备（替代 Excel）
  2. 备份前后记录操作日志（替代仅靠print/日志文件）
  3. 备份文件信息入库（替代仅靠文件夹浏览）
"""

from concurrent.futures import ThreadPoolExecutor
from network_device import NetworkDevice
from database import get_all_devices, log_operation, log_backup
import datetime
import os
import time
from logger_config import setup_logger

logger = setup_logger(__name__)


def backup_single_device(dev_info: dict, folder: str, now: str):
    """
    备份单台设备（线程池调用）
    改造点：
      - 入参从 Excel 行变成 database 查出来的 dict（键名一样，无缝兼容）
      - 增加 log_operation 记录操作结果
      - 增加 log_backup 记录备份文件信息
    """
    ip = dev_info['host']
    device = NetworkDevice(dev_info)

    # 【第6课新增】记录"开始尝试备份"
    log_operation(ip, "backup", "started", f"开始备份到 {folder}")

    try:
        if device.connect():
            success = device.backup(folder, now)
            device.disconnect()

            if success:
                # 【第6课新增】记录成功
                file_path = f"{folder}/backup_{ip}_{now}.txt"
                log_operation(ip, "backup", "success", f"文件: {file_path}")
                log_backup(ip, file_path)  # 备份文件信息入库
                logger.info(f"[✓] {ip} 备份成功")
            else:
                # 【第6课新增】记录失败（backup返回False）
                log_operation(ip, "backup", "failed", "backup() 返回 False")
                logger.error(f"[✗] {ip} 备份失败")
        else:
            # 【第6课新增】记录连接失败
            log_operation(ip, "backup", "failed", "连接失败")
            logger.error(f"[✗] {ip} 连接失败")
    except Exception as e:
        # 【第6课新增】记录异常
        log_operation(ip, "backup", "failed", f"异常: {str(e)}")
        logger.error(f"[✗] {ip} 异常: {e}")


def main():
    # ========== 第6课核心改造点1：从 SQLite 读设备 ==========
    # 原：devices = read_devices("devices.xlsx")
    # 新：从数据库读，支持按角色筛选，Excel被打开也不影响
    devices = get_all_devices()  # 读所有active设备

    if not devices:
        logger.error("数据库中没有设备，请先运行 migrate_to_sqlite.py")
        return

    today = datetime.datetime.now().strftime("%Y%m%d")
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    folder = f"backup_{today}"
    os.makedirs(folder, exist_ok=True)

    logger.info(f">>> 开始并发备份（SQLite驱动），共 {len(devices)} 台设备")
    logger.info(f">>> 保存到文件夹: {folder}")
    start_time = time.time()

    with ThreadPoolExecutor(max_workers=5) as executor:
        for dev_info in devices:
            executor.submit(backup_single_device, dev_info, folder, now)

    end_time = time.time()
    logger.info(f">>> 全部完成！总耗时: {end_time - start_time:.2f} 秒")
    logger.info(f">>> 备份保存在: {folder}")

    # 【第6课新增】跑完后打印统计
    from database import get_operation_summary
    stats = get_operation_summary(days=0)  # 今天
    logger.info(f">>> 本次统计: 总计{stats['total']}次操作, 成功{stats['success']}次, 成功率{stats['success_rate']}%")


if __name__ == "__main__":
    main()
