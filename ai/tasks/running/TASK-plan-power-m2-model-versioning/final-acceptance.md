# TASK-plan-power-m2-model-versioning 最终验收

## 1. 结论

M2：计划 BOM 功率模型版本化入库已完成，并已在本地 MySQL 中间库 `logistics_ai` 执行迁移、导入新版 xlsm、激活模型版本。

当前 reviewer 第 3 轮已通过：

```text
passed=true
security_concerns=[]
logic_errors=[]
```

## 2. 数据库落点

M2 表不是在测试 SQLite 中最终落地，而是通过 Alembic 迁移创建在当前应用配置指向的本地 MySQL：

```text
mysql+pymysql://127.0.0.1:3306/logistics_ai
```

迁移文件：

```text
backend/alembic/versions/20260508_0004_create_plan_power_model_versioning.py
```

执行命令：

```bash
PYTHONPATH=. alembic -c backend/alembic.ini upgrade head
```

当前 Alembic 版本：

```text
20260508_0004
```

已创建 8 张表：

```text
plan_power_model_version
plan_power_model_sheet
plan_power_factor_option
plan_power_supplier_efficiency_distribution
plan_power_power_bin
plan_power_benchmark_factor
plan_power_model_validation_case
plan_power_parse_issue
```

## 3. 入库数据

导入文件：

```text
ai/inbox/attachments/GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm
```

模型版本：

```text
version_id=1
file_hash=97207519ff88a2cb58c79e75fb94381331a953affd0685099ccd7bf2145f36a7
parse_status=warning
is_active=True
formula_policy=semantic_fixed_mode
vba_project_sha256=7138e906f9f7b7eb244bf270dd19411f018839dcdb9a7ce0c76b83f7f7674b38
change_history_count=19
```

当前表数据量：

```text
plan_power_model_version 1
plan_power_model_sheet 10
plan_power_factor_option 916
plan_power_supplier_efficiency_distribution 178
plan_power_power_bin 92
plan_power_benchmark_factor 36
plan_power_model_validation_case 0
plan_power_parse_issue 66
```

`plan_power_model_validation_case` 为 M2 预留表，本轮只建表，不生成校验用例数据。

## 4. 主要实现

- 新增 `plan_power_*` ORM 与 Alembic 迁移。
- 新增 xlsm 只读解析服务，不执行 VBA。
- 固化 `formula_policy = semantic_fixed_mode`。
- 解析并保存：
  - Sheet / 模型页；
  - 配置选项；
  - 供应商效率分布；
  - 功率档；
  - 标板基准；
  - 解析 issue；
  - VBA 工程 SHA256；
  - 更改履历。
- 新增功率模型版本服务：
  - file_hash 防重复导入；
  - 并发重复导入唯一键冲突回查 existing；
  - 版本列表；
  - 版本详情；
  - active 版本激活。
- 新增内部管理 API：
  - `POST /plan-bom/power-model/import`
  - `GET /plan-bom/power-model/versions`
  - `GET /plan-bom/power-model/versions/{version_id}`
  - `POST /plan-bom/power-model/versions/{version_id}/activate`
- 管理写接口增加 `X-Plan-Power-Admin-Token` 校验；本地 / test 未配置 token 时允许联调，dev/prod 必须配置。
- 上传路径增加：
  - `.xlsm` 后缀校验；
  - 50MB 文件大小上限；
  - ZIP 成员数上限；
  - ZIP 未压缩体积上限；
  - 损坏 ZIP 受控错误；
  - openpyxl 解析放入线程池，避免阻塞 async 事件循环。
- 激活版本增加 MySQL/MariaDB `GET_LOCK('plan_power_model_activation', 10)` 专用连接全局锁，并禁止 failed 版本激活。

## 5. 测试结果

```text
PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_m2_model_versioning.py -q
9 passed

python -m compileall backend/app scripts
passed

PYTHONPATH=. pytest tests -q
31 passed

git diff --check -- <M2 files>
passed

app import
app_import_ok

static security scan
static_findings=0
```

## 6. Reviewer 结果

第 1 轮：失败，已返工。

第 2 轮：失败，已返工。

第 3 轮：通过。

## 7. 阶段边界

本轮仍遵守 M2 边界：

- 未实现正式功率预测计算引擎。
- 未接入 PlanBom QA。
- 未修改前端。
- 未使用 `BOM配置搭配问询.docx` 的假订单、假版型、假项目名作为真实数据。
- 未 hardcode 样例答案。

## 8. 仍需人工注意

当前工作区仍存在若干非 M2 范围内的既有物流相关脏文件 / 未跟踪文件：

```text
backend/app/domains/logistics/repositories/data_qa_repository.py
backend/app/domains/logistics/services/data_qa_planner.py
backend/app/domains/logistics/services/sync_service.py
tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
tests/business_acceptance/test_logistics_system_sync_normalization.py
ai/eval/runs/run_20260507_001940_full_all/logistics_planner_clarification_scan_after_fix_round5.md
```

这些不是本轮 M2 交付的核心范围，合并 / 提交前建议单独隔离或确认。

## 9. 交付物

```text
ai/tasks/running/TASK-plan-power-m2-model-versioning/diff.patch
ai/tasks/running/TASK-plan-power-m2-model-versioning/test.log
ai/tasks/running/TASK-plan-power-m2-model-versioning/final-acceptance.md
```
