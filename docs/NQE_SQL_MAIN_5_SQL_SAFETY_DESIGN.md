# NQE-SQL-MAIN-5：SQL 生成 / validate / correct / execute 安全边界设计

## 0. 文档边界

本文是 NQE 统一 SQL Agent 正式主链路替换任务第五张设计卡交付物。

本卡性质：

```text
只读设计卡；不写业务代码；不改前端；不新增数据库迁移；不创建真实表；不调用编码代理；不替换正式链路。
```

本卡事实源：

1. `ai/inbox/Hermes_NQE_统一SQLAgent最终执行指令_修正版.md`
2. `ai/inbox/NQE_统一SQLAgent正式主链路替换_最终报告_修正版.md`
3. `docs/NQE_SQL_MAIN_1_MAIN_LINK_DESIGN.md`
4. `docs/NQE_SQL_MAIN_2_METADATA_KB_DESIGN.md`
5. `docs/NQE_SQL_MAIN_3_RETRIEVAL_DESIGN.md`
6. `docs/NQE_SQL_MAIN_4_GRAPH_FLOW_DESIGN.md`
7. `docs/NQE_SQL_MAIN_SAFETY_BOUNDARY.md`
8. 当前仓库 SQL 生成、校验、修正、执行节点和提示词只读审计结果

明确排除：

1. `docs/CURRENT_STATUS.md`
2. `docs/NEXT_TASK.md`
3. `docs/HANDOFF.md`

上述三份通用状态文件当前记录物管 / SAP MID 并行任务，只读用于冲突判断，不作为 NQE 需求依据，也不得被本任务覆盖。

---

## 1. 当前仓库能力判断

### 1.1 已完成能力

只读审计确认当前仓库已具备以下基础：

1. 已有统一 Graph 原型，主流程包含 SQL 生成、SQL 校验、SQL 修正和 SQL 执行节点。
2. SQL 生成节点已采用“LLM 直接生成 SQL 文本”的路线，不再依赖 SQLPlan 中间层。
3. SQL 生成 Prompt 已要求只输出单条查询 SQL，不输出解释、注释或 Markdown 代码块。
4. SQL 校验节点已具备 EXPLAIN 验证雏形。
5. SQL 修正节点已能基于错误信息调用 LLM 修正 SQL。
6. Graph 现有条件分支支持校验失败后进入修正，再回到校验。
7. SQL 执行节点已具备基本查询执行、行结果转换和流式进度事件输出。
8. 依赖清单中已存在 SQL AST 解析库，可作为后续确定性安全预检基础。
9. 评测侧已有用户可见技术泄露检查思路，可作为回答层防泄露补充。

### 1.2 未完成能力

当前仓库距离 NQE 正式安全闭环仍有以下差距：

1. SQL 生成后直接进入 EXPLAIN，缺少 EXPLAIN 前的确定性 SQL 安全预检节点。
2. 当前没有 AST 级单语句、SELECT-only、表白名单、字段白名单、join 白名单校验。
3. 当前没有系统库、跨库访问、外部源库直查、危险函数、文件读写函数、锁等待函数等禁止规则。
4. 当前没有统一 LIMIT 自动补齐、最大 LIMIT、结果行数、结果体积和超时策略。
5. 当前 correct loop 最大轮次仍偏宽，应按 NQE 设计收敛为最多 2 轮。
6. 当前修正 SQL 未显式记录 SQL revision、修正原因、安全结果和 EXPLAIN 结果。
7. 当前执行节点未明确只读连接、只读事务、statement timeout、rollback-only 和禁止 commit。
8. 当前无数据库连接时会返回 SQL 片段占位说明，NQE 正式链路用户可见输出不得展示 SQL 片段。
9. 当前错误信息截断但未做结构化脱敏，可能泄露表名、字段名、库名、host、user、路径或连接信息。
10. 当前 trace / query log / replay 尚未记录安全预检、SQL revision、EXPLAIN 和执行摘要的完整链路。

