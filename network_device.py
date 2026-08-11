from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
import datetime
import os
import re


class NetworkDevice:
    """
    网络设备类：一台设备就是一个对象
    包含连接、备份、巡检、断开等方法
    """
    
    def __init__(self, device_dict):
        """
        构造函数：创建对象时自动执行
        device_dict: 从 Excel 读出来的一行设备信息
        """
        self.device_type = device_dict['device_type']
        self.host = device_dict['host']
        self.username = device_dict['username']
        self.password = device_dict['password']
        self.connection = None  # 初始未连接
    
    def connect(self) -> bool:
        """
        建立 SSH 连接
        返回值: True 成功, False 失败
        """
        try:
            self.connection = ConnectHandler(
                device_type=self.device_type,
                host=self.host,
                username=self.username,
                password=self.password,
            )
            return True
        except NetmikoTimeoutException:
            print(f"    连接超时: {self.host}")
            return False
        except NetmikoAuthenticationException:
            print(f"    认证失败: {self.host}")
            return False
        except Exception as e:
            print(f"    其他错误: {e}")
            return False
    
    def disconnect(self):
        """断开 SSH 连接"""
        if self.connection:
            self.connection.disconnect()
            self.connection = None
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connection is not None
    
    def backup(self, folder: str, timestamp: str) -> bool:
        """
        备份设备配置
        folder: 保存文件夹路径
        timestamp: 时间戳字符串
        返回值: True 成功, False 失败
        """
        if not self.is_connected():
            print(f"    未连接，跳过备份: {self.host}")
            return False
        
        try:
            # 根据设备类型选择命令
            if self.device_type == 'huawei':
                command = "display current-configuration"
            else:
                command = "show running-config"
            
            config = self.connection.send_command(command)
            
            filename = f"{folder}/backup_{self.host}_{timestamp}.txt"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(config)
            
            print(f"    备份成功 -> {filename}")
            return True
            
        except Exception as e:
            print(f"    备份失败: {e}")
            return False
    
    def inspect(self) -> dict:
        """
        巡检设备，返回字典格式的结果
        返回值: {'cpu': 'xx%', 'memory': 'xx%', 'intf_down': 'x', 'status': '成功/失败'}
        """
        result = {
            'host': self.host,
            'device_type': self.device_type,
            'status': '失败',
            'cpu': 'N/A',
            'memory': 'N/A',
            'intf_down': 'N/A',
        }
        
        if not self.is_connected():
            return result
        
        try:
            # 抓 CPU
            cpu_out = self.connection.send_command("display cpu-usage")
            result['cpu'] = self._parse_cpu(cpu_out)
            
            # 抓内存
            mem_out = self.connection.send_command("display memory")
            result['memory'] = self._parse_memory(mem_out)
            
            # 抓接口
            intf_out = self.connection.send_command("display interface brief")
            result['intf_down'] = self._parse_interface(intf_out)
            
            result['status'] = '成功'
            print(f"    CPU: {result['cpu']} | 内存: {result['memory']} | 接口异常: {result['intf_down']}")
            
        except Exception as e:
            print(f"    巡检出错: {e}")
        
        return result
    
    # ========== 私有方法：解析函数，只在类内部使用 ==========
    def _parse_cpu(self, output: str) -> str:
        """解析 CPU 使用率"""
        if 'disabled' in output.lower():
            return 'eNSP不支持'
        
        match = re.search(r'CPU\s*[Uu]sage\s*[:：]\s*(\d+)%', output)
        if match:
            return match.group(1) + '%'
        return 'N/A'
    
    def _parse_memory(self, output: str) -> str:
        """解析内存使用率"""
        match = re.search(r'Memory\s*Using\s*Percentage\s*Is\s*[:：]\s*(\d+)%', output)
        if match:
            return match.group(1) + '%'
        return 'N/A'
    
    def _parse_interface(self, output: str) -> str:
        """统计 down 掉的接口数"""
        down_count = 0
        for line in output.splitlines():
            stripped = line.strip()
            if not stripped or stripped[0] in '*^#(':
                continue
            if 'Interface' in line or 'PHY' in line or 'Protocol' in line:
                continue
            if 'down' in stripped.lower():
                if '/' in line or 'Ethernet' in line or 'LoopBack' in line or 'Vlan' in line:
                    down_count += 1
        return str(down_count)
    
    def create_vlan(self, vlan_id: int, vlan_name: str) -> bool:
        """
        下发 VLAN 配置
        """
        if not self.is_connected():
            return False
    
        try:
            # Netmiko 自动进入配置模式，下发命令，自动保存
            commands = [
                f'vlan {vlan_id}',
                f'name {vlan_name}',
            ]
            self.connection.send_config_set(commands)
            self.connection.save_config()  # 自动执行 save
            print(f"    ✓ VLAN {vlan_id} 创建成功")
            return True
        except Exception as e:
            print(f"    ✗ 下发失败: {e}")
            return False