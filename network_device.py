from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoTimeoutException, NetmikoAuthenticationException
import datetime
import os
import re
from logger_config import setup_logger

# 创建模块级 logger
logger = setup_logger(__name__)

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
            # 【改动】关闭命令回显校验：telnet 下华为设备对含中文的 description 命令
            #   回显会换行，netmiko 默认的逐条回显校验(cmd_verify=True)匹配不到 →
            #   报 "Pattern not detected"。设 False 后全局跳过回显校验，
            #   send_command / send_config_set / save_config 一并生效。
            self.connection.global_cmd_verify = False
            return True
        except NetmikoTimeoutException:
            logger.error(f"连接超时: {self.host}")
            return False
        except NetmikoAuthenticationException:
            logger.error(f"认证失败: {self.host}")
            return False
        except Exception as e:
            logger.error(f"其他错误: {e}")
            return False
    
    def disconnect(self):
        """断开 SSH 连接"""
        if self.connection:
            self.connection.disconnect()
            self.connection = None
    
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self.connection is not None

# ========== 通用底层方法（新增）==========
    def send_command(self, command: str) -> str:
        if not self.is_connected():
            return ""
        try:
            return self.connection.send_command(command)
        except Exception as e:
            logger.error(f"命令执行失败: {e}")
            return ""

    def send_config(self, commands: list) -> str:
        if not self.is_connected():
            return ""
        try:
            # 【改动】原：output = self.connection.send_config_set(commands)
            #   问题：send_config_set 是"先把全部命令一次性写完、再末尾一次性读回显"，
            #        遇到 eNSP 上极慢的 interface Vlanif 命令（实测单条 150s+，期间
            #        设备静默无输出），读到 2 秒静默就提前返回 → 报
            #        "read_channel_timing's absolute timer expired"。
            #   新：逐条 send_command，每条都等提示符（read_timeout=300s 够慢命令跑完），
            #       且 cmd_verify=False 跳过回显校验，中文 description 也不会报
            #        "Pattern not detected"。
            output = "" 
            if not self.connection.check_config_mode():
                output += self.connection.config_mode()
                # - `check_config_mode()`：检查当前是否已经处于**系统配置视图**。
                # - 如果不在配置视图，调用`config_mode()`输入`system‑view`进入配置模式。
            for cmd in commands:
                # 【改动】加 auto_find_prompt=False：
                #   原：send_command 默认 auto_find_prompt=True，会先 find_prompt()（发回车重新读提示符），
                #       SSH 上会把上一条命令回显误读成提示符（实测读到 'descriptio'）→ 报
                #       "Pattern not detected"。设 False 后用稳定的 base_prompt（主机名）匹配子视图提示符。
                output += self.connection.send_command(
                    cmd, read_timeout=300, cmd_verify=False, auto_find_prompt=False
                )
            output += self.connection.exit_config_mode()
            return output
        except Exception as e:
            logger.error(f"配置下发失败: {e}")
            # 【改动】原：return ""  ← 吞掉异常，上层 safe_push_config 会误判"下发成功"
            #   新：重新抛出，让上层正确捕获并报告失败
            raise
    
    def backup(self, folder: str, timestamp: str) -> bool:
        """
        备份设备配置
        folder: 保存文件夹路径
        timestamp: 时间戳字符串
        返回值: True 成功, False 失败
        """
        if not self.is_connected():
            logger.warning(f"未连接，跳过备份: {self.host}")
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
            
            logger.info(f"备份成功 -> {filename}")
            return True
            
        except Exception as e:
            logger.error(f"备份失败: {e}")
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
            logger.info(f"    CPU: {result['cpu']} | 内存: {result['memory']} | 接口异常: {result['intf_down']}")
            
        except Exception as e:
            logger.error(f"    巡检出错: {e}")
        
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
    