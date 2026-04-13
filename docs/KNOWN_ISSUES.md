# KNOWN_ISSUES.md

## 一、项目当前已知问题概览

本文件记录的是：
- 当前项目中已知但不一定阻塞开发的问题
- 需要 Codex 在接手时优先核实的问题
- 已确认的边界问题

重要说明：
**不要假设这里写的问题一定已经修复或一定仍存在。Codex 必须先以当前仓库代码和测试结果为准。**

---

## 二、需要优先核实的历史问题

### 1. compare 空结果误判
历史上曾出现：
- compare 查询在 `items = []` 但有 `left_value / right_value / diff_value` 时
- 被错误判定为空结果

需要 Codex 核实：
- `result_count_helper.py` 是否已对 compare 总量对比结构做特殊处理
- `execution_audit` / `result_explanation` / `no_result_analysis` 是否已统一生效

---

### 2. fallback 承运商映射错误
历史上曾出现：
- 用户问“各承运商发货量分别是多少”
- fallback 结果返回“合肥基地 / 阜宁基地 / 芜湖基地”

需要 Codex 核实：
- `query_service.py` 是否仍将 `logistics_company_name` 映射到 demo 的 `company` 字段
- 是否已阻止 fallback 模式下把基地冒充成承运商

---

### 3. aggregate 空结果误判
历史上曾出现：
- aggregate 查询已有 `summary` / `items`
- 却被包装成 `EMPTY_RESULT`

该问题曾被修复，但 Codex 仍应在当前仓库核实：
- `result_count_helper.py`
- `execution_audit_service.py`
- `result_explainer.py`
- `no_result_analyzer.py`

是否仍保持一致。

---

## 三、当前架构边界问题

### 1. 仓库维度当前不可靠
当前采用路线 1：不补 allocate 链路。  
因此：
- `warehouse_id`
- `warehouse_name`

在 ship_task / assign_task 这类链路中不能默认视为可靠统计维度。

这不是普通 bug，而是当前阶段的明确边界。

---

### 2. 多域模板已存在，但多域真正执行能力未全部就绪
当前虽然有：
- logistics
- plan_bom
- business_analysis
- material_management

四个域的模板和路由结构，但真正稳定可执行的主要仍然是 `logistics`。  
Codex 不应误把“模板分层已存在”理解为“多域已全部完成”。

---

### 3. SQL preview 只是解释层，不是最终真实执行 SQL
当前 `sql_preview` 的作用主要是：
- 解释命中模板后的 SQL 意图
- 便于排查问题

不应直接视为数据库真实执行 SQL，也不应仅凭 preview 判断结果是否可信。

---

## 四、工程问题

### 1. 打包污染问题
历史压缩包中曾出现：
- `.env`
- `__pycache__`
- `*.pyc`
- `__MACOSX`
- `.idea`
- `.pytest_cache`

Codex 如果需要输出交付包，应统一排除这些内容。

---

### 2. 测试环境依赖问题
历史上曾出现：
- 轻量单测环境中因为 import 链强依赖数据库包而失败

需要 Codex 核实：
- 是否已通过惰性依赖 / `TYPE_CHECKING` / 兼容导入等方式缓解

---

## 五、前端当前已知状态

### 1. 前端 V1 已完成
当前前端第一版通常包含：
- 自然语言查询页
- 条件查询页
- 任务与日志页

### 2. 当前推荐方向
优先进入前端第二版优化：
- 结果表格增强
- 明细视图
- 查询历史

### 3. 当前不建议的方向
不建议继续无限叠加后端版本，而忽略前端联调与业务可见成果。

---

## 六、Codex 接手时的工作顺序建议

1. 先审查当前仓库代码，不要假设历史补丁已存在。  
2. 先判断以下两类问题当前是否已修：
   - compare 空结果误判
   - fallback 承运商映射错误
3. 如果这两类问题已修，再优先推进前端第二版。  
4. 如果未修，先补阻塞修复，再做前端。
