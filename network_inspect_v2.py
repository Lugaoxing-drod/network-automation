"""
network_inspect_v2.py
第6课产物：改造后的并发巡检脚本
核心变化：
  1. 从 SQLite 读取设备
  2. 巡检结果写入数据库（替代仅生成Excel）
  3. 保留Excel报表作为辅助输出
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from network_device import NetworkDevice
from database import get_all_devices, log_operation, log_inspection
from openpyxl import Workbook
import datetime
import os
from logger_config import setup_logger

logger = setup_logger(__name__)


def inspect_single_device(dev_info: dict):
    """
    巡检单台设备
    改造点：增加 log_operation 和 log_inspection
    """
    ip = dev_info['host']
    device = NetworkDevice(dev_info)

    # 默认失败结果
    result = {
        'host': ip,
        'device_type': dev_info.get('device_type', ''),
        'status': '失败',
        'cpu': 'N/A',
        'memory': 'N/A',
        'intf_down': 'N/A',
    }

    try:
        if device.connect():
            result = device.inspect()
            device.disconnect()

            # 【第6课新增】记录操作日志 + 巡检结果入库
            if result['status'] == '成功':
                log_operation(ip, "inspect", "success", 
                              f"CPU:{result['cpu']} 内存:{result['memory']} 接口:{result['intf_down']}")
            else:
                log_operation(ip, "inspect", "failed", "inspect() 返回失败状态")

            log_inspection(ip, result['cpu'], result['memory'], result['intf_down'], result['status'])

            logger.info(f"[✓] {ip} 完成 | CPU:{result['cpu']} | 内存:{result['memory']} | 接口异常:{result['intf_down']}")
        else:
            log_operation(ip, "inspect", "failed", "连接失败")
            log_inspection(ip, 'N/A', 'N/A', 'N/A', '失败')
            logger.error(f"[✗] {ip} 连接失败")
    except Exception as e:
        log_operation(ip, "inspect", "failed", f"异常: {str(e)}")
        log_inspection(ip, 'N/A', 'N/A', 'N/A', '失败')
        logger.error(f"[✗] {ip} 巡检异常: {e}")

    return result


def main():
    # 从 SQLite 读设备
    devices = get_all_devices()
    if not devices:
        logger.error("数据库中没有设备，请先运行 migrate_to_sqlite.py")
        return

    today = datetime.datetime.now().strftime("%Y%m%d")
    now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    # 【改动】记下本次运行起始时刻，末尾统计只算"本次"，不会被 24h 内其他运行累计进来
    run_start = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    folder = f"report_{today}"
    os.makedirs(folder, exist_ok=True)
    report_file = f"{folder}/巡检报告_{now}.xlsx"

    # 创建 Excel 工作簿（保留原有功能）
    wb = Workbook()
    ws = wb.active
    ws.title = "巡检结果"
    headers = ['设备IP', '设备类型', '连接状态', 'CPU使用率', '内存使用率', '接口异常数', '巡检时间']
    ws.append(headers)

    logger.info(f">>> 开始并发巡检（SQLite驱动），共 {len(devices)} 台设备")
    logger.info(f">>> 报告将保存到: {report_file}")

    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_ip = {
            executor.submit(inspect_single_device, dev): dev['host']
            for dev in devices
        }

        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                result = future.result()
                ws.append([
                    result['host'], result['device_type'], result['status'],
                    result['cpu'], result['memory'], result['intf_down'], now,
                ])
            except Exception as e:
                logger.error(f"[✗] {ip} 处理结果时出错: {e}")

    wb.save(report_file)
    logger.info(f">>> 巡检完成！报告已保存: {report_file}")

    # 新增：打印数据库统计
    from database import get_operation_summary
    # 【改动】原：stats = get_operation_summary(days=0)
    #   问题：days=0 时 since=now 只统计到最后一秒；days=1 又会把 24h 内多次运行累计进来。
    #   新：传 run_start（本次运行起始时刻）给 since，只统计"本次"的操作。
    stats = get_operation_summary(since=run_start)
    logger.info(f">>> 本次统计: 总计{stats['total']}次操作, 成功{stats['success']}次, 成功率{stats['success_rate']}%")


if __name__ == "__main__":
    main()
