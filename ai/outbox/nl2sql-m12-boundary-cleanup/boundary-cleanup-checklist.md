# M12-2 物流 NL2SQL 边界状态清理清单

生成时间：2026-05-21

## 一、统计范围

针对 `backend/app/domains/logistics/services/nl2sql/` 下全部 Python 代码，
统计 disabled/skipped/fallback 类边界状态共 **77 处匹配**。

## 二、按文件分布

| 文件 | 匹配数 | 主要边界类型 |
|------|--------|-------------|
| `m10d_shadow_gate.py` | 21 | disabled/skipped gate 状态、fallback executor |
| `live_shadow_adapter.py` | 8 | disabled/skipped live shadow 状态 |
| `shadow_pipeline.py` | 4 | skipped pipeline 状态 |
| `shadow_smoke.py` | 5 | skipped 样例 |
| `m9_sqlplan_generation.py` | 4 | route_skipped/disabled 生成状态 |
| `m8_shadow_eval.py` | 3 | skipped 评估 |
| `evaluation_report.py` | 4 | skipped_count 统计字段 |
| `evaluation_log.py` | 4 | skipped_count 日志字段 |
| `m10_shadow_gate_runner.py` | 2 | expected_gate_status |
| `m10d2_explain_smoke.py` | 1 | trial_status=disabled |
| `catalog_retrieval.py` | 3 | disabled recall 状态 |

## 三、边界状态分类

### 1. 设计保留（应该保留，不是技术债）

| 边界状态 | 原因 |
|----------|------|
| gate 总开关 `enabled=False` → `disabled` | 安全设计：默认关闭，避免误执行 |
| `real_db_access_enabled=False` → fake executor fallback | 测试环境不需要真实 DB |
| `trial_enabled=False` → trial_status=disabled | 安全设计：trial 默认不启用 |
| source_system 非 `middle_db` → skipped | 域边界保护 |
| LLM 未配置 → `m9_llm_not_configured` | 环境配置缺失时 fail-closed |

### 2. 可移除（代码已不再需要）

| 边界状态 | 文件 | 建议 |
|----------|------|------|
| `shadow_smoke.py` 中的 skipped 样例 | shadow_smoke.py:125-153 | **可移除**：M7 的 smoke 已被 M9/M10/M11 覆盖，这些 skipped 样例不再具有独立评估价值 |
| `m8_shadow_eval.py` 中的 `m8_skipped_missing_candidate` | m8_shadow_eval.py:343 | **可移除**：此场景已被 M10 gate 的 `rendered_sql=None` 处理覆盖 |
| `m10d_shadow_gate.py` 中的 `source_system` 检查 | m10d_shadow_gate.py:170-180 | **可整合**：MVP 只允许 `middle_db`，后续如果扩展，此处可以升级为白名单而非报错 |

### 3. 需保留但可清理（不影响功能，但可减少噪音）

| 边界状态 | 文件 | 建议 |
|----------|------|------|
| 重复的 `disabled`/`skipped` 字面量 | 多处 | **可提取常量**：`M10DStepStatus` 已定义，但多个地方直接写字符串 |
| `shadow_pipeline.py` 的 exit early 路径 | shadow_pipeline.py:233-257 | **保持现状**：这是 pipeline 的正常分流路径 |
| `live_shadow_adapter.py` 的 fallback 路径 | live_shadow_adapter.py | **保持现状**：这是 live shadow sidecar 的必要设计 |

### 4. 需升级（边界处理不完整）

| 边界状态 | 文件 | 建议 |
|----------|------|------|
| `real_db_access_enabled=True` 但加载失败时 `静默 fallback` | m10d_shadow_gate.py:295 | **需升级**：当前是静默 fallback 到 fake executor，生产环境应该明确 BLOCKED 而非静默降级 |
| `route_skipped` 错误码名称 | m9_sqlplan_generation.py:260 | **需升级**：命名不统一，其他文件用 `skipped`，这里用 `route_skipped` |

## 四、建议优先级

### P0：本次立即修复

1. `m10d_shadow_gate.py` real_db 加载失败时静默 fallback → 改为显式 BLOCKED
2. 删除 `shadow_smoke.py` 中已不再使用的 skipped 样例（3 个）

### P1：后续迭代

3. 统一 `route_skipped` → `skipped` 命名
4. 删除 `test_m8_shadow_eval.py` 中已覆盖的 `m8_skipped_missing_candidate` 样例
5. 提取 `disabled`/`skipped` 字符串常量为统一常量集

### P2：保持现状

6. 所有 gate default-disabled 设计保留
7. 所有 pipeline 分流路径保留
8. live_shadow_adapter fallback 保留

## 五、不修改列表（保持现状）

1. gate 默认关闭 —— 安全设计，不可移除
2. trial 默认不启用 —— 安全设计
3. pipeline exit early (unsupported/route/safety) —— 正常分流
4. live shadow adapter 的 route_skipped —— 正常分流
5. catalog_retrieval 的 disabled recall —— 配置缺失时正常行为
