from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

BASE_DIR = Path("/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai")
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.question_bank_response_policy import LogisticsQuestionBankResponsePolicy

CLASSIFICATION_PATH = BASE_DIR / "tmp/logistics_question_bank/logistics_question_bank_classification.json"
OUTPUT_PATH = BASE_DIR / "tmp/logistics_question_bank/logistics_question_bank_b_clarification_templates.json"


def build_report() -> dict:
    """构建 B 类题澄清模板覆盖报告。

    说明：
        1. 当前只统计题库里已判定为 B 类的问题；
        2. 若命中响应策略模块中的 clarification 分类，则视为“业务化澄清模板”；
        3. 若 planner 最终仍走通用兜底澄清，则归入 generic_fallback，便于下一批继续细化。
    """

    classification_data = json.loads(CLASSIFICATION_PATH.read_text())
    items = classification_data["items"]
    planner = LogisticsDataQaPlanner()
    policy = LogisticsQuestionBankResponsePolicy()

    business_template_items: list[dict] = []
    generic_fallback_items: list[dict] = []
    category_examples: dict[str, list[dict]] = defaultdict(list)
    category_counter: Counter[str] = Counter()
    anomalies: list[dict] = []

    for item in items:
        if item.get("classification") != "B":
            continue

        question = item["question"]
        decision = policy.match(question)
        plan = planner.build_plan(question)

        if plan.intent != "clarification":
            anomalies.append(
                {
                    "question_id": item["question_id"],
                    "question": question,
                    "actual_intent": plan.intent,
                }
            )
            continue

        record = {
            "question_id": item["question_id"],
            "question": question,
            "source_group": item["source_group"],
            "category_label": item["category_label"],
            "clarification_questions": plan.clarification_questions,
        }

        if decision and decision.decision_type == "clarification":
            record["clarification_mode"] = "business_template"
            record["policy_category"] = decision.category
            business_template_items.append(record)
            category_counter[decision.category] += 1
            if len(category_examples[decision.category]) < 6:
                category_examples[decision.category].append(
                    {
                        "question_id": item["question_id"],
                        "question": question,
                    }
                )
        else:
            record["clarification_mode"] = "generic_fallback"
            record["policy_category"] = None
            generic_fallback_items.append(record)

    return {
        "classification_source": str(CLASSIFICATION_PATH),
        "summary": {
            "total_b_questions": len(business_template_items) + len(generic_fallback_items),
            "business_template_count": len(business_template_items),
            "generic_fallback_count": len(generic_fallback_items),
            "anomaly_count": len(anomalies),
            "business_category_breakdown": dict(category_counter),
        },
        "implemented_batches": [
            {
                "batch_name": "第一批已细化",
                "categories": [
                    "missing_time_for_metric",
                    "vague_status",
                    "special_case",
                    "transport_record_scope",
                    "product_spec_scope",
                    "high_fee_address_scope",
                    "state_breakdown_scope",
                    "breakdown_scope",
                ],
            },
            {
                "batch_name": "第二批建议继续细化",
                "focus": [
                    "仍落在通用澄清的复杂多维拆分题",
                    "仍缺少稳定口径定义的综合比较题",
                    "虽然应澄清但还没有专属追问模板的边界题",
                ],
            },
        ],
        "business_template_examples": dict(category_examples),
        "generic_fallback_examples": generic_fallback_items[:20],
        "anomalies": anomalies,
    }


def main() -> None:
    """生成 B 类题澄清模板覆盖报告。"""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(build_report(), ensure_ascii=False, indent=2))
    print(f"已生成报告：{OUTPUT_PATH}")


if __name__ == "__main__":
    main()
