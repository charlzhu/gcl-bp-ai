本目录是“协鑫集成经营计划部智能平台”的前端子项目。
对应后端子项目在 ../backend。
整体项目状态与交接说明请先阅读 ../AGENTS.md 和 ../docs/HANDOFF.md。


# 前端查询页第二版优化（基于当前后端接口）

## 一、版本目标

本版本在第一版基础上，重点增强：

1. 结果表格增强
2. 明细视图
3. 查询历史

适用于物流一期当前阶段的前后端联调、小范围业务试用和结果核对。

## 二、页面说明

### 1. 自然语言查询页
- 输入问题
- 查看 parsed
- 查看 query_result
- 打开完整明细页
- 导出当前结果 JSON

### 2. 条件查询页
- 按指标、来源范围、月份、物流公司、区域、运输方式查询
- 打开完整明细页
- 导出当前结果 JSON

### 3. 明细视图页
- 查看最近一次查询的完整 items
- 查看选中行详情
- 查看 summary
- 查看原始响应

### 4. 查询历史页
- 查看已落库查询记录
- 查看单条查询详情
- 如果后端未开放查询历史接口，会显示友好提示

### 5. 任务与日志页
- 查看历史导入任务
- 查看系统同步任务
- 保留原始响应折叠面板

## 三、启动方式

```bash
npm install
cp .env.example .env.local
npm run dev
```

## 四、后端接口

### 已直接对接
- `POST /api/v1/logistics/nl2query/parse-and-query`
- `POST /api/v1/logistics/query-service/aggregate`
- `GET /api/v1/logistics/data/hist/import/tasks`
- `GET /api/v1/logistics/data/sys/sync/tasks`

### 可选对接
- `GET /api/v1/sys/query/log`

> 如果你的查询历史接口路径不同，只需要修改 `src/api/logistics.ts` 中的 `fetchQueryHistory()`。

## 五、后续建议

下一版建议继续做：
1. 图表增强
2. Excel 导出
3. 对比结果专用展示
4. 登录与权限
5. 领导演示页
