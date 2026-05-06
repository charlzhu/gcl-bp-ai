from __future__ import annotations

import json
import re
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "tmp" / "business_acceptance"

ORACLE_STATUSES = (
    "READY",
    "NEED_ORACLE",
    "NEED_DATA",
    "NEED_CLARIFICATION",
    "UNSUPPORTED",
)

BOM_KEYWORDS = (
    "bom",
    "物料",
    "订单",
    "接线盒",
    "线盒",
    "玻璃",
    "焊带",
    "互联条",
    "汇流条",
    "间隙贴膜",
    "间隙膜",
    "胶膜",
    "电池片",
    "边框",
    "规格描述",
    "a0",
    "a1",
)

LOGISTICS_KEYWORDS = (
    "物流",
    "运费",
    "运输",
    "发运",
    "承运商",
    "物流公司",
    "车次",
    "车型",
    "运量",
    "省",
    "城市",
    "区域",
    "始发",
    "客户",
    "采购方式",
    "发货类型",
    "单瓦",
    "额外费用",
    "异常费用",
    "达标率",
    "签收",
    "路程",
    "距离",
    "单价",
    "装车",
    "招标",
    "询比价",
    "采购类型",
    "任务状态",
    "司机",
    "手机号",
    "身份证号",
    "仓库",
    "运价",
    "报价",
    "发货",
    "辅料送样",
    "倒运",
    "中转",
    "换车",
    "压车",
    "放空",
)

UNSUPPORTED_KEYWORDS = (
    "预测",
    "预计",
    "未来",
    "明天",
    "后天",
    "方案设计",
    "设计一套",
    "优化策略",
    "调度策略",
    "根因分析",
    "原因分析",
    "为什么会",
)

CLARIFICATION_KEYWORDS = (
    "最近",
    "异常",
    "有没有问题",
    "效率怎么样",
    "风险怎么样",
    "哪些有问题",
    "特殊订单",
    "怎么样",
    "是否变高",
    "是不是变高",
)

METRIC_KEYWORDS = (
    "发运量",
    "运量",
    "发货量",
    "出货量",
    "总费用",
    "总运费",
    "车次",
    "车辆数",
    "签收率",
    "元/瓦",
    "件数",
    "平均运费",
    "偏差率",
    "额外费用",
    "物料",
    "版本",
    "用量",
    "规格",
)


def now_iso() -> str:
    """返回秒级时间戳。

    参数：无。
    返回值：当前本地时间的 ISO 字符串，用于验收产物追踪。
    """

    return datetime.now().isoformat(timespec="seconds")


def write_json(path: Path, payload: Any) -> None:
    """写入 JSON 文件。

    参数：
        path：输出文件路径。
        payload：可 JSON 序列化的数据。
    返回值：无。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_markdown(path: Path, title: str, lines: list[str]) -> None:
    """写入 Markdown 文件。

    参数：
        path：输出文件路径。
        title：一级标题。
        lines：正文行列表。
    返回值：无。
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([f"# {title}", "", *lines]).rstrip() + "\n", encoding="utf-8")


def extract_docx_paragraphs(question_file: Path) -> list[str]:
    """从 docx 文档中提取段落文本。

    参数：
        question_file：业务问题 docx 文件路径。
    返回值：
        按 Word 文档顺序提取出的非空段落文本列表。

    业务逻辑：
        使用标准库直接读取 `word/document.xml`，避免为了导入问题集引入新依赖。
        表格内文本在 docx 中也会落到段落节点，因此可被同一路径读取。
    """

    if not question_file.exists():
        raise FileNotFoundError(f"业务问题文件不存在：{question_file}")
    if question_file.suffix.lower() != ".docx":
        raise ValueError(f"当前导入模块仅支持 .docx 文件：{question_file}")

    try:
        with zipfile.ZipFile(question_file) as archive:
            document_xml = archive.read("word/document.xml")
    except KeyError as exc:
        raise ValueError(f"docx 文件缺少 word/document.xml：{question_file}") from exc
    except zipfile.BadZipFile as exc:
        raise ValueError(f"不是有效的 docx 压缩包：{question_file}") from exc

    root = ElementTree.fromstring(document_xml)
    word_ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
    paragraphs: list[str] = []
    for paragraph in root.iter(f"{word_ns}p"):
        fragments: list[str] = []
        for node in paragraph.iter():
            if node.tag == f"{word_ns}t" and node.text:
                fragments.append(node.text)
            elif node.tag == f"{word_ns}tab":
                fragments.append("\t")
            elif node.tag == f"{word_ns}br":
                fragments.append("\n")
        text = re.sub(r"\s+", " ", "".join(fragments)).strip()
        if text:
            paragraphs.append(text)
    return paragraphs


