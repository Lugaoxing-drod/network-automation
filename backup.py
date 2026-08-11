import datetime
import os
from openpyxl import load_workbook
from network_device import NetworkDevice  # 从类文件导入


def read_devices(excel_file):
    """从 Excel 读取设备列表"""
    wb = load_workbook(excel_file)
    sheet = wb.active
    devices = []
    for row in sheet.iter_rows(min_row=2, values_only=True):
        device_type, host, username, password = row
        devices.append({
            'device_type': device_type,
            'host': host,
            'username': username,
            'password': password,
        })
    return devices


# ========== 主程序 ==========
devices = read_devices("devices.xlsx")

today = datetime.datetime.now().strftime("%Y%m%d")
now = datetime.datetime.now().strftime("%Y%m%d_%H%M")

folder = f"backup_{today}"
os.makedirs(folder, exist_ok=True)

print(f">>> 开始备份，共 {len(devices)} 台设备")
print(f">>> 保存到文件夹: {folder}")

for dev_info in devices:
    # 创建设备对象
    device = NetworkDevice(dev_info)
    
    # 连接 → 备份 → 断开，一气呵成
    if device.connect():
        device.backup(folder, now)
        device.disconnect()

print("\n>>> 备份全部完成！")