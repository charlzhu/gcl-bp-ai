# NQE-N3：多候选消歧统一交互 — 验收报告

## 任务目标
建立统一的多候选消歧流程，让用户选择订单/BOM文件/客户实例/承运商等实体时前端+后端流程统一。

## 交付内容

### 1. 新建模块：`backend/app/domains/semantic_catalog/disambiguation/`

| 文件 | 说明 |
|------|------|
| `__init__.py` | 模块入口，导出所有公开符号 |
| `schema.py` | 5个Schema：DisambiguationCandidate, Request, Response, ResolveRequest, ResolveResponse |
| `service.py` | DisambiguationService：生成业务追问 + 解析用户选择 + DisambiguationError |

### 2. 新增 API 端点：`POST /api/v1/disambiguation/resolve`

- 文件：`backend/app/domains/semantic_catalog/api.py`
- 路由注册：`backend/app/api/router.py`

### 3. 测试：`tests/unit/semantic_catalog/test_disambiguation.py`

- 29 个 focused tests（Schema + Service + Business Rules + API 完整性）
- 92 total semantic_catalog tests (29 new + 63 existing) — 全部通过

## 测试结果

```
tests/unit/semantic_catalog/ — 92 passed in 0.31s
tests/ (full suite) — 621 passed, 2 pre-existing failures (unrelated logistics)
```

## 验收标准检查

- [x] 多候选时不确定不执行查询（needs_selection 状态）
- [x] 用户选择后正确路由到领域服务（resolved 状态 + resolved_candidate）
- [x] 现有多候选消歧测试不回退（89→92，无退步）
- [x] 不暴露 SQL/表名/字段名/query_key 等技术内容
- [x] 不做物管/SAP MID M2
- [x] 不引入 ES
- [x] 不替代 NL2SQL
- [x] 不触碰 data-agent/
- [x] 未 push/deploy
- [x] 中文注释完整

## 独立 Review 结果

- **passed**: true
- **security_concerns**: 0
- **logic_errors**: 0
- **suggestions**: 3（非阻塞，已记录）

## 修改文件清单

1. `backend/app/api/router.py` — 注册 semantic_catalog 路由
2. `backend/app/domains/semantic_catalog/__init__.py` — 导出 disambiguation 模块
3. `backend/app/domains/semantic_catalog/api.py` — 新增 POST /disambiguation/resolve
4. `backend/app/domains/semantic_catalog/disambiguation/__init__.py` — 新增
5. `backend/app/domains/semantic_catalog/disambiguation/schema.py` — 新增
6. `backend/app/domains/semantic_catalog/disambiguation/service.py` — 新增
7. `tests/unit/semantic_catalog/test_disambiguation.py` — 新增

## 后续工作（不在本卡范围）

- 前端在 BusinessChatPage 中消费 needs_selection 状态的应答，展示候选列表
- 服务端会话级候选存储（当前 MVP 由前端随请求传入）
- 接入现有的承运商/订单/客户解析器的多候选返回
