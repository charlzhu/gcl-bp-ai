# gcl-bp-ai 架构大修实施计划

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** 修复 gcl-bp-ai 九大架构缺陷，LLM 根据 catalog 上下文直接生成 SQL 字符串（非 SQLPlan 中间层），融合安全校验为统一受控问数链路。

**Architecture:** LLM catalog-driven SQL generation: 关键词提取 → catalog召回 → LLM过滤 → LLM直接出SQL → EXPLAIN验证+循环修正 → 执行。四大业务域统一 Graph。

**关键变化（vs 原计划）:**
- domain_route: **LLM 根据 catalog 上下文做语义域分类**（非关键词+LLM兜底）
- generate_sql: **LLM 直接输出 SQL 字符串**（非 SQLPlan JSON → renderer）

**Tech Stack:** LangGraph, Milvus, SQLAlchemy, OpenAI SDK, jieba, FastAPI + SSE.

**当前阶段边界:** 物管 SAP MID M2（不扩展到多Agent/多工具/RAG）。

---

## 修复总览

| # | 缺陷 | 修复策略 | 阶段 |
|---|------|---------|------|
| 1 | 双Graph割裂 | 融合为**统一12节点Graph** | P1 |
| 2 | 骨架Graph缺召回 | 集成三路召回到统一Graph | P1 |
| 3 | NL2SQL仅限物流 | 扩展灰度到四大域 | P2 |
| 4 | 纯关键词路由 | 加入LLM语义辅助 | P2 |
| 5 | 领域服务碎片化 | 统一DomainQaService抽象 | P1 |
| 6 | Prompt质量不足 | 补充业务口径+示例 | P1 |
| 7 | 缺EXPLAIN循环修正 | validate→correct循环(最多3次) | P2 |
| 8 | 元数据硬编码 | 从SQLCatalog查询 | P2 |
| 9 | 测试覆盖不足 | E2E+集成+多域测试 | P3 |

---

## Phase 1: Graph融合 + 统一抽象层（核心架构修复）

### Task 1: 融合两个Graph为统一 builder_v2.py

**Objective:** 将骨架层7节点安全校验 + 掌柜对齐层12节点召回/SQLPlan 融合为一个统一Graph。

**Files:**
- Create: `backend/app/domains/business_qa_graph/builder_v2.py`
- Read: `backend/app/domains/business_qa_graph/builder.py`（骨架层参考）
- Read: `backend/app/domains/business_qa_graph/builder_zg.py`（掌柜对齐层参考）

**融合后节点结构（14节点，1 Graph）：**

```
START
  │
  ▼
[1. receive]              ← 骨架层 receive_node（写入trace）
  │
  ▼
[2. domain_route]         ← 骨架层 domain_route_node（关键词白名单 + LLM辅助）
  │
  ├── unknown ──→ [clarify] → END
  │
  ▼ (ok)
[3. extract_keywords]     ← 掌柜层 jieba分词
  │
  ├────────── 并行 ──────────┐
  ▼            ▼             ▼
[4. recall_col] [5. recall_val] [6. recall_metric]
  │            │             │
  └────────────┼─────────────┘
               ▼
[7. merge_retrieved_info]
  │
  ├──────────┼──────────┐
  ▼          ▼
[8. filter_table] [9. filter_metric]
  │          │
  └──────────┼──────────┘
             ▼
[10. add_extra_context]
  │
  ▼
[11. plan_validate]       ← 骨架层 4层安全闸门
  │
  ├── clarify → [clarify_node] → END
  ├── unsupported → [unsupported_node] → END
  ├── error → [error_node] → END
  │
  ▼ (ok)
[12. generate_sql]        ← 掌柜层 SQLPlan
  │
  ▼
[13. validate_sql]
  │
  ├── 成功 → [14. execute_sql] → END
  └── 失败 → [15. correct_sql] → 回到13 (最多3次)
```

**Step 1: 写compilation test（Graph能否compile）**

```python
def test_builder_v2_compiles():
    from backend.app.domains.business_qa_graph.builder_v2 import build_unified_graph
    graph = build_unified_graph()
    assert graph is not None
```

运行: `pytest tests/unit/business_qa_graph/test_builder_v2.py::test_builder_v2_compiles -v`
预期: FAIL — module not found

**Step 2: 创建 builder_v2.py（融合图）**

