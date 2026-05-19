# M1.5 SAP MID Oracle 只读 smoke test 验收记录

任务：t_2c15aff8
验收记录时间：2026-05-19 19:16:22 CST
最新 smoke 执行时间：2026-05-19 19:15:55 CST
分支：feature/m15-sap-mid-oracle-smoke-t_2c15aff8
范围：只处理 Oracle Python 驱动与 SAP MID 只读 smoke test；未进入 M2 正式同步开发。

## 修改文件与交付产物

1. `backend/requirements.txt`
   - 补齐并保持 `oracledb==4.0.0`，将当前可导入的 Oracle Python 驱动写入项目依赖锁定。
2. `docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md`
   - 按最新 M1.5 smoke 结果刷新：驱动已补齐，但最新 TCP 探针超时，且 thick 模式 Oracle Client 仍缺失。
3. `tmp/hermes/sap_mid_oracle_smoke.py`
   - 固定脱敏只读 smoke 脚本，只输出配置存在性、错误码、行数/字段摘要，不输出真实连接值。
4. `tmp/hermes/sap_mid_oracle_client_probe.py`
   - 固定 thick-mode Oracle Client 可用性探针，不连接数据库，不输出真实路径/连接值。
5. `tmp/hermes/m15_secret_scan.py`
   - 固定敏感值扫描脚本，扫描 host/user/password 原始值和 host/service、host:port/service、user/password 等组合片段是否泄露到本任务交付文件；短 service 裸值不做全文匹配，避免普通短词误判。
6. `tmp/hermes/run_m15_acceptance.py`
   - 固定验收执行脚本，记录 smoke/client/pip check 输出和退出码。
7. `tmp/hermes/generate_m15_diff.py`
   - 固定任务范围 diff 生成脚本，只收集 M1.5 相关文件，避免混入当前工作树中无关脏文件。
8. `ai/outbox/kanban/t_2c15aff8/test.log`
   - 记录本轮脱敏 smoke、thick client 探针、pip check 及退出码。
9. `ai/outbox/kanban/t_2c15aff8/oracle_smoke_safe_result.json`
   - 保存本轮完整脱敏探针 JSON 结果，不包含真实 host/service/user/password/DSN。
10. `ai/outbox/kanban/t_2c15aff8/smoke-result-sanitized.json`
    - 保存本轮摘要级脱敏探针结果。
11. `ai/outbox/kanban/t_2c15aff8/oracle_client_probe_safe_result.json`
    - 保存 thick-mode Oracle Client 可用性脱敏探针结果。
12. `ai/outbox/kanban/t_2c15aff8/pip-check.log`
    - 保存 `pip check` 原始输出。
13. `ai/outbox/kanban/t_2c15aff8/py-compile.status` / `py-compile.log`
    - 保存 helper 脚本语法编译结果。
14. `ai/outbox/kanban/t_2c15aff8/secret-scan.log` / `secret-scan.status`
    - 保存敏感值扫描结果。
15. `ai/outbox/kanban/t_2c15aff8/diff.patch`
    - 保存本任务范围 diff。
16. `ai/outbox/kanban/t_2c15aff8/final-acceptance.md`
    - 本验收记录。

## 已读取/核对的任务资料

- `docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md`
- `docs/NEXT_TASK.md`
- `docs/HANDOFF.md`
- `AGENTS.md`
- `README_WORKSPACE.md`
- `docs/PLATFORM_OVERALL_ARCHITECTURE_AND_ROADMAP.md`
- `docs/CURRENT_STATUS.md`
- `ai/protocols/company_task_protocol.md`
- `ai/company/roles/technical_manager.md`
- `ai/hermes_skills/company-code-builder/SKILL.md`
- `ai/inbox/requirement.md`
- `ai/inbox/attachments_manifest.md`
- `docs/MATERIAL_MANAGEMENT_SAP_MID_DATA_ASSET_AUDIT.md`
- `docs/MATERIAL_MANAGEMENT_MIDDLE_DB_MODEL_PLAN.md`
- `docs/SAP_MID_SYNC_DESIGN.md`
- `docs/MATERIAL_MANAGEMENT_AI_QUERY_PLAN.md`
- `docs/PLAN_BOM_SAP_DATA_SOURCE_MIGRATION_PLAN.md`
- `docs/FRONTEND_MATERIAL_MANAGEMENT_ADAPTATION_PLAN.md`
- `docs/SAP_MID_INTEGRATION_ROADMAP.md`