### 1.3 本次任务与当前状态是否一致

一致。本卡只输出安全边界设计，不修改代码。重点是把 NQE-SQL-MAIN-4 的主流程中：

```text
generate_sql_direct → precheck_sql_safety → explain_validate_sql → correct_sql → execute_sql_readonly
```

细化为可直接支撑后续 RED 测试和编码实现的安全设计。

### 1.4 本轮允许修改范围

仅允许新增或更新：

1. `docs/NQE_SQL_MAIN_5_SQL_SAFETY_DESIGN.md`
2. `docs/NQE_SQL_MAIN_CURRENT_STATUS.md`
3. `docs/NQE_SQL_MAIN_NEXT_TASK.md`
4. `docs/NQE_SQL_MAIN_HANDOFF.md`

### 1.5 本轮禁止修改范围

1. 不修改 `backend/` 业务代码。
2. 不修改 `frontend/` 代码。
3. 不新增数据库迁移。
4. 不创建真实数据库表。
5. 不调用编码代理。
6. 不替换正式问答链路。
7. 不覆盖物管 / SAP MID 的三份通用状态文件。
8. 不写入真实密钥、连接串、账号、Token、API Key 或内部凭证。
9. 不把外部参考项目名称写入 NQE 文档、看板标题、代码命名或用户可见输出。

---

## 2. SQL 生命周期总原则

NQE 正式 SQL 生命周期必须分为 7 个确定阶段：

```text
1. context_ready
2. generate_sql_direct
3. normalize_sql_text
4. precheck_sql_safety
5. explain_validate_sql
6. correct_sql_loop
7. execute_sql_readonly
```

核心原则：

1. **先上下文门禁，再生成 SQL**：缺表、缺字段、缺指标口径、缺 join 时不得让 LLM 猜测。
2. **先安全预检，再 EXPLAIN**：任何 SQL 未通过确定性预检前，不允许进入数据库 EXPLAIN。
3. **先 EXPLAIN，再执行**：任何 SQL 未通过 EXPLAIN / 语法 / 权限 / 计划成本检查前，不允许正式执行。
4. **只读执行**：执行阶段只能使用只读连接或只读事务，不允许写入、DDL、DML、存储过程或外部系统调用。
5. **修正不绕过安全**：修正后的 SQL 必须重新进入 `precheck_sql_safety` 和 `explain_validate_sql`。
6. **安全失败不交给 LLM 绕过**：策略类安全失败不得让 LLM 通过改写绕过规则。
7. **全链路可追溯**：每一版 SQL 都必须有 revision、hash、安全结果、EXPLAIN 结果、执行摘要和脱敏错误。
8. **用户不可见内部实现**：用户可见回答不得展示 SQL、表名、字段名、query_key、planner、guardrail、schema、raw/debug、LLM、prompt、trace 原文。

---

## 3. `generate_sql_direct` 设计

### 3.1 输入

`generate_sql_direct` 只允许读取以下输入：

| 输入 | 说明 |
|---|---|
| `question` | 用户原始问题，仅用于语义目标 |
| `normalized_question` | 标准化问题 |
| `selected_domain` | 选中业务域 |
| `selected_capability` | 选中能力 |
| `retrieval_context_package` | 多路召回后被选中的上下文包 |
| `metadata_version_id` | 元数据版本 |
| `prompt_version_id` | Prompt 版本 |
| `dialect` | 目标数据库方言 |
| `date_context` | 当前日期、默认年份、用户指定时间范围 |
| `security_policy_summary` | 安全策略摘要，只包含允许行为，不暴露底层实现 |

禁止输入：

1. 未过滤的候选表、候选字段、候选取值全集。
2. restricted / inactive / expired 元数据资产。
3. 真实数据库连接信息。
4. 密钥、账号、DSN、host、password、Token。
5. 旧链路 raw debug、原始异常堆栈。

### 3.2 输出

