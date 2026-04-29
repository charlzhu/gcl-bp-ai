from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TMP_DIR = PROJECT_ROOT / "tmp" / "trial_sample_eval"
SCREENSHOT_DIR = TMP_DIR / "screenshots"
DOCS_DIR = PROJECT_ROOT / "docs"

DEFAULT_QUESTION_FILE = Path("/Users/zhuchangchao/Downloads/物流和 bom样例题.docx")
DEFAULT_HIST_ZIP = Path("/Users/zhuchangchao/Desktop/01_工作业务/计划经营部/业务计划/物流/23 年至 25 年物流台账数据.zip")
DEFAULT_SYS_ZIP = Path("/Users/zhuchangchao/Downloads/物流 26 年源数据.zip")
DEFAULT_BOM_ZIP = Path("/Users/zhuchangchao/Desktop/01_工作业务/计划经营部/业务计划/计划/电池/BOM 源数据.zip")

LEDGER_PATH = TMP_DIR / "sample_question_ledger.json"
EXPECTED_PATH = TMP_DIR / "expected_answers.json"
EXPECTED_REPORT_PATH = TMP_DIR / "expected_answer_build_report.json"
FRONTEND_RESULTS_PATH = TMP_DIR / "frontend_e2e_results.json"
COMPARE_REPORT_PATH = TMP_DIR / "answer_compare_report.json"
FAILED_CASES_PATH = TMP_DIR / "failed_cases.json"
FIXED_CASES_PATH = TMP_DIR / "fixed_cases.json"
FULL_ACCEPTANCE_REPORT_PATH = TMP_DIR / "trial_sample_full_e2e_acceptance_report.json"


def now_iso() -> str:
    """返回秒级时间戳，便于报告追踪生成时间。"""
    return datetime.now().isoformat(timespec="seconds")


def ensure_output_dirs() -> None:
    """创建本轮样例题验收需要的输出目录。"""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    DOCS_DIR.mkdir(parents=True, exist_ok=True)


def write_json(path: Path, payload: Any) -> None:
    """写入 JSON 文件。

    参数：
        path: 输出文件路径；
        payload: 可 JSON 序列化的数据。
    返回值：
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def read_json(path: Path, default: Any = None) -> Any:
    """读取 JSON 文件；不存在时返回默认值。"""
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def write_markdown(path: Path, title: str, lines: list[str]) -> None:
    """写入 Markdown 文档。

    参数：
        path: 输出文档路径；
        title: 一级标题；
        lines: 正文行列表。
    返回值：
        无。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    body = [f"# {title}", "", *lines]
    path.write_text("\n".join(body).rstrip() + "\n", encoding="utf-8")


def load_docx_numbered_questions(question_file: Path) -> list[dict[str, Any]]:
    """从 docx 中解析编号问题。

    参数：
        question_file: 样例题 docx 路径。
    返回值：
        包含原始编号和问题文本的列表。
    """
    if not question_file.exists():
        raise FileNotFoundError(f"样例题文件不存在：{question_file}")
    try:
        from docx import Document
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("缺少 python-docx，无法解析样例题 docx。") from exc

    document = Document(str(question_file))
    items: list[dict[str, Any]] = []
    number_pattern = re.compile(r"^\s*(\d+)[\.、\)]\s*(.+?)\s*$")
    for paragraph in document.paragraphs:
        text = re.sub(r"\s+", " ", paragraph.text or "").strip()
        if not text:
            continue
        matched = number_pattern.match(text)
        if not matched:
            continue
        number = int(matched.group(1))
        question = matched.group(2).strip()
        if question:
            items.append({"original_number": number, "question": question, "raw_text": text})
    return items


BOM_KEYWORDS = [
    "bom",
    "BOM",
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
    "A0",
    "A1",
]

LOGISTICS_KEYWORDS = [
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
    "风险",
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
    "经营计划",
    "刘娟",
    "辅料送样",
    "倒运",
    "中转",
    "换车",
    "压车",
    "放空",
]


def classify_domain(question: str) -> str:
    """识别样例题业务域。

    说明：
        只做测试台账分类，不改变前端自动识别逻辑。
    """
    lower = question.lower()
    bom_score = sum(1 for word in BOM_KEYWORDS if word.lower() in lower)
    logistics_score = sum(1 for word in LOGISTICS_KEYWORDS if word.lower() in lower)
    if bom_score > logistics_score and bom_score > 0:
        return "plan_bom"
    if logistics_score > 0:
        return "logistics"
    return "unknown"


def classify_question_type(question: str, domain: str) -> str:
    """识别题型，供分批验收和报告聚合使用。"""
    q = question.lower()
    if any(word in q for word in ["无法", "不能", "预测", "倒推", "需要什么条件", "需要哪些条件"]):
        return "unsupported_or_clarification"
    if domain == "plan_bom":
        if any(word in q for word in ["不一样", "差异", "对比", "比较"]):
            return "bom_compare"
        if any(word in q for word in ["版本", "a0", "a1"]):
            return "bom_version"
        if any(word in q for word in ["多个订单", "所有", "清单", "表格", "excel"]):
            return "bom_batch_table"
        return "bom_material_spec"
    if any(word in q for word in ["top", "前十", "前五", "排名", "最高", "最低"]):
        return "topn"
    if any(word in q for word in ["同比", "环比", "差值", "对比", "相比", "比较"]):
        return "comparison"
    if any(word in q for word in ["趋势", "折线", "柱状", "图表", "图形"]):
        return "chart"
    if any(word in q for word in ["矩阵", "交叉", "透视", "宽表"]):
        return "matrix_or_wide_table"
    if any(word in q for word in ["每月", "月度", "月份", "1月", "2月", "3月", "季度", "q1", "q2", "q3", "q4"]):
        return "period_grouping"
    if any(word in q for word in ["明细", "列表", "清单"]):
        return "detail_list"
    if any(word in q for word in ["占比", "比例", "平均", "单瓦", "达标率"]):
        return "derived_metric"
    if any(word in q for word in ["按", "分组", "分别", "各"]):
        return "grouping"
    return "aggregate"


