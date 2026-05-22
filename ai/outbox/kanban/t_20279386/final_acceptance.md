# NQE-N4 最终验收报告

## 任务摘要

将现有物流 query_key 口径、BOM intent 口径、功率 capability 映射迁移到统一 semantic catalog。

## 交付物

### 代码变更（6 个文件）

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `backend/app/domains/semantic_catalog/schema.py` | 修改 | 新增 `SemanticCapability` Pydantic 模型，支持 query_key/intent/domain_capability 三种能力类型 |
| `backend/app/domains/semantic_catalog/catalog.py` | 修改 | 新增 `register_capability`、`get_capabilities`、`get_capability` 方法和 `_capabilities` 存储 |
| `backend/app/domains/semantic_catalog/loader.py` | 修改 | 新增 `capabilities.yaml` 加载逻辑 |
| `backend/app/domains/semantic_catalog/__init__.py` | 修改 | 导出 `SemanticCapability` |
| `backend/app/config/unified_catalog/capabilities.yaml` | 新建 | 81 个能力注册条目 |
| `tests/unit/semantic_catalog/test_unified_semantic_capabilities.py` | 新建 | 23 个 focused tests |

### 能力注册统计

| 业务域 | 能力类型 | 数量 | 示例 |
|--------|----------|------|------|
| logistics | query_key | 67 | hist_route_pricing_analysis, hist_carrier_kpi_by_year, sys_total_fee_by_filters |
| plan_bom | intent | 11 | single_order_material_specs, bom_version_compare, power_cell_requirement |
| plan_bom | domain_capability | 3 | plan_power_prediction, plan_power_supplier_recommendation, plan_power_factor_effect_compare |
| **合计** | | **81** | |

### 测试结果

- **semantic_catalog 测试**: 115/115 PASSED（92 N1-N3 已有 + 23 N4 新增）
- **单元回归**: 382/382 PASSED
- **业务验收**: 258/260 PASSED（2 个预存失败：test_logistics_carrier_filter_scope.py，不相关）
- **review_result**: PASSED（无 security_concerns，无 logic_errors）

## 验收标准检查

- [x] 物流 67 个 query_key 全部可在统一 catalog 中查询到
- [x] BOM 11 个 intent 全部可在统一 catalog 中查询到
- [x] 功率 3 个 capability 全部可在统一 catalog 中查询到
- [x] 现有路由/执行/边界/前端测试不回退
- [x] 不暴露 SQL、表名、字段名等技术实现细节
- [x] 不替代 NL2SQL，作为辅助能力
- [x] 保留旧接口和回退

## 风险点

- 无。本卡新增内容完全为增量式，不修改任何现有物流/计划 BOM/功率预测主链路。

## 遵循阶段边界

- [x] 不做物管/SAP MID M2
- [x] 不引入 ES
- [x] 不替代 NL2SQL
- [x] 不 push/deploy
- [x] 不触及 data-agent/
