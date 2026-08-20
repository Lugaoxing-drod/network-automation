"""
config_push_v2.py
第7课产物：改造后的基础配置下发脚本
核心变化：使用 SafePusher 替代原有的 safe_push_config，实现完整的 备份→下发→验证→回滚 闭环
"""

from jinja2 import Template
from openpyxl import load_workbook
from network_device import NetworkDevice
from safe_pusher import SafePusher
from database import get_all_devices
from logger_config import setup_logger

logger = setup_logger(__name__)


def read_devices_from_db():
    """
    从 SQLite 读取设备（第6课已迁移）
    替代原有的 read_devices("devices.xlsx")
    """
    devices = get_all_devices()
    # 【改动】原：直接返回 get_all_devices() 的全部设备（含路由器/核心/汇聚/服务器）
    #   问题：本脚本只用 vlan_config.j2 / interface_ip.j2 两个"接入交换机"基础模板，
    #        路由/核心/汇聚的 vlan_id、interface 字段是 "-" 或空，会渲染出 "vlan -"、
    #        "interface -" 垃圾命令，下发到这些设备上会配错。
    #   新：只保留 role='access' 的接入交换机，基础模板只适用于接入设备。
    devices = [d for d in devices if d.get('role') == 'access']
    if not devices:
        logger.error("数据库中没有接入交换机(role='access')，请先运行 migrate_to_sqlite.py")
    return devices


def render_template(template_file: str, variables: dict) -> list:
    """
    读取 Jinja2 模板，渲染变量，返回命令列表
    """
    with open(template_file, 'r', encoding='utf-8') as f:
        template = Template(f.read())

    config_text = template.render(**variables)
    commands = [line.strip() for line in config_text.split('\n') if line.strip() and not line.strip().startswith('#')]
    return commands


def main():
    devices = read_devices_from_db()

    if not devices:
        return

    logger.info(f">>> 开始配置下发（SafePusher闭环），共 {len(devices)} 台设备\n")

    success_count = 0
    rollback_count = 0
    fail_count = 0

    for dev_info in devices:
        ip = dev_info['host']
        logger.info(f">>> 正在处理 {ip} ...")

        device = NetworkDevice(dev_info)
        pusher = SafePusher(device)

        # ========== 下发 VLAN（使用模板）==========
        vlan_vars = {
            'vlan_id': dev_info.get('vlan_id', ''),
            'vlan_name': dev_info.get('vlan_name', ''),
            'interface': dev_info.get('interface', ''),
        }
        vlan_commands = render_template('templates/vlan_config.j2', vlan_vars)

        vlan_result = pusher.push(
            commands=vlan_commands,
            description=f"VLAN {dev_info.get('vlan_id', '')} ({dev_info.get('vlan_name', '')})",
            verify=True  # 启用验证
        )

        if vlan_result['success']:
            success_count += 1
        elif vlan_result['action'] == 'rollbacked':
            rollback_count += 1
        else:
            fail_count += 1

        logger.info(f"    [{vlan_result['action'].upper()}] {vlan_result['detail']}")

        # 如果VLAN下发失败且已回滚，跳过IP配置（设备已断开）
        if not vlan_result['success'] and vlan_result['action'] != 'rollbacked':
            logger.warning(f"    ⚠ {ip} VLAN下发彻底失败，跳过IP配置\n")
            continue

        # 如果VLAN回滚了，设备已断开，需要重新连接才能继续
        if vlan_result['action'] == 'rollbacked':
            logger.warning(f"    ⚠ {ip} VLAN已回滚，跳过IP配置\n")
            continue

        # ========== 下发接口 IP（使用模板）==========
        ip_vars = {
            'interface': dev_info.get('interface', ''),
            'ip_address': dev_info.get('ip_address', ''),
            'subnet_mask': dev_info.get('subnet_mask', ''),
        }
        ip_commands = render_template('templates/interface_ip.j2', ip_vars)

        # 重新创建pusher（因为之前的push已断开连接）
        device2 = NetworkDevice(dev_info)
        pusher2 = SafePusher(device2)

        ip_result = pusher2.push(
            commands=ip_commands,
            description=f"接口 {dev_info.get('interface', '')} IP",
            verify=True
        )

        if ip_result['success']:
            success_count += 1
        elif ip_result['action'] == 'rollbacked':
            rollback_count += 1
        else:
            fail_count += 1

        logger.info(f"    [{ip_result['action'].upper()}] {ip_result['detail']}")
        logger.info(f">>> {ip} 处理完成\n")

    logger.info(">>> 全部设备处理完成")
    logger.info(f">>> 统计: 成功保存 {success_count} 次, 自动回滚 {rollback_count} 次, 失败 {fail_count} 次")


if __name__ == "__main__":
    main()
