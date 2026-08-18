# SQLite 操作统计改动说明

> 本次改动围绕 `operations` 表的统计逻辑，解决两个问题：
>
> 1. **「本次统计」语义不对**：原 `days=0` 只统计到最后 1 秒；`days=1` 又会把 24h 内多次运行累计进来。
> 2. **`started` 状态被误算**：原 `total` 统计所有操作，`failed = total - success` 把 `started` 也当成了失败。

---

## 改动总览

| 文件 | 改动内容 |
|------|----------|
| `database.py` | `get_operation_summary` 新增 `since` 参数；`total` 查询排除 `started` |
| `backup_v2.py` | 记录 `run_start`，末尾统计传 `since=run_start` |
| `network_inspect_v2.py` | 同上 |

---

## 1. database.py — get_operation_summary

### 改前

```python
def get_operation_summary(days: int = 7) -> Dict:
    ...
    since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    c.execute("SELECT COUNT(*) FROM operations WHERE created_at >= ?", (since,))
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM operations WHERE created_at >= ? AND status = 'success'", (since,))
    success = c.fetchone()[0]
    ...
    failed = total - success
```

### 改后

```python
def get_operation_summary(days: int = 7, since: str = None) -> Dict:
    """
    :param days: 最近N天（since 为空时生效）
    :param since: 可选，起始时间戳（'%Y-%m-%d %H:%M:%S'），传了就从该时间点起算，忽略 days
    """
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    if since is None:
        since = (datetime.datetime.now() - datetime.timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")

    # 只统计有最终结果的操作（success/failed），排除 started
    c.execute("SELECT COUNT(*) FROM operations WHERE created_at >= ? AND status IN ('success','failed')", (since,))
    total = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM operations WHERE created_at >= ? AND status = 'success'", (since,))
    success = c.fetchone()[0]
    ...
    failed = total - success
```

### 改动点说明

| 项 | 原 | 新 |
|----|----|----|
| 函数签名 | `get_operation_summary(days=7)` | 加 `since: str = None`，传了就按指定时间点起算 |
| `total` 统计范围 | 所有 status | 只统计 `success` / `failed`，排除 `started` |

> 兼容性：`db_query.py` 仍用 `get_operation_summary(days=7)`（不传 since），行为不变。

---

## 2. backup_v2.py — 只统计「本次」运行

### 改前

```python
    stats = get_operation_summary(days=1)  # 最近24小时
```

### 改后

```python
    # 开头记下本次运行起始时刻
    run_start = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ...
    # 末尾传 since=run_start，只统计本次运行的操作
    stats = get_operation_summary(since=run_start)
```

---

## 3. network_inspect_v2.py — 同上

与 `backup_v2.py` 完全一致的改动：开头记 `run_start`，末尾传 `since=run_start`。

---

## 验证结果

| | 改动前 | 改动后 |
|---|---|---|
| 总数 total | 24（含 12 条 `started`） | **12** |
| 成功 success | 9 | 9 |
| 失败 failed | 15（`started` 被误算成失败） | **3** |
| 成功率 | 37.5% | **75.0%** |

`py_compile` 语法检查通过。

---

## 附：未在本文范围内的改动

- `paramiko` 2.12.0 → 3.5.1：修复 `CryptographyDeprecationWarning (TripleDES)`，属依赖环境升级，与 SQLite 无关，不在本文展开。
- `migrate_to_sqlite.py`：注释掉 `devices.xlsx` 迁移（只迁 `new_topology.xlsx`），是更早一轮「3 台老设备 inactive」的改动，也不在本文范围。
