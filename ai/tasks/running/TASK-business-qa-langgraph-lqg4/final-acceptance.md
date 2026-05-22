# LQG-4 验收报告：统一 plan validate / clarify / unsupported / no_answer 分支

## 任务概要

建立 LangGraph 统一安全校验和边界状态分支，把非执行路径（clarify/unsupported/error/no_answer）做稳。

## 修改文件清单

### 新增文件（5 个）
| 文件 | 说明 |
|------|------|
| `backend/app/domains/business_qa_graph/schemas/policy.py` | 安全校验策略定义：PlanValidationResult、白名单规则、技术泄露检测、安全危险检测、必填槽位映射 |
| `backend/app/domains/business_qa_graph/nodes/plan_validate_node.py` | 统一校验门：对 shadow_plan_raw 执行策略校验，决定后续路由（ok/clarify/unsupported/error） |
| `backend/app/domains/business_qa_graph/nodes/clarify_node.py` | 业务化追问节点：生成用户可见追问消息，不泄露技术标识 |
| `backend/app/domains/business_qa_graph/nodes/unsupported_node.py` | 业务化拒答节点：生成用户可见拒答，含输出 sanitization |
| `backend/app/domains/business_qa_graph/nodes/error_node.py` | 异常处理节点：安全降级，通用错误消息不暴露内部详情 |
| `tests/unit/business_qa_graph/test_lqg4_plan_validate.py` | LQG-4 focused tests（22 个用例） |

### 修改文件（5 个）
| 文件 | 变更 |
|------|------|
| `backend/app/domains/business_qa_graph/schemas/state.py` | 新增 validation_result/validation_details/user_visible_message 字段、ERROR 状态 |
| `backend/app/domains/business_qa_graph/schemas/response.py` | status 追加 ERROR |
| `backend/app/domains/business_qa_graph/builder.py` | 插入 plan_validate 节点 + 条件路由（ok→plan_build、clarify→clarify、unsupported→unsupported、error→error_handler） |
| `backend/app/domains/business_qa_graph/nodes/__init__.py` | 导出新节点 |
| `tests/unit/business_qa_graph/test_business_qa_graph_skeleton.py` | 适配 LQG-4 新的 trace 结构 |

## 测试结果

```
tests/unit/business_qa_graph/ — 51 passed in 1.46s
  - LQG-1/2 skeleton tests: 16/16 ✓
  - LQG-3 graph understanding tests: 13/13 ✓
  - LQG-4 plan validate tests: 22/22 ✓
```

## 验收标准达成

| 标准 | 状态 |
|------|------|
| "查一下这个订单" → 业务化追问 | ✓ clarify_node 生成不含技术标识的追问 |
| "用 SQL 查物流表" → 不执行 SQL、不暴露技术链路 | ✓ plan_validate 检测 tech leak 并路由 unsupported；unsupported_node sanitize 输出 |
| unsupported 不变成成功 | ✓ unsupported_node 强制 status=UNSUPPORTED，永远不会是 success class |
| 物流/BOM clarification 与 unsupported 测试不回归 | ✓ LQG-2/3 全量测试通过 |

## 架构设计

Graph 流程（LQG-4）：
```
START → receive → domain_route → question_understanding → plan_validate
                                                              ↓ (conditional)
                                    ┌─────────────────────────┼──────────────────────┐
                                    ↓                         ↓                      ↓
                              plan_build → END          clarify → END         unsupported → END
                              (ok 通过)                 (缺少信息追问)         (拒答)

                                                              ↓
                                                         error_handler → END
                                                         (安全降级)
```

## 安全边界

- plan_validate_node：对用户原始 question 做 tech leak / safety danger 检测（最高优先级）
- unsupported_node：输出 sanitization 确保用户可见消息不含 SQL/表名/字段名/query_key 等
- clarify_node：追问只使用业务化表述
- error_node：用户可见消息始终为通用降级文案，内部错误详情仅写入 audit trace

## 静态检查

```
Python compile: 5/5 new files OK
```

## 未解决问题

无。

## 是否影响现有能力

- 物流问答：不受影响（LQG-2 domain registry 测试全通过）
- 计划 BOM 问答：不受影响（LQG-2 domain registry 测试全通过）
- LQG-3 graph understanding：适配通过
- 前端：不受影响（本卡只涉及后端 Graph 编排）

## 是否遵守阶段边界

- ✓ 只做外层编排（LangGraph）
- ✓ 不替代 NL2SQL / QueryPlanningV2 / SQLPlan
- ✓ 不做物管 / SAP MID M2
- ✓ 不引入 ES
- ✓ 禁止 LLM 自由 SQL / 查数 / 算功率
- ✓ 保留旧接口和回归路径
- ✓ 未 push / deploy / reset / clean / rebase
