# 四域旧链路下线评估报告

NQE-SQL-MAIN-42：仅评估，不执行下线。

## 结论：不建议立即下线任何旧链路

## 各域评估

### 物流

- 旧链路：LogisticsDataQaService
- NQE 替代：NQE SQL Agent + gray mode (off→shadow)
- 保留理由：物流 903 题语义回归未在 NQE 上全量验证
- 建议：保留至少到 shadow 模式稳定运行 3 个月

### 产销存

- 旧链路：BusinessQaStream 中的 business_analysis 分支
- NQE 替代：NQE SQL Agent + auto-context
- 保留理由：测评样本仅基础验证
- 建议：保留

### BOM

- 旧链路：PlanBomQaService + candidate/compare/replay
- NQE 替代：NQE adapter 非侵入式包装
- 保留理由：BOM 候选消歧、compare/replay 是核心生产逻辑
- 建议：保留，NQE 只做辅助

### 功率预测

- 旧链路：PowerPredictionEngine
- NQE 替代：NQE PowerPredictionEngine fallback adapter
- 保留理由：功率预测公式不可替代
- 建议：**永不替换**

## 风险清单

| 风险 | 等级 |
|---|---|
| 评测覆盖不足 | 中 |
| 生产 shadow compare 数据不足 | 高 |
| 无生产 on 模式运营经验 | 高 |
| PowerPredictionEngine 不可替代 | 极端 |

## 回滚方案

所有 NQE 接入均为非侵入式（adapter/fallback/off-default）。
回滚只需将各域 mode 保持 off 即可。
