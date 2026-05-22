# M12-3 物流 NL2SQL QA Sidecar 设计文档

## 一、概述

本文档定义"物流正式 QA 请求旁路运行 NL2SQL shadow"的 QA Sidecar 架构方案。
当前已有 `live_shadow_adapter.py` 的 MVP 实现（`LogisticsNl2SqlLiveShadowAdapter`），
本文档规划该适配器如何接入正式物流 QA 请求的旁路，以及接入后的运行模型。

## 二、当前状态

### 已有实现

| 模块 | 文件 | 状态 |
|------|------|------|
| Live Shadow Adapter | `live_shadow_adapter.py` | ✅ MVP 实现完成 |
| 脱敏摘要模型 | `LogisticsNl2SqlLiveShadowSummary` | ✅ 已实现 |
| 正式 QA 结果模型 | `LogisticsDataQaResult` (在 schemas/) | ✅ 已实现 |
| 环境开关 | `LOGISTICS_NL2SQL_LIVE_SHADOW_ENABLED` | ✅ 已有 |
| Shadow Pipeline | `shadow_pipeline.py` | ✅ 已实现 |
| M9+ 全链路 | M9→M10→M11 | ✅ 已实现 |

### 缺失环节

| 环节 | 状态 | 说明 |
|------|------|------|
| 正式 QA Service 中调用 Sidecar | ❌ 未接入 | `LogisticsDataQaService` 还未调用 adapter |
| 前端旁路结果展示 | ❌ 未接入 | 用户看不到 NL2SQL shadow 对比 |
| 多请求并发 shadow | ❌ 未设计 | 当前 adapter 是同步调用 |
| shadow 结果对比阈值 | ❌ 未设计 | 多少差异算可接受 |
| shadow 结果 logging 与告警 | ❌ 未设计 | 没有旁路失败告警 |

## 三、架构方案

### 3.1 Sidecar 调用点

```
[用户请求]
    ↓
[BusinessChatPage (前端)]
    ↓
[BusinessAnswerStreamService]
    ↓
[LogisticsDataQaService.get_qa_result()]  ← 接入点
    ├──→ [现有物流 QA 主链路]  → 业务结果
    └──→ [NL2SQL Live Shadow Adapter]  → shadow 摘要 (并行走)
            ↓
        [response_meta 附加 shadow 摘要]
```

### 3.2 调用方式

```python
class LogisticsDataQaService:
    async def get_qa_result(self, request):
        # 1. 正式物流 QA 主链路（非 NL2SQL）
        formal_result = await self._run_formal_qa(request)
        
        # 2. 旁路 NL2SQL shadow（默认关闭，flaky 不影响正式链路）
        shadow_summary = None
        if self.live_shadow_enabled:
            try:
                shadow = LogisticsNl2SqlLiveShadowAdapter()
                shadow_summary = shadow.run(
                    question=request.question,
                    user_params=request.params,
                    trace_id=request.trace_id,
                )
            except Exception:
                pass  # shadow 失败不影响正式回答
        
        # 3. 附加 shadow 摘要
        formal_result.response_meta["nl2sql_shadow"] = (
            shadow_summary.model_dump(mode="json") if shadow_summary else None
        )
        return formal_result
```

### 3.3 安全边界

1. **默认关闭**：环境变量 `LOGISTICS_NL2SQL_LIVE_SHADOW_ENABLED` 必须显式设为 `true` 才生效
2. **失败不传递**：adapter 抛出任何异常都不影响正式链路
3. **脱敏摘要**：`LogisticsNl2SqlLiveShadowSummary` 已确保字段白名单、hash、枚举校验
4. **不暴露 SQL**：`response_meta` 不包含 SQL 原文、参数值、表名、字段名
5. **超时保护**：adapter 使用 `execute_timeout`（M11-4）确保不超过 5 秒

## 四、后续阶段规划

### M13：QA Sidecar 接入 MVP

**目标**：将 `LogisticsNl2SqlLiveShadowAdapter` 接入 `LogisticsDataQaService`，实现正式 QA 旁路 shadow。

**范围**：
1. 在 `LogisticsDataQaService.get_qa_result()` 中注入 adapter 调用
2. 环境开关控制，默认关闭
3. shadow 摘要附加到 `response_meta`
4. focused 测试验证：开启/关闭/异常/超时
5. 全量回归

**不做**：
- 不在前端展示 shadow 对比
- 不在 shadow 失败时发告警
- 不在正式回答被替换

### M14：Shadow 结果对比与告警

**目标**：建立正式 QA 结果与 NL2SQL shadow 结果的结构化对比。

**范围**：
1. 对比字段：status/row_count/stage/error_codes/指标摘要
2. 差异阈值定义
3. 差异时旁路日志告警
4. 差异率统计报表

### M15：灰度接管

**目标**：在 shadow 稳定后，对低风险问题类型逐步灰度切换。

**范围**：
1. 风险分类：简单 aggregate / 按维度拆分 / 多指标汇总
2. 灰度开关：每类问题独立开关
3. 旧链路兜底
4. A/B 对比报表

## 五、风险与约束

| 风险 | 影响 | 缓解措施 |
|------|------|----------|
| live provider 故障导致 shadow 超时 | 延迟正式回答（当前 adapter 同步） | 设置严格超时 + 异步化（M14） |
| shadow 结果被误认为是正式回答 | 用户混淆 | `response_meta` 不进入前端显示 |
| NL2SQL 结果与正式结果差异大 | 业务困惑 | 只旁路记录，不展示；M14 加差异分析 |
| live provider token 消耗 | 额外成本 | 按比例采样；默认只 shadow 10% 请求 |
| 正式 QA 升级导致 adapter 失效 | shadow 静默停止 | 单元测试 + CI gate 覆盖 adapter |

## 六、验收标准（M13）

1. `LogisticsDataQaService.get_qa_result()` 在 shadow 开启时附加脱敏摘要
2. shadow 关闭时不附加任何内容
3. shadow 任何异常不中断正式回答
4. shadow 超时（>5s）不阻塞正式回答
5. `response_meta["nl2sql_shadow"]` 不包含 SQL/表名/字段名/参数值
6. 全量 NL2SQL 回归 318+ passed
7. 物流正式 QA 回归通过
