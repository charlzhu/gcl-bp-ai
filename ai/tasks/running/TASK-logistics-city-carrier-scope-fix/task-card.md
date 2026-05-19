# TASK-logistics-city-carrier-scope-fix

## 任务来源

用户反馈：在智能问答中询问“2025年常州的物流公司发运多少量？”，页面返回了“2025年总发运量 17374.913MW”，即全国/全年总量，没有保留“常州 + 物流公司”业务范围。

## 当前仓库能力判断

### 已完成能力

1. 历史物流发运量 `hist_mw_summary` 已支持年份、月份、客户、区域、始发地、承运商、运输方式等单值过滤。
2. 承运商/物流公司年度 KPI `hist_carrier_kpi_by_year` 已支持按承运商分组，并已支持区域 `region_name` 范围过滤。
3. 区域拆分题已具备回归测试，避免“各区域”退化为总量。

### 未完成能力 / 本次缺陷

1. 问句中的“常州的物流公司”未被识别为城市范围 + 承运商分组。
2. “发运多少量”虽属于 MW 发运量口径，但承运商 KPI 判定的兜底正则未覆盖“多少量”口语问法。
3. 承运商 KPI 仓储接口暂不支持 `city` 下推，导致即使命中承运商分组也会丢失城市范围。

## 任务类型

缺陷修复 + 通用 NLU 槽位增强 + TDD 回归。

## 验收标准

1. `2025年常州的物流公司发运多少量？` 必须命中 `hist_carrier_kpi_by_year`，维度为 `carrier_name`，过滤条件包含 `year=2025` 和 `city=常州`。
2. 同类问法如 `2025年苏州的承运商发货量分别是多少？` 必须同样下推城市过滤，不允许 hardcode 常州。
3. 服务层调用仓储时必须透传 city，仓储 SQL 的分子和分母都必须应用 city 过滤，避免占比按全国总量计算。
4. 页面/API 结果应按物流公司/承运商明细展示，不返回单行“总发运量”。
5. 不修改 main，不 commit/push/deploy；不触碰 .env、密钥、生产配置。

## 允许修改范围

- `backend/app/domains/logistics/services/data_qa_planner.py`
- `backend/app/domains/logistics/repositories/data_qa_repository.py`
- `backend/app/domains/logistics/services/data_qa_service.py`
- 新增或修改物流业务验收测试文件
- 本任务目录下验收材料

## 禁止修改范围

- 不改前端 UI。
- 不改数据库结构/迁移。
- 不改计划 BOM / 功率模块。
- 不做任务外大范围重构。

## 工作流

1. RED：先补 planner/service/repository 级回归测试并确认失败。
2. GREEN：由 Codex 作为工程执行者修复通用城市+物流公司问法。
3. 验证：focused/full/API/browser 可行验证 + 静态扫描 + 独立 review。
4. 交付：生成 `diff.patch`、`test.log`、`final-acceptance.md`。

创建时间：2026-05-12T09:50:29
