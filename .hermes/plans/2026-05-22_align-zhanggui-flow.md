# 掌柜问数取数流程全面对齐计划

## 一、目标

将 gcl-bp-ai 的取数流程全面对齐「掌柜问数」项目的 12 步 LangGraph 工作流。

## 二、掌柜问数完整流程（目标架构）

```
START
  │
  ▼
[1. extract_keywords]          jieba 分词 + 停用词过滤
  │
  ├────────────────────────── 并行 ──────────────────────────┐
  ▼                     ▼                     ▼
[2. recall_column]     [3. recall_value]     [4. recall_metric]
 Qdrant 向量检索字段    ES 全文检索维度值      Qdrant 向量检索指标
  │                     │                     │
  └─────────────────────┼─────────────────────┘
                        ▼
              [5. merge_retrieved_info]
               合并召回 + 补充主外键 + 分组
                        │
          ├─────────────┴─────────────┐
          ▼                           ▼
  [6. filter_table]           [7. filter_metric]
   LLM 过滤不相关表             LLM 过滤不相关指标
          │                           │
          └─────────────┬─────────────┘
                        ▼
              [8. add_extra_context]
               添加日期 + DB 方言
                        │
                        ▼
              [9. generate_sql]
               LLM 生成 SQL
                        │
                        ▼
              [10. validate_sql]
               EXPLAIN 验证
                        │
              ┌─────────┴─────────┐
              ▼                   ▼
        [11. correct_sql]   [12. execute_sql]
         LLM 校正 SQL          执行 + 返回
              │
              ▼
        [12. execute_sql]
         执行 + 返回结果
              │
              ▼
             END
```

## 三、对齐方案

### 核心原则

1. **流结构完全对齐**：12 节点、并行分支、条件路由全部对齐
2. **安全边界保留**：generate_sql 节点不使用 LLM 自由生成 SQL，改用受控 SQLPlan；但在 SQLPlan 不可用或兜底时可通过 LLM 协助
3. **现有基础设施复用**：Milvus 替代 Qdrant、SQL 中间库维度表替代 ES、现有 SQLPlan/Catalog 能力
4. **多域支持**：物流、产销存、计划 BOM 统一走同一个 Graph

### 节点映射表

| 掌柜节点 | gcl-bp-ai 对应 | 实施方式 |
|----------|---------------|---------|
| extract_keywords | 新增 | jieba 分词（conda 环境已有） |
| recall_column | 改造 catalog_retrieval | Milvus 向量检索字段（已有） |
| recall_value | 新增 | SQL 查中间库维度字典表 |
| recall_metric | 改造 catalog_retrieval | Milvus 向量检索指标（已有） |
| merge_retrieved_info | 新增 | 合并三路结果 + JOIN 发现 |
| filter_table | 新增（LLM 节点） | LLM 筛选相关表/字段 |
| filter_metric | 新增（LLM 节点） | LLM 筛选相关指标 |
| add_extra_context | 新增 | 日期 + DB 方言注入 |
| generate_sql | **适配** SQLPlan | 受控 SQLPlan（非自由 SQL） |
| validate_sql | 复用 EXPLAIN smoke | 已有 m10d_explain |
| correct_sql | 复用 SQLPlan repair | 已有 sql_plan_repair |
| execute_sql | 复用 sql_execution | 已有 |

## 四、实施阶段

### Phase 1: 基础 Graph + 关键字提取 + 三路召回（3-4 天）

```
新增文件：
  backend/app/domains/business_qa_graph/nodes/extract_keywords_node.py
  backend/app/domains/business_qa_graph/nodes/recall_column_node.py
  backend/app/domains/business_qa_graph/nodes/recall_metric_node.py
  backend/app/domains/business_qa_graph/nodes/recall_value_node.py

改造文件：
  backend/app/domains/business_qa_graph/builder.py → 新 12 节点 Graph
  backend/app/domains/business_qa_graph/schemas/state.py → 扩展 State 字段
```

### Phase 2: 合并 + 过滤 + 上下文（2-3 天）

```
新增文件：
  backend/app/domains/business_qa_graph/nodes/merge_retrieved_info_node.py
  backend/app/domains/business_qa_graph/nodes/filter_table_node.py
  backend/app/domains/business_qa_graph/nodes/filter_metric_node.py
  backend/app/domains/business_qa_graph/nodes/add_extra_context_node.py
```

### Phase 3: SQL 生成 + 验证 + 校正 + 执行（2-3 天）

```
新增文件：
  backend/app/domains/business_qa_graph/nodes/generate_sql_node.py
  backend/app/domains/business_qa_graph/nodes/validate_sql_node.py
  backend/app/domains/business_qa_graph/nodes/correct_sql_node.py
  backend/app/domains/business_qa_graph/nodes/execute_sql_node.py
```

### Phase 4: API 端点 + Prompt 外部化 + SSE 流式（1-2 天）

### Phase 5: 全量回归 + 规则引擎下线（1-2 天）

## 五、关键安全适配说明

**generate_sql 节点的安全策略**（与掌柜问数的关键差异）：

- 掌柜问数：LLM 直接输出 SQL 字符串，不安全
- gcl-bp-ai：保持受控 SQLPlan 模式
  1. LLM 根据 catalog 上下文输出 **结构化 SQLPlan**（metric_code, query_key, dimensions, filters...）
  2. 后端确定性代码将 SQLPlan 渲染为参数化 SQL
  3. 多层安全校验（AST 校验、候选门禁、安全检查器、EXPLAIN smoke）
  4. 仅在 SQLPlan 失败且 `correct_sql` 兜底时，LLM 可协助修正 SQLPlan（不直接输出 SQL）

## 六、测试策略

- 每个 Phase 结束后跑全量回归（当前 511+ tests）
- 新节点逐个 TDD（RED → GREEN）
- Phase 5 做端到端评测集验证

## 七、风险

1. Graph 复杂度增加 → 每个节点需独立可测试
2. 性能：三路并行召回 + 多次 LLM 调用 → 需超时保护和降级策略
3. 与现有 Business QA Graph builder 冲突 → 新建 `builder_v2.py` 或直接替换
