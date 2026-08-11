\# 网络自动化项目 (Network Automation)



基于 Netmiko 的企业级网络设备自动化管理工具。



\## 功能特性

\- 批量备份设备配置

\- 自动巡检（CPU / 内存 / 接口状态）

\- 配置下发（VLAN、接口等）

\- Excel 驱动设备清单



\## 项目结构

network-automation/

├── network\_device.py      # 设备连接与操作类（核心封装）

├── backup.py              # 配置备份脚本

├── network\_inspect.py     # 巡检报表脚本

├── config\_push.py         # 配置下发脚本

├── devices.xlsx           # 设备台账

└── README.md              # 项目说明



\## 运行环境

\- Python 3.8+

\- 依赖库：`netmiko`, `openpyxl`

