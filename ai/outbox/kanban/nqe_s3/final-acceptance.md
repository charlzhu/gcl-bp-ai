# NQE-S3: NL2SQL 结果与旧链路 shadow compare — 最终验收

## 任务概述

在 `backend/app/domains/business_qa_graph/` 下建立统一 shadow compare 平台，
对比 NL2SQL 执行结果与旧规则链路执行结果，记录差异到 JSONL 文件。

## 交付物

### 新增文件
1. `backend/app/domains/business_qa_graph/services/shadow_compare.py`
   — ShadowCompareService：签名提取、对比、JSONL 写入
2. `backend/app/domains/business_qa_graph/nodes/shadow_compare_node.py`
   — shadow_compare_node：Graph 节点，编排 NL2SQL vs 旧链路对比
3. `tests/unit/business_qa_graph/test_nqe_s3_shadow_compare.py`
   — 19 focused tests

### 修改文件
4. `backend/app/domains/business_qa_graph/schemas/state.py`
   — 新增 `nl2sql_result`、`shadow_comparison` 字段 + 初始值
5. `backend/app/domains/business_qa_graph/nl2sql_adapter.py`
   — 新增 `build_full_result()` 方法 + 辅助方法
6. `backend/app/domains/business_qa_graph/builder.py`
   — 新增 shadow_compare_node 节点 + 路由逻辑

## 测试结果

| 测试集 | 数量 | 结果 |
|---|---|---|
| NQE-S3 focused | 19 | 19 PASS |
| NQE-S1 回归 | 12 | 12 PASS |
| NQE-S2 回归 | 15 | 15 PASS |
| **合计** | **46** | **46 PASS** |

完整 business_qa_graph 套件：141 PASS / 8 pre-existing failures（LQG 配置问题，非本卡引入）

## 验收标准检查

- [x] shadow compare 节点可记录 NL2SQL 和旧链路的结果差异
- [x] 差异报告不泄露技术信息（SQL/表名/字段名）
- [x] 现有测试不回归（NQE-S1 12/12、NQE-S2 15/15）
- [x] fail-closed：NL2SQL 链路异常不阻断正常返回
- [x] 仅物流域执行对比（plan_bom/unknown 域跳过）
- [x] JSONL 写入失败不抛异常
- [x] DB 连接在查询完成后显式关闭

## 独立 Review

- reviewer: delegate_task subagent
- verdict: **passed**
- security_concerns: none
- logic_errors: none
- suggestions: 3（DB leak 已修复，另 2 个为 nice-to-have）
