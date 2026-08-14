"""
logger_config.py
全局日志配置，所有脚本共用
"""

import logging
import datetime
import os


def setup_logger(name: str = "network_automation") -> logging.Logger:
    """
    配置并返回一个日志记录器
    :param name: 日志器名称，建议用模块名
    :return: 配置好的 Logger 对象
    """
    # 创建 logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  #  logger 级别设为最低，让 handler 控制实际输出
    
    # 防止重复添加 handler（如果多次调用 setup_logger）
    if logger.handlers:
        return logger
    
    # 创建 logs 文件夹
    log_folder = "logs"
    os.makedirs(log_folder, exist_ok=True)
    
    # 日志文件名：network_20260814.log
    log_file = f"{log_folder}/network_{datetime.datetime.now().strftime('%Y%m%d')}.log"
    
    # ========== Handler 1：写入文件（记录 DEBUG 及以上）==========
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)
    
    # ========== Handler 2：输出到屏幕（只显示 INFO 及以上）==========
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter('%(levelname)s: %(message)s')
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    return logger