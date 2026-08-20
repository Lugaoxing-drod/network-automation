"""
safe_pusher.py
安全配置下发器（第7课核心产物）
职责：整合 备份 → 下发 → 验证 → 保存/回滚 → 审计 的完整闭环

使用方式：
    from safe_pusher import SafePusher

    pusher = SafePusher(device)
    result = pusher.push(commands, description="创建VLAN10", verify=True)

    # result 示例：
    # {'success': True, 'action': 'saved', 'detail': '配置已保存。备份文件: backup_xxx/...'}
    # {'success': False, 'action': 'rollbacked', 'detail': '验证失败，已自动回滚。备份文件: ...'}
    # {'success': False, 'action': 'rollback_failed', 'detail': '回滚执行失败，需人工介入。备份文件: ...'}
"""

import datetime
import os
from config_verifier import ConfigVerifier
from rollback_engine import RollbackEngine
from database import log_operation
from logger_config import setup_logger

logger = setup_logger(__name__)


class SafePusher:
    """
    安全配置下发器

    完整闭环流程：
        1. 备份当前配置 → 落盘到文件
        2. 下发新配置
        3. 验证配置是否生效（可选）
        4. 验证通过 → 保存配置
        5. 验证失败 → 执行回滚 → 再次验证回滚结果
        6. 全程记录操作审计到数据库
    """

    def __init__(self, device):
        """
        :param device: NetworkDevice 对象（已创建，未连接）
        """
        self.device = device
        self.verifier = ConfigVerifier()
        self.rollback_engine = RollbackEngine()
        self.host = device.host

    def push(self, commands: list, description: str = "", verify: bool = True) -> dict:
        """
        安全下发入口

        :param commands: 配置命令列表（Jinja2渲染后的结果）
        :param description: 变更描述，用于日志和审计
        :param verify: 是否验证配置（默认True，批量初始化时可设False）
        :return: dict，包含 success/action/detail 三个键
        """
        logger.info(f">>> [{self.host}] 开始安全下发: {description}")

        # ========== 第1步：连接设备 ==========
        if not self.device.connect():
            log_operation(self.host, "config_push", "failed", f"{description} | 连接失败")
            return {
                'success': False,
                'action': 'failed',
                'detail': '设备连接失败'
            }

        # ========== 第2步：备份当前配置 ==========
        backup_folder = f"backup_{datetime.datetime.now().strftime('%Y%m%d')}"
        os.makedirs(backup_folder, exist_ok=True)
        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')

        if not self.device.backup(backup_folder, timestamp):
            self.device.disconnect()
            log_operation(self.host, "config_push", "failed", f"{description} | 备份失败")
            return {
                'success': False,
                'action': 'failed',
                'detail': '备份当前配置失败，终止下发'
            }

        backup_path = f"{backup_folder}/backup_{self.host}_{timestamp}.txt"
        logger.info(f"    ✓ 配置已备份: {backup_path}")

        # 检查命令是否全部支持自动回滚（提前预警）
        fully_supported, unsupported = self.rollback_engine.is_fully_supported(commands)
        if not fully_supported:
            logger.warning(f"    ⚠ 以下命令不支持自动回滚，验证失败时需人工介入: {unsupported}")

        # ========== 第3步：下发新配置 ==========
        try:
            self.device.send_config(commands)
            logger.info(f"    ✓ 配置下发完成")
        except Exception as e:
            self.device.disconnect()
            log_operation(self.host, "config_push", "failed", f"{description} | 下发异常: {e}")
            return {
                'success': False,
                'action': 'failed',
                'detail': f'配置下发异常: {e}。备份文件: {backup_path}'
            }

        # ========== 第4步：验证配置（如果启用）==========
        if verify:
            logger.info(f"    >>> 开始验证配置...")
            verified, verify_results = self.verifier.verify_config_set(self.device, commands)

            if verified:
                logger.info(f"    ✓ 验证通过")
            else:
                # 验证失败，执行回滚
                failed_items = [k for k, v in verify_results.items() if not v]
                logger.error(f"    ✗ 验证失败: {failed_items}")

                # 生成undo命令
                undo_commands = self.rollback_engine.generate_undo(commands)

                if undo_commands:
                    logger.info(f"    >>> 开始回滚...")
                    rollback_ok, rollback_detail = self.rollback_engine.execute_rollback(
                        self.device, undo_commands
                    )

                    if rollback_ok:
                        # 回滚后再次验证（确认回滚成功）
                        re_verified, _ = self.verifier.verify_config_set(self.device, commands)

                        if re_verified:
                            # 回滚不彻底，配置仍然存在
                            self.device.disconnect()
                            log_operation(
                                self.host, "config_push", "rollback_failed",
                                f"{description} | 回滚后配置仍存在 | 备份: {backup_path}"
                            )
                            return {
                                'success': False,
                                'action': 'rollback_failed',
                                'detail': f'验证失败，回滚执行后配置仍存在，需人工介入。备份文件: {backup_path}'
                            }

                        # 回滚成功，配置已清除
                        self.device.disconnect()
                        log_operation(
                            self.host, "config_push", "rollbacked",
                            f"{description} | 已自动回滚 | 备份: {backup_path}"
                        )
                        return {
                            'success': False,
                            'action': 'rollbacked',
                            'detail': f'验证失败，已自动回滚。备份文件: {backup_path}'
                        }
                    else:
                        # 回滚执行失败
                        self.device.disconnect()
                        log_operation(
                            self.host, "config_push", "rollback_failed",
                            f"{description} | 回滚执行失败: {rollback_detail} | 备份: {backup_path}"
                        )
                        return {
                            'success': False,
                            'action': 'rollback_failed',
                            'detail': f'验证失败，回滚执行失败: {rollback_detail}。备份文件: {backup_path}'
                        }
                else:
                    # 没有可用的undo命令
                    self.device.disconnect()
                    log_operation(
                        self.host, "config_push", "rollback_failed",
                        f"{description} | 无可用undo命令 | 备份: {backup_path}"
                    )
                    return {
                        'success': False,
                        'action': 'rollback_failed',
                        'detail': f'验证失败，且命令不支持自动回滚。备份文件: {backup_path}'
                    }

        # ========== 第5步：保存配置 ==========
        try:
            self.device.connection.save_config()
            logger.info(f"    ✓ 配置已保存")
        except Exception as e:
            self.device.disconnect()
            log_operation(
                self.host, "config_push", "failed",
                f"{description} | 保存失败: {e} | 备份: {backup_path}"
            )
            return {
                'success': False,
                'action': 'failed',
                'detail': f'配置保存失败: {e}。备份文件: {backup_path}'
            }

        # ========== 第6步：断开连接，记录成功 ==========
        self.device.disconnect()
        log_operation(
            self.host, "config_push", "success",
            f"{description} | 已保存 | 备份: {backup_path}"
        )

        return {
            'success': True,
            'action': 'saved',
            'detail': f'配置已保存。备份文件: {backup_path}'
        }