def split_inline_oracle(text: str) -> tuple[str, str | None]:
    """拆分问题文本中的内联标准答案。

    参数：
        text：原始段落中的题目文本。
    返回值：
        `(question, expected_answer)`；没有内联答案时 expected_answer 为 None。
    """

    marker = re.search(r"\s*(?:标准答案|参考答案|答案|oracle|expected)\s*[:：]\s*", text, re.IGNORECASE)
    if not marker:
        return text.strip(), None
    question = text[: marker.start()].strip()
    answer = text[marker.end() :].strip()
    return question, answer or None


def parse_oracle_paragraph(text: str) -> str | None:
    """解析单独段落中的标准答案。

    参数：
        text：一个非编号段落。
    返回值：
        标准答案文本；无法识别时返回 None。
    """

    matched = re.match(r"^\s*(?:标准答案|参考答案|答案|oracle|expected)\s*[:：]\s*(.+?)\s*$", text, re.IGNORECASE)
    if not matched:
        return None
    return matched.group(1).strip() or None


def load_docx_questions(question_file: Path) -> list[dict[str, Any]]:
    """从 docx 中读取编号业务问题。

    参数：
        question_file：Word/docx 业务问题文档路径。
    返回值：
        raw question 列表，保留原始编号、问题文本、原段落和可选标准答案。

    业务逻辑：
        只识别 `1. 问题`、`1、问题`、`1) 问题` 这类稳定编号格式；
        这与当前 trial_sample 问题文档习惯一致，也便于后续扩展更多导入器。
    """

    paragraphs = extract_docx_paragraphs(question_file)
    number_pattern = re.compile(r"^\s*(\d+)[\.、\)]\s*(.+?)\s*$")
    items: list[dict[str, Any]] = []
    current_item: dict[str, Any] | None = None

    for paragraph_index, text in enumerate(paragraphs, start=1):
        matched = number_pattern.match(text)
        if matched:
            original_number = int(matched.group(1))
            question, expected_answer = split_inline_oracle(matched.group(2).strip())
            item = {
                "id": f"RAW-{original_number:04d}",
                "original_number": original_number,
                "question": question,
                "raw_text": text,
                "paragraph_index": paragraph_index,
                "expected_answer": expected_answer,
                "oracle_source": "inline" if expected_answer else None,
            }
            items.append(item)
            current_item = item
            continue

        oracle_text = parse_oracle_paragraph(text)
        if current_item and oracle_text and not current_item.get("expected_answer"):
            current_item["expected_answer"] = oracle_text
            current_item["oracle_source"] = "following_paragraph"

    return items


def classify_domain(question: str) -> str:
    """识别业务问题所属领域。

    参数：
        question：业务问题文本。
    返回值：
        `logistics`、`bom` 或 `unknown`。

    业务逻辑：
        这里只服务验收问题集导入和报告分层，不改变 `/smart-chat` 的真实路由逻辑。
    """

    lower = question.lower()
    bom_score = sum(1 for keyword in BOM_KEYWORDS if keyword.lower() in lower)
    logistics_score = sum(1 for keyword in LOGISTICS_KEYWORDS if keyword.lower() in lower)
    if bom_score > logistics_score and bom_score > 0:
        return "bom"
    if logistics_score > 0:
        return "logistics"
    if bom_score > 0:
        return "bom"
    return "unknown"


def classify_question_type(question: str, domain: str) -> str:
    """识别验收题型。

    参数：
        question：业务问题文本。
        domain：已识别的业务域。
    返回值：
        题型标签，用于后续报告聚合。
    """

    lower = question.lower()
    if any(keyword in lower for keyword in UNSUPPORTED_KEYWORDS):
        return "unsupported"
    if domain == "bom":
        if any(keyword in lower for keyword in ("对比", "比较", "差异", "不一样")):
            return "bom_compare"
        return "bom_lookup"
    if any(keyword in lower for keyword in ("明细", "列表", "清单")):
        return "detail"
    if any(keyword in lower for keyword in ("同比", "环比", "对比", "比较", "差值")):
        return "comparison"
    if any(keyword in lower for keyword in ("top", "前十", "前五", "排名", "最高", "最低")):
        return "topn"
    if any(keyword in lower for keyword in ("按", "分组", "分别", "各")):
        return "grouping"
    return "aggregate"


