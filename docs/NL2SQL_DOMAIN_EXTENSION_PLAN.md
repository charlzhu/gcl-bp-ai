# NL2SQL 多业务域扩展总体规划

## 一、文档用途

本文档定义 NL2SQL 架构从"物流域私有"抽象为"多域通用"的总体方案，
以及各业务域（产销存、计划 BOM + 功率测算）的扩展路线和替换规则模式的最终目标。

对应 AGENTS.md 长期目标中的"多 Agent 受控调度 + 多业务域智能问答 + 多工具调用"定位。

---

## 二、总体路线

```
Phase A ── NL2SQL 架构抽象化（核心重构）
   │
   ├──→ Phase B ── 产销存（经营分析）NL2SQL Shadow 接入
   │
   └──→ Phase C ── 计划 BOM（含功率测算）NL2SQL Shadow 接入
                        │
                        └──→ Phase D ── 全域指标补齐 → 灰度替换规则模式
```

### Phase 划分

| Phase | 名称 | 产出 | 预计工作量 |
|---|---|---|---|
| A | NL2SQL 架构抽象化 | 通用 NL2SQL 框架 + 域注册机制 | 中（2-3 天） |
| B | 产销存 NL2SQL Shadow 接入 | business_analysis 域的 catalog/templates/gate | 中（1-2 天） |
| C | 计划 BOM（含功率测算）NL2SQL Shadow 接入 | plan_bom 域的 catalog/templates/gate | 中大（2-3 天） |
| D | 全域指标补齐 + 灰度替换规则模式 | 物流 67 query_key + 产销存 3 + BOM A 类灰度替换 | 大（3-5 天） |

---

## 三、Phase A：NL2SQL 架构抽象化

### 3.1 设计原则

1. **轻量抽象**：不改文件路径，不移动文件，不改 import 链
2. **兼容优先**：已有 `Logistics*` 类名保留别名兼容，不破坏现有测试
3. **注册模式**：域差异通过注册 catalog + templates 注入，不新增路由层次
4. **增量改造**：每个改动步骤独立可测，不出现"超大提交"

### 3.2 当前约束

- 物流 NL2SQL 包路径：`backend/app/domains/logistics/services/nl2sql/`
- 32 个文件，~12800 行代码
- 全量回归 685 passed（325 NL2SQL + 物流 QA + query planning）
- 核心入口点：
  - `data_qa_service.py` 中 `LogisticsNl2SqlLiveShadowAdapter`
  - `data_qa_service.py` 中 `_decide_grayscale_and_replace` (M15 灰度门禁)
  - `M9` 中的 `LogisticsNl2SqlDomainRouter`
  - `live_shadow_adapter.py` 中的 `LogisticsNl2SqlLiveShadowAdapter`
  - 当前 DomainRouter 对其他域返回 `should_process=False`

### 3.3 具体改造方案

#### 3.3.1 新增文件清单

```
backend/app/domains/logistics/services/nl2sql/
├── domain_router.py          [新建] 抽象多域路由，支持域注册
├── domain_registry.py        [新建] 域 catalog/templates 注册表
└── domains/                  [新建] 按域组织的 catalog 目录
    ├── __init__.py
    ├── logistics/            [移入] 当前物流 catalog 配置
    ├── business_analysis/    [新建] 产销存 catalog 注册
    └── plan_bom/             [新建] 计划 BOM catalog 注册
```

#### 3.3.2 `domain_router.py`（新建）

```python
"""NL2SQL 多域路由——支持按域注册 catalog + templates。"""

class Nl2SqlDomainRoute(BaseModel):
    """域路由结果。"""
    should_process: bool
    domain: str
    source_system: str = "middle_db"
    mode: str = "shadow"
    reason_code: str | None = None

class Nl2SqlDomainRouter:
    """多域路由基类——通过 domain_registry 注册判断。"""

    def __init__(self, registry: Nl2SqlDomainRegistry | None = None):
        self._registry = registry or Nl2SqlDomainRegistry()

    def route(self, question: str | ...) -> Nl2SqlDomainRoute:
        """遍历已注册域→执行域识别→返回匹配域或失败。"""
        ...
```

- `LogisticsNl2SqlDomainRouter` 作为 `Nl2SqlDomainRouter` 的子类保留别名兼容
- 默认行为保持不变（物流域，其他域返回 `should_process=False`）

#### 3.3.3 `domain_registry.py`（新建）

