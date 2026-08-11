from openpyxl import load_workbook
from network_device import NetworkDevice


def read_devices(excel_file):
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


devices = read_devices("devices.xlsx")

print(">>> 开始批量下发 VLAN 100")
for dev_info in devices:
    device = NetworkDevice(dev_info)
    if device.connect():
        device.create_vlan(100, "Office_5F")
        device.disconnect()

print("\n>>> 全部完成！")