# 改动学习文档（第7课 HIGH / MEDIUM 修复）

> 本文件记录对第7课新增五个文件评审出的 **5 个 HIGH / MEDIUM 问题**的修复。
> 遵循老规则：**改动处标注「问题 + 怎么改」，旧代码用注释保留，不删除**。
> 修改日期：2026-08-20

---

## 一、本次改动总览

| 编号 | 级别 | 问题一句话 | 涉及文件 | 改动动作 |
|---|---|---|---|---|
| H1 | HIGH | 回滚时漏发 `quit`，接口视图下的全局命令报错 | rollback_engine.py | 退出接口视图前先补发 `quit` |
| H2 | HIGH | v2 台账读取退回 Excel，开倒车 | topology_push_v2.py | 改回 `get_all_devices()`（SQLite） |
| H3 | HIGH | 接入模板被下发到全部 9 台设备 | config_push_v2.py | 只保留 `role='access'` 设备 |
| M1 | MEDIUM | 回滚状态在统计里隐身，成功率虚高 | database.py | 两处统计把回滚状态纳入失败 |
| M2 | MEDIUM | 空验证通过（验证器没干活也算通过） | config_verifier.py | `results` 为空时打警告 |

> 说明：M1 涉及 `database.py` 的两个函数（`get_operation_summary` 的 total、
> `get_failure_stats` 的 WHERE），是同一个根因的两处体现，合并为一条 M1。

---

## 二、逐项改动详解

### H1：回滚引擎漏发 `quit`（最关键的 bug）

**文件**：`rollback_engine.py` 的 `generate_undo()`

**问题**：`generate_undo` 倒序遍历已解析的命令，处理 `interface_enter`（进入接口视图）
这条时，原代码只清掉了状态变量 `current_interface = None`，**没有真的发 `quit` 退回系统视图**。
后果：前面刚 undo 完接口内命令（如 `undo ip address`），设备此刻仍停在接口视图，
紧接其后的全局命令（如 `undo vlan 10`）会在接口视图下执行 → 华为 VRP 报
`Unrecognized command`，导致最常见的 `vlan + interface + ip address` 组合场景回滚失败。

**怎么改**：清状态前先判断"当前是否还在接口视图内"，是的话先追加一条 `quit` 退回系统视图，
再清状态。

**改前**：
```python
for item in reversed(parsed):
    if item["type"] == "interface_enter":
        current_interface = None  # 只清状态，没发 quit 退出接口视图
        continue
```

**改后**：
```python
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
```

**知识点**：华为 VRP 的配置视图是层级嵌套的（系统视图 → 接口视图），`quit` 退回上一级。
回滚是"倒序 undo"，所以必须先 `quit` 回到系统视图，才能执行全局命令。这也是为什么
回滚引擎要在 `generate_undo` 里显式管理接口上下文，而不是简单地把命令倒过来。

---

### H2：topology_push_v2 台账读取退回 Excel

**文件**：`topology_push_v2.py` 的 `read_topology()`

**问题**：第6课已经把设备台账迁到 SQLite，`topology_push.py` 也早已改成 `get_all_devices()`，
但 v2 又退回从 `new_topology.xlsx` 读，等于开倒车，还重新依赖 Excel 表结构（易碎）。

**怎么改**：改回 `get_all_devices()`（SQLite），返回 dict，字段与 Excel 版完全一致。
旧的 Excel 版 `read_topology(excel_file)` 整个注释保留。同时 `main()` 里调用处
从 `read_topology("new_topology.xlsx")` 改成无参 `read_topology()`。

**改前（read_topology）**：
```python
def read_topology(excel_file):
    wb = load_workbook(excel_file)
    ...
    return devices, all_devices
```

**改后（read_topology）**：
```python
def read_topology():
    """从 SQLite 读取设备并按角色分组（第6课已迁移）"""
    devices = {'core': [], 'agg': [], 'access': [], 'router': [], 'server': []}
    for dev in get_all_devices():
        role = dev['role']
        if role in devices:
            devices[role].append(dev)
        else:
            logger.warning(f"未知角色 {role}，跳过 {dev['host']}")
    return devices
```

**改前（main 调用处）**：
```python
devices_dict, all_devices = read_topology("new_topology.xlsx")
```