```python
"""NL2SQL 域注册表——管理各域的 catalog 加载和路由判断。"""

@dataclass
class DomainCatalogRegistration:
    domain: str
    priority: int             # 匹配优先级
    keywords: list[str]       # 域识别关键词
    catalog_loader: Callable  # → LogisticsSemanticCatalog | ...
    templates_loader: Callable # → query_templates
    allowed_tables: tuple[str, ...]

class Nl2SqlDomainRegistry:
    def __init__(self):
        self._domains: dict[str, DomainCatalogRegistration] = {}

    def register(self, registration: DomainCatalogRegistration) -> None:
        """注册域到注册表。"""

    def identify(self, text: str) -> tuple[str, int] | None:
        """根据关键词匹配识别域。"""

    def get_catalog(self, domain: str) -> Any:
        """获取域下的 semantic catalog。"""

    def get_templates(self, domain: str) -> list[dict]:
        """获取域下的 query_templates。"""
```

#### 3.3.4 需要修改的文件（影响范围最小化）

| 文件 | 改动内容 |
|---|---|
| `m9_sqlplan_generation.py` | `LogisticsNl2SqlDomainRouter` 改为继承 `Nl2SqlDomainRouter`；导入 registry |
| `live_shadow_adapter.py` | `LogisticsNl2SqlLiveShadowAdapter` 默认使用 `Nl2SqlDomainRouter`；`run_shadow()` 按域分派 catalog + generator |
| `data_qa_service.py` | `_decide_grayscale_and_replace` 扩展 M15 门禁支持多域 domain 字段；`run_shadow` 传递域信息 |
| `__init__.py` (nl2sql) | 导出新增的 `domain_router`、`domain_registry` 模块 |
| `m15_grayscale_gate.py` | 灰度门禁新增 `domain` 字段支持，域粒度开关 |
| `m15_grayscale_decision_result.py` | 新增 `domain` 属性 |

#### 3.3.5 不改动的文件

- `semantic_catalog.py`（物流的）— 继续是物流私有，其他域自行注册
- `catalog_retrieval.py` — 继续物流私有，其他域需要自己的 recall
- `sql_plan.py` / `sql_renderer.py` / `sql_ast_safety.py` — 域无关基础设施，不动
- 全部测试文件 — 不改，保留兼容性

### 3.4 Phase A 子阶段划分

```
A-0: 设计评审 + 看板卡创建
A-1: 新建 domain_router.py + domain_registry.py（含完整测试）
A-2: 迁移 LogisticsNl2SqlDomainRouter → 继承 Nl2SqlDomainRouter（保留别名兼容）
A-3: 物流域注册到 registry（验证现有行为不变，全量回归通过）
A-4: 扩展 M15 灰度门禁支持域粒度和 domain 字段
A-5: 适配 live_shadow_adapter.py 和 data_qa_service.py 的分派
A-6: 全量回归 + Phase A 验收
```

---

## 四、Phase B：产销存（经营分析）NL2SQL Shadow 接入

### 4.1 业务域现状

- 31 个标准指标（production/sales/inventory/cost 四大类）
- 5 个 query_key（ba_isp_metric_summary/breakdown/trend/budget_achievement/inventory_snapshot）
- 独立 semantic_catalog（`InventorySalesProductionCatalog*` 类）
- 已有 M5/M6 shadow 框架
- 中间库表 `dwd_ba_isp_monthly_fact` + `dim_ba_isp_metric` + `dim_ba_isp_metric_alias`

### 4.2 具体工作

1. **创建 business_analysis 域的 query_templates**（替换当前占位模板）
   - 路径：`config/domains/business_analysis/query_templates.yaml`
   - 基于 5 个 query_key 的查询模式设计 templates
2. **将产销存 catalog 适配到通用 catalog 格式**
   - 创建 `domains/business_analysis/catalog.py`（注册到 registry）
3. **注册产销存域到 DomainRouter**
   - `Nl2SqlDomainRegistry.register()` 注册产销存
   - 不再返回 `should_process=False`
4. **创建产销存 SQL 模板 / renderer**
   - 参考物流 renderer 结构，但不复制文件
5. **创建 NL2SQL shadow 测试集**
   - 基于 5 个 query_key 的 NL 样例题（15-20 个）
6. **全量回归 + Merge**

---

## 五、Phase C：计划 BOM（含功率测算）NL2SQL Shadow 接入

### 5.1 业务域现状

- 6 张 plan_bom_* 表（header/material_line/revision/import_batch/export_task/export_file）
- 7 张 plan_power_* 表（model_version/model_sheet/factor_option/supplier_efficiency/power_bin/benchmark_factor/validation_case）
- 现有 PlanBomQaService 分类 A/B/C/D 模式
- 无 catalog、无 query_templates、无 NL2SQL

### 5.2 具体工作

1. **创建 plan_bom semantic_catalog**
   - 梳理 BOM 表的字段语义
   - 创建 `domains/plan_bom/catalog.py`
2. **创建 plan_bom query_templates**
   - BOM 查询类（A 类问题，如版型搭配、物料清单）
3. **创建 Nl2SqlPlanBomGenerator**
   - 继承或适配物流 SQLPlan 生成器
   - 功率预测类问题 → LLM 理解 + 参数提取，调用确定性计算引擎