def is_focus_question(question: str, domain: str, question_type: str) -> bool:
    """判断是否为重点题，重点题会生成更多变体。"""
    focus_types = {
        "bom_compare",
        "bom_version",
        "bom_batch_table",
        "topn",
        "comparison",
        "chart",
        "matrix_or_wide_table",
        "period_grouping",
        "unsupported_or_clarification",
    }
    if domain == "plan_bom":
        return True
    if question_type in focus_types:
        return True
    return any(word in question.lower() for word in ["自动识别", "bom", "b/c", "拒答"])


def generate_question_variants(question: str, *, domain: str, focus: bool) -> list[str]:
    """生成语义等价变体。

    说明：
        变体只用于真实网页回归输入，不作为答案来源；若替换后没有变化，会用口语化前缀兜底。
    """
    variants: list[str] = []

    def add(candidate: str) -> None:
        candidate = re.sub(r"\s+", " ", candidate).strip()
        if candidate and candidate != question and candidate not in variants:
            variants.append(candidate)

    if domain == "plan_bom":
        add(question.replace("接线盒", "线盒"))
        # 只替换独立“线盒”，避免把“接线盒”错误变成“接接线盒”。
        add(re.sub(r"(?<!接)线盒", "接线盒", question))
        add(question.replace("间隙贴膜", "间隙膜"))
        add(question.replace("表格", "清单"))
    elif domain == "logistics":
        add(question.replace("运费", "运输费用"))
        add(question.replace("物流公司", "承运商"))
        # 避免“各物流承运商”被机械替换成“各物流物流公司”这类失真变体。
        if "物流承运商" in question:
            add(question.replace("物流承运商", "物流公司"))
        else:
            add(question.replace("承运商", "物流公司"))
        add(question.replace("发运量", "运量"))
        add(re.sub(r"(\d{4}) 年", r"\1年", question))
        add(re.sub(r"(\d{4})年", lambda m: f"{m.group(1)[2:]}年", question, count=1))
    else:
        add(f"请帮我看一下：{question}")

    add(f"请帮我查询{question.rstrip('？?。')}")
    if focus:
        add(f"把{question.rstrip('？?。')}整理成业务可读的结果")

    return variants[:2 if focus else 1]


def build_distribution(items: list[dict[str, Any]], field: str) -> dict[str, int]:
    """统计列表中字典字段的分布。"""
    return dict(Counter(str(item.get(field, "unknown")) for item in items))


def extract_years(question: str) -> list[int]:
    """从中文问题中提取年份。"""
    years = [int(year) for year in re.findall(r"(20\d{2})\s*年?", question)]
    # 兼容业务手工输入的“025年”这类多打 0 的年份写法，按 2025 年理解。
    typo_short_years = [2000 + int(year) for year in re.findall(r"(?<!\d)0(2[3-6])\s*年", question)]
    short_years = [2000 + int(year) for year in re.findall(r"(?<!\d)(2[3-6])\s*年", question)]
    return sorted(set(years + typo_short_years + short_years))


def extract_months(question: str) -> list[int]:
    """从中文问题中提取月份，兼容 1 到 3 月、1-3 月和单月表达。"""
    months: set[int] = set()
    range_match = re.search(r"(\d{1,2})\s*(?:到|至|-|—|~)\s*(\d{1,2})\s*月", question)
    if range_match:
        start, end = int(range_match.group(1)), int(range_match.group(2))
        if 1 <= start <= end <= 12:
            months.update(range(start, end + 1))
    for value in re.findall(r"(\d{1,2})\s*月", question):
        month = int(value)
        if 1 <= month <= 12:
            months.add(month)
    quarter_match = re.search(r"(?:第?\s*([一二三四1234])\s*季度|Q([1-4]))", question, re.IGNORECASE)
    if quarter_match:
        raw = quarter_match.group(1) or quarter_match.group(2)
        quarter_map = {"一": 1, "二": 2, "三": 3, "四": 4}
        quarter = int(quarter_map.get(raw, raw))
        months.update({quarter * 3 - 2, quarter * 3 - 1, quarter * 3})
    return sorted(months)


def extract_top_n(question: str) -> int | None:
    """提取 TopN 限制。"""
    numeric = re.search(r"(?:top|前)\s*(\d+)", question, re.IGNORECASE)
    if numeric:
        return int(numeric.group(1))
    cn_map = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}
    matched = re.search(r"前([一二三四五六七八九十])", question)
    if matched:
        return cn_map[matched.group(1)]
    return None


def sanitize_filename(value: str, *, max_length: int = 80) -> str:
    """把问题编号等文本转换成安全文件名。"""
    cleaned = re.sub(r"[^0-9A-Za-z_\-\u4e00-\u9fff]+", "_", value).strip("_")
    return cleaned[:max_length] or "case"
