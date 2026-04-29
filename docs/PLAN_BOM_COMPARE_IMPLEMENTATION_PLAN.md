# PLAN_BOM_COMPARE_IMPLEMENTATION_PLAN

> 历史基线说明：
> 本文保留 compare 最小实现计划形成时的分里程碑执行口径。
> 当前仓库事实状态已经推进到：compare 里程碑 1 / 2 / 3 / 4 已完成，`BOM compare Go / No-Go 判断` 已执行，且 `compare.go` 已同步为 `true`。
> 当前状态请以 `docs/CURRENT_STATUS.md`、`docs/HANDOFF.md` 与 compare 运行态报告为准。

## 1. 文档用途

本文件用于固化 `计划 BOM` 一期 `compare` 能力的最小实现计划。

本文件属于仓库事实源，后续如果进入 `compare` 编码，应以本文件与 `docs/PLAN_BOM_COMPARE_TECH_DESIGN.md` 为准。

当前阶段说明（计划形成时）：
- `compare.go = false`
- 当前只允许进入 `compare` 的最小实现计划与后续分里程碑推进
- 当前不允许直接把 `compare` 当成已实现能力

---

## 2. 四个里程碑拆分

### 里程碑 1：compare schema / repository / service / endpoint 骨架与候选链路

#### 目标
- 建立 `compare` 请求入口和最小返回结构。
- 打通三类候选链路：
  - `order_identity`
  - `file_instance`
  - `version`
- 确保 compare 在候选未明确时不误落单。

#### 修改文件范围
- `backend/app/domains/plan_bom/schemas/query.py`
- `backend/app/domains/plan_bom/repositories/query_repository.py`
- `backend/app/domains/plan_bom/services/query_service.py`
- `backend/app/domains/plan_bom/api/endpoints/query.py`
- `backend/app/domains/plan_bom/api/router.py`
- `backend/tests/test_plan_bom_query_service.py`

#### 测试范围
- `00106` 命中多个 `order_identity_key` 时返回 `candidate_scope=order_identity`
- `00120` 命中多个 `file_instance_key` 时返回 `candidate_scope=file_instance`
- 未指定版本且存在多个可选版本时返回 `candidate_scope=version`
- 既有单订单 detail 查询不回归

#### 通过标准
- compare 请求可正常进入 service 层
- 三类候选都不会误落单
- compare 在候选态能返回稳定结构
- 既有 detail 查询和候选链路不回归

---

### 里程碑 2：compare 核心差异计算

#### 目标
- 落地 compare 的最小差异计算能力。
- 输出：
  - `left`
  - `right`
  - `only_left`
  - `only_right`
  - `changed`
  - `same`
  - `diff_summary`

#### 修改文件范围
- `backend/app/domains/plan_bom/constants.py`
- `backend/app/domains/plan_bom/repositories/query_repository.py`
- `backend/app/domains/plan_bom/services/query_service.py`
- `backend/tests/test_plan_bom_query_service.py`

#### 测试范围
- 两订单对比
- 同订单不同版本对比
- 指定 `file_instance_key` 的文件实例对比
- `material_categories` 过滤
- 5 类核心材料差异判断

#### 通过标准
- `only_left / only_right / changed / same` 结果稳定
- `diff_summary` 计数正确
- 在候选已明确后，可以进入 compare 差异结果输出

---

### 里程碑 3：查询历史 / 快照 / 回放

#### 目标
- 将 compare 写入现有平台历史链路。
- 保证快照可回放，但不无限制写入全量差异明细。

#### 修改文件范围
- `backend/app/domains/plan_bom/services/query_service.py`
- 如需复用公共日志写入能力，则补对应平台公共日志文件
- `backend/tests/test_plan_bom_query_service.py`

#### 测试范围
- compare 成功结果写日志
- compare 候选态写日志
- 快照体积控制生效
- 历史详情能识别 compare 请求

