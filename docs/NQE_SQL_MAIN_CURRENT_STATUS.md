# NQE_SQL_MAIN_CURRENT_STATUS.md

## 当前阶段：NQE-SQL-MAIN-16 完成，等待 checkpoint + NQE-17

更新时间：2026-05-24 16:30 CST

---

## 一、看板状态

| 范围 / 卡号 | 状态 |
|---|---:|
| NQE-SQL-MAIN-0 ~ 15 | done |
| **NQE-SQL-MAIN-16** | **done (t_5a833e34)** — off/shadow 完成，assist/on 预留 |
| NQE-SQL-MAIN-17 ~ 43 | blocked |

---

## 二、NQE-SQL-MAIN-16 完成摘要

1. 新增 `nqe_logistics_mode` 配置（默认 off）
2. 新增 `nqe_logistics_gray.py` 灰度模块
3. API 层 `_nqe_shadow_attach` 集成
4. off/shadow 模式行为已实现
5. assist/on 模式配置预留
6. 53/53 focused tests passed

## 三、当前风险

1. 建议 checkpoint 后再进 NQE-17
2. assist/on 完整行为待 NQE-17 实现
