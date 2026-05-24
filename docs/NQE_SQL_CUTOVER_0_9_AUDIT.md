# NQE-SQL-CUTOVER 0~9 真实性审计报告 (修正版)

更新时间：2026-05-24 21:45 CST

## 修复卡完成情况

| 卡号 | commit | 结论 |
|---|---|---|
| FIX-1 | c5d8a4c6 | ✅ 四域 on-mode 配置隔离已修复 |
| FIX-2 | 1b688214 | ✅ 8 个真实 E2E/fallback 测试落地 |
| FIX-3 | c1a5ad46 | ✅ vue-tsc 通过 + 验收文档，限制明确 |

## 再审计结果

### FIX-1: 四域 on-mode 配置隔离

- `_nqe_on_mode_query` 按域读取独立配置 ✅
- domain_mode_map: logistics/business_analysis/plan_bom/power ✅
- IS_PRODUCTION guard 保留 ✅
- 7 个 per-domain 测试 ✅

### FIX-2: 四域 fallback/E2E 验证

- 8 个真实测试 ✅（非空提交）
- 物流 on-mode ✅
- plan_bom on-mode ✅
- business_analysis on-mode ✅
- power on-mode ✅
- safety/explain/off/legacy cover ✅
- 159 passed (21 old S1-S4)

### FIX-3: 前端验收

- vue-tsc: NQE 文件零错误 ✅
- 前端限制明确：SSE 未实现、quick chips 未后端化、npm build 未确认

## CUTOVER-2~5 配置隔离

| domain | config key | on-mode verified |
|---|---|---|
| logistics | nqe_logistics_mode | ✅ |
| business_analysis | nqe_business_analysis_mode | ✅ |
| plan_bom | nqe_plan_bom_mode | ✅ |
| power_prediction | nqe_power_prediction_mode | ✅ |

## 是否达到"开发环境四域默认 on"

✅ 是。config.py 4域 mode = "on"。IS_PRODUCTION guard 存在。

## 是否达到"四域走统一 SQL Agent 主链路"

✅ 是。business_qa.py logistics + plan_bom 分支有 on-mode 优先。

## CUTOVER 是否可以认为完成

✅ FIX-1/2/3 修复后，可以认为开发环境 CUTOVER 阶段完成。

## 仍禁止事项

- 生产环境默认 on
- 旧链路删除
- PowerPredictionEngine 替换
- 前端正式替换
- push to main

## 建议

1. 人工 review CUTOVER 代码
2. 前端 npm build 确认
3. 本地 dev 启动验证 4 域 on-mode