要点：
- 复用骨架层 receive_node、domain_route_node、plan_validate_node、clarify_node、unsupported_node、error_node
- 复用掌柜层 extract_keywords、三路recall、merge、filter、add_extra_context、generate_sql、validate_sql、correct_sql、execute_sql
- domain_route → extract_keywords（known域）或 clarify（unknown域）
- plan_validate 放在 generate_sql 之前（安全校验在SQL生成前）
- validate_sql 失败时回 correct_sql → validate_sql 循环（最多3次）

**Step 3: 运行编译测试验证**

运行: `pytest tests/unit/business_qa_graph/test_builder_v2.py::test_builder_v2_compiles -v`
预期: PASS

**Step 4: Commit**

```bash
git add backend/app/domains/business_qa_graph/builder_v2.py tests/unit/business_qa_graph/test_builder_v2.py
git commit -m "feat: 融合骨架Graph与掌柜对齐Graph为builder_v2 14节点统一问数链路"
```

---

### Task 2: 创建统一 DomainQaService 抽象层

**Objective:** 解决三个域各有独立service类的问题，创建统一接口。

**Files:**
- Create: `backend/app/domains/business_qa_graph/services/unified_domain_service.py`

**接口设计：**

```python
from abc import ABC, abstractmethod
from typing import Any

class UnifiedDomainQaService(ABC):
    """统一领域问数服务抽象。
    
    每个业务域（物流/计划BOM/经营分析/物控物管）实现此接口。
    """
    
    @abstractmethod
    def domain_id(self) -> str:
        """返回业务域ID: logistics/plan_bom/business_analysis/material_mgmt"""
        ...
    
    @abstractmethod
    def execute(self, sql: str, question: str) -> dict[str, Any]:
        """执行SQL返回业务化结果。
        
        Returns:
            {"answer_summary": str, "result_table": {...}, "warnings": [...]}
        """
        ...
    
    @abstractmethod
    def get_catalog_context(self, question: str) -> dict[str, Any]:
        """获取该域的目录上下文（表/字段/指标）。
        
        Returns:
            {"tables": [...], "metrics": [...], "domain_rules": {...}}
        """
        ...
```

**Step 1: 写抽象接口**

```python
class UnifiedDomainQaService(ABC):
    ...
```

**Step 2: 写现有 LogisticsDataQaService 适配器**

```python
class LogisticsDomainService(UnifiedDomainQaService):
    domain_id = "logistics"
    
    def execute(self, sql, question):
        service = LogisticsDataQaService(...)
        return service._execute_raw_sql(sql)
    
    def get_catalog_context(self, question):
        recall = LogisticsCatalogRecallService()
        return recall.get_domain_catalog()
```

**Step 3: 写 PlanBomQaService 适配器**

```python
class PlanBomDomainService(UnifiedDomainQaService):
    domain_id = "plan_bom"
    ...
```

**Step 4: 写 BusinessAnalysisDomainService 适配器**

```python
class BusinessAnalysisDomainService(UnifiedDomainQaService):
    domain_id = "business_analysis"
    ...
```

**Step 5: 写 MaterialMgmtDomainService 骨架（M2待实现）**

```python
class MaterialMgmtDomainService(UnifiedDomainQaService):
    domain_id = "material_mgmt"
    # M2: execute 从中间库查库存/出入库
    # M2: get_catalog_context 返回V_HF_SAP_INOUT_DAILY/V_SAP_HFFN_CRKLSZ
    ...
```

**Step 6: 写测试验证所有适配器**

运行: `pytest tests/unit/business_qa_graph/test_unified_service.py -v`
预期: 4 passed

**Step 7: Commit**

---

### Task 3: 重写 execute_sql_node 使用统一 DomainQaService

**Objective:** execute_sql_node 不再直连DB，而是通过 domain→service dispatcher 调用。

**Files:**
- Modify: `backend/app/domains/business_qa_graph/nodes/execute_sql_node.py`

**改动：**

```python
# 旧: db_session.execute(text(sql))
# 新: service.execute(sql, question)

def execute_sql_node(state: dict) -> dict:
    domain = state.get("domain", "unknown")
    sql = state.get("sql", "")
    question = state.get("question", "")
    
    service = _get_domain_service(domain)
    result = service.execute(sql, question)
    
    _emit_result(state, result)
    return {"execution_result": result, "execution_status": "EXECUTED"}
```

**Step 1: Modify execute_sql_node.py**

**Step 2: Run existing tests**

运行: `pytest tests/unit/business_qa_graph/test_zg_nodes.py::TestExecuteSql -v`
预期: PASS

**Step 3: Commit**

---

## Phase 2: 领域路由LLM辅助 + NL2SQL全域灰度 + EXPLAIN循环

### Task 4: 领域路由加入 LLM 语义辅助

