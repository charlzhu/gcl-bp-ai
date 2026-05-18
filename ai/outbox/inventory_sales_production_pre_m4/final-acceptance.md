# 产销存 pre-M4 数据底座验收说明

完成时间：2026-05-18 13:48:35 CST

## 1. 执行边界

本轮按方案 A 执行：继续在独立 worktree 中完成产销存数据底座准备，不切换当前主工作区的 NL2SQL 分支。

- 独立 worktree：`/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai-isp-m3`
- 分支：`feature/inventory-sales-production-m3-query-executor`
- 当前主工作区 `/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai` 未切换分支。
- 本轮未进入 M4 编码，只完成 M4 前置的数据迁移、导入、验证。

## 2. 数据库迁移结果

已在 `.env` 指向的中间库执行 Alembic 迁移：

```text
20260508_0004 -> 20260518_0005
```

当前 Alembic 版本：

```text
20260518_0005 (head)
```

已创建并验证存在的产销存中间表：

```text
ods_ba_isp_excel_workbook
ods_ba_isp_excel_sheet
dim_ba_isp_metric
dim_ba_isp_metric_alias
dwd_ba_isp_monthly_fact
```

## 3. Excel 导入结果

已导入 4 个业务 Excel：

| 年份 | 文件 | 截止月份 | sheet 数 | 月度事实数 | 状态 |
|---:|---|---:|---:|---:|---|
| 2023 | 2023年产量与预算达成率分析.xlsx | 12 | 1 | 295 | created，复跑为 existing |
| 2024 | 经营数据汇总表2024年.xlsx | 12 | 2 | 457 | created，复跑为 existing |
| 2025 | 组件事业部月度产销存-2025年.xlsx | 12 | 1 | 503 | created，复跑为 existing |
| 2026 | 组件事业部月度产销存-2026.04.xlsx | 4 | 1 | 158 | created，复跑为 existing |

入库后事实总数：

```text
1413
```

幂等验证：重复导入同一批文件时，均返回 `existing`，未重复写入事实。

## 4. 数据验证结果

验证通过：

```text
ods_ba_isp_excel_workbook: rows=4
ods_ba_isp_excel_sheet: rows=5
dim_ba_isp_metric: rows=17
dim_ba_isp_metric_alias: rows=11
dwd_ba_isp_monthly_fact: rows=1413
```

年份范围验证通过：

```text
2023: min_month=1, max_month=12, facts=295
2024: min_month=1, max_month=12, facts=457
2025: min_month=1, max_month=12, facts=503
2026: min_month=1, max_month=4, facts=158
```

关键业务口径验证通过：

1. 2023 年按 1-12 月月度事实入库，保留“年度列漏 12 月，需要后端重算”的质量标记。
2. 2023 年 12 月年度预算事实已入库。
3. 2026 年只导入已发布的 1-4 月，5 月及之后没有事实数据。
4. 2026 年 4 月库存/存货事实已按时点指标入库。
5. 2024 年“组件事业部剔除内部交易”已作为默认对外销量口径入库。
6. M3 QueryExecutor 对 2026 年 5 月未发布月份 fail closed，返回 clarification。
7. M3 QueryExecutor 查询库存年度数据时按期末口径取 4 月，不做 1-4 月累计。

## 5. 回归测试

已执行：

```text
tests/business_acceptance/test_inventory_sales_production_m2_fact_import.py
tests/unit/business_analysis/test_inventory_sales_production_m3_query_executor.py
```

结果：

```text
13 passed in 0.80s
```

## 6. 验收材料

已生成：

```text
ai/outbox/inventory_sales_production_pre_m4/alembic-current.log
ai/outbox/inventory_sales_production_pre_m4/import-idempotent.log
ai/outbox/inventory_sales_production_pre_m4/table-status.log
ai/outbox/inventory_sales_production_pre_m4/data-verification.log
ai/outbox/inventory_sales_production_pre_m4/regression-test.log
ai/outbox/inventory_sales_production_pre_m4/git-status.log
ai/outbox/inventory_sales_production_pre_m4/final-acceptance.md
```

敏感信息扫描：验收材料中未发现凭证、私钥、连接串等敏感内容。

## 7. Git 状态

本轮只执行数据库迁移、Excel 导入和验证；未修改业务代码，未切换主工作区分支。

本轮新增的 `ai/outbox/inventory_sales_production_pre_m4/` 为验收材料目录，已做敏感信息扫描，并随产销存 feature 分支提交留痕。

## 8. 是否可以进入 M4

可以。

M4 前置条件已满足：

1. 产销存中间表已建成。
2. 2023-2026 Excel 已导入。
3. 数据条数和关键口径已验证。
4. M2/M3 回归测试通过。
5. QueryExecutor 已可基于中间库执行查询。

下一步可进入：

```text
M4：产销存智能问答入口接入
```

建议 M4 继续保持在独立 `gcl-bp-ai-isp-m3` worktree 中开发，不切换 NL2SQL 主任务分支。
