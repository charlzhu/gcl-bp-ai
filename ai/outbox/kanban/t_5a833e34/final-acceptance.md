# NQE-SQL-MAIN-16 最终验收

## 验收结论

通过。NQE-SQL-MAIN-16：物流正式链路灰度切换基础能力已完成。

## 测试结果：53 passed, 0 failed

## 模式实现状态

| 模式 | 配置值 | 状态 | 说明 |
|---|---|---|---|
| off | `"off"` | ✅ 已完成 | 默认模式，完全走旧物流链路 |
| shadow | `"shadow"` | ✅ 已完成 | NQE 后台执行，记录 shadow compare |
| assist | `"assist"` | 🔧 接口预留 | 本卡未实现具体行为，后继卡负责 |
| on | `"on"` | 🔧 接口预留 | 本卡未实现具体行为，后继卡负责 |

**默认值**：`nqe_logistics_mode = "off"`

## 已实现的测试覆盖

| 测试 | 覆盖模式 |
|---|---|
| off 是默认值 | off |
| off 模式下不调用 NQE | off |
| shadow 模式允许 NQE 后台执行 | shadow |
| NQE Graph 执行返回结构化结果 | shadow/on |
| shadow compare 记录包含双方摘要 | shadow |
| NQE 错误不影响 shadow compare | shadow |
| 旧链路未被替换 | 所有 |
| 物管状态文件未触碰 | 所有 |

## 接口预留（本卡未完成）

- assist 模式：配置项和 `get_nqe_logistics_mode()` 已支持读取 "assist"，但 `_nqe_shadow_attach` 中 assist 行为与 shadow 相同
- on 模式：配置项和 `get_nqe_logistics_mode()` 已支持读取 "on"，但本卡未将 NQE 提升为主链路

NQE-SQL-MAIN-17 将负责更完整的 fallback 与 shadow compare 策略。

## 边界确认

- 默认 off，不影响生产
- 旧 LogisticsDataQaService 未删除
- NQE shadow 异常不中断用户响应
- 未 commit / push
