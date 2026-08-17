# 网络自动化项目 (Network Automation)

基于 Netmiko 的企业级网络设备自动化管理工具。

## 功能特性

- **批量备份设备配置**（串行 + 并发）
- **自动巡检**（CPU / 内存 / 接口状态，串行 + 并发，实时生成 Excel 报表）
- **配置下发**（基于 Jinja2 模板，支持 VLAN、接口 IP 等差异化配置）
- **企业级全网拓扑自动化**（第5课新增：9 设备全网配置下发 + 验证）
- **并发执行**：使用 ThreadPoolExecutor，支持同时连接多台设备
- **模板化配置**：修改 `.j2` 模板文件即可调整配置，无需修改 Python 代码
- **Excel 驱动设备清单**：修改表格不用改代码
- **文件自动归档**：备份与报告按日期分文件夹存放，避免覆盖
- **安全下发框架**：配置下发前自动备份当前配置
- **分级日志系统**：DEBUG/INFO/WARNING/ERROR 同时输出到屏幕和文件

## 项目结构

```
network-automation/
├── network_device.py              # 设备连接与操作类（核心封装）
├── backup.py                      # 串行备份脚本
├── backup_concurrent.py           # 并发备份脚本（多线程）
├── network_inspect.py             # 串行巡检脚本
├── network_inspect_concurrent.py  # 并发巡检脚本（实时生成报表）
├── config_push.py                 # 配置下发脚本（Jinja2 模板 + 安全框架）
├── topology_push.py               # 企业级全网配置下发（9设备）
├── topology_verify.py             # 全网连通性验证脚本
├── new_topology.xlsx              # 9设备企业网台账
├── devices.xlsx                   # 基础设备台账（第1-4课）
├── requirements.txt               # Python 依赖清单
├── logger_config.py               # 全局日志配置
├── templates/                     # Jinja2 配置模板
│   ├── vlan_config.j2
│   ├── interface_ip.j2
│   ├── core_config.j2             # 核心交换机模板
│   ├── agg_config.j2              # 汇聚交换机模板
│   ├── access_config.j2           # 接入交换机模板
│   ├── server_config.j2           # 服务器区模板
│   └── router_config.j2           # 出口路由器模板
├── tests/                         # 测试脚本
│   ├── test_jinja2.py
│   └── test_render_only.py
├── .gitignore                     # Git 忽略规则
└── README.md                      # 项目说明
```

## 企业网设备台账

`new_topology.xlsx` 内容如下：

| device_type | host | username | password | role | dept | vlan_id | vlan_name | interface | ip_address | subnet_mask | uplink | mgmt_ip |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| huawei | 192.168.100.2 | admin | admin123 | router | 出口 | - | - | GE0/0/0 | 10.0.0.2 | 255.255.255.252 | - | 192.168.100.2 |
| huawei | 192.168.1.254 | admin | admin123 | core | 核心 | - | - | - | - | - | GE0/0/24 | 192.168.1.254 |
| huawei | 192.168.1.11 | admin | admin123 | agg | 研发市场 | 10,20 | VLAN10,VLAN20 | - | - | - | GE0/0/24 | 192.168.1.11 |
| huawei | 192.168.1.12 | admin | admin123 | agg | 财务行政 | 30,40 | VLAN30,VLAN40 | - | - | - | GE0/0/24 | 192.168.1.12 |
| huawei | 192.168.1.13 | admin | admin123 | access | 研发 | 10 | VLAN10_R&D | Ethernet0/0/1 | - | - | GE0/0/1 | 192.168.1.13 |
| huawei | 192.168.1.14 | admin | admin123 | access | 市场 | 20 | VLAN20_Mkt | Ethernet0/0/1 | - | - | GE0/0/1 | 192.168.1.14 |
| huawei | 192.168.1.15 | admin | admin123 | access | 财务 | 30 | VLAN30_Fin | Ethernet0/0/1 | - | - | GE0/0/1 | 192.168.1.15 |
| huawei | 192.168.1.16 | admin | admin123 | access | 行政 | 40 | VLAN40_Adm | Ethernet0/0/1 | - | - | GE0/0/1 | 192.168.1.16 |
| huawei | 192.168.1.100 | admin | admin123 | server | 服务器 | 100 | VLAN100_Srv | Ethernet0/0/1 | - | - | GE0/0/1 | 192.168.1.100 |

