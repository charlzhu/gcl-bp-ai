# NQE-E2 最终验收报告

## 任务概述

NQE-E2：物流问法评测集接入 Graph。

目标：让 Graph 可自动运行物流评测集并生成报告。

## 交付物

| 文件 | 说明 |
|------|------|
| `backend/app/domains/qa_evaluation/eval_runner.py` | EvalGraphRunner 评测运行器（476 行） |
| `backend/app/domains/qa_evaluation/__init__.py` | 更新导出 EvalGraphRunner |
| `tests/unit/qa_evaluation/test_eval_runner.py` | EvalGraphRunner focused tests（17 条） |
| `tests/evaluation/logistics/samples.py` | 物流首批评测样例（10 条 case） |
| `tests/evaluation/logistics/__init__.py` | 包初始化 |
| `tests/evaluation/__init__.py` | 包初始化 |
| `ai/outbox/kanban/nqe_e2_diff.patch` | 代码变更 diff |
| `ai/outbox/kanban/nqe_e2_test.log` | 测试运行日志 |
| `ai/outbox/kanban/nqe_e2_review_result.json` | 独立 review 结果 |

## 测试结果

| 测试集 | 用例数 | 结果 |
|--------|--------|------|
| NQE-E2 focused tests | 17 | PASSED |
| NQE-E1 schema 回归 | 35 | PASSED |
| query_planning 回归 | 14 | PASSED |
| **合计** | **66** | **全部通过** |

## Review 结果

独立 review：**PASSED**
- 无安全风险
- 无逻辑错误
- 3 条非阻塞建议

## 核心功能

1. **EvalGraphRunner**：遍历评测套件，调用 GraphRunner，生成 EvaluationResult 和 EvaluationReport
2. **状态匹配**：支持 success/clarification/unsupported/empty_result/error 五种状态匹配
3. **行数校验**：预期行数与实际行数对比
4. **文本匹配**：预期文本子串匹配，计算 0.0~1.0 相似度
5. **技术泄露检测**：黑名单关键词扫描（SQL/表名/字段名/query_key 等）
6. **JSONL 输出**：评测结果持久化
7. **异常兜底**：GraphRunner 异常不中断评测流程
8. **物流样例集**：10 条样例覆盖聚合/运价/承运商/澄清/不支持五类场景

## 边界合规

- [x] 不改变现有 GraphRunner 行为
- [x] 不暴露 SQL/表名/字段名等内部技术细节
- [x] 评测用例独立可序列化
- [x] 中文注释已覆盖所有新增代码
- [x] 不触碰 material_management/SAP MID
- [x] 不替代 NL2SQL/LangGraph 已有能力
- [x] 不引入 LLM 自由 SQL
- [x] 保留旧接口和回退