只允许输出：

```text
一条 SQL 文本
```

输出必须满足：

1. 只输出 SQL，不输出解释文本。
2. 不输出 Markdown 代码块。
3. 不输出多条 SQL。
4. 不输出注释。
5. 不输出未在上下文包中授权的表、字段、函数、指标、join。

### 3.3 Prompt 边界

Prompt 必须强调：

1. 只能使用上下文包中 `selected=true` 且安全状态允许的资产。
2. 指标必须遵循元数据中的业务口径、计算公式、过滤规则、时间口径和单位口径。
3. 禁止猜测表、字段、join、函数和默认过滤条件。
4. 禁止访问外部源库或系统库。
5. 只能生成查询 SQL。
6. 只能生成单语句。
7. 明细类查询必须受 LIMIT 策略约束。
8. 未指定时间时使用本域默认时间口径；如当前域定义为全历史默认，则遵循域配置。
9. 无法生成时应让上游进入澄清或 fallback，不得编造 SQL。

### 3.4 生成失败分支

| 场景 | 分支 |
|---|---|
| 上下文不足 | `terminal_clarify` 或 `legacy_fallback` |
| LLM 调用失败 | `legacy_fallback` 或 `terminal_error` |
| 输出为空 | `correct_sql` 不处理，直接 `legacy_fallback` 或 `terminal_error` |
| 输出包含解释/多语句/代码块 | 先进入文本规范化；若仍不合规则安全拒绝或 fallback |
| 输出引用未授权资产 | 安全预检拒绝，不能直接执行 |

---

## 4. `normalize_sql_text` 设计

`normalize_sql_text` 是安全预检内部的第一步，不单独暴露为 Graph 节点也可以，但必须有确定性实现。

### 4.1 处理内容

1. 去除首尾空白。
2. 去除 Markdown 代码块包裹。
3. 去除尾部单个分号。
4. 统一换行和空白。
5. 保留字符串字面量内容，不擅自改写业务值。
6. 计算 `sql_hash`，用于 revision、trace 和 replay。

### 4.2 禁止处理

1. 不自动删除 SQL 内部注释后继续执行；如存在注释，应标记为需要安全预检处理。
2. 不自动删除第二条语句。
3. 不自动修复写操作为读操作。
4. 不自动替换表名、字段名或业务过滤条件。
5. 不自动拼接用户输入。

---

## 5. `precheck_sql_safety` 设计

`precheck_sql_safety` 是 NQE SQL 安全闭环的核心确定性节点，必须位于 SQL 生成后、EXPLAIN 前。

### 5.1 输出结构

建议输出：

| 字段 | 含义 |
|---|---|
| `status` | `PASS` / `CORRECTABLE` / `REJECT` / `FALLBACK` |
| `normalized_sql` | 规范化后的 SQL，仅内部使用 |
| `sql_hash` | SQL hash |
| `violations` | 安全违规列表 |
| `rewrite_actions` | LIMIT 补齐、LIMIT 降档等确定性改写摘要 |
| `allowed_assets` | 本轮允许资产 ID 摘要 |
| `risk_level` | `low` / `medium` / `high` / `critical` |
| `public_reason` | 用户可见业务化原因，不含 SQL、表字段或内部术语 |
| `trace_reason` | 内部 trace 脱敏原因 |

### 5.2 解析策略

建议采用 SQL AST 解析库，并按目标数据库方言解析。

处理顺序：

```text
SQL 文本 → 规范化 → AST parse → AST walk → policy checks → optional deterministic rewrite → safety result
```

解析失败分支：

| 解析结果 | 分支 |
|---|---|
| 纯语法错误，且未触发危险关键字 | `CORRECTABLE`，进入 correct loop |
| 解析失败且包含写操作、系统库、危险函数等关键风险 | `REJECT` |
| 方言不支持导致解析不稳定 | `FALLBACK` 或 `terminal_error` |

### 5.3 单语句检查

必须拒绝：

