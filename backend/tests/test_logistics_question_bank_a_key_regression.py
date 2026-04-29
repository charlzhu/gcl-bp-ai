from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path("/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai")
KEY_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/question_bank_a_key_questions.json"
CLASSIFICATION_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_question_bank_classification.json"


def test_a_key_question_config_points_to_a_class_items() -> None:
    """验证关键题黄金断言清单只引用当前 A 类题。

    说明：
        1. 当前关键题集必须来源于已完成的 A 类分层结果；
        2. 不允许人为把 B/C 类题混进精确断言回归；
        3. 这里优先校验 question_bank_id 与分类结果的一致性。
    """
    key_items = json.loads(KEY_PATH.read_text(encoding="utf-8"))
    classification_items = {
        item["question_id"]: item
        for item in json.loads(CLASSIFICATION_PATH.read_text(encoding="utf-8"))["items"]
    }
    assert len(key_items) == 20
    for item in key_items:
        cls_item = classification_items[item["question_bank_id"]]
        assert cls_item["classification"] == "A"
        assert cls_item["query_key"] == item["query_key"]


def test_a_key_question_config_has_unique_acceptance_ids() -> None:
    """验证关键题清单不会重复引用同一条官方验收题。"""
    key_items = json.loads(KEY_PATH.read_text(encoding="utf-8"))
    acceptance_ids = [item["acceptance_id"] for item in key_items]
    assert len(acceptance_ids) == len(set(acceptance_ids))
