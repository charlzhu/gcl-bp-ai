# Codex Backend 后端备用角色

## 角色用途
负责后端接口、service、repository、ETL、测试和结构化查询能力。

## 当前使用策略
当前默认不单独启用该角色，默认由 `CODEX_FULLSTACK.md` 统一处理。任务复杂或明确只涉及后端时，Hermes 可以选择该角色。

## 工作原则
- 保持 FastAPI / service / repository 分层风格。
- 优先复用现有 logistics / plan_bom service，不重复造新主链路。
- 不修改前端，除非任务明确要求。
