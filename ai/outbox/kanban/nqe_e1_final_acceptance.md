# NQE-E1 统一业务问法评测集 Schema -- 最终验收材料

## 任务概述

- **任务 ID**: t_2c26f1f7
- **任务名称**: NQE-E1：统一业务问法评测集 schema
- **分支**: feature/nqe-eval
- **工作区**: /Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai-nqe-eval

## 交付物清单

| 文件 | 说明 | 状态 |
|------|------|------|
| backend/app/domains/qa_evaluation/__init__.py | 模块初始化 + __all__ 导出 | 新增 |
| backend/app/domains/qa_evaluation/schema.py | 核心 Schema 定义（EvaluationCase/EvaluationSuite/EvaluationResult/EvaluationReport） | 新增 |
| tests/unit/qa_evaluation/test_evaluation_schema.py | Focused tests (32 个) | 新增 |
| ai/outbox/kanban/nqe_e1_diff.patch | 完整变更 diff | 生成 |
| ai/outbox/kanban/nqe_e1_test.log | 测试运行日志 | 生成 |

## 测试结果

- **Focused tests**: 35/35 passed
- **Adjacent regression (semantic_catalog)**: 108/115 passed (7 个预存失败，与本次无关)
- **Adjacent regression (query_planning)**: 44/44 passed
- **Compile/syntax check**: 通过
- **Independent review**: PASSED (3 suggestions all addressed)

## Schema 定义说明

### EvaluationCase（评测用例）
- question (必填)：用户自然语言问题
- domain (必填)：物流/logistics, 计划BOM/plan_bom, 功率预测/power_prediction, 经营分析/business_analysis
- expected_status (必填)：success/clarification/unsupported/empty_result/error
- expected_text (可选)：预期回答核心文本
- expected_row_count (可选)：预期结果行数
- caliber (可选)：业务口径说明
- tags (可选)：分类标签
- allow_empty_substitute (默认 True)：空结果回填开关
- case_id (自动生成 UUID)

### EvaluationSuite（评测套件）
- name (必填)：套件名称
- domain (必填)：所属业务域
- cases (默认 [])：评测用例列表
- description (可选)：套件描述

### EvaluationResult（评测结果）
- case_id (必填)：关联用例标识
- matched_status (默认 False)：状态是否匹配
- key_numbers_match (可选)：关键数字是否匹配
- text_similarity (可选，0.0~1.0)：文本相似度
- leak_found (默认 False)：是否技术泄露
- actual_status (可选)：实际回答状态
- actual_answer_summary (可选)：实际回答摘要
- actual_row_count (可选)：实际返回行数
- mismatch_detail (可选)：差异说明

### EvaluationReport（评测报告）
- suite_name (必填)：套件名称
- total_cases/passed_cases/failed_cases (必填)
- pass_rate (计算属性)：通过率
- 一致性校验：passed + failed == total

## 影响分析

- **不影响现有业务能力**：新增 schema 仅定义数据结构，不修改现有 logistics/plan_bom/power_prediction 链路
- **不修改现有 shared workspace**：仅新增 backend/app/domains/qa_evaluation/ 目录
- **不触及 data-agent/**：完全在独立域内工作

## 验收确认

- [x] 评测集 schema 可存储物流、BOM、功率的标准问题及预期结果
- [x] 新增 focused tests (32 个)
- [x] 不影响现有业务能力
- [x] 中文注释完整
- [x] 编译/语法检查通过
- [x] 静态安全扫描通过
- [x] 相邻回归通过（排除预存失败）
