# M10-D0 risk review — EXPLAIN / readonly trial gate

## 总体风险判断

M10-D 的风险高于 M10-A/B/C，因为后续可能从纯文本/内存 shadow 进入真实只读中间库 EXPLAIN 或 readonly trial。必须拆小，先 fake executor schema，再真实 EXPLAIN smoke，最后 readonly trial row cap/timeout。

## 主要风险与控制措施

### 1. 误接生产写库

风险：真实 DB 访问如果配置错误，可能连接生产写库。

控制：

1. 默认关闭真实 DB 访问总开关。
2. 必须显式使用只读 profile。
3. 连接层必须验证 read-only guard。
4. 不允许在日志/report 中输出连接串。
5. 未通过 read-only guard 时 fail-closed。

### 2. 误接 SAP Oracle MID

风险：M2/MID 相关配置存在后，后续开发可能误把 SAP Oracle MID 当作 NL2SQL trial 数据源。

控制：

1. M10-D 只允许物流智能助手中间库 / 只读 MySQL。
2. source system 必须是 middle_db。
3. 出现 sap_mid/oracle 等来源时 skipped/fail-closed。
4. 不读取 SAP_ORACLE_*。

### 3. SQL 或参数泄露

风险：response_meta、evaluation log、report 或异常文本泄露 SQL、params value、表字段名、host/DSN。

控制：

1. 只记录 sql_hash 和稳定错误码。
2. 只记录 param_keys 或 param_count，不记录 param values。
3. error message 固定白名单化。
4. 增加泄露负例测试。

### 4. EXPLAIN 失败被误判成功

风险：EXPLAIN 异常、超时或权限不足被降级成 success。

控制：

1. EXPLAIN 失败必须 fail-closed。
2. `explain_status` 必须可区分 disabled/skipped/success/failed。
3. 总体 status 不得把 failed 伪装为 success。

### 5. readonly trial 误返回业务数据

风险：trial row value 进入 report 或用户历史响应。

控制：

1. 不记录 trial row value。
2. 只记录 row_count、row_cap_applied、timeout_ms、elapsed_ms。
3. 对 response/report 做泄露负例。
4. 正式 QA 主返回不读取 trial 结果。

### 6. 无 LIMIT 或超 LIMIT 查询进入 trial

风险：试跑变成大表扫描或大量返回。

控制：

1. candidate_sql_gate 要求 LIMIT。
2. SQLPlan validator/renderer/safety 继续约束 LIMIT。
3. readonly trial gate 再次执行 limit/row cap 检查。
4. aggregate 类无用户 limit 的场景必须由确定性逻辑追加受控 LIMIT 0 或小样本 cap。

### 7. 超时控制不足

风险：EXPLAIN 或 trial 长时间占用连接。

控制：

1. EXPLAIN 和 trial 分别配置 timeout。
2. 默认小于或等于 1000ms 级别。
3. 超时固定错误码 fail-closed。
4. 超时不得影响正式 QA。

### 8. M8 artifact 副作用

风险：部分测试会写脏 `ai/outbox/kanban/t_7895e090/m8-shadow-eval-records.jsonl`。

控制：

1. D0 不跑测试，不产生该副作用。
2. D1/D2/D3 若跑测试后出现该文件 dirty，必须精确恢复该文件，不使用 `git clean` 或大范围 reset。

### 9. 阶段越界

风险：D1/D2/D3 开发中把 NL2SQL 接入正式 QA 答案或前端。

控制：

1. D 阶段全部 shadow/dry-run。
2. 正式 QA 主返回不变。
3. 不接前端。
4. 不进入 M10-E。

## 阻断条件

后续任一阶段出现以下情况必须停止：

1. 当前 worktree 不 clean 且 dirty 不属于本任务范围。
2. HEAD 不在确认基线上。
3. 需要读取 `.env` 或输出连接信息。
4. 需要连接 SAP Oracle MID。
5. EXPLAIN/trial 需要绕过 gate/validator/safety。
6. 需要返回 trial rows 给用户。
7. 需要把 NL2SQL 结果作为正式答案来源。

## 本轮风险结论

M10-D0 只写审计材料，不执行数据库或 EXPLAIN，因此风险可控。建议进入 M10-D1，但 D1 仍必须限制在 fake executor/schema/report 层，不触碰真实数据库。
