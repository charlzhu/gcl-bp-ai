# SAP MID Oracle 只读 Smoke Test 报告（M1.5）

执行时间：2026-05-19 19:15:55 CST
范围：只读 smoke test；不导出大表；不写 Oracle；不记录真实 host/service/user/password/DSN/login user。

本次复测产物：

- `ai/outbox/kanban/t_2c15aff8/test.log`
- `ai/outbox/kanban/t_2c15aff8/pip-check.log`
- `ai/outbox/kanban/t_2c15aff8/py-compile.status`
- `ai/outbox/kanban/t_2c15aff8/secret-scan.log`
- `ai/outbox/kanban/t_2c15aff8/oracle_smoke_safe_result.json`
- `ai/outbox/kanban/t_2c15aff8/smoke-result-sanitized.json`
- `ai/outbox/kanban/t_2c15aff8/oracle_client_probe_safe_result.json`

## 1. 是否读取到 SAP_ORACLE_* 配置

读取方式：仅检查 `backend/.env` 与进程环境变量中的配置项存在性，不输出真实值。

| 配置项 | 存在性 |
|---|---|
| SAP_ORACLE_HOST | present |
| SAP_ORACLE_PORT | present |
| SAP_ORACLE_SERVICE | present |
| SAP_ORACLE_USER | present |
| SAP_ORACLE_PASSWORD | present |
| SAP_ORACLE_OWNER | present |

## 2. Oracle Python 驱动状态

| 项目 | 结果 |
|---|---|
| `backend/.venv` 导入 `oracledb` | 通过 |
| `oracledb` 版本 | 4.0.0 |
| `backend/.venv` 导入 `cx_Oracle` | 未安装；本轮不采用 |
| 项目依赖锁定 | 已在 `backend/requirements.txt` 保持 `oracledb==4.0.0` |

说明：Python driver 已可导入，依赖文件已包含 `oracledb==4.0.0`。当前阻塞不再是 Python 包缺失，而是尚未建立 Oracle 会话。

## 3. 是否成功连接 Oracle

未成功建立 Oracle 会话。

最新复测结果：

1. `backend/.env` 中 `SAP_ORACLE_*` 必填项均存在。
2. TCP 层到配置 host/port 的 10 秒连通性探针未通过；报告不记录真实 host/port。
3. 因 TCP 探针未通过，本轮未继续发起 thin/default Oracle SQL 会话，避免输出连接细节或长时间阻塞。
4. 单独执行 thick-mode Oracle Client 可用性探针，仍未发现可用 64-bit Oracle Client 动态库 `libclntsh.dylib`。

安全错误摘要（已脱敏）：

| 阶段 | 结果 | 摘要 |
|---|---|---|
| TCP host/port 探针 | `未通过` | `10 秒 TCP 探针超时` |
| thin/default 连接 | 未执行 | TCP 探针未通过，未进入 Oracle SQL session |
| thick client 初始化探针 | `未通过` | `DPI-1047: Cannot locate a 64-bit Oracle Client library: libclntsh.dylib`；候选尝试 5 次 |

判断：最新复测首先被网络/TCP 层阻塞；即使网络恢复，当前本机仍缺少 thick 模式所需 Oracle Instant Client / `libclntsh.dylib`。需要先恢复到配置 host/port 的 TCP 连通性，并安装/配置与本机架构匹配的 Oracle Instant Client，或由 DBA 提供 thin 模式兼容的 Oracle 服务端/连接方式后再重跑 smoke test。

## 4. 是否成功执行 SELECT 1 FROM dual

未执行成功。

原因：Oracle 会话未建立，`SELECT 1 FROM dual` 无法进入执行阶段。

## 5. 是否能读取白名单视图字段结构

未通过 live Oracle 读取。

计划验证对象：

1. `V_HF_SAP_INOUT_DAILY`
2. `V_SAP_HFFN_CRKLSZ`

原因：Oracle 会话未建立，无法查询 `all_views` / `all_tab_columns`。

## 6. 是否能对重点视图做 ROWNUM <= 5 抽样

未执行。

原因：Oracle 会话未建立。未对任何 Oracle 大表做全量导出，也未执行无 `ROWNUM` 上限的数据抽样。

## 7. 是否能做 count 验证

未执行。

原因：Oracle 会话未建立，无法执行两个白名单视图的 `COUNT(*)`。

## 8. 网络 / 权限 / 驱动问题

1. 驱动：`oracledb==4.0.0` 已可导入，并已写入项目依赖文件。
2. 网络：最新 TCP host/port 探针超时，尚未进入 Oracle 登录/SQL 阶段。
3. Python thin 模式：本轮未执行，因为 TCP 探针未通过；上一轮曾观测到服务端版本不支持 thin 模式（DPY-3010/DPY-6005），但最新结论以本轮 TCP 阻塞为准。
4. Oracle Client thick 模式：阻塞。本机未定位到 64-bit Oracle Client 动态库 `libclntsh.dylib`。
5. 权限：未验证。连接建立前无法确认只读账号是否可访问 `all_views`、`all_tab_columns` 以及两个白名单视图。

## 9. M2 进入条件判断

当前不满足进入 M2 正式同步开发的条件。

原因：虽然 Python 驱动已补齐并锁定，但 Oracle 只读连接 smoke test 仍未通过，且未完成以下 M2 前置验证：

1. `SELECT 1 FROM dual`
2. 当前连接身份 / schema 摘要读取
3. 两个白名单视图字段结构 live 验证
4. 两个白名单视图 `COUNT(*)`
5. 两个白名单视图 `ROWNUM <= 5` 小样本读取
6. 只读账号权限和查询边界确认

## 10. 后续建议

1. 先确认当前机器/网络到 `SAP_ORACLE_*` 配置 host/port 的 TCP 连通性，必要时检查 VPN、内网、白名单或防火墙。
2. 安装与当前 macOS `arm64` 架构匹配的 Oracle Instant Client，并确保 `python-oracledb` thick 模式可定位 `libclntsh.dylib`。
3. 网络与客户端准备完成后，重跑只读 smoke test，优先验证 `SELECT 1 FROM dual`。
4. 连接通过后，再按白名单顺序验证字段结构、count 和 `ROWNUM <= 5` 小样本。
5. 后续报告继续只记录存在性、行数、字段名、字段类型和脱敏错误摘要，不记录真实 host/user/password/DSN/login user。
6. 在上述 smoke test 通过前，不进入 M2 正式同步开发，不把用户问答链路直接接到 Oracle MID。