#### 通过标准
- compare 请求能进入 `sys_query_log`
- 左右上下文、候选态和 `diff_summary` 可回放
- 不无限制写入全量差异明细

---

### 里程碑 4：compare 运行态抽验与标准答案对照

#### 目标
- 基于真实样本完成 compare 小范围运行态抽验。
- 建立 compare 的答案对照与验收基线。

#### 修改文件范围
- 代码不一定新增
- 运行态报告建议写入：
  - `tmp/plan_bom_compare_*`

#### 测试范围
- `00106` 业务实例候选
- `00120` 文件实例候选
- 至少 `2~3` 组多版本样本
- compare 标准答案对照

#### 通过标准
- compare 查询成功定义明确
- 候选链路正确
- 标准答案对照结果可复核
- 才能重新判断 `compare.go`

---

## 3. 当前最小可做范围

当前最小可做范围是：

> **里程碑 1：compare schema / repository / service / endpoint 骨架与候选链路**

原因：
- 当前最大风险不在差异算法本身，而在 compare 输入侧的候选链路是否稳定。
- 如果 `order_identity` / `file_instance` / `version` 三类候选没有先收口，后续差异结果都不可信。

---

## 4. 明确不做范围

当前 compare 最小实现阶段明确不做：
- 导出
- 前端
- SAP
- RAG
- Agent

补充说明：
- 本计划只定义 compare 的最小实现推进顺序
- 不进入 compare 之外的导入或单查询逻辑扩展

---

## 5. 需要业务侧提前准备的 compare 标准答案样本

### 5.1 同订单不同版本
- 至少 `2~3` 组
- 版本链明确
- 左右侧版本明确

### 5.2 两订单对比
- 至少 `2` 组真实问题
- 左右订单明确

### 5.3 `00106`
- 如果 compare 涉及该订单，必须明确：
  - 左侧用哪个 `order_identity_key`
  - 右侧用哪个 `order_identity_key`

### 5.4 `00120`
- 如果 compare 涉及该订单，必须按文件实例拆到：
  - `A(2)`
  - `A(3)`
- 未明确 `file_instance_key` 时，不允许用并集答案验 compare

### 5.5 `00106_SJZKL_A0`
- 在业务侧标准答案修订完成前，不建议纳入 compare 验收基线

---

## 6. 实现前仍需确认的问题

1. compare 历史详情中是否展示 `same` 全量明细，还是只展示计数与抽样。
2. `changed` 是否一期就做字段级 diff，还是先做整行变化。
3. compare 标准答案是否单独维护，还是继续挂在现有问题集下。
4. compare 候选态是否允许前端后续直接“重新查询”回放。

---

## 7. 风险点

### 7.1 `order_identity` 候选风险
- `00106` 这类场景如果不先返回候选，compare 会直接误落到错误业务实例。

### 7.2 `file_instance` 候选风险
- `00120` 这类场景如果不先返回文件实例候选，会重新落回覆盖或并集误区。

### 7.3 `version` 候选风险
- 未指定版本且版本链无法唯一判定时，如果不返回候选，会导致 compare 左右侧基线不可信。

### 7.4 `00106_SJZKL_A0` 标准答案待修订项
- 当前这条仍是业务侧待修订项。
- 在 compare 验收中不能把它混成实现问题。

### 7.5 既有 detail 查询不能回归
- compare 接入不能破坏当前已通过的：
  - `00104`
  - `00067`
  - `00114`
  - `00048`
  - `00097`
  - `00106` 候选链路

---

## 8. 当前结论

当前 compare 最小实现应严格按四个里程碑推进：

1. 先做骨架与候选链路
2. 再做核心差异计算
3. 再做历史 / 快照 / 回放
4. 最后做运行态抽验与标准答案对照

当前最小可做范围是：

> **里程碑 1**

在里程碑 1 未通过前：
- 不建议进入差异算法
- 不建议进入历史快照
- 不建议进入运行态抽验
