# 网络自动化项目 (Network Automation)

基于 Netmiko 的企业级网络设备自动化管理工具。

## 功能特性

- **批量备份设备配置**（串行 + 并发）
- **自动巡检**（CPU / 内存 / 接口状态，串行 + 并发，实时生成 Excel 报表）
- **配置下发**（基于 Jinja2 模板，支持 VLAN、接口 IP 等差异化配置）
- **并发执行**：使用 ThreadPoolExecutor，支持同时连接多台设备
- **模板化配置**：修改 `.j2` 模板文件即可调整配置，无需修改 Python 代码
- **Excel 驱动设备清单**：修改表格不用改代码
- **文件自动归档**：备份与报告按日期分文件夹存放，避免覆盖
- **安全下发框架**：配置下发前自动备份当前配置

## 项目结构
```
network-automation/
├── network_device.py              # 设备连接与操作类（核心封装）
├── backup.py                      # 串行备份脚本
├── backup_concurrent.py           # 并发备份脚本（多线程）
├── network_inspect.py             # 串行巡检脚本
├── network_inspect_concurrent.py  # 并发巡检脚本（实时生成报表）
├── config_push.py                 # 配置下发脚本（Jinja2 模板 + 安全框架）
├── devices.xlsx                   # 设备台账（含模板变量）
├── requirements.txt               # Python 依赖清单
├── templates/                     # Jinja2 配置模板
│   ├── vlan_config.j2
│   └── interface_ip.j2
├── tests/                         # 测试脚本
│   ├── test_jinja2.py
│   └── test_render_only.py
├── .gitignore                     # Git 忽略规则
└── README.md                      # 项目说明
```
```
## 运行环境

- Python 3.8+
- 依赖库：`netmiko`, `openpyxl`, `Jinja2`

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 配置设备清单

编辑 `devices.xlsx`，填入设备信息：

表格

| device_type | host | username | password | vlan_id | vlan_name | interface | ip_address | subnet_mask |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| huawei | 192.168.100.10 | admin | admin123 | 10 | VLAN10 | GE0/0/1 | 192.168.10.1 | 255.255.255.0 |
| huawei | 192.168.100.11 | admin | admin123 | 20 | VLAN20 | GE0/0/1 | 192.168.20.1 | 255.255.255.0 |
| huawei | 192.168.100.12 | admin | admin123 | 30 | VLAN30 | GE0/0/1 | 192.168.30.1 | 255.255.255.0 |

### 2. 执行备份

```
# 串行备份（1台1台来）
python backup.py

# 并发备份（同时连5台）
python backup_concurrent.py
```

备份文件保存在 `backup_YYYYMMDD/` 文件夹。

### 3. 执行巡检

```
# 串行巡检
python network_inspect.py

# 并发巡检（实时生成Excel报表）
python network_inspect_concurrent.py
```

巡检报告保存在 `report_YYYYMMDD/` 文件夹。

### 4. 配置下发（基于 Jinja2 模板）

```
python config_push.py
```

- 自动读取 `templates/` 下的 `.j2` 模板
- 根据 `devices.xlsx` 中的变量渲染配置
- 连接设备 → 备份当前配置 → 下发新配置 → 保存

### 5. 测试模板渲染（不连设备，仅本地测试）

```
cd tests
python test_render_only.py
```

## 技术栈

- **Netmiko**：SSH 连接网络设备
- **OpenPyXL**：读写 Excel 文件
- **Jinja2**：配置模板渲染
- **concurrent.futures**：Python 原生线程并发库
- **Git**：版本控制

## 更新日志

- **v1.4 (2026-08-14)**：引入 Jinja2 模板引擎，重构配置下发架构，新增 templates/ 和 tests/ 文件夹
- **v1.3 (2026-08-12)**：更新 README，修复时间戳覆盖问题（精确到秒）
- **v1.2 (2026-08-12)**：增加并发备份和并发巡检功能，巡检报告独立存放至 report 文件夹
- **v1.1 (2026-08-11)**：完善 README，增加项目结构说明
- **v1.0 (2026-08-11)**：项目初始化，整合代码（备份 + 巡检 + NetworkDevice 类封装）
