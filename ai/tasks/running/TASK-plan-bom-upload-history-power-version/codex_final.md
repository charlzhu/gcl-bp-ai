# TASK-plan-bom-upload-history-power-version Codex Final

本轮已完成计划 BOM 数据管理历史查看与功率模型版本生效切换补充需求。

## 本轮做了什么

1. 移除功率模型管理 token：
   - 删除后端临时配置与依赖。
   - 删除前端 token 输入、状态和请求头。
2. 新增 BOM 上传历史能力：
   - 后端新增上传批次历史查询接口。
   - 前端新增 BOM 上传历史表格。
3. 新增功率模型版本管理能力：
   - 前端新增功率模型版本历史表格。
   - 前端支持手动“设为生效”。
   - 后端导入有效模型后默认激活最新上传版本。
   - 同文件重复上传不新增模型版本，命中 existing 后重新激活该版本。
   - 解析失败版本保留历史但不覆盖 active。
4. 修复 reviewer 三个阻塞点：
   - 非 0 ApiResponse / data=null 不误判成功。
   - parse_status=failed / error_count>0 不误判成功。
   - 激活失败不误判成功。

## 验证

- Focused：26 passed
- Full：66 passed, 2 warnings
- compileall：通过
- frontend build：通过
- diff check：通过
- static scan：通过
- independent reviewer：passed=true

## 交付物

- `diff.patch`
- `test.log`
- `static_scan.txt`
- `reviewer.md`
- `final-acceptance.md`
