# Review Bundle: TASK-plan-power-factor-effect-compare-fix

## Task scope
用户指出问题：`NT12-66GDF，汇流条6*0.3+4*0.3反光和4 *0.4+4*0.3反光相差多少` 被错误追问订单号。正确业务口径：`NT12-66GDF` 是功率测算版型，应查询当前生效功率测试基准模型中“汇流条”配置项，`6*0.3+4*0.3反光=0.6`，`4*0.4+4*0.3反光=0.3`，差值 `0.3`。

## Changed files in focused patch
backend/app/domains/plan_bom/services/answer_presentation_service.py
backend/app/domains/plan_bom/services/nlu_center_service.py
backend/app/domains/plan_bom/services/qa_service.py
tests/business_acceptance/test_plan_power_docx_question_regression.py

## Known dirty-worktree note
当前仓库已有大量与本任务无关的历史/并行脏改动和未跟踪文件；本审查只覆盖 `diff.patch` 中的计划 BOM 功率问答相关文件，不审查其它 dirty state。

## Implementation summary
- NLU 新增 `plan_power_factor_effect_compare` 受控意图：只有问题同时包含功率版型、差异词、唯一配置项、两个配置选项时才进入该分支。
- QA 新增功率模型配置影响值对比分支：从 active `PlanPowerModelVersion`、对应 `PlanPowerModelSheet` 和 `PlanPowerFactorOption` 查询真实 option effect_value，未命中时 fail-closed 追问，不走 BOM 订单查询。
- 表达层将该意图纳入确定性功率类回答，绕过 LLM 改写数值，并把叙事改为“功率测试基准模型”而非 BOM 订单明细。
- 回归测试覆盖截图问题，验证输出 `0.6`、`0.3`、`0.3`。

## Final verification summary
[
  {
    "name": "focused_regression",
    "exit_code": 0
  },
  {
    "name": "docx_regression_file",
    "exit_code": 0
  },
  {
    "name": "full_business_acceptance",
    "exit_code": 0
  },
  {
    "name": "py_compile_scoped_services",
    "exit_code": 0
  },
  {
    "name": "frontend_build",
    "exit_code": 0
  },
  {
    "name": "diff_check_scoped",
    "exit_code": 0
  }
]

## Static scan
STATIC SCAN: PASS
No added-line findings for hardcoded secrets, shell injection, eval/exec, pickle.loads, or formatted SQL.


## Business smoke output
```text
A OK plan_power_factor_effect_compare
NT12-66GDF 的汇流条功率影响值对比：6*0.3+4*0.3反光 为 0.6W，4*0.4+4*0.3反光 为 0.3W，二者相差 0.3W。
```

## Artifacts
- diff.patch
- test.log
- static-scan.log
- business-smoke.log
- workspace-status.txt
