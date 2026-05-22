# LQG-2 最终验收报告

## 一、修改文件清单

### 新增文件（LQG-1 骨架未含，LQG-2 新增或大幅修改）
1. `backend/app/domains/business_qa_graph/schemas/domain.py`
   - 新增：BusinessQaDomainDefinition、BusinessQaCapabilityDefinition、BusinessQaDomainRouteResult、BusinessQaDomainRouteCandidate、BusinessQaRoutableDomainId、BusinessQaCapabilityId、BusinessQaNormalizedDomainHint
   - 所有 Pydantic model 使用 extra='forbid'

2. `backend/app/domains/business_qa_graph/schemas/state.py`
   - 扩展：BusinessQaGraphState 新增 domain、capabilities、domain_route、execution_mode
   - build_business_qa_initial_state 默认 domain="unknown"、capabilities=[]、domain_route={}

3. `backend/app/domains/business_qa_graph/domain_registry.py`
   - **核心文件**：BusinessQaDomainRegistry 类
   - 支持 domain_hint: auto/logistics/plan_bom → 别名映射闭环
   - 自动识别: logistics/plan_bom/unknown
   - capability: logistics_data_qa、plan_bom_qa、plan_power_prediction、plan_power_supplier_recommendation、plan_power_factor_effect_compare
   - 功率关键词**已移除单字符 "w"**
   - 新增 `_POWER_UNIT_PATTERN = re.compile(r"\d+(?:\.\d+)?(?:w|瓦)")`
   - 新增 `_has_power_signal` 方法：先关键词匹配，再正则匹配
   - _detect_domain 正确引用 question 参数，无 undefined 变量

4. `backend/app/domains/business_qa_graph/nodes/domain_route_node.py`
   - 新节点：调用 registry.route()，写入 state，构造 trace event
   - 不执行查数、不计算事实、不调用 NL2SQL

5. `backend/app/domains/business_qa_graph/builder.py`
   - Graph 从 START→receive→END 扩展为 START→receive→domain_route→END

6. `tests/unit/business_qa_graph/test_business_qa_graph_skeleton.py`
   - 16 个测试，包括：
     - domain_registry 声明验证
     - 物流/BOM/功率预测/功率供应商推荐/功率影响值对比路由
     - 数字+W 功率路由（新）
     - 普通英文 w 不误路由（新）
     - WMS 不误路由（新）
     - unknown → CLARIFY + 候选域
     - domain_route_node 写入 state 和 trace
     - graph 完整链路验证
     - runner disabled 桩验证

## 二、核心改动说明
1. 统一领域路由：物流、计划 BOM、unknown 在三态模糊时 fail-closed 拒绝硬路由
2. 功率能力强信号绑定：数字+W/瓦 或 中文功率语义词 → 自动归 plan_bom + power capability
3. guard 保护：英文 w、WMS 等非功率缩写不会误路由到 plan_bom

## 三、测试方法
```bash
# focused tests
pytest tests/unit/business_qa_graph/test_business_qa_graph_skeleton.py -v

# 相邻回归
pytest tests/unit/logistics/query_planner_v2/test_logistics_query_planner_v2.py -q
pytest tests/business_acceptance/test_plan_bom_qa_multi_candidate_compare.py -q

# compile
python -m compileall backend/app/domains/business_qa_graph tests/unit/business_qa_graph -q
```

## 四、风险点
1. 功率关键词中 "电池片" 同时出现在 _POWER_KEYWORDS（领域提升）和 _POWER_SUPPLIER_RECOMMEND_KEYWORDS（能力选择），当前 capability selection 正确短回路但值得留意
2. 语义路由只使用确定性关键词启发式，不调用 LLM；如果后续要增加 LLM 候选路由，必须经过 validate_node 校验

## 五、当前仍未解决的问题
- LQG-2 不解决执行、不解决查询效率、不解决表达问题；这些后续卡继续做
- LQG-2 的域 registry 尚不支持配置化加载（hardcoded keywords），后续语义资产阶段再改进

## 六、是否影响现有 BOM / 物流 / 功率预测能力
**不影响**。graph 默认 disabled，新旧接口均不受干扰。

## 七、是否遵守本轮阶段边界
是。不做物管/SAP MID M2，不引 ES，不替代 NL2SQL，不自由 SQL。

## 八、是否未自动 commit / push / deploy
是。
