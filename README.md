# 网络自动化项目 (Network Automation)

基于 Netmiko 的企业级网络设备自动化管理工具。

## 功能特性

- **批量备份设备配置**（串行 + 并发）
- **自动巡检**（CPU / 内存 / 接口状态，串行 + 并发）
- **并发执行**：使用 ThreadPoolExecutor，支持同时连接多台设备
- **实时报表**：巡检结果自动生成 Excel 汇总表
- **Excel 驱动设备清单**：改表格不用改代码
- **文件自动归档**：备份与报告按日期分文件夹存放，避免覆盖

## 项目结构
network-automation/
├── network_device.py              # 设备连接与操作类（核心封装）
├── backup.py                      # 串行备份脚本
├── backup_concurrent.py           # 并发备份脚本（多线程）
├── network_inspect.py             # 串行巡检脚本
├── network_inspect_concurrent.py  # 并发巡检脚本（实时生成报表）
├── devices.xlsx                   # 设备台账
├── .gitignore                     # Git 忽略规则
└── README.md                      # 项目说明
plain

## 运行环境

- Python 3.8+
- 依赖库：`netmiko`, `openpyxl`

```bash
pip install netmiko openpyxl
快速开始
1. 配置设备清单
编辑 devices.xlsx，填入设备信息：
表格
device_type	host	username	password
huawei	192.168.100.10	admin	admin123
huawei	192.168.100.11	admin	admin123
2. 执行备份
bash
# 串行备份（1台1台来）
python backup.py

# 并发备份（同时连5台）
python backup_concurrent.py
备份文件保存在 backup_YYYYMMDD/ 文件夹。
3. 执行巡检
bash
# 串行巡检
python network_inspect.py

# 并发巡检（实时生成Excel报表）
python network_inspect_concurrent.py
巡检报告保存在 report_YYYYMMDD/ 文件夹。
技术栈
Netmiko：SSH 连接网络设备
OpenPyXL：读写 Excel 文件
concurrent.futures：Python 原生并发库（内置）
Git：版本控制
更新日志
v1.3 (2026-08-12): 更新 README，补充并发功能说明和使用文档
v1.2 (2026-08-12): 增加并发备份和并发巡检功能，巡检报告独立存放至 report 文件夹
v1.1 (2026-08-11): 完善 README，增加项目结构说明
v1.0 (2026-08-11): 项目初始化，整合 V6 版本代码（备份 + 巡检 + NetworkDevice 类封装）

