# NQE_SQL_MAIN_CURRENT_STATUS.md

## 当前阶段：NQE-SQL-MAIN-15 完成，等待 NQE-SQL-MAIN-16

更新时间：2026-05-24 16:00 CST

---

## 一、看板状态

| 范围 / 卡号 | 状态 | 判断 |
|---|---:|---|
| NQE-SQL-MAIN-0 ~ 10 | done | 已完成 |
| NQE-SQL-MAIN-11 | missing | 看板缺失，不伪造为 done |
| NQE-SQL-MAIN-11-R | done (t_e69caeb6) | 恢复记录完成 |
| NQE-SQL-MAIN-12 | done | 已完成 |
| NQE-SQL-MAIN-13 | archived | completed archived |
| NQE-SQL-MAIN-14 | done (t_60cb2f95) | 已完成 |
| **NQE-SQL-MAIN-15** | **done (t_b280ecb1)** | **物流 SQL Agent 接入完成，44/44 passed** |
| NQE-SQL-MAIN-16 ~ 43 | blocked | 等待用户确认后逐卡推进 |

---

## 二、NQE-SQL-MAIN-15 完成摘要 (t_b280ecb1)

1. enhance generate_sql_direct：auto-context 场景使用实际表字段构造安全 SQL
2. 新增 test_nqe_sql_agent_logistics.py：9 个物流域测试
3. 全量 focused pytest：44/44 passed（新增 9 + 存量 35）
4. 物流 on/shadow/off 三模式验证通过
5. 未替换物流正式问答接口
6. outbox：ai/outbox/kanban/t_b280ecb1/

---

## 三、当前风险

1. NQE-SQL-MAIN-16（物流正式链路灰度切换）需谨慎接入现有物流入口
2. 建议先做本地 checkpoint commit
