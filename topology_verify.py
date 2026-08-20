"""
topology_verify.py
全网连通性验证
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from network_device import NetworkDevice
#from openpyxl import load_workbook
from database import get_all_devices
from logger_config import setup_logger

logger = setup_logger(__name__)


# def read_devices(excel_file):
#     wb = load_workbook(excel_file)
#     sheet = wb.active
#     devices = []
#     for row in sheet.iter_rows(min_row=2, values_only=True):
#         if not row or not row[0] or not row[1]:
#             continue
#         _, host, username, password, role = row[:5]
#         devices.append({
#             # 【改动】按角色切换连接方式（同 topology_push.py）：
#             #   原：'device_type': device_type,  ← 读 Excel 第1列（全是 'huawei' 即 SSH）
#             #   新：路由器保持 huawei(SSH)，8 台老交换机改 huawei_telnet，
#             #       否则老交换机 SSH 不兼容连不上（和下发脚本同样的坑）。
#             'device_type': 'huawei' if role == 'router' else 'huawei_telnet',
#             'host': host,
#             'username': username,
#             'password': password,
#             'role': role,
#         })
#     wb.close()
#     return devices


def verify_device(dev_info):
    ip = dev_info['host']
    role = dev_info['role']
    device = NetworkDevice(dev_info)
    
    checks = {
        'host': ip,
        'role': role,
        'connect': False,
        'vlan_status': 'N/A',
        'routes': 'N/A',
        'acl': 'N/A'
    }
    
    if not device.connect():
        logger.error(f"[✗] {ip} 连接失败")
        return checks
    
    checks['connect'] = True
    
    try:
        # 【改动】下面 4 处 show 命令从 device.send_command(...) 改为
        #   device.connection.send_command_timing(..., read_timeout=30)。
        #   原因：send_command 默认 auto_find_prompt=True 会先重读提示符，
        #        把登录时 screen-length 0 temporary 残留的 "Info: ..." 误当提示符，
        #        真正的 show 输出还没读就被当成"读完了"→ 返回空字符串 → 误报"异常"。
        #   send_command_timing 原样读完整输出，不受残留回显影响。
        if role in ['core', 'agg', 'access', 'server']:
            # 原：vlan_out = device.send_command("display vlan")
            vlan_out = device.connection.send_command_timing("display vlan", read_timeout=30)
            checks['vlan_status'] = '已配置' if 'VLAN' in vlan_out else '异常'

        if role in ['core', 'router']:
            # 原：route_out = device.send_command("display ip routing-table")
            route_out = device.connection.send_command_timing("display ip routing-table", read_timeout=30)
            checks['routes'] = '有路由' if 'Static' in route_out or 'Direct' in route_out else '异常'

        if role == 'core':
            # 原：acl_out = device.send_command("display acl all")
            acl_out = device.connection.send_command_timing("display acl all", read_timeout=30)
            checks['acl'] = '已配置' if '3000' in acl_out else '未配置'

        if role == 'access':
            # 原：intf_out = device.send_command("display interface brief")
            intf_out = device.connection.send_command_timing("display interface brief", read_timeout=30)
            checks['vlan_status'] = '接口UP' if 'up' in intf_out.lower() else '检查接口'

        logger.info(f"[✓] {ip} ({role}) 验证完成")
        
    except Exception as e:
        logger.error(f"[✗] {ip} 验证出错: {e}")
    
    device.disconnect()
    return checks


def main():
    #devices = read_devices("new_topology.xlsx")
    devices = get_all_devices()
    logger.info(f">>> 开始全网验证，共 {len(devices)} 台设备")
    
    results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_ip = {executor.submit(verify_device, d): d['host'] for d in devices}
#       future_to_ip = {}
#       for d in devices:
#       # d就是read_devices解析出来的单台设备字典(dev_info)
#       future = executor.submit(verify_device, d)   # ✅提交校验任务，子线程跑verify_device(d)
#       future_to_ip[future] = d['host']             # key:future对象，value:设备IP
        for future in as_completed(future_to_ip):
            ip = future_to_ip[future]
            try:
                results.append(future.result())
            except Exception as e:
                logger.error(f"[✗] {ip} 验证异常: {e}")
    
    logger.info("\n========== 验证汇总 ==========")
    for r in results:
        status = "✓" if r['connect'] else "✗"
        logger.info(f"{status} {r['host']} ({r['role']}) | VLAN:{r['vlan_status']} | 路由:{r['routes']} | ACL:{r['acl']}")


if __name__ == "__main__":
    main()