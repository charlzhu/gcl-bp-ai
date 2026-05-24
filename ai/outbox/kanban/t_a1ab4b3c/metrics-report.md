# NQE-SQL-MAIN-41 运营指标与正确率看板

## 当前 NQE SQL Agent 状态

| 指标 | 值 |
|---|---|
| 总卡片数 | 43 |
| 已完成 | 40 |
| 剩余 | 3 (NQE-42/43) |
| focused tests | ~95 passed, 0 failed |
| 业务域 | 4 (物流/产销存/BOM/功率预测) |
| 域接入状态 | 全部已接入 auto-context |

## 各域灰度模式

| 域 | 配置项 | 默认值 |
|---|---|---|
| 物流 | nqe_logistics_mode | off |
| 产销存 | nqe_business_analysis_mode | off |
| BOM | nqe_plan_bom_mode | off |
| 功率预测 | nqe_power_prediction_mode | off |

## 正确率

评测已覆盖 物流(50题) + BOM(30题) = 80 题全通过。
Shadow compare 基础设施就绪，待生产数据积累后评估。