**改后（main 调用处）**：
```python
devices_dict = read_topology()
```

---

### H3：config_push_v2 把接入模板下发到全部设备

**文件**：`config_push_v2.py` 的 `read_devices_from_db()`

**问题**：`get_all_devices()` 返回全部 9 台设备（路由器/核心/汇聚/接入/服务器），
但本脚本只用 `vlan_config.j2` / `interface_ip.j2` 两个"接入交换机"基础模板。
路由/核心/汇聚的 `vlan_id`、`interface` 字段是 `-` 或空，会渲染出 `vlan -`、
`interface -` 这类垃圾命令，下发到这些设备上会配错。

**怎么改**：只保留 `role='access'` 的接入交换机，基础模板只适用于接入设备。

**改前**：
```python
def read_devices_from_db():
    devices = get_all_devices()
    return devices
```

**改后**：
```python
def read_devices_from_db():
    devices = get_all_devices()
    # 【改动】原：直接返回 get_all_devices() 的全部设备（含路由器/核心/汇聚/服务器）
    #   问题：本脚本只用 vlan_config.j2 / interface_ip.j2 两个"接入交换机"基础模板，
    #        路由/核心/汇聚的 vlan_id、interface 字段是 "-" 或空，会渲染出 "vlan -"、
    #        "interface -" 垃圾命令，下发到这些设备上会配错。
    #   新：只保留 role='access' 的接入交换机，基础模板只适用于接入设备。
    devices = [d for d in devices if d.get('role') == 'access']
    if not devices:
        logger.error("数据库中没有接入交换机(role='access')，请先运行 migrate_to_sqlite.py")
    return devices
```

---

### M1：回滚状态在统计里隐身，成功率虚高

**文件**：`database.py` 的 `get_operation_summary()` 和 `get_failure_stats()`

**问题**：第7课 `SafePusher` 会记 `rollbacked` / `rollback_failed` 两种新状态，
但这两处统计的 SQL 还只认 `success` / `failed`：

- `get_operation_summary`：`total` 只统计 `success/failed`，`failed = total - success`
  时回滚操作被整个漏掉 → 成功率被虚高（回滚其实是失败，却被"看不见"）。
- `get_failure_stats`：`WHERE status = 'failed'` 抓不到回滚，导致"这台设备其实没配成功过"
  的事实被漏算。

**怎么改**：两处 SQL 都把 `rollbacked` / `rollback_failed` 纳入失败口径。

**改前（get_operation_summary 的 total）**：
```python
c.execute("SELECT COUNT(*) FROM operations WHERE created_at >= ? AND status IN ('success','failed')", (since,))
total = c.fetchone()[0]
```

**改后（get_operation_summary 的 total）**：
```python
# 【改动】原：status IN ('success','failed')
#   问题：第7课 safe_pusher 会记 'rollbacked'/'rollback_failed' 两种状态，不在
#        'success'/'failed' 里，导致回滚的操作在统计里完全隐身，成功率被虚高。
#   新：把两种回滚状态也计入 total，failed = total - success 自然把回滚归入失败。
c.execute("SELECT COUNT(*) FROM operations WHERE created_at >= ? AND status IN ('success','failed','rollbacked','rollback_failed')", (since,))
total = c.fetchone()[0]
```

**改前（get_failure_stats 的 WHERE）**：
```python
WHERE created_at >= ? AND status = 'failed'
```

**改后（get_failure_stats 的 WHERE）**：
```python
# 【改动】原：WHERE ... AND status = 'failed'
#   问题：第7课 safe_pusher 会记 'rollbacked'/'rollback_failed'，它们是"下发失败后回滚"，
#        也是失败的一种，但 status='failed' 抓不到，导致这些设备的失败次数被漏算。
#   新：把两种回滚状态也计入失败统计，运维看板才能看到"这台设备其实没配成功过"。
WHERE created_at >= ? AND status IN ('failed','rollbacked','rollback_failed')
```

**知识点**：SQL 的 `IN (...)` 是"值集合匹配"。状态机扩展时（新增 `started` /
`rollbacked` / `rollback_failed`），所有按状态过滤的查询都要跟着更新，否则口径不一致。
`get_operation_summary` 用 `failed = total - success` 倒推失败数，所以只要 `total`
的 `IN` 列表包含"所有非 success 的最终状态"，失败数就自动正确。