**拓扑架构：**

```
                    [Cloud/PC]
                         │
                    [AR1 出口路由器]  192.168.100.2
                         │
                    [Core-SW 核心交换机]  192.168.1.254
           ┌─────────────┼─────────────┐
     [Agg1]            [Agg2]         [Srv-SW]
   研发/市场          财务/行政        服务器区
      │                  │
  [Acc1][Acc2]      [Acc3][Acc4]
  研发   市场         财务   行政
```

**VLAN 规划：**

| VLAN | 部门 | 网段 | 网关 |
|---|---|---|---|
| 10 | 研发 | 192.168.10.0/24 | 192.168.10.254 |
| 20 | 市场 | 192.168.20.0/24 | 192.168.20.254 |
| 30 | 财务 | 192.168.30.0/24 | 192.168.30.254 |
| 40 | 行政 | 192.168.40.0/24 | 192.168.40.254 |
| 100 | 服务器 | 192.168.200.0/24 | 192.168.200.254 |
| 1 | 管理 | 192.168.1.0/24 | 192.168.1.254 |

## 运行环境

- Python 3.8+
- 依赖库：`netmiko`, `openpyxl`, `Jinja2`

```bash
pip install -r requirements.txt
```

## 快速开始

### 1. 配置设备清单

编辑 `devices.xlsx` 或 `new_topology.xlsx`，填入设备信息。

### 2. 执行备份

```bash
# 串行备份
python backup.py

# 并发备份
python backup_concurrent.py
```

备份文件保存在 `backup_YYYYMMDD/` 文件夹。

### 3. 执行巡检

```bash
# 串行巡检
python network_inspect.py

# 并发巡检
python network_inspect_concurrent.py
```

巡检报告保存在 `report_YYYYMMDD/` 文件夹。

### 4. 配置下发（基础版）

```bash
python config_push.py
```

### 5. 企业级全网配置下发

```bash
# 前提：eNSP 已搭建 9 设备拓扑，手工基础配置已完成
python topology_push.py
```

- 自动识别路由器（SSH）和交换机（Telnet）
- 串行下发避免 eNSP 并发崩溃
- 自动生成 Excel 配置报告到 `report_YYYYMMDD/`

### 6. 全网验证

```bash
python topology_verify.py
```

- 并发验证 9 台设备连通性
- 检查 VLAN、路由、ACL 配置状态

### 7. 测试模板渲染（不连设备）

```bash
cd tests
python test_render_only.py
```

## 技术栈

- **Netmiko**：SSH/Telnet 连接网络设备
- **OpenPyXL**：读写 Excel 文件
- **Jinja2**：配置模板渲染
- **concurrent.futures**：Python 原生线程并发库
- **logging**：分级日志系统
- **Git**：版本控制

## 更新日志

- **v1.5 (2026-08-16)**：企业级全网自动化拓扑
  - 新增 9 设备企业网拓扑（1路由+2汇聚+4接入+1服务器区+1核心）
  - 新增 `topology_push.py` 全网配置下发（Jinja2模板+安全框架+串行执行）
  - 新增 `topology_verify.py` 全网连通性验证
  - 新增 5 个企业级 Jinja2 配置模板
  - 新增 `new_topology.xlsx` 9设备台账
  - 改良 `network_device.py` 支持 Telnet、中文 description、慢命令兼容
- **v1.4 (2026-08-14)**：引入 Jinja2 模板引擎，重构配置下发架构
- **v1.3 (2026-08-12)**：更新 README，修复时间戳覆盖问题
- **v1.2 (2026-08-12)**：增加并发备份和并发巡检功能
- **v1.1 (2026-08-11)**：完善 README，增加项目结构说明
- **v1.0 (2026-08-11)**：项目初始化，整合代码
