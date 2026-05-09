# TASK-plan-power-m4-bom-config-resolver 最终验收

## 1. 结论

M4：BOM 配置自动映射已完成。

本轮新增 BOM → 功率模型配置的确定性映射服务，能够从真实 `plan_bom_header` / `plan_bom_material_line` 中提取版型、玻璃、焊带、汇流条、接线盒线缆等信息，并映射到 M3 `PowerPredictionEngine` 支持的 configuration。

终审结论：

```json
{"passed":true,"security_concerns":[],"logic_errors":[],"suggestions":[],"summary":"M4 变更通过终审，前两轮阻塞均已修复且未发现越界或安全问题。"}
```

## 2. 修改文件

```text
backend/app/domains/plan_bom/config/power_aliases.json
backend/app/domains/plan_bom/config/power_bom_mapping.yaml
backend/app/domains/plan_bom/services/power_config_resolver_service.py
tests/business_acceptance/test_plan_power_m4_config_resolver.py
ai/tasks/running/TASK-plan-power-m4-bom-config-resolver/plan.md
ai/tasks/running/TASK-plan-power-m4-bom-config-resolver/diff.patch
ai/tasks/running/TASK-plan-power-m4-bom-config-resolver/m4_combined.diff
ai/tasks/running/TASK-plan-power-m4-bom-config-resolver/test.log
ai/tasks/running/TASK-plan-power-m4-bom-config-resolver/codex_final.md
ai/tasks/running/TASK-plan-power-m4-bom-config-resolver/final-acceptance.md
```

## 3. 核心能力

### 3.1 新增配置文件

```text
backend/app/domains/plan_bom/config/power_aliases.json
backend/app/domains/plan_bom/config/power_bom_mapping.yaml
```

包含：

- 版型别名：`NT12R/66GDF -> NT12R-66GDF` 等。
- 标板别名：`北德 / 新北德 / TÜV北德 / 莱茵 / 计量院`。
- 玻璃映射规则。
- 焊带直径解析规则。
- 汇流条组合解析规则。
- 接线盒线缆长度 + 线径解析规则。
- 默认 `cell_size` / `supplier` / `benchmark` 读取策略。

### 3.2 新增映射服务

```text
PlanBomPowerConfigResolverService
```

位置：

```text
backend/app/domains/plan_bom/services/power_config_resolver_service.py
```

职责：

- 定位唯一 BOM header。
- 多订单 / 多文件命中时返回受控 candidate_required。
- 读取真实核心材料行。
- 从订单名解析功率模型版型。
- 从 BOM 材料解析：
  - `glass`
  - `ribbon`
  - `busbar`
  - `cable`
- 从 active 功率模型读取默认：
  - `cell_size`
  - `supplier`
  - `benchmark`
- 将所有输出二次校验到当前 active 模型有效 option。
- 对无法确认项返回 `unresolved_items`，不瞎猜。
- 输出 `source_lines` / `source_line_ids` / `confidence` / `candidate_options`，支持后续 M5 追问与解释。

### 3.3 Fail-closed 修复

Reviewer 推动并已修复：

1. 玻璃非镀釉规则必须显式出现：
   - `无涂釉`
   - `非镀釉`
   - `非镀膜`
2. 镀釉规则排除否定词，避免“非镀釉”因包含“镀釉”子串而误命中。
3. 接线盒只识别到线长但没有线径时，返回 unresolved，不默认 4mm²。
4. 删除裸线长到 4mm² 的 cable alias。
5. 多候选返回 `candidate_total_count` / `candidate_has_more`，候选列表限制为 `CANDIDATE_LIMIT=20`。
6. 显式 benchmark 输入无效时返回 unresolved，不回退模型默认值。

## 4. 测试结果

### M4 focused

```text
9 passed in 1.50s
```

### M3 回归

```text
9 passed, 2 warnings in 4.24s
```

### M2 回归

```text
9 passed in 3.82s
```

### 全量测试

```text
49 passed, 2 warnings in 9.57s
```

### 其他验证

```text
compileall: 通过
git diff --check: 通过
static_findings=0
reviewer 第 3 轮终审: passed=true
```

## 5. M4 禁止项遵守情况

本轮未做：

```text
未接入 PlanBom QA / NLU / smart-chat
未修改前端
未实现 M5 智能问答链路
未新增数据库迁移
未执行 Excel VBA / 宏
未让 LLM 参与配置猜测或功率数值计算
未 hardcode BOM配置搭配问询.docx 中假订单/假版型/假答案
未破坏 M2/M3 已验收能力
未自动合并 main
未部署生产
```

## 6. 风险与后续

当前 M4 是 service 层能力，尚未接入自然语言问答链路。

后续 M5 可在该服务基础上实现：

```text
用户自然语言提问
-> 槽位识别订单/版型/供应商/目标功率比例
-> 调用 M4 解析 BOM configuration
-> 调用 M3 预测/推荐
-> 输出可解释答案与追问项
```

## 7. 验收结论

M4 已满足当前阶段验收要求，可以提交给用户确认。