**Objective:** 当关键词匹配失败时，用LLM做兜底语义分类。

**Files:**
- Modify: `backend/app/domains/business_qa_graph/nodes/domain_route_node.py`
- Create: `backend/app/prompts/zg/domain_route.prompt`

**Prompt 设计（gcl-bp-ai 四大域语境）：**

```
【角色】你是经营计划智能助手，覆盖四大业务域：
- 物流: 发运、运输、车次、线路、运费...
- 计划BOM: BOM、版型、评审号、组件配置、功率...
- 经营分析: 产量、销量、库存、产销存、达成率...
- 物控物管: 库存、出入库、SAP、物料...

请将用户问题分类到最匹配的业务域。
输出: {"domain": "logistics|plan_bom|business_analysis|material_mgmt|unknown"}
```

**Step 1: 写 domain_route.prompt**

**Step 2: 修改 domain_route_node**

流程：关键词匹配 → 成功则返回 → 失败则LLM兜底 → 仍失败则 clarify

**Step 3: 写测试**

运行: `pytest tests/unit/business_qa_graph/test_domain_route.py -v`
预期: PASS

**Step 4: Commit**

---

### Task 5: NL2SQL 灰度扩展到四大域

**Objective:** 每个域的 UnifiedDomainQaService 内部启用 NL2SQL shadow。

**Files:**
- Modify: `backend/app/domains/logistics/services/data_qa_service.py`（已有，无变化）
- Modify: `backend/app/domains/plan_bom/services/plan_bom_qa_service.py`（新增 shadow）
- Modify: `backend/app/domains/business_analysis/services/qa_service.py`（新增 shadow）
- Create: `backend/app/domains/material_management/services/qa_service.py`（M2骨架）

**实现：每个域 service 内部：**

```python
if FEATURE_NL2SQL_LIVE_SHADOW:
    from backend.app.domains.logistics.services.nl2sql.live_shadow_adapter import (
        run_shadow_pipeline,
    )
    run_shadow_pipeline(
        question=question,
        domain=domain_id,
        primary_result=rule_result,
        db_session=db_session,
    )
```

**Step 1: PlanBomQaService 加 shadow**

**Step 2: BusinessAnalysisQaService 加 shadow**

**Step 3: 写 shadow smoke test 验证四域双写**

运行: `pytest tests/unit/nl2sql/test_multi_domain_shadow.py -v`
预期: 4 passed

**Step 4: Commit**

---

### Task 6: EXPLAIN 验证→校正循环（最多3次）

**Objective:** validate_sql 失败时自动 correct_sql → 再 validate，最多3次。

**Files:**
- Modify: `backend/app/domains/business_qa_graph/builder_v2.py`（加循环边）

**实现：**

```python
def _route_after_validate(state: dict) -> str:
    error = state.get("error")
    retry_count = state.get("_sql_retry_count", 0)
    if error and retry_count < 3:
        state["_sql_retry_count"] = retry_count + 1
        return "correct_sql"
    elif error:
        return "error_handler"
    return "execute_sql"
```

**Step 1: 修改 builder_v2 加 validate→correct→validate 循环边**

**Step 2: 写循环测试（模拟错误SQL）**

```python
def test_sql_correct_loop():
    state = {"sql": "SELEC * FRO tab", "error": "syntax error", "_sql_retry_count": 0}
    # 应进入 correct_sql
    assert _route_after_validate(state) == "correct_sql"
    
    state["_sql_retry_count"] = 3
    # 超过3次应进入 error_handler
    assert _route_after_validate(state) == "error_handler"
```

运行: `pytest tests/unit/business_qa_graph/test_correct_loop.py -v`
预期: PASS

**Step 3: Commit**

---

## Phase 3: Prompt 业务化 + 测试补全 + 前端适配

### Task 7: Prompt 全面业务化（四大域口径注入）

**Objective:** 所有 prompt 加入四大域业务示例和口径规则。

**Files:**
- Modify: `backend/app/prompts/zg/extend_keywords_for_column_recall.prompt`
- Modify: `backend/app/prompts/zg/extend_keywords_for_metric_recall.prompt`
- Modify: `backend/app/prompts/zg/extend_keywords_for_value_recall.prompt`
- Modify: `backend/app/prompts/zg/filter_table_info.prompt`
- Modify: `backend/app/prompts/zg/filter_metric_info.prompt`
- Modify: `backend/app/prompts/zg/generate_sqlplan.prompt`
- Modify: `backend/app/prompts/zg/correct_sql.prompt`
- Create: `backend/app/prompts/zg/domain_route.prompt`

**每个 prompt 需注入：**

