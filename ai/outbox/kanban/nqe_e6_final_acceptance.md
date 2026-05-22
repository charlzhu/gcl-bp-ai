# NQE-E6 评测报告与 CI 门禁 — 最终验收文档

## 1. 任务概述

目标：建立评测报告自动生成与 CI 门禁。

## 2. 交付物清单

### 新增文件
| 文件 | 行数 | 说明 |
|------|------|------|
| `backend/app/domains/qa_evaluation/report_generator.py` | ~350 | HTML/Markdown 评测报告生成器 |
| `backend/app/domains/qa_evaluation/ci_gate.py` | ~195 | CI 门禁（pass_rate 阈值 + 泄露阻断）|
| `backend/app/domains/qa_evaluation/history.py` | ~260 | 评测历史对比（逐 case 对比 + 趋势分析）|
| `tests/unit/qa_evaluation/test_e6_report_generator.py` | ~400 | 21 focused tests |
| `tests/unit/qa_evaluation/test_e6_ci_gate.py` | ~350 | 18 focused tests |
| `tests/unit/qa_evaluation/test_e6_history.py` | ~460 | 17 focused tests |
| `tests/unit/qa_evaluation/test_e6_conftest.py` | ~190 | 10 focused tests (conftest plugin)|
| `tests/evaluation/conftest.py` | ~210 | pytest --eval-report CLI 插件 |

### 修改文件
| 文件 | 说明 |
|------|------|
| `backend/app/domains/qa_evaluation/__init__.py` | 新增 CIGate/GateResult/EvalHistory/HistoryComparison/ReportGenerator 导出 |

## 3. 验收标准检查

| 验收项 | 状态 | 证据 |
|--------|------|------|
| CLI 可运行评测并输出报告 | ✅ | `python -m pytest tests/evaluation/ --eval-report` 选项已注册并可用 |
| ReportGenerator 可输出 HTML/Markdown | ✅ | 21 focused tests 覆盖 HTML/MD 生成、多套件合并、文件输出 |
| 门禁可阻断 pass_rate < 90% 的场景 | ✅ | 18 focused tests 覆盖阈值边界、自定义阈值 |
| 门禁可阻断新增技术泄露 | ✅ | 泄露优先于 pass_rate 检查（hard fail）|
| 历史对比（当前 vs 上次）| ✅ | 17 focused tests 覆盖新增失败、已修复、新增/删除 case、泄露对比、趋势分析、持久化 |
| focused tests 存在 | ✅ | 66 new focused tests (56 core + 10 conftest) |
| 不破坏现有基线 | ✅ | 144→154 qa_evaluation tests pass；23 pre-existing failures in business_qa_graph/semantic_catalog（非 E6 相关）|

## 4. 测试结果

- **qa_evaluation focused**: 154/154 PASS
- **E6-new focused**: 66/66 PASS
- **Full suite**: 933/956 PASS (23 pre-existing failures unrelated)
- **Static scan**: Clean (no hardcoded secrets, SQL injection, shell injection, eval/exec/pickle)
- **Compile**: All 3 new modules compile OK
- **Independent review**: PASSED (2 rounds)

## 5. 设计要点

1. **ReportGenerator** — 纯确定性代码，不依赖 LLM。HTML/Markdown 使用标准格式，中文注释完整。
2. **CIGate** — fail-closed 设计。技术泄露为硬性阻断（优先级高于 pass_rate）。支持单/多套件检查。
3. **EvalHistory** — 逐 case_id 匹配对比。识别新增失败、已修复、新增/删除 case、泄露变化。通过率趋势分三档（improved/degraded/stable）。
4. **conftest 插件** — 模块级全局列表作为数据桥梁（绕过 pytest session fixture 在 sessionfinish 中的访问限制）。`--eval-report` 默认输出到 `ai/outbox/eval_reports/`。

## 6. 未解决问题

- conftest 插件的 `pytest_sessionfinish` 异常处理仅打印 stderr（建议后续版本增加 traceback）
- 23 个 pre-existing 的 business_qa_graph/semantic_catalog 测试失败（非本任务范围，属于 LangGraph/SemanticCatalog 相关环境问题）

## 7. 验证命令

```bash
# 运行全部评测测试
python -m pytest tests/unit/qa_evaluation/ -v

# 运行评测集并生成报告
python -m pytest tests/evaluation/ --eval-report

# 指定输出目录
python -m pytest tests/evaluation/ --eval-report=ai/outbox/eval_reports/
```
