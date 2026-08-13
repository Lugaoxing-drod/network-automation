import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config_push import read_devices, render_template

devices = read_devices("../devices.xlsx")

for dev in devices:
    print(f"\n=== 设备 {dev['host']} ===")
    
    vlan_vars = {
        'vlan_id': dev['vlan_id'],
        'vlan_name': dev['vlan_name'],
        'interface': dev['interface'],
    }
    commands = render_template('../templates/vlan_config.j2', vlan_vars)
    print("VLAN 命令：")
    for cmd in commands:
        print(f"  {cmd}")
    
    ip_vars = {
        'interface': dev['interface'],
        'ip_address': dev['ip_address'],
        'subnet_mask': dev['subnet_mask'],
    }
    commands = render_template('../templates/interface_ip.j2', ip_vars)
    print("IP 命令：")
    for cmd in commands:
        print(f"  {cmd}")