# SAP MID Oracle 只读 Smoke Test 报告（M1.5）

执行时间：2026-05-14 18:08:20 CST
范围：只读 smoke test；不导出大表；不写 Oracle；不记录真实 host/user/password/DSN/login user。

## 1. 是否读取到 SAP_ORACLE_* 配置

读取方式：仅检查 `backend/.env` 中配置项存在性，不输出真实值。

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
| 项目依赖锁定 | 已在 `backend/requirements.txt` 增加 `oracledb==4.0.0` |

说明：本轮已解除上一版报告中的“Python driver 不可导入”阻塞，但连接仍受 Oracle thick client / 数据库版本兼容性阻塞，见第 3 节。

## 3. 是否成功连接 Oracle

未成功建立 Oracle 会话。

已验证项：

1. `backend/.env` 中 `SAP_ORACLE_*` 必填项均存在。
2. TCP 层到配置的 host/port 可连通；报告不记录真实 host/port。
3. 使用 `python-oracledb` thin/default 模式发起连接，失败。
4. 尝试初始化 thick 模式默认 Oracle Client，失败，因为本机未发现 `libclntsh.dylib`。

安全错误摘要（已脱敏）：

| 阶段 | 错误类型 | 摘要 |
|---|---|---|
| thin/default 连接 | `OperationalError` / `NotSupportedError` | `DPY-3010: connections to this database server version are not supported by python-oracledb in thin mode` |
| thick client 初始化 | `DatabaseError` | `DPI-1047: Cannot locate a 64-bit Oracle Client library: libclntsh.dylib` |

判断：当前 Oracle 服务器版本不支持 `python-oracledb` thin 模式；需要安装并配置 Oracle Instant Client / thick 模式后再重跑 smoke test，或由 DBA 提供 thin 模式兼容的 Oracle 服务端/连接方式。

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

原因：Oracle 会话未建立。未对任何 Oracle 大表做全量导出，也未执行 `SELECT *` 无限制查询。

## 7. 是否能做 count 验证

未执行。

原因：Oracle 会话未建立，无法执行两个白名单视图的 `COUNT(*)`。

## 8. 网络 / 权限 / 驱动问题

1. 驱动：`oracledb==4.0.0` 已可导入，并已写入项目依赖文件。
2. Python thin 模式：阻塞。当前 Oracle 服务端版本不被 `python-oracledb` thin 模式支持。
3. Oracle Client thick 模式：阻塞。本机未定位到 64-bit Oracle Client 动态库 `libclntsh.dylib`。
4. 网络：TCP host/port 连通，但这不等于 Oracle 会话成功。
5. 权限：未验证。连接建立前无法确认只读账号是否可访问 `all_views`、`all_tab_columns` 以及两个白名单视图。

## 9. M2 进入条件判断

当前不满足进入 M2 正式同步开发的条件。

原因：虽然 Python 驱动已补齐并锁定，但 Oracle 只读连接 smoke test 仍未通过，且未完成以下 M2 前置验证：

1. `SELECT 1 FROM dual`
2. 当前连接身份 / schema 摘要读取
3. 两个白名单视图字段结构 live 验证
4. 两个白名单视图 `COUNT(*)`
5. 两个白名单视图 `ROWNUM <= 5` 小样本读取

## 10. 后续建议

1. 安装与当前 macOS 架构匹配的 Oracle Instant Client，并确保 `python-oracledb` thick 模式可定位 `libclntsh.dylib`。
2. 重跑只读 smoke test，优先验证 `SELECT 1 FROM dual`。
3. 连接通过后，再按白名单顺序验证字段结构、count 和 `ROWNUM <= 5` 小样本。
4. 后续报告继续只记录存在性、行数、字段名、字段类型和脱敏错误摘要，不记录真实 host/user/password/DSN/login user。
5. 在上述 smoke test 通过前，不进入 M2 正式同步开发，不把用户问答链路直接接到 Oracle MID。
