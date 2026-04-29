from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = PROJECT_ROOT / "tmp/trial_release_readiness_check_report.json"
DOC_PATH = PROJECT_ROOT / "docs/TRIAL_RELEASE_READINESS_CHECK.md"


def _load_json(path: Path) -> dict[str, Any]:
    """读取 JSON 文件。

    参数：
        path: JSON 文件路径。

    返回：
        JSON 对象；文件不存在或解析失败时返回空字典。
    """

    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _relative(path: Path) -> str:
    """将路径转换为仓库相对路径。

    参数：
        path: 任意路径。

    返回：
        仓库内相对路径，仓库外保留原始字符串。
    """

    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _check_doc_secret_leak(doc_paths: list[Path]) -> list[dict[str, Any]]:
    """扫描文档中的疑似真实 API Key。

    参数：
        doc_paths: 待扫描 Markdown 文件。

    返回：
        疑似泄露列表。只检查明显密钥形态，不拦截 `LLM_API_KEY` 变量名和占位说明。
    """

    findings: list[dict[str, Any]] = []
    suspicious_patterns = [
        re.compile(r"\bsk-[A-Za-z0-9_\-]{20,}\b"),
        re.compile(r"(?i)\b(api[_-]?key|llm_api_key)\s*[:=]\s*['\"]?(?!<|your|xxx|空|占位|placeholder)([A-Za-z0-9_\-]{20,})"),
    ]
    for path in doc_paths:
        if not path.exists():
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            for pattern in suspicious_patterns:
                if pattern.search(line):
                    findings.append({"path": _relative(path), "line": line_no, "text": line.strip()[:160]})
    return findings


def _status_doc_bad_phrases(paths: list[Path]) -> list[dict[str, Any]]:
    """检查状态文档是否误写成继续 Wave3、迁 A 或 query_key 扩展。

    参数：
        paths: 状态文档路径。

    返回：
        命中的风险表述。允许出现“不要开启 Wave3”等边界说明。
    """

    bad_patterns = [
        re.compile(r"当前阶段[:：].*(Wave3|迁 A|扩 query_key|后端收口)"),
        re.compile(r"当前自动执行队列[:：].*(Wave3|迁 A|扩 query_key|后端收口)"),
        re.compile(r"继续(.*迁 A|.*扩 query_key|.*BOM Wave3|.*物流后端收口)"),
    ]
    allowed_markers = ("不要", "不是", "不继续", "不再", "非阻塞")
    findings: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            findings.append({"path": _relative(path), "line": None, "text": "missing"})
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), start=1):
            if any(marker in line for marker in allowed_markers):
                continue
            if any(pattern.search(line) for pattern in bad_patterns):
                findings.append({"path": _relative(path), "line": line_no, "text": line.strip()})
    return findings


