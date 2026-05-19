# M1.5 SAP MID Oracle 只读 smoke test 验收记录

任务：t_2c15aff8
时间：2026-05-14 18:08 CST
范围：只处理 Oracle Python 驱动与 SAP MID 只读 smoke test；未进入 M2 正式同步开发。

## 修改文件

1. backend/requirements.txt
   - 增加 `oracledb==4.0.0`，将已可导入的 Oracle Python 驱动写入项目依赖锁定。
2. docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md
   - 更新 M1.5 smoke 结果：驱动已补齐，但 Oracle 会话仍被 thin/thick 兼容性阻塞。
3. ai/outbox/kanban/t_2c15aff8/diff.patch
   - 本任务范围 diff。
4. ai/outbox/kanban/t_2c15aff8/final-acceptance.md
   - 本验收记录。

## 实测结果

| 检查项 | 结果 |
|---|---|
| 读取 docs/SAP_MID_ORACLE_SMOKE_TEST_REPORT.md、docs/NEXT_TASK.md、docs/HANDOFF.md | 通过 |
| backend/.venv 导入 oracledb | 通过，版本 4.0.0 |
| backend/.venv 导入 cx_Oracle | 未安装，本轮不采用 |
| backend/.env 必填 SAP_ORACLE_* 存在性 | 通过，6/6 present |
| TCP 到配置 host/port 连通性 | 通过；未记录真实 host/port |
| python-oracledb thin/default 连接 Oracle | 未通过，DPY-3010：数据库服务端版本不支持 thin 模式 |
| python-oracledb thick client 默认初始化 | 未通过，DPI-1047：未定位到 64-bit Oracle Client 动态库 libclntsh.dylib |
| SELECT 1 FROM dual | 未执行成功；Oracle 会话未建立 |
| 两个白名单视图字段结构、COUNT、ROWNUM <= 5 小样本 | 未执行；Oracle 会话未建立 |
| 敏感连接值扫描 | 通过，未发现真实 host/user/password/full DSN 写入本任务变更文件 |
| pip check | 未通过；命中当前环境已有 s3fs/streamlit 依赖冲突，非本任务新增问题 |

## M2 进入条件判断

当前不满足进入 M2 条件。

已完成：

- Python 驱动 `oracledb` 可导入。
- 项目依赖文件已锁定 `oracledb==4.0.0`。
- `SAP_ORACLE_*` 配置存在性已确认。
- TCP 层连通。

仍阻塞：

- 当前 Oracle 服务端版本不支持 `python-oracledb` thin 模式。
- 本机未配置 Oracle Instant Client thick 模式所需 `libclntsh.dylib`。
- 因会话未建立，尚未完成 SELECT 1、字段结构、count、小样本验证。

## 安全边界

- 未输出真实 host/user/password/DSN/login user。
- 未写 Oracle。
- 未全量导出大表。
- 未把用户问答链路接到 Oracle MID。
- 未进入 M2 正式开发。