1. 多个分号分隔的语句。
2. CTE 后附带第二条语句。
3. SQL 文本中出现第二个顶层 statement。
4. 通过注释或字符串逃逸构造第二条语句的可疑模式。

允许：

1. 单条 SELECT。
2. 单条只读 CTE + SELECT。
3. 单条 UNION / UNION ALL 查询，前提是每个分支均通过相同白名单校验。

### 5.4 SELECT-only 检查

允许的顶层 AST 类型：

1. `SELECT`
2. `WITH ... SELECT`
3. `UNION` / `UNION ALL`，所有子查询均为只读 SELECT

必须拒绝：

1. INSERT、UPDATE、DELETE、MERGE、REPLACE。
2. CREATE、ALTER、DROP、TRUNCATE、RENAME。
3. CALL、EXEC、存储过程、用户自定义过程调用。
4. SET、USE、SHOW、DESCRIBE、ANALYZE、OPTIMIZE、LOCK、UNLOCK。
5. LOAD DATA、SELECT INTO OUTFILE、INFILE、COPY、导入导出类语句。
6. 事务控制：BEGIN、COMMIT、ROLLBACK、SAVEPOINT。
7. 权限控制：GRANT、REVOKE。

### 5.5 表白名单检查

所有表引用必须同时满足：

1. 来自 `retrieval_context_package.selected_tables`。
2. 所属 domain / capability 与当前请求一致。
3. 元数据状态为 active。
4. 未过期。
5. 未被标记为 restricted。
6. 当前用户或角色有读取权限。
7. 不属于外部源库直查资产。
8. 不属于系统库、元数据库、审计库或迁移工具内部表。

必须拒绝：

1. 任意未召回或未 selected 的表。
2. 任意跨 domain 表。
3. 任意通过库名前缀访问的非中间库表。
4. 任意系统库对象。
5. 任意直接访问外部同步源的表、视图或同义词。

### 5.6 字段白名单检查

所有字段引用必须同时满足：

1. 属于已授权表。
2. 在 `selected_columns` 或指标公式依赖字段中登记。
3. 未被标记为敏感字段或 restricted 字段。
4. 计算字段必须来自已登记 metric expression 或安全函数组合。
5. ORDER BY、GROUP BY、HAVING、WHERE 中的字段同样必须校验。

特别规则：

1. 默认禁止 `SELECT *`。
2. `COUNT(*)` 可允许，但必须绑定已授权表。
3. 未带表别名的字段需能唯一解析到授权表；无法唯一解析时拒绝或进入修正。
4. 指标别名允许，但不得被当成真实字段再参与未授权过滤。

### 5.7 join 白名单检查

跨表查询必须满足：

1. 所有 join pair 均在 `nqe_join_relation` 或等价元数据中登记。
2. join key 必须来自登记关系，不允许 LLM 自由猜 join 条件。
3. join 类型必须在登记范围内；默认只允许 inner / left join。
4. join 数量不得超过当前域策略上限。
5. 不允许无条件 join、笛卡尔积或缺失 ON 条件的 join。
6. 不允许通过 WHERE 隐式构造未登记跨表关系。

若用户问题需要多表但无登记 join：

```text
不得生成跨表 SQL → terminal_clarify 或 legacy_fallback
```

### 5.8 系统库和外部源库禁止

必须拒绝：

1. 系统库、元数据库、执行计划库、权限库、审计库。
2. 数据库内置用户、角色、权限、连接、进程、变量表。
3. 外部系统源库直查对象。
4. 通过同义词、库名前缀、跨库引用绕过中间库的对象。

物管域特别规则：

1. 外部系统只能作为同步源或受控工具源。
2. 面向用户问答必须查询智能助手中间库。
3. 不允许用户问答实时直查外部源库。

### 5.9 危险函数和高风险表达式禁止

必须拒绝：