4. **注册 plan_bom 到 DomainRouter**
   - 不再返回 `should_process=False`
5. **创建 plan_bom shadow 测试集**
   - 基于 BOM 129 多问法语义回归（查询类部分）
6. **全量回归 + Merge**

### 5.3 功率测算的特殊处理

功率预测问题**不走完整的 SQLPlan → Render → Execute 流程**，而是：

```
NL 问题 → 路由识别域 plan_bom
  → catalog recall（确定功率预测相关的表和字段）
  → LLM 提取参数（功率档位、供应商、版型、评审号...）
  → 参数传递给 power_prediction_engine（确定性代码）
  → 返回功率预测结果
```

这种"参数提取 + 调用确定性引擎"的模式是 NL2SQL 框架以外的能力扩展，但统一走 NL2SQL 的路由、catalog、灰度门禁基础设施。

---

## 六、Phase D：全域指标补齐 + 灰度替换规则模式

### 6.1 物流域灰度路线

```
阶段 1: SIMPLE_AGGREGATE（简单聚合类查询）
  → 环境变量: LOGISTICS_NL2SQL_GRAYSCALE_TYPES="simple_aggregate"
  → 观察差异率日报 1-3 天
阶段 2: DIMENSION_SPLIT（维度拆分类查询）
  → 环境变量: ...="simple_aggregate,dimension_split"
  → 观察差异率日报 3-5 天
阶段 3: MULTI_METRIC_SUMMARY（多指标汇总类查询）
  → 环境变量: ...="simple_aggregate,dimension_split,multi_metric_summary"
  → 观察差异率日报 5-7 天
阶段 4: 全量 67 query_key
  → 环境变量: ...="*"（或逐个添加剩余 query_key）
  → 稳定运行 7-14 天
阶段 5: 去掉 _decide_grayscale_and_replace 的规则回退
  → NL2SQL 正式成为主链路
  → 规则代码标记 deprecated
```

### 6.2 产销存域灰度路线

```
阶段 1: ba_isp_metric_summary shadow 灰度
阶段 2: ba_isp_metric_breakdown / trend 扩展
阶段 3: budget_achievement / inventory_snapshot 扩展
阶段 4: 去掉业务分析域的规则回退
```

### 6.3 计划 BOM 域灰度路线

```
阶段 1: BOM 查询类 A 问题 shadow 灰度
阶段 2: BOM 查询类 B 问题扩展
阶段 3: 功率预测参数提取上线（LLM 负责理解，引擎负责计算）
阶段 4: 去掉 BOM 域的规则回退
```

### 6.4 统一灰度门禁

当前 M15 门禁只支持物流的 3 类问题，Phase D 扩展为：

```
Nl2SqlGrayscaleGate:
  enabled_types: set[str]       # SIMPLE_AGGREGATE / DIMENSION_SPLIT / ...
  enabled_domains: set[str]     # logistics / business_analysis / plan_bom
  domain_config: dict[str, set[str]]  # 域粒度的类型开关
```

环境变量改为 `NL2SQL_GRAYSCALE_CONFIG`（JSON 格式），支持域 + 类型联合控制。

### 6.5 最终验收标准

1. 物流 67 个 query_key：NL2SQL 结果与规则模式结果完全一致（行数/字段/排序可比）
2. 产销存 3 个 query_key：同上
3. 计划 BOM A 类问题：NL2SQL 结果与现有 QA 服务结果一致
4. 功率预测：NL 理解部分由 LLM 完成，计算结果由确定性引擎保证
5. 全量回归通过（新增 60+ 测试）
6. 可观测：统一差异率日报每天 9:00 输出

---

## 七、关键风险与控制

| 风险 | 缓解措施 |
|---|---|
| Phase A 重构破坏物流回归 | 不改文件路径 + 类名别名兼容 + 每步独立测试 |
| 产销存 catalog 与现有框架不兼容 | 已设计注册模式适配层 |
| 计划 BOM NL2SQL 无法处理复杂消歧 | BOM 消歧保留下游规则逻辑作为兜底 |
| 功率预测的 NL → 参数提取不可靠 | LLM 提取后加参数校验，失败回退旧链路 |
| 灰度替换后规则回退难以移除 | 先 shadow 1-3 个月，diff 率稳定在 <1% 后移除 |
| 各域 catalog 规模增长过大 | 各域独立 catalog 文件不互相污染 |

---

## 八、分支策略

```
agent/bp-main
  └── feature/nl2sql-domain-extension  (Phase A 基础分支)
       ├── feature/nl2sql-ba-shadow     (Phase B)
       ├── feature/nl2sql-planbom-shadow (Phase C)
       └── feature/nl2sql-grayscale-all  (Phase D)
```

每个 Phase 完成后独立 PR → agent/bp-main。

---

*编制日期：2026-05-22*
*对应 README / AGENTS.md / docs/CURRENT_STATUS.md 约束*
