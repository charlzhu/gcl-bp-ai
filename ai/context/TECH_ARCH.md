# Tech Architecture

## 技术栈
- 后端：FastAPI、SQLAlchemy、Pydantic、pandas、Redis、pytest。
- 前端：Vue 3、TypeScript、Vite、Element Plus、Axios。
- 自动化：Hermes Agent + Codex CLI + Git + `ai/` 协作目录。

## 主要目录
- `backend/app/domains/logistics/`：物流域主线。
- `backend/app/domains/plan_bom/`：计划 BOM 域主线。
- `backend/tests/`：后端测试。
- `frontend/src/views/business-chat/BusinessChatPage.vue`：当前 `/smart-chat` 主页面。
- `frontend/src/views/logistics-data-qa/`：物流 data-qa 历史页面和相关能力。
- `frontend/src/views/plan-bom/`：计划 BOM 前端页面。
- `scripts/`：验收、回归、E2E、标准答案和批量执行脚本。
- `docs/`：项目事实源、交接文档、验收报告和状态说明。

## 启动和测试常用命令
- 后端安装依赖：`python -m pip install -r backend/requirements.txt`。
- 后端启动：`python backend/run.py` 或根据本地环境启动 FastAPI。
- 后端测试：`PYTHONPATH=. python -m pytest backend/tests -q`。
- 前端安装依赖：`npm install --prefix frontend`。
- 前端构建：`npm run build --prefix frontend`。

## 当前主入口
- 前端真实入口：`/smart-chat`。
- 根路径 `/` 重定向到 `/smart-chat`。
