"""
config_verifier.py
配置验证模块（第7课核心）
职责：下发配置后，验证配置是否真的生效了
"""

import re
from logger_config import setup_logger

logger = setup_logger(__name__)


class ConfigVerifier:
    """
    配置验证器
    针对不同类型的配置，提供对应的验证方法
    """

    @staticmethod
    def verify_vlan_exists(device, vlan_id) -> bool:
        """
        验证VLAN是否存在
        :param device: NetworkDevice 对象（已连接）
        :param vlan_id: VLAN编号
        :return: True存在, False不存在
        """
        try:
            # 【第5课经验】用send_command_timing避免残留回显影响
            output = device.connection.send_command_timing("display vlan", read_timeout=30)
            # 匹配 "10    common  UT:GE0/0/1" 或 "VLAN 10" 等格式
            pattern = rf"\b{vlan_id}\b"
            found = bool(re.search(pattern, output))
            logger.debug(f"[Verify] VLAN {vlan_id} 验证结果: {found}")
            return found
        except Exception as e:
            logger.error(f"[Verify] VLAN {vlan_id} 验证异常: {e}")
            return False

    @staticmethod
    def verify_interface_ip(device, interface: str, expected_ip: str) -> bool:
        """
        验证接口IP是否配置成功
        """
        try:
            output = device.connection.send_command_timing(
                "display ip interface brief", read_timeout=30
            )
            # 简化判断：只要IP出现在输出里就认为成功（精确匹配需要解析表格）
            found = expected_ip in output
            logger.debug(f"[Verify] 接口 {interface} IP {expected_ip} 验证结果: {found}")
            return found
        except Exception as e:
            logger.error(f"[Verify] 接口IP验证异常: {e}")
            return False

    @staticmethod
    def verify_acl_exists(device, acl_number) -> bool:
        """
        验证ACL是否存在
        """
        try:
            output = device.connection.send_command_timing("display acl all", read_timeout=30)
            # 匹配 "Advanced ACL 3000" 或 "ACL number 3000" 或 "3000"
            pattern = rf"\b{acl_number}\b"
            found = bool(re.search(pattern, output))
            logger.debug(f"[Verify] ACL {acl_number} 验证结果: {found}")
            return found
        except Exception as e:
            logger.error(f"[Verify] ACL验证异常: {e}")
            return False

    @staticmethod
    def verify_route_exists(device, dest_network: str) -> bool:
        """
        验证静态路由是否存在
        :param dest_network: 目标网段，如 "192.168.10.0"
        """
        try:
            output = device.connection.send_command_timing(
                "display ip routing-table", read_timeout=30
            )
            found = dest_network in output
            logger.debug(f"[Verify] 路由 {dest_network} 验证结果: {found}")
            return found
        except Exception as e:
            logger.error(f"[Verify] 路由验证异常: {e}")
            return False

    @staticmethod
    def verify_trunk_vlan(device, interface: str, vlan_id) -> bool:
        """
        验证Trunk口是否允许指定VLAN通过
        """
        try:
            output = device.connection.send_command_timing(
                f"display interface {interface}", read_timeout=30
            )
            # 简化判断：接口输出中包含vlan_id且包含trunk
            has_vlan = str(vlan_id) in output
            has_trunk = "trunk" in output.lower()
            found = has_vlan and has_trunk
            logger.debug(f"[Verify] Trunk {interface} VLAN{vlan_id} 验证结果: {found}")
            return found
        except Exception as e:
            logger.error(f"[Verify] Trunk验证异常: {e}")
            return False

    @staticmethod
    def verify_access_vlan(device, interface: str, vlan_id) -> bool:
        """
        验证Access口是否属于指定VLAN
        """
        try:
            output = device.connection.send_command_timing(
                f"display interface {interface}", read_timeout=30
            )
            # 查找 "Port link-type: access" 和 "Port default VLAN: 10"
            has_access = "access" in output.lower()
            has_vlan = f"Port default VLAN: {vlan_id}" in output or f"default vlan {vlan_id}" in output.lower()
            found = has_access and (has_vlan or str(vlan_id) in output)
            logger.debug(f"[Verify] Access {interface} VLAN{vlan_id} 验证结果: {found}")
            return found
        except Exception as e:
            logger.error(f"[Verify] Access验证异常: {e}")
            return False

    def verify_config_set(self, device, commands: list) -> tuple:
        """
        智能验证入口：根据commands内容自动判断需要验证什么

        :return: (全部通过?, {验证项: 结果})
        """
        results = {}
        in_interface = False
        current_interface = None

        for cmd in commands:
            stripped = cmd.strip()

            # 进入接口视图
            if stripped.startswith("interface "):
                in_interface = True
                current_interface = stripped.replace("interface ", "").strip()
                continue

            # 退出接口视图
            if stripped == "quit" or stripped == "return":
                in_interface = False
                current_interface = None
                continue

            # VLAN创建
            if stripped.startswith("vlan ") and "batch" not in stripped:
                parts = stripped.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    vid = parts[1]
                    key = f"vlan_{vid}"
                    results[key] = self.verify_vlan_exists(device, vid)

            # 接口IP
            elif stripped.startswith("ip address ") and in_interface and current_interface:
                parts = stripped.split()
                if len(parts) >= 2:
                    ip = parts[2] if parts[1] == "address" else parts[1]
                    key = f"ip_{current_interface}"
                    results[key] = self.verify_interface_ip(device, current_interface, ip)

            # ACL
            elif stripped.startswith("acl number "):
                parts = stripped.split()
                if len(parts) >= 3:
                    acl_num = parts[2]
                    key = f"acl_{acl_num}"
                    results[key] = self.verify_acl_exists(device, acl_num)

            # 静态路由
            elif stripped.startswith("ip route-static "):
                parts = stripped.split()
                if len(parts) >= 2:
                    dest = parts[2] if parts[1] == "route-static" else parts[1]
                    key = f"route_{dest}"
                    results[key] = self.verify_route_exists(device, dest)

            # Trunk配置
            elif stripped.startswith("port trunk allow-pass vlan ") and in_interface:
                # 提取最后一个vlan id（简化处理）
                parts = stripped.split()
                if len(parts) >= 5:
                    vlan_part = parts[-1]
                    # 可能 "10 20 30" 或 "10"
                    first_vlan = vlan_part.split(",")[0].split()[0]
                    key = f"trunk_{current_interface}_vlan{first_vlan}"
                    results[key] = self.verify_trunk_vlan(device, current_interface, first_vlan)

            # Access配置
            elif stripped.startswith("port default vlan ") and in_interface:
                parts = stripped.split()
                if len(parts) >= 4:
                    vid = parts[3]
                    key = f"access_{current_interface}_vlan{vid}"
                    results[key] = self.verify_access_vlan(device, current_interface, vid)

        # 【改动】原：all_passed = all(results.values()) if results else True
        #   问题：当 commands 里没有任何可识别的验证项（比如只有 description/port-security
        #        等不支持验证的命令）时，results 为空，`else True` 会让"什么都没验证"被当成
        #        "全部通过"，属于空验证通过——掩盖了"验证器根本没干活"的事实。
        #   新：results 为空时打警告提示"无可验证项"，但仍返回 True，避免误触发回滚
        #        （空配置≠配置失败，宁可放过、不要因验证器没覆盖而误回滚）。
        if not results:
            logger.warning("[Verify] 未识别到任何可验证的配置项（results 为空），跳过验证")
        all_passed = all(results.values()) if results else True

        if not all_passed:
            failed = [k for k, v in results.items() if not v]
            logger.warning(f"[Verify] 验证未通过项: {failed}")

        return all_passed, results
