# TASK-backend-startup-scroll-fix 最终验收

## 用户问题

1. 后端 `run.py` 启动时出现：
   - IDE 调试器 `Connected to: <socket.socket ...>` 提示重复出现；
   - Pydantic warning：`Field "model_sheet_count" in PowerModelVersionSummary has conflict with protected namespace "model_"`。
2. BOM 数据管理页面无滚动条，下面数据无法查看。

## 根因分析

### 1. Pydantic warning

`PowerModelVersionSummary` 中存在业务字段 `model_sheet_count`。Pydantic v2 默认将 `model_` 作为保护命名空间，因此启动加载 schema 时会输出 warning。

### 2. `Connected to: <socket.socket ...>` 重复提示

该提示来自 IDE 调试器连接 Python 进程，不是业务代码主动打印。当前 `run.py` 在 `APP_DEBUG=true` 时启用 uvicorn reload；调试器附加时，reload 会产生 reloader/worker 多进程，IDE 可能对多个进程分别输出连接提示。

处理原则：不能直接控制 IDE 自身日志，但可以在检测到调试器附加时关闭 uvicorn reload，减少重复派生和重复连接提示；普通非调试运行仍保留 `APP_DEBUG` 热重载行为。

### 3. BOM 页面无滚动条

全局 `html/body/#app` 和 `AppLayout` 主容器使用 `overflow: hidden`，而 `BomDataManagementPage.vue` 页面内容新增上传历史/版本历史后高度超过视口，但页面自身没有内部滚动容器，导致底部数据不可见。

## 修复内容

### 后端启动提示

- `backend/run.py`：
  - 新增 `sys.gettrace()` 检测调试器；
  - 调试器附加时关闭 uvicorn reload；
  - 普通非调试运行仍使用 `settings.APP_DEBUG` 控制 reload。

### Pydantic warning

- `backend/app/domains/plan_bom/schemas/power_model.py`：
  - 为 `PowerModelVersionSummary` 增加：

```python
model_config = ConfigDict(protected_namespaces=())
```

  - 保留 API 字段名 `model_sheet_count`，避免破坏前后端契约。

### BOM 页面滚动条

- `frontend/src/views/plan-bom/BomDataManagementPage.vue`：
  - `.bom-page` 增加页面内滚动容器：

```css
height: calc(100vh - 64px);
margin: 0 auto;
padding: 48px 0;
overflow-y: auto;
overflow-x: hidden;
```

### 生产写门禁补充

Reviewer 指出旧 token 移除后功率模型导入/激活写接口需要兜底保护。本轮未恢复旧 token，而是新增环境门禁：

- `backend/app/api/deps.py`：新增 `require_plan_power_write_access`；
- `backend/app/domains/plan_bom/api/endpoints/power_model.py`：导入和激活接口挂载该 dependency；
- 非生产环境保持本地/测试可用；
- `APP_ENV=prod` 时，在正式用户/权限模块接入前返回 403。

## 验证结果

```text
Focused startup/scroll/write-guard: 5 passed in 1.50s
Related focused: 19 passed in 3.86s
Full tests: 71 passed, 2 warnings in 13.69s
Python compileall: passed
Frontend npm run build: passed
Diff check: passed
Static scan: passed
Reviewer: passed=true
Manual backend smoke: /api/v1/health returned 200; startup log no Pydantic protected namespace warning
```

说明：full tests 的 2 个 warnings 为 openpyxl 读取 Excel 扩展 / 条件格式的既有提示，不是本轮 Pydantic warning。

## 修改文件

```text
backend/run.py
backend/app/api/deps.py
backend/app/domains/plan_bom/api/endpoints/power_model.py
backend/app/domains/plan_bom/schemas/power_model.py
frontend/src/views/plan-bom/BomDataManagementPage.vue
tests/business_acceptance/test_backend_run_startup.py
tests/business_acceptance/test_plan_power_m2_model_versioning.py
tests/business_acceptance/test_plan_power_frontend_upload_entry.py
```

## 验收材料

```text
ai/tasks/running/TASK-backend-startup-scroll-fix/diff.patch
ai/tasks/running/TASK-backend-startup-scroll-fix/test.log
ai/tasks/running/TASK-backend-startup-scroll-fix/static_scan.txt
ai/tasks/running/TASK-backend-startup-scroll-fix/reviewer.md
ai/tasks/running/TASK-backend-startup-scroll-fix/final-acceptance.md
```

## 注意事项

- 若生产环境需要开放功率模型上传/激活，必须先接入正式用户/权限模块，或明确配置生产权限策略；当前生产环境会阻断这些写操作。
- IDE 自身的单次 `Connected to:` 调试连接提示不属于业务日志，无法由后端代码完全消除；本轮已避免 uvicorn reload 在调试态造成多进程重复连接提示。