1. 睡眠、延迟、benchmark、锁等待类函数。
2. 文件读取、文件写入、导入导出类函数。
3. 网络访问、HTTP、外部连接、远程调用类函数。
4. 系统变量、会话变量、权限、连接信息读取函数。
5. 动态 SQL、执行字符串、过程调用。
6. 大随机排序、无界窗口、明显造成资源放大的表达式。
7. 常量恒真注入模式，例如 `1=1` 与用户值无关且扩大范围的条件。

### 5.10 LIMIT 与结果上限策略

默认策略：

| 查询类型 | LIMIT 策略 |
|---|---|
| 明细查询 | 无 LIMIT 时自动补齐默认 LIMIT |
| 排名 TopN | 尊重用户 N，但不得超过最大 LIMIT |
| 聚合单行 | 可不补 LIMIT，但执行层仍有限制 |
| 分组聚合 | 默认补齐或设置最大返回组数 |
| 导出型问题 | 不支持全量导出，进入澄清或拒绝 |

建议默认值：

1. 明细默认 LIMIT：100。
2. 明细最大 LIMIT：1000。
3. 分组聚合最大组数：1000。
4. 前端展示默认行数：100。
5. 执行层 fetch 上限：LIMIT + 1，用于判断是否截断。

确定性改写允许：

1. 自动补齐 LIMIT。
2. 将超过上限的 LIMIT 降为最大值。
3. 为无界分组结果追加外层 LIMIT。

确定性改写禁止：

1. 改写业务过滤条件。
2. 改写指标公式。
3. 改写时间范围。
4. 改写 join 条件。

### 5.11 复杂度预算

安全预检应计算 SQL 复杂度，超过阈值时拒绝或 fallback。

建议维度：

1. 表数量。
2. join 数量。
3. 子查询深度。
4. CTE 数量。
5. 窗口函数数量。
6. group by 字段数。
7. order by 字段数。
8. selected columns 数量。
9. 预估结果行数或 EXPLAIN rows。

复杂度超限分支：

```text
terminal_clarify 或 legacy_fallback
```

---

## 6. `explain_validate_sql` 设计

### 6.1 前置条件

EXPLAIN 节点只能在以下条件全部满足时执行：

1. `precheck_sql_safety.status == PASS`。
2. 使用的是 `normalized_sql`。
3. SQL revision 已记录。
4. 当前模式允许执行 NQE 校验。
5. 数据库连接为只读连接或只读权限账号。
6. 已设置 EXPLAIN 超时。

### 6.2 校验内容

EXPLAIN 至少应校验：

1. SQL 语法是否被目标数据库接受。
2. 表和字段权限是否满足。
3. 是否触发数据库级权限错误。
4. 预估扫描行数是否超过阈值。
5. 是否出现全表扫描且无合理限制。
6. 是否存在过高排序、临时表或文件排序风险。
7. 是否超过语句超时或执行计划超时。

### 6.3 失败分支

| 失败类型 | 分支 |
|---|---|
| 语法错误 | correct loop，未超过最大轮次时允许修正 |
| 字段/表不存在 | correct loop 或 fallback，取决于上下文是否可唯一修正 |
| 权限错误 | fallback 或 terminal_error，不允许 LLM 猜权限绕过 |
| 安全策略错误 | terminal_safety_reject，不允许 correct 绕过 |
| 成本超限 | terminal_clarify 或 fallback |
| 超时 | fallback 或 terminal_error |
| 数据库连接不可用 | fallback 或 terminal_error |

### 6.4 错误脱敏

EXPLAIN 错误进入 LLM 修正前必须脱敏：

1. 去除 host、IP、端口、user、schema、DSN、路径、连接串。
2. 去除真实账号、密码、Token、密钥。
3. 内部 trace 可保留错误分类、数据库错误码、资产 ID、SQL hash。
4. 给 LLM 的错误只保留修正所需的最小摘要。
5. 用户可见回答只表达“当前查询条件不足、暂不支持或系统暂时无法完成”，不得展示原始错误。

