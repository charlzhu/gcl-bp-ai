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

### 4. 前端固定 console error 已在 V2.1 里程碑 1 修复
历史现象：
- 页面加载后前端 console 中稳定出现 1 条 error

已确认根因：
- 浏览器在页面初始化时自动请求 `/favicon.ico`
- 当前前端入口没有显式 favicon 声明
- dev server 也没有提供对应静态资源
- 因此固定产生 404 console error

当前状态：
- 已通过在前端入口显式声明内联 favicon 的方式修复
- 该问题不再视为当前活动问题

保留说明：
- 若后续调整前端入口模板或静态资源策略，应再次确认 favicon 不会回退为 404

### 5. 条件查询页解释契约已在 V2.1 里程碑 2 收口
历史现象：
- 条件查询页直连 `aggregate` 接口时
- 后端只返回 `summary / items / filters / execution_mode`
- 前端需要额外兼容生成：
  - `status`
  - `result_explanation`
  - `no_result_analysis`

当前状态：
- `aggregate` 已补齐最小原生契约
- 前端已优先直接消费后端返回的：
  - `status`
  - `result_explanation`
  - `no_result_analysis`
  - `response_meta`

保留说明：
- 前端兼容生成逻辑仍保留兜底，以兼容旧数据或未升级环境
- 当前这轮只收口 `aggregate`，未扩展到 `detail / compare` 的全面契约统一
- `aggregate` 空结果场景下的 `Decimal('0.0000')` 误判，以及 `fallback + 空结果` 状态优先级问题，也已在 V2.1 里程碑 2 一并修复并补齐回归测试

### 6. 查询历史页已支持分页与关键词检索，高级筛选仍未实现
当前前端 V2 已完成查询历史页的：
- 列表概览
- 状态展示
- 执行模式展示
- 模板命中展示
- 详情查看
- 重新查询
- 分页
- 关键词检索

但当前仍未包含：
- 更细粒度的高级筛选（如按时间范围、状态组合、模板组合筛选）

处理原则：
- 当前能力已满足联调、问题回放和第一轮业务演示
- 高级筛选仍属于下一阶段可选优化，不在当前里程碑范围内

---

## 六、Codex 接手时的工作顺序建议

1. 先审查当前仓库代码，不要假设历史补丁已存在。  
2. 先判断以下两类问题当前是否已修：
   - compare 空结果误判
   - fallback 承运商映射错误
3. 如果这两类问题已修，再优先推进前端第二版。  
4. 如果未修，先补阻塞修复，再做前端。