def build_report() -> dict[str, Any]:
    """构建试运行发布前检查报告。

    返回：
        包含文档、报告、状态分布和安全扫描结果的报告字典。
    """

    required_docs = [
        "docs/TRIAL_RELEASE_OVERVIEW.md",
        "docs/TRIAL_API_REFERENCE.md",
        "docs/TRIAL_POSTMAN_GUIDE.md",
        "docs/TRIAL_USER_GUIDE.md",
        "docs/TRIAL_FEEDBACK_LOOP.md",
        "docs/TRIAL_LEADER_BRIEFING.md",
        "docs/PLAN_BOM_UPLOAD_API.md",
        "docs/PLAN_BOM_QA_API_E2E_CHECK.md",
        "docs/PLAN_BOM_ACCEPTANCE_REPORT.md",
        "docs/LOGISTICS_903_ACCEPTANCE_REPORT.md",
        "docs/CURRENT_STATUS.md",
        "docs/NEXT_TASK.md",
        "docs/HANDOFF.md",
    ]
    required_reports = [
        "tmp/plan_bom/plan_bom_acceptance_report.json",
        "tmp/plan_bom/plan_bom_upload_api_check_report.json",
        "tmp/plan_bom/plan_bom_qa_api_e2e_check_report.json",
        "tmp/logistics_question_bank/logistics_903_semantic_closure_full_report.json",
        "tmp/logistics_question_bank/logistics_nlu_center_eval_report.json",
        "tmp/logistics_question_bank/logistics_llm_guardrail_rollout_check_report.json",
    ]
    frontend_files = [
        "frontend/src/views/logistics-data-qa/LogisticsDataQaPage.vue",
        "frontend/src/views/plan-bom/PlanBomDetailQueryPage.vue",
        "frontend/src/api/logistics.ts",
        "frontend/src/api/planBom.ts",
        "frontend/src/router/index.ts",
    ]
    env_examples = ["backend/.env.example"]

    doc_status = {path: (PROJECT_ROOT / path).exists() for path in required_docs}
    report_status = {path: (PROJECT_ROOT / path).exists() for path in required_reports}
    frontend_status = {path: (PROJECT_ROOT / path).exists() for path in frontend_files}
    env_status = {path: (PROJECT_ROOT / path).exists() for path in env_examples}

    bom_acceptance = _load_json(PROJECT_ROOT / "tmp/plan_bom/plan_bom_acceptance_report.json")
    logistics_903 = _load_json(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_semantic_closure_full_report.json")
    bom_distribution = bom_acceptance.get("bom_distribution") or {}
    logistics_distribution = logistics_903.get("ledger_distribution") or {}
    logistics_distribution = {**logistics_distribution, "D": logistics_distribution.get("D", 0)}

    docs_to_scan = list((PROJECT_ROOT / "docs").glob("*.md"))
    secret_findings = _check_doc_secret_leak(docs_to_scan)
    phrase_findings = _status_doc_bad_phrases(
        [PROJECT_ROOT / "docs/CURRENT_STATUS.md", PROJECT_ROOT / "docs/NEXT_TASK.md", PROJECT_ROOT / "docs/HANDOFF.md"]
    )

    checks = {
        "required_docs_exist": all(doc_status.values()),
        "required_reports_exist": all(report_status.values()),
        "frontend_files_exist": all(frontend_status.values()),
        "env_example_exists": all(env_status.values()),
        "logistics_distribution_ok": logistics_distribution == {"A": 656, "B": 178, "C": 69, "D": 0},
        "bom_distribution_ok": bom_distribution == {"A": 86, "B": 40, "C": 3, "D": 0} or bom_distribution == {"B": 40, "C": 3, "A": 86},
        "bom_upload_api_report_ok": bool((_load_json(PROJECT_ROOT / "tmp/plan_bom/plan_bom_upload_api_check_report.json")).get("passed")),
        "bom_qa_api_e2e_ok": (_load_json(PROJECT_ROOT / "tmp/plan_bom/plan_bom_qa_api_e2e_check_report.json")).get("passed") == 30,
        "logistics_e2e_report_ok": (logistics_903.get("summary") or {}).get("overall_passed") == 1559,
        "guardrail_bounded_check_ok": (_load_json(PROJECT_ROOT / "tmp/logistics_question_bank/logistics_llm_guardrail_rollout_check_report.json")).get("passed") == 10,
        "no_real_api_key_in_docs": not secret_findings,
        "status_docs_not_wave_or_migration": not phrase_findings,
    }
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "release_name": "经营计划智能助手试运行发布包：物流问答 + 计划 BOM 问答",
        "passed": all(checks.values()),
        "checks": checks,
        "doc_status": doc_status,
        "report_status": report_status,
        "frontend_status": frontend_status,
        "env_status": env_status,
        "logistics_distribution": logistics_distribution,
        "bom_distribution": {"A": bom_distribution.get("A", 0), "B": bom_distribution.get("B", 0), "C": bom_distribution.get("C", 0), "D": bom_distribution.get("D", 0)},
        "secret_findings": secret_findings,
        "status_doc_phrase_findings": phrase_findings,
        "non_blocking_notes": [
            "logistics full rollout 路径仍保留；发布前门禁使用 bounded Guardrail check，避免长时间挂起。",
            "当前检查不执行能力开发，不迁 A，不扩 query_key。",
        ],
    }
    return report


def render_markdown(report: dict[str, Any]) -> str:
    """渲染试运行发布前检查 Markdown。

    参数：
        report: build_report 返回的报告。

    返回：
        Markdown 文本。
    """

    checks = report["checks"]
    lines = [
        "# 试运行发布前检查报告",
        "",
        f"- 发布包：{report['release_name']}",
        f"- 生成时间：`{report['generated_at']}`",
        f"- 总体结果：`{'通过' if report['passed'] else '未通过'}`",
        "",
        "## 状态分布",
        "",
        f"- 物流：`A={report['logistics_distribution'].get('A')} / B={report['logistics_distribution'].get('B')} / C={report['logistics_distribution'].get('C')} / D={report['logistics_distribution'].get('D')}`",
        f"- BOM：`A={report['bom_distribution'].get('A')} / B={report['bom_distribution'].get('B')} / C={report['bom_distribution'].get('C')} / D={report['bom_distribution'].get('D')}`",
        "",
        "## 检查项",
        "",
        "| 检查项 | 结果 |",
        "| --- | --- |",
    ]
    for key, value in checks.items():
        lines.append(f"| `{key}` | `{'PASS' if value else 'FAIL'}` |")
    lines.extend(
        [
            "",
            "## 非阻塞说明",
            "",
            "- logistics full rollout 路径仍保留；发布前门禁使用 bounded Guardrail check，避免长时间挂起。",
            "- 当前发布包不包含继续迁 A、扩 query_key 或 BOM Wave3 能力开发。",
            "",
            "## 失败明细",
            "",
        ]
    )
    if report["passed"]:
        lines.append("- 无。")
    else:
        if report["secret_findings"]:
            lines.append(f"- 文档疑似 API Key：`{report['secret_findings']}`")
        if report["status_doc_phrase_findings"]:
            lines.append(f"- 状态文档风险表述：`{report['status_doc_phrase_findings']}`")
        missing_docs = [path for path, ok in report["doc_status"].items() if not ok]
        missing_reports = [path for path, ok in report["report_status"].items() if not ok]
        if missing_docs:
            lines.append(f"- 缺失文档：`{missing_docs}`")
        if missing_reports:
            lines.append(f"- 缺失报告：`{missing_reports}`")
    return "\n".join(lines)


def main() -> None:
    """执行试运行发布前检查，并写入 JSON 与 Markdown 报告。"""

    report = build_report()
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    DOC_PATH.write_text(render_markdown(report), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "checks": report["checks"]}, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