1. 角色定位中加入"经营计划智能助手"
2. 四大域业务示例（物流: 发运量→运输量, BOM: 评审号→版型号...）
3. gcl-bp-ai 特有口径规则（刘娟→委托人, 经营计划→扩充部门）

**Step 1: 逐个检查并补充每个 prompt**

**Step 2: 验证 prompt 加载和格式化**

运行: `python -m pytest tests/unit/business_qa_graph/test_prompt_loader.py -v`
预期: ALL PASS

**Step 3: Commit**

---

### Task 8: E2E 集成测试（SQLite mock + SSE验证）

**Objective:** 用 SQLite mock 跑通整个 14 节点 Graph。

**Files:**
- Create: `tests/integration/business_qa_graph/test_e2e_unified_graph.py`

**Step 1: 创建 SQLite mock fixture**

```python
@pytest.fixture
def sqlite_db_session():
    engine = create_engine("sqlite:///:memory:")
    # 创建模拟物流表
    engine.execute("CREATE TABLE logistics_shipment (id INT, base_name TEXT, ...)")
    session = Session(engine)
    yield session
    session.close()
```

**Step 2: 写 E2E 测试（物流问数）**

```python
async def test_e2e_logistics_query(sqlite_db_session):
    graph = build_unified_graph()
    state = {"question": "2024年合肥发运量", "domain": "logistics", "_db_session": sqlite_db_session}
    final_state = graph.invoke(state)
    assert final_state["execution_status"] == "EXECUTED"
```

**Step 3: 写 E2E 测试（未知域→clarify）**

```python
def test_e2e_unknown_domain():
    state = {"question": "今天天气怎么样", "domain": "unknown"}
    final_state = graph.invoke(state)
    assert "CLARIFY" in str(final_state.get("status", ""))
```

**Step 4: 写 SSE 流式测试**

```python
async def test_sse_streaming():
    service = ZgQueryService()
    events = []
    async for event in service.query("2024年合肥发运量"):
        events.append(event)
    assert any("running" in e for e in events)
    assert any("success" in e for e in events)
```

**Step 5: Run all integration tests**

运行: `pytest tests/integration/business_qa_graph/ -v`
预期: ALL PASS

**Step 6: Commit**

---

### Task 9: 全量回归验证 + 无破坏确认

**Objective:** 跑所有存量测试确认无回归。

**Files:** 无修改。

```bash
# 全量回归
pytest tests/unit/logistics/nl2sql/ tests/unit/business_qa_graph/ -q --tb=short
# 预期: 450+ passed, 0 failures

# 编译检查所有新文件
for f in backend/app/domains/business_qa_graph/builder_v2.py \
         backend/app/domains/business_qa_graph/services/unified_domain_service.py; do
    python -m py_compile "$f" && echo "OK" || echo "FAIL"
done
```

---

### Task 10: 灰度激活配置 + API 入口切换

**Objective:** 新 Graph 通过 feature flag 控制，shadow→on 灰度。

**Files:**
- Modify: `backend/app/core/config.py`（已有 ZG_GRAPH_MODE，扩展）
- Modify: `backend/app/api/v1/zg_query.py` → 改为调用统一 builder_v2

**配置：**

```python
# config.py
UNIFIED_GRAPH_MODE: Literal["off", "shadow", "on"] = "shadow"
# off: 保持现有骨架层
# shadow: 新Graph并行执行，结果写审计表
# on: 新Graph替代旧Graph
```

**Step 1: Modify config.py**

**Step 2: Modify zg_query.py → 调用 build_unified_graph()**

**Step 3: 写灰度开关测试**

运行: `pytest tests/unit/business_qa_graph/test_gray_gate.py -v`
预期: PASS

**Step 4: Commit**

---

## 测试基线

| 类别 | 当前 | 目标 |
|------|------|------|
| NL2SQL 单元测试 | 413 | 413（不变） |
| 掌柜节点 focused | 30 | 30（不变） |
| 新 integration 测试 | 0 | 6+ |
| 全量通过率 | 100% | 100% |

## 不可破坏基线

- 物流问答主链路（413 个 NL2SQL 测试）
- 计划 BOM Excel 导入/查询/QA
- 前端现有物流/计划BOM体验
- 用户可见回答业务化（不暴露SQL/表名/字段名）
- 所有 `.env` 安全值不泄露

## 不做的（超出阶段边界）

- 多 Agent 编排
- 多工具调用平台
- RAG 知识库
- 经营分析全域入口
- 功率预测继续开发
- M2 物管 SAP Oracle 直连（另卡）