## 实测结果

| 检查项 | 结果 |
|---|---|
| 当前分支 | `feature/m15-sap-mid-oracle-smoke-t_2c15aff8` |
| `backend/.venv` 导入 `oracledb` | 通过，版本 4.0.0 |
| `backend/.venv` 导入 `cx_Oracle` | 未安装，本轮不采用 |
| `backend/requirements.txt` 锁定 `oracledb==4.0.0` | 通过 |
| `backend/.env` 必填 `SAP_ORACLE_*` 存在性 | 通过，6/6 present |
| TCP 到配置 host/port 连通性 | 未通过；10 秒探针超时；未记录真实 host/port |
| `python-oracledb` thin/default 连接 Oracle | 未执行；最新 TCP 探针未通过，未进入 Oracle SQL session |
| `python-oracledb` thick client 初始化 | 未通过，`DPI-1047`：未定位到 64-bit Oracle Client 动态库 `libclntsh.dylib`；候选尝试 5 次 |
| `SELECT 1 FROM dual` | 未执行成功；Oracle 会话未建立 |
| 两个白名单视图字段结构、COUNT、`ROWNUM <= 5` 小样本 | 未执行；Oracle 会话未建立 |
| helper 脚本 `py_compile` | 通过，`py_compile_rc=0` |
| `pip check` | 未通过；命中当前环境已有 s3fs/fsspec 与 streamlit packaging/pillow 依赖冲突，未出现 oracledb 冲突 |
| 敏感值扫描 | 通过；host/user/password 裸值已检查；service 因短值仅做组合片段检查；host:port、host/service、host:port/service、user/password 组合均无命中 |

## Review / 修复记录

- 独立 review 初审结论：未发现写库/无界导出代码，但指出两个阻塞项：`m15_secret_scan.py` 与 `sap_mid_secret_scan.py` 路径引用不一致、service/DSN 扫描证据不完整。
- 已修复：`generate_m15_diff.py` 已改为纳入 `tmp/hermes/m15_secret_scan.py`；`final-acceptance.md` 已同步正确脚本名；`m15_secret_scan.py` 已补充 service/port/owner 的存在性记录，并补充 host/service、host:port/service 等组合片段扫描。
- 修复后已重新执行 smoke、py_compile、secret scan；独立复审通过：`passed=true`，无 `security_concerns`，无 `logic_errors`；建议在网络连通性和 Oracle Instant Client/libclntsh 修复后，再重跑只读 smoke test 并同步重跑 secret scan。

## M2 进入条件判断

当前不满足进入 M2 条件。

已完成：

- Python 驱动 `oracledb` 可导入。
- 项目依赖文件已锁定 `oracledb==4.0.0`。
- `SAP_ORACLE_*` 配置存在性已确认。
- 只读 smoke、thick client 探针、脱敏扫描和验收产物已形成。

仍阻塞：

- 最新 TCP host/port 探针超时，Oracle SQL 会话未建立。
- 本机未配置 Oracle Instant Client thick 模式所需 `libclntsh.dylib`。
- 因会话未建立，尚未完成 `SELECT 1`、连接身份/schema 摘要、字段结构、count、小样本验证。
- 只读账号权限和查询边界尚未验证。

## 安全边界

- 未输出真实 host/user/password/DSN/login user。
- service 裸值因当前值过短不做全文匹配，避免普通短词误判；改以 host/service、host:port/service 等组合片段扫描证明未输出完整 DSN/连接串。
- 未写 Oracle。
- 未全量导出大表。
- 未把用户问答链路接到 Oracle MID。
- 未进入 M2 正式开发。
- 未自动 commit / push / deploy。
- 本轮未触碰当前工作树中与本任务无关的既有脏文件。

## 当前能力判断

- 当前仓库已具备：物管 SAP MID M1 文档与 M1.5 Python 驱动可导入基础。
- 当前仓库未具备：稳定可达的 Oracle 网络连接、可建立的 Oracle 会话、live 字段/COUNT/小样本验证、M2 同步开发前置放行。
- 本轮任务与当前仓库状态一致：继续处理 M2 前置 Oracle smoke 阻塞，不进入 M2 正式开发。