---

### M2：空验证通过（验证器没干活也算通过）

**文件**：`config_verifier.py` 的 `verify_config_set()`

**问题**：当 `commands` 里没有任何可识别的验证项（比如只有 `description` /
`port-security` 这类不支持验证的命令）时，`results` 为空，`else True` 会把
"什么都没验证"当成"全部通过"。属于空验证通过 —— 掩盖了"验证器根本没干活"的事实，
让 `SafePusher` 误以为配置已验证成功。

**怎么改**：`results` 为空时打警告提示"无可验证项"，但**仍返回 True**，避免误触发回滚
（空配置 ≠ 配置失败，宁可放过、不要因验证器没覆盖而误回滚）。

**改前**：
```python
all_passed = all(results.values()) if results else True

if not all_passed:
    failed = [k for k, v in results.items() if not v]
    logger.warning(f"[Verify] 验证未通过项: {failed}")

return all_passed, results
```

**改后**：
```python
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
```

**知识点**：`all(空集)` 在 Python 里返回 `True`（空真值），但"空验证"和"全通过"语义完全不同。
这里选择**告警 + 仍通过**，是因为验证器的覆盖范围有限，若把"没验证"直接判失败，
会导致一批合法配置被误回滚，代价远大于放过。属于"宁可漏报，不要误报"的取舍。

---

## 三、验证结果

1. **语法检查**：`python -m py_compile rollback_engine.py topology_push_v2.py
   config_push_v2.py database.py config_verifier.py` 全部通过。

2. **逻辑核对**（未真连设备，仅静态推演）：
   - H1：`vlan 10 → interface GE0/0/1 → ip address ...` 场景，倒序生成
     `system-view → interface GE0/0/1 → undo ip address → quit → undo vlan 10 → return`，
     视图层级正确。
   - H2/H3：不再依赖 Excel，且 config_push_v2 只取 access 设备。
   - M1：状态机 5 种状态里，最终态 `success/failed/rollbacked/rollback_failed`
     均进入统计口径，`started`（进行中）仍被排除（上一轮已修）。
   - M2：空验证项时告警但返回 True，不误触发回滚。

---

## 四、本次未改动项（按约定留给后续）

以下为评审出的 **LOW 级别**问题，本轮按用户要求「只改 HIGH 和 MEDIUM」未处理：

| 编号 | 级别 | 问题 | 文件 |
|---|---|---|---|
| L1 | LOW | `safe_pusher.py:84` 备份路径硬编码 | safe_pusher.py |
| L2 | LOW | `config_verifier.py:49` `expected_ip in output` 子串误判（如 10 匹配 100） | config_verifier.py |
| L3 | LOW | `rollback_engine.py:176-177` 死代码（`ip route-static 0.0.0.0` 分支不可达） | rollback_engine.py |
| L4 | LOW | `rollback_engine.py` `is_fully_supported` 里 `in_interface` 变量未使用 | rollback_engine.py |
| L5 | LOW | `rollback_engine.py` 冗余的 `system-view`/`return`（`send_config` 已自动进出配置视图） | rollback_engine.py |
| L6 | LOW | `topology_push_v2.py` 未使用的 `load_workbook` / `ThreadPoolExecutor` 导入 | topology_push_v2.py |
| L7 | LOW | `config_push_v2.py` 未使用的 `load_workbook` 导入 | config_push_v2.py |

> 另有两条**已决定不修**的既有问题（沿用上一轮约定）：
> - **严重问题 #1**：密码明文写在 Excel —— 模拟器项目，复现成本低，不改。
> - **严重问题 #6**：路由器配置漂移 —— 用户手动删除，脚本不处理。

---

## 五、老规则说明

本次所有改动都遵循：

1. **改动处标注**：每处改动上方用 `# 【改动】原：... / 问题：... / 新：...` 三行说明。
2. **旧代码注释保留**：不删除旧逻辑，用注释形式留在原地，方便对照和回退。
3. **相关知识点**：华为 VRP 视图层级与 `quit`、SQLite 状态机口径（`IN` 集合匹配）、
   Python `all(空集)==True` 的空真值陷阱，可配合《第7课_配置回滚机制_深度教学版.pdf》
   和《排障学习文档》一起看。
