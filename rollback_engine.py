"""
rollback_engine.py
回滚引擎（第7课核心）
职责：根据已下发的命令，生成对应的 undo 命令，执行回滚

重要说明：
  华为 VRP 没有 Cisco 的 "configure replace" 命令，回滚需要手动生成 undo 命令。
  本引擎处理常见命令，复杂场景（如ACL规则逐条undo）标记为"需人工介入"。
"""

from logger_config import setup_logger

logger = setup_logger(__name__)


class RollbackEngine:
    """
    回滚引擎
    将配置命令转换为对应的 undo 命令
    """

    def __init__(self):
        # 记录哪些命令类型支持自动回滚
        self.auto_rollback_supported = {
            'vlan', 'ip route-static', 'stp', 'acl number',
            'interface_ip', 'interface_desc', 'port_link_type',
            'port_default_vlan', 'port_trunk_vlan', 'traffic_filter'
        }

    def generate_undo(self, original_commands: list) -> list:
        """
        根据原命令生成 undo 命令列表

        核心逻辑：
          1. 倒序遍历原命令（先undo后配的配置，避免依赖问题）
          2. 识别命令类型，生成对应undo
          3. 接口视图内的命令，需要重新进入接口再undo

        :param original_commands: 原配置命令列表
        :return: undo 命令列表（可直接传给 send_config）
        """
        undo_commands = []
        undo_commands.append("system-view")  # 确保在配置视图

        # 倒序处理，但先收集接口上下文
        interface_stack = []
        parsed = []

        for cmd in original_commands:
            stripped = cmd.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("interface "):
                interface_stack.append(stripped)
                parsed.append({"type": "interface_enter", "cmd": stripped, "interface": stripped.replace("interface ", "")})
            elif stripped in ("quit", "return", "exit"):
                if interface_stack:
                    interface_stack.pop()
                parsed.append({"type": "exit", "cmd": stripped})
            elif interface_stack:
                parsed.append({
                    "type": "interface_cmd",
                    "cmd": stripped,
                    "interface": interface_stack[-1]
                })
            else:
                parsed.append({"type": "global_cmd", "cmd": stripped})

        # 倒序生成undo
        current_interface = None

        for item in reversed(parsed):
            if item["type"] == "interface_enter":
                # 【改动】原：current_interface = None  # 只清状态，没发 quit 退出接口视图
                #   问题：前面已 undo 完接口内命令（如 undo ip address），但此时仍停在
                #         接口视图，紧接的全局命令（如 undo vlan 10）会在接口视图下执行
                #         → 报 "Unrecognized command"，导致最常见的
                #         vlan + interface + ip address 场景回滚失败。
                #   新：如果当前还在接口视图内，先发 quit 退回系统视图，再清状态。
                if current_interface:
                    undo_commands.append("quit")
                current_interface = None  # 退出接口视图
                continue

            if item["type"] == "exit":
                continue

            cmd = item["cmd"]

            # 接口视图命令
            if item["type"] == "interface_cmd":
                intf = item["interface"]
                if current_interface != intf:
                    undo_commands.append(intf)
                    current_interface = intf

                undo = self._undo_single_command(cmd)
                if undo:
                    undo_commands.append(undo)

            # 全局命令
            elif item["type"] == "global_cmd":
                # 全局命令不需要接口上下文
                if current_interface:
                    undo_commands.append("quit")
                    current_interface = None

                undo = self._undo_single_command(cmd)
                if undo:
                    undo_commands.append(undo)

        # 最后退出配置视图
        undo_commands.append("return")

        logger.info(f"[Rollback] 生成 {len(undo_commands)} 条 undo 命令")
        return undo_commands

    def _undo_single_command(self, cmd: str) -> str:
        """
        单条命令的 undo 生成
        返回空字符串表示"不支持自动undo，需人工处理"
        """
        stripped = cmd.strip()
        parts = stripped.split()

        # VLAN
        if stripped.startswith("vlan ") and "batch" not in stripped:
            return f"undo {stripped}"

        # 静态路由
        if stripped.startswith("ip route-static "):
            return f"undo {stripped}"

        # STP
        if stripped.startswith("stp "):
            return f"undo {stripped}"

        # ACL整体
        if stripped.startswith("acl number "):
            return f"undo {stripped}"

        # ACL规则（在ACL视图内）
        if stripped.startswith("rule "):
            return f"undo {stripped}"

        # 接口IP
        if stripped.startswith("ip address "):
            return "undo ip address"

        # 接口描述
        if stripped.startswith("description "):
            return "undo description"

        # 端口类型
        if stripped.startswith("port link-type "):
            return "undo port link-type"

        # Access VLAN
        if stripped.startswith("port default vlan "):
            return "undo port default vlan"

        # Trunk允许VLAN
        if stripped.startswith("port trunk allow-pass vlan "):
            return "undo port trunk allow-pass vlan"

        # 流量过滤
        if stripped.startswith("traffic-filter "):
            return f"undo {stripped}"

        # NAT
        if stripped.startswith("nat outbound "):
            return "undo nat outbound"

        # 端口安全
        if stripped.startswith("port-security "):
            return f"undo {stripped}"

        # 边缘端口
        if stripped.startswith("stp edged-port "):
            return "undo stp edged-port"

        # 默认路由
        if stripped.startswith("ip route-static 0.0.0.0 "):
            return f"undo {stripped}"

        # 不支持的命令，记录日志但不生成undo
        logger.warning(f"[Rollback] 不支持自动undo的命令: {stripped}")
        return ""

    def execute_rollback(self, device, undo_commands: list) -> tuple:
        """
        执行回滚

        :return: (成功?, 详情)
        """
        if not undo_commands:
            return False, "无可用undo命令"

        # 过滤空命令
        clean_commands = [c for c in undo_commands if c.strip()]

        logger.info(f"[Rollback] 开始执行回滚，共 {len(clean_commands)} 条命令")

        try:
            output = device.send_config(clean_commands)
            logger.info("[Rollback] 回滚命令下发完成")
            return True, output
        except Exception as e:
            logger.error(f"[Rollback] 回滚执行失败: {e}")
            return False, str(e)

    def is_fully_supported(self, commands: list) -> tuple:
        """
        判断一批命令是否全部支持自动回滚

        :return: (是否全支持, [不支持的命令列表])
        """
        unsupported = []
        in_interface = False

        for cmd in commands:
            stripped = cmd.strip()
            if not stripped or stripped.startswith("#"):
                continue

            if stripped.startswith("interface "):
                in_interface = True
                continue
            if stripped in ("quit", "return", "exit"):
                in_interface = False
                continue

            undo = self._undo_single_command(stripped)
            if not undo:
                unsupported.append(stripped)

        return len(unsupported) == 0, unsupported