def question_has_year_or_period(question: str) -> bool:
    """判断问题是否包含明确时间范围。

    参数：
        question：业务问题文本。
    返回值：
        True 表示问题中有年份、月份、季度或历史/系统来源暗示。
    """

    compact = re.sub(r"\s+", "", question)
    return bool(
        re.search(r"(20\d{2}|2[3-6])年", compact)
        or re.search(r"\d{1,2}月|Q[1-4]|[一二三四]季度", compact, re.IGNORECASE)
        or any(keyword in compact for keyword in ("历史", "系统", "今年", "去年", "本月", "上月"))
    )


def question_has_metric(question: str) -> bool:
    """判断问题是否包含明确指标或对象。

    参数：
        question：业务问题文本。
    返回值：
        True 表示问题中有可计算指标、编号或 BOM 物料对象。
    """

    lower = question.lower()
    return any(keyword.lower() in lower for keyword in METRIC_KEYWORDS) or bool(re.search(r"[A-Za-z]{1,}\d{2,}", question))


def determine_oracle_status(
    *,
    question: str,
    domain: str,
    expected_answer: str | None,
) -> tuple[str, list[str], list[str]]:
    """标记标准答案准备状态。

    参数：
        question：业务问题文本。
        domain：业务域分类结果。
        expected_answer：导入文档中可选的标准答案。
    返回值：
        `(oracle_status, reasons, data_requirements)`。

    业务逻辑：
        当前框架先完成问题导入、分类和 oracle 缺口标记，不接入业务核心查询链路。
        因此有明确答案的题才标 READY；没有答案但域明确的题标 NEED_ORACLE，
        等后续物流 Excel/MySQL 或 BOM Excel 标准答案计算器补齐。
    """

    compact = re.sub(r"\s+", "", question)
    if any(keyword in compact for keyword in UNSUPPORTED_KEYWORDS):
        return "UNSUPPORTED", ["问题包含预测、策略设计或开放分析类表达，当前不进入可执行 Web E2E。"], []

    if domain == "unknown":
        return "NEED_DATA", ["无法识别为 logistics 或 bom，需要先确认数据域和业务归属。"], []

    data_requirements = {
        "logistics": ["物流 Excel/MySQL 标准答案计算器"],
        "bom": ["BOM 不规则 Excel 标准答案计算器"],
    }[domain]

    needs_clarification = any(keyword in compact for keyword in CLARIFICATION_KEYWORDS) and (
        not question_has_year_or_period(question) or not question_has_metric(question)
    )
    if needs_clarification:
        return "NEED_CLARIFICATION", ["问题缺少明确时间、指标、异常定义或比较口径，需要业务补槽。"], data_requirements

    if expected_answer:
        return "READY", ["导入文档中已携带标准答案，可进入后续 Web E2E 绑定。"], data_requirements

    return "NEED_ORACLE", ["问题域已识别，但尚未绑定可复算的标准答案。"], data_requirements


def build_raw_questions(question_file: Path) -> dict[str, Any]:
    """构建 raw_questions.json 数据。

    参数：
        question_file：Word/docx 业务问题文档路径。
    返回值：
        raw question JSON 对象。
    """

    items = load_docx_questions(question_file)
    return {
        "generated_at": now_iso(),
        "source_file": str(question_file),
        "source_file_type": question_file.suffix.lower(),
        "total_questions": len(items),
        "items": items,
    }