---

## 7. `correct_sql` 设计

### 7.1 最大轮次

NQE 正式链路建议：

```text
max_correction_rounds = 2
```

超过 2 轮仍失败：

```text
legacy_fallback 或 terminal_error
```

### 7.2 允许修正范围

仅允许修正：

1. SQL 方言语法差异。
2. 别名引用错误。
3. 聚合与 GROUP BY 兼容问题。
4. 日期函数或类型转换的方言问题。
5. 明确由 EXPLAIN 报出的字段歧义，且上下文可唯一解析。
6. LIMIT 位置、外层包裹等安全改写后产生的语法问题。

### 7.3 禁止修正范围

不得让 LLM 修正以下问题：

1. 写操作、DDL、DML、过程调用等策略违规。
2. 未授权表、未授权字段、跨域资产。
3. 未登记 join。
4. 系统库或外部源库访问。
5. 危险函数或高风险表达式。
6. 缺少业务口径、缺少指标定义、缺少时间范围且不能按域默认口径处理。
7. 用户问题本身不支持或需要澄清。

策略类安全失败必须终止或 fallback，不能进入 correct loop。

### 7.4 修正 Prompt 输入

LLM 修正只允许接收：

1. 脱敏后的错误摘要。
2. 当前 SQL 的脱敏/内部版本，禁止对用户展示。
3. 原始业务问题。
4. 当前 selected 上下文包。
5. 当前修正轮次和禁止事项。

不得接收：

1. 数据库连接信息。
2. 真实 host、user、password、DSN、Token。
3. 未授权候选资产全集。
4. 原始异常堆栈。

### 7.5 SQL revision 记录

每次生成或修正 SQL 都必须记录 revision。

建议字段：

| 字段 | 含义 |
|---|---|
| `revision_id` | SQL 修订 ID |
| `trace_id` | 查询追踪号 |
| `round` | 0 表示首次生成，1/2 表示修正轮次 |
| `source` | `generated` / `corrected` / `deterministic_rewrite` |
| `sql_hash` | SQL hash |
| `sql_redacted` | 内部脱敏 SQL，可用于 replay 权限范围内查看 |
| `metadata_version_id` | 元数据版本 |
| `prompt_version_id` | Prompt 版本 |
| `safety_status` | 安全预检状态 |
| `explain_status` | EXPLAIN 状态 |
| `error_code` | 脱敏错误码或分类 |
| `created_at` | 创建时间 |

---

## 8. `execute_sql_readonly` 设计

### 8.1 前置条件

执行节点只能在以下条件全部满足时运行：

1. 安全预检通过。
2. EXPLAIN 通过。
3. 当前 SQL revision 是最新 revision。
4. 执行 SQL 与 EXPLAIN SQL hash 一致。
5. 当前业务域灰度模式允许执行。
6. 当前用户权限允许查询该域数据。
7. 只读连接或只读事务已开启。

### 8.2 只读事务与连接策略

执行层必须满足：

1. 使用只读账号或只读连接池。
2. 如数据库支持，开启只读事务。
3. 设置 statement timeout。
4. 设置连接级或语句级最大执行时间。
5. 执行完成后 rollback-only，不进行 commit。
6. 不复用带写权限的业务事务上下文。
7. 不允许执行多语句或批处理。
8. 记录执行耗时、返回行数、截断标记和错误分类。

### 8.3 结果截断

执行层必须：

1. 使用 fetch 上限，避免一次性拉取无界结果。
2. 对超过展示上限的结果做截断。
3. 结果表只输出业务化列名，不输出真实字段名。
4. 不返回内部 SQL、表名、字段名、raw/debug。
5. 对空结果返回业务化空结果说明。
6. 对大结果引导用户补充筛选条件，而不是导出全量数据。

### 8.4 执行失败分支

| 场景 | 分支 |
|---|---|
| 超时 | fallback 或业务化失败 |
| 权限错误 | fallback 或业务化失败 |
| 连接不可用 | fallback 或业务化失败 |
| 结果过大 | 截断或澄清筛选条件 |
| 空结果 | 业务化空结果说明 |
| SQL hash 不一致 | 安全拒绝 |
| 只读事务设置失败 | 不执行，fallback 或 terminal_error |

### 8.5 用户可见输出

用户可见输出只允许：

1. 业务化摘要。
2. 业务化结果表。
3. 统计口径说明。
4. 数据时间范围。
5. 截断提示。
6. 空结果说明。
7. 可给用户报障用的公开 trace_id。

禁止输出：

1. SQL。
2. 表名。
3. 字段名。
4. query_key。
5. planner / guardrail / schema / raw / debug。
6. LLM / prompt / 内部 trace 原文。
7. 数据库错误原文。

---

## 9. Trace、query log 与 replay 设计

### 9.1 必须记录的 trace step

SQL 生命周期至少记录：

1. `generate_sql_direct.started`
2. `generate_sql_direct.completed`
3. `precheck_sql_safety.started`
4. `precheck_sql_safety.completed`
5. `explain_validate_sql.started`
6. `explain_validate_sql.completed`
7. `correct_sql.started`
8. `correct_sql.completed`
9. `execute_sql_readonly.started`
10. `execute_sql_readonly.completed`
11. `present_business_answer.completed`

### 9.2 trace 最小字段

| 字段 | 说明 |
|---|---|
| `trace_id` | 查询追踪号 |
| `step_name` | 节点名 |
| `status` | started / completed / failed / skipped |
| `latency_ms` | 耗时 |
| `metadata_version_id` | 元数据版本 |
| `prompt_version_id` | Prompt 版本 |
| `sql_revision_id` | SQL revision |
| `sql_hash` | SQL hash |
| `safety_status` | 安全预检状态 |
| `error_class` | 脱敏错误分类 |
| `fallback_reason` | fallback 原因 |

### 9.3 replay 快照

replay 必须能复现：

1. 原始问题。
2. 领域路由结果。
3. 召回上下文包。
4. 元数据版本。
5. Prompt 版本。
6. SQL revisions。
7. 安全预检结果。
8. EXPLAIN 结果摘要。
9. 执行摘要。
10. 用户可见输出摘要。

replay 不得保存：

1. 密钥。
2. 连接串。
3. 真实账号。
4. 未脱敏异常堆栈。
5. 无权限用户不可见的数据快照。

---

## 10. SQL 安全测试集设计

后续实现卡必须先写 RED 测试，再实现。

### 10.1 正向通过用例

| 类别 | 期望 |
|---|---|
| 单表明细查询，已授权表字段，带 LIMIT | PASS |
| 单表聚合查询，已授权指标字段 | PASS |
| 分组聚合查询，字段均在白名单 | PASS |
| 只读 CTE + SELECT，所有表字段授权 | PASS |
| UNION 查询，每个分支均为授权 SELECT | PASS |
| COUNT(*) 查询，绑定授权表 | PASS |
| TopN 查询，LIMIT 在上限内 | PASS |
| 无 LIMIT 明细查询 | 自动补 LIMIT 后 PASS |
| LIMIT 超过最大值 | 降档到最大值后 PASS |

### 10.2 策略拒绝用例

| 类别 | 期望 |
|---|---|
| 多语句 | REJECT |
| INSERT / UPDATE / DELETE | REJECT |
| CREATE / ALTER / DROP / TRUNCATE | REJECT |
| CALL / EXEC / 存储过程 | REJECT |
| SET / USE / SHOW / DESCRIBE | REJECT |
| 事务控制语句 | REJECT |
| 权限控制语句 | REJECT |
| 导入导出文件类语句 | REJECT |
| 系统库访问 | REJECT |
| 外部源库直查 | REJECT |
| 未授权表 | REJECT |
| 未授权字段 | REJECT |
| restricted 字段 | REJECT |
| SELECT * 明细 | REJECT 或确定性改写为授权字段 |
| 未登记 join | REJECT 或 FALLBACK |
| 无 ON 的 join | REJECT |
| 危险函数 | REJECT |
| 睡眠 / benchmark / 锁等待 | REJECT |
| 文件读取 / 网络访问函数 | REJECT |
| 常量恒真扩大范围 | REJECT 或 FALLBACK |
| 注释注入 | REJECT |
| 全量导出型请求 | terminal_clarify 或 REJECT |