def normalize_cases(raw_questions: dict[str, Any]) -> dict[str, Any]:
    """生成 normalized_cases.json 数据。

    参数：
        raw_questions：`build_raw_questions` 生成的原始问题对象。
    返回值：
        标准化 case JSON 对象。
    """

    cases: list[dict[str, Any]] = []
    for item in raw_questions["items"]:
        question = item["question"]
        domain = classify_domain(question)
        question_type = classify_question_type(question, domain)
        oracle_status, reasons, data_requirements = determine_oracle_status(
            question=question,
            domain=domain,
            expected_answer=item.get("expected_answer"),
        )
        cases.append(
            {
                "case_id": f"BA-{item['original_number']:04d}",
                "source_question_id": item["id"],
                "original_number": item["original_number"],
                "question": question,
                "domain": domain,
                "question_type": question_type,
                "oracle_status": oracle_status,
                "oracle_reasons": reasons,
                "data_requirements": data_requirements,
                "expected_answer": item.get("expected_answer"),
                "oracle_source": item.get("oracle_source"),
            }
        )

    return {
        "generated_at": now_iso(),
        "source_file": raw_questions["source_file"],
        "total_cases": len(cases),
        "domain_distribution": dict(Counter(case["domain"] for case in cases)),
        "question_type_distribution": dict(Counter(case["question_type"] for case in cases)),
        "oracle_status_distribution": dict(Counter(case["oracle_status"] for case in cases)),
        "allowed_oracle_statuses": list(ORACLE_STATUSES),
        "items": cases,
    }


def build_case_classification_report(
    *,
    normalized_cases: dict[str, Any],
    raw_path: Path,
    normalized_path: Path,
) -> list[str]:
    """生成问题分类报告正文。

    参数：
        normalized_cases：标准化 case 数据。
        raw_path：raw_questions.json 输出路径。
        normalized_path：normalized_cases.json 输出路径。
    返回值：
        Markdown 正文行列表。
    """

    domain_lines = [f"- {key}: `{value}`" for key, value in normalized_cases["domain_distribution"].items()] or ["- 无"]
    status_lines = [
        f"- {key}: `{value}`" for key, value in normalized_cases["oracle_status_distribution"].items()
    ] or ["- 无"]
    sample_rows = [
        "| Case ID | Domain | Oracle Status | Question Type | Question |",
        "| --- | --- | --- | --- | --- |",
    ]
    for case in normalized_cases["items"][:80]:
        question = case["question"].replace("|", "｜")
        sample_rows.append(
            f"| {case['case_id']} | {case['domain']} | {case['oracle_status']} | "
            f"{case['question_type']} | {question} |"
        )

    return [
        f"- 源文件：`{normalized_cases['source_file']}`",
        f"- 原始问题产物：`{raw_path}`",
        f"- 标准化用例产物：`{normalized_path}`",
        f"- 标准化用例数：`{normalized_cases['total_cases']}`",
        "",
        "## Domain Distribution",
        *domain_lines,
        "",
        "## Oracle Status Distribution",
        *status_lines,
        "",
        "## Oracle Status Semantics",
        "- `READY`：问题已携带标准答案，可绑定后续 Web E2E。",
        "- `NEED_ORACLE`：问题域明确，但仍需物流或 BOM 标准答案计算器补齐。",
        "- `NEED_DATA`：问题无法归入当前 logistics / bom，需先确认数据来源。",
        "- `NEED_CLARIFICATION`：问题缺少时间、指标或业务口径，需要业务补槽。",
        "- `UNSUPPORTED`：预测、开放分析或策略设计类问题，不进入当前 Web E2E。",
        "",
        "## Sample Cases",
        *sample_rows,
        "",
        "## Notes",
        "- 本框架只做问题导入、分类和 oracle 准备状态标记，不调用业务 service。",
        "- 当前 `trial_sample_*` 脚本和 3281/3281 既有验收口径保持独立。",
    ]


def import_business_questions(question_file: Path, output_dir: Path = DEFAULT_OUTPUT_DIR) -> dict[str, Path]:
    """导入业务问题并写出三类验收产物。

    参数：
        question_file：Word/docx 业务问题文档路径。
        output_dir：输出目录。
    返回值：
        包含 raw、normalized、report 三个产物路径的字典。
    """

    output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = output_dir / "raw_questions.json"
    normalized_path = output_dir / "normalized_cases.json"
    report_path = output_dir / "case_classification_report.md"

    raw_questions = build_raw_questions(question_file)
    normalized_cases = normalize_cases(raw_questions)
    write_json(raw_path, raw_questions)
    write_json(normalized_path, normalized_cases)
    write_markdown(
        report_path,
        "CASE_CLASSIFICATION_REPORT",
        build_case_classification_report(
            normalized_cases=normalized_cases,
            raw_path=raw_path,
            normalized_path=normalized_path,
        ),
    )
    return {"raw": raw_path, "normalized": normalized_path, "report": report_path}