### 10.3 可修正用例

| 类别 | 期望 |
|---|---|
| 方言函数轻微错误 | CORRECTABLE → correct → PASS |
| GROUP BY 缺少必要字段 | CORRECTABLE → correct → PASS |
| 别名引用位置错误 | CORRECTABLE → correct → PASS |
| 日期格式函数错误 | CORRECTABLE → correct → PASS |
| LIMIT 方言位置错误 | CORRECTABLE → correct → PASS |
| 字段歧义但上下文可唯一解析 | CORRECTABLE → correct → PASS |

### 10.4 不可修正用例

| 类别 | 期望 |
|---|---|
| 安全策略失败 | 不进入 correct |
| 未授权资产 | 不进入 correct |
| 未登记 join | 不进入 correct |
| 系统库访问 | 不进入 correct |
| 外部源库直查 | 不进入 correct |
| 危险函数 | 不进入 correct |
| 超过最大修正轮次 | fallback 或 terminal_error |

### 10.5 执行层用例

| 类别 | 期望 |
|---|---|
| 只读事务设置成功 | 执行 |
| 只读事务设置失败 | 不执行 |
| EXPLAIN 与执行 SQL hash 不一致 | 拒绝执行 |
| statement timeout | fallback 或业务化失败 |
| 返回行数超过展示上限 | 截断并提示 |
| 空结果 | 业务化空结果 |
| 数据库错误含连接信息 | 脱敏后记录，用户不可见 |
| 无数据库连接 | 不展示 SQL，返回业务化不可执行说明或 fallback |

### 10.6 用户可见泄露用例

必须验证回答中不包含：

1. SQL 关键片段。
2. 表名。
3. 字段名。
4. query_key。
5. planner / guardrail / schema / raw / debug。
6. LLM、prompt、内部 trace 原文。
7. 数据库错误原文。
8. host、user、DSN、Token、API Key。

---

## 11. 后续实现建议

NQE-SQL-MAIN-6 及后续编码卡可按以下顺序落地：

1. 先落地 `nqe_*` 元数据和运行审计表。
2. 再实现 SQL revision、trace step、安全预检结果的数据模型。
3. 实现 `precheck_sql_safety` 的纯函数测试，不接数据库。
4. 实现 EXPLAIN validate 测试，使用只读测试库或 mock session。
5. 实现 correct loop 测试，mock LLM 输出。
6. 实现 execute readonly 测试，mock 或测试库验证只读、超时和截断。
7. 接入 Graph 前先跑 SQL 安全集 RED/GREEN。
8. 接入 Graph 后先 shadow，不直接 on。

---

## 12. 本卡验收结论

NQE-SQL-MAIN-5 完成后，应满足：

1. SQL 生成输入、输出、Prompt 边界清晰。
2. SQL 安全预检规则完整，且明确位于 EXPLAIN 前。
3. SELECT-only、单语句、白名单、系统库禁止、危险函数禁止、LIMIT、超时、行数上限规则明确。
4. EXPLAIN validate 的前置条件和失败分支清晰。
5. correct_sql 的修正范围、最大轮次和 SQL revision 记录清晰。
6. execute_sql_readonly 的只读执行、错误脱敏、结果截断和 fallback 策略清晰。
7. SQL 安全测试集可直接支撑后续 RED 测试。
8. 本卡不修改业务代码、不覆盖物管状态文件、不泄露密钥、不调用编码代理。
