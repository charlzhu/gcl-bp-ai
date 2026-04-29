from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLASSIFICATION_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_question_bank_classification.json"
TOP200_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_top200_questions.json"
TOP200_P12_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_top200_p1_p2_regression_report.json"
ROUND_REPORT_TEMPLATE = "tmp/logistics_question_bank/logistics_top200_b_factory_round{round_no}_report.json"
A_BEHAVIOR_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_question_bank_A_regression_report.json"
A_KEY_PRECISE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/question_bank_a_key_questions.json"
ROUND45_PRECISE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_round45_new_a_precise_questions.json"
P1P2_PRECISE_BASELINE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_top200_p1_p2_a_precise_baseline.json"
ASTABILITY_ROUND1_PRECISE_BASELINE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_a_stability_round1_precise_baseline.json"
ASTABILITY_ROUND2_PRECISE_BASELINE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_a_stability_round2_precise_baseline.json"
ASTABILITY_ROUND3_PRECISE_BASELINE_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_a_stability_round3_precise_baseline.json"
C2A_PRECISE_REPORT_TEMPLATE = "tmp/logistics_question_bank/logistics_c2a_p{round_no}_precise_regression_report.json"
B2A_PRECISE_REPORT_TEMPLATE = "tmp/logistics_question_bank/logistics_b2a_p{round_no}_precise_regression_report.json"
TOPN_V2_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_topn_v2_questions.json"
B_LONG_ROUND5_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_b_long_clarification_round5_report.json"
C_ROUND2_MIGRATION_CANDIDATES_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_c_boundary_round2_migration_candidates.json"
)
C_ROUND2_A_CANDIDATE_QUESTIONS_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_c_round2_a_candidate_questions.json"
)
C_ROUND2_ACCEPTED_MIGRATION_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_c_round2_accepted_migration.json"
)
B2A_MIGRATION_CANDIDATES_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b2a_migration_review_candidates.json"
)
B_GAP_WAVE1_MIGRATION_CANDIDATES_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave1_migration_candidates.json"
)
B_GAP_WAVE1_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_gap_wave1_report.json"
B_GAP_WAVE2_MIGRATION_CANDIDATES_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave2_migration_candidates.json"
)
B_GAP_WAVE2_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_gap_wave2_report.json"
B_GAP_WAVE3_MIGRATION_CANDIDATES_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave3_migration_candidates.json"
)
B_GAP_WAVE3_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_gap_wave3_report.json"
B_GAP_WAVE4_MIGRATION_CANDIDATES_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave4_migration_candidates.json"
)
B_GAP_WAVE4_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_gap_wave4_report.json"
B_GAP_WAVE5_MIGRATION_CANDIDATES_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_b_gap_wave5_migration_candidates.json"
)
B_GAP_WAVE5_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_b_wave5_executable_review_report.json"
A_PRECISE_WAVE3_BATCH1_BASELINE_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_a_precise_wave3_batch1_baseline.json"
)
A_PRECISE_WAVE4_BATCH2_BASELINE_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_a_precise_wave4_batch2_baseline.json"
)
A_PRECISE_WAVE5_BATCH3_BASELINE_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_a_precise_wave5_batch3_baseline.json"
)
A_PRECISE_ACCEPTANCE_BATCH4_BASELINE_PATH = (
    PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_a_precise_acceptance_batch4_baseline.json"
)

MASTER_LEDGER_CONFIG_PATH = PROJECT_ROOT / "backend/app/domains/logistics/config/logistics_903_master_ledger.json"
MASTER_LEDGER_REPORT_PATH = PROJECT_ROOT / "tmp/logistics_question_bank/logistics_903_master_ledger_report.json"
MASTER_LEDGER_DOC_PATH = PROJECT_ROOT / "docs/LOGISTICS_903_CLOSURE_MASTER_LEDGER.md"


def _load_json(path: Path) -> Any:
    """读取 JSON 文件。"""

    return json.loads(path.read_text(encoding="utf-8"))


def _contains_any(text: str, keywords: list[str]) -> bool:
    """判断文本中是否包含任一关键词。"""

    return any(keyword in text for keyword in keywords)


def _derive_family(question: str) -> str:
    """给问题归并题族，便于全量治理时按族推进。"""

    if _contains_any(question, ["预测", "预计", "波动区间", "相关性", "离群点", "模型", "治理原则", "ETA", "到达时间", "在途"]):
        return "预测/诊断/开放讨论类"
    if _contains_any(question, ["客户", "项目", "项目地", "收货地址"]):
        return "客户/项目分析类"
    if _contains_any(question, ["承运商", "物流公司", "物流供应商", "签收率"]):
        return "承运商经营与排名类"
    if _contains_any(question, ["始发", "发往", "线路", "城市", "17.5", "13m", "运价", "单车均价"]):
        return "线路/城市运价类"
    if _contains_any(question, ["运输方式", "公路", "铁路", "水路", "多式联运"]):
        return "运输方式分析类"
    if _contains_any(question, ["区域", "省", "基地"]) and _contains_any(question, ["发运量", "运量", "MW", "费用", "运费"]):
        return "区域/省份/基地汇总类"
    if _contains_any(question, ["状态", "任务", "填充率", "解析成功率", "assign_detail", "supplier_price", "mapping"]):
        return "2026系统状态与数据质量类"
    if _contains_any(question, ["经营计划", "辅料送样", "刘娟"]):
        return "特殊业务口径类"
    return "综合统计类"


def _derive_theme_tags(question: str) -> list[str]:
    """给问题打主题标签。"""

    tags: list[str] = []
    if _contains_any(question, ["发运量", "运量", "MW", "总瓦数", "瓦数", "车次", "总车数", "车辆数"]):
        tags.append("运量/车次类")
    if _contains_any(question, ["运费", "费用", "总费用", "总运费", "元/瓦", "元瓦", "单瓦"]):
        tags.append("费用/成本类")
    if _contains_any(question, ["承运商", "物流公司", "物流供应商", "签收率"]):
        tags.append("承运商类")
    if _contains_any(question, ["客户", "项目", "项目地", "收货地址"]):
        tags.append("客户/项目类")
    if _contains_any(question, ["区域", "省", "城市", "基地"]):
        tags.append("区域/省份类")
    if _contains_any(question, ["排名", "前五", "前十", "后十", "最高", "最低"]):
        tags.append("排名类")
    if _contains_any(question, ["2026", "26年", "任务", "填充率", "解析成功率"]):
        tags.append("2026系统类")
    if _contains_any(question, ["预测", "预计", "波动区间", "相关性", "离群点", "模型", "治理原则"]):
        tags.append("预测/诊断类")
    return sorted(set(tags)) or ["其他"]


def _load_current_top200_state() -> dict[str, dict[str, Any]]:
    """还原当前 Top200 真实状态。

    说明：
        1. 原始 Top200 配置只代表最初选入时的分类；
        2. 当前真实状态需要叠加 P1/P2 收口结果和 Round1～Round5 的最终迁移结果；
        3. 后续 903 总台账也必须以这里的最终状态为准，而不是回退到最初 Top200 配置。
    """

    top200_items = {
        item["question_id"]: dict(item)
        for item in _load_json(TOP200_CONFIG_PATH)["items"]
    }
    for item in top200_items.values():
        item["final_status"] = item["current_classification"]
        item["final_reason"] = item.get("current_blocker_reason") or ""
        item["final_query_key"] = item.get("query_key")

    p12_items = _load_json(TOP200_P12_REPORT_PATH)["b_closure_progress"]["items"]
    for record in p12_items:
        top200_items[record["question_id"]]["final_status"] = {
            "promoted_to_a": "A",
            "remain_b": "B",
            "moved_to_c": "C",
        }[record["closure_result"]]
        top200_items[record["question_id"]]["final_reason"] = record["closure_reason"]
        if record.get("actual_query_key"):
            top200_items[record["question_id"]]["final_query_key"] = record["actual_query_key"]

    for round_no in range(1, 6):
        round_items = _load_json(PROJECT_ROOT / ROUND_REPORT_TEMPLATE.format(round_no=round_no))["items"]
        for record in round_items:
            top200_items[record["question_id"]]["final_status"] = record["final_classification"]
            top200_items[record["question_id"]]["final_reason"] = record["closure_reason"]
            if record.get("actual_query_key"):
                top200_items[record["question_id"]]["final_query_key"] = record["actual_query_key"]

    return top200_items


def _load_precise_ids() -> set[str]:
    """读取已经进入更严格精确断言的题号集合。"""

    precise_ids: set[str] = set()
    for path in (A_KEY_PRECISE_PATH, ROUND45_PRECISE_PATH):
        for item in _load_json(path):
            question_id = item.get("question_id") or item.get("question_bank_id")
            if question_id:
                precise_ids.add(question_id)
    for item in _load_json(P1P2_PRECISE_BASELINE_PATH)["items"]:
        question_id = item.get("question_id") or item.get("question_bank_id")
        if question_id:
            precise_ids.add(question_id)
    for path in (
        ASTABILITY_ROUND1_PRECISE_BASELINE_PATH,
        ASTABILITY_ROUND2_PRECISE_BASELINE_PATH,
        ASTABILITY_ROUND3_PRECISE_BASELINE_PATH,
    ):
        if path.exists():
            for item in _load_json(path)["items"]:
                question_id = item.get("question_id") or item.get("question_bank_id")
                if question_id:
                    precise_ids.add(question_id)
    for round_no in range(1, 5):
        report_path = PROJECT_ROOT / C2A_PRECISE_REPORT_TEMPLATE.format(round_no=round_no)
        if not report_path.exists():
            continue
        # C2A 报告里只把通过精确断言的题纳入 precise。
        # 例如 P3 中 2 条预测题应回到 C 边界，不能仅因生成过基线就算作 A 精确断言。
        for item in _load_json(report_path).get("items", []):
            if item.get("passed") is True and item.get("question_id"):
                precise_ids.add(item["question_id"])
    for round_no in range(1, 4):
        report_path = PROJECT_ROOT / B2A_PRECISE_REPORT_TEMPLATE.format(round_no=round_no)
        if not report_path.exists():
            continue
        # B2A 精确断言只有通过项才算正式进入更严格基线，失败项不能被总账标记为 precise。
        for item in _load_json(report_path).get("items", []):
            if item.get("passed") is True and item.get("question_id"):
                precise_ids.add(item["question_id"])
    if A_PRECISE_WAVE3_BATCH1_BASELINE_PATH.exists():
        # Wave3 A 精确增强批次使用当前主链路生成黄金基线；只有基线存在才纳入总账 precise 标记。
        for item in _load_json(A_PRECISE_WAVE3_BATCH1_BASELINE_PATH).get("items", []):
            if item.get("question_id"):
                precise_ids.add(item["question_id"])
    if A_PRECISE_WAVE4_BATCH2_BASELINE_PATH.exists():
        # Wave4 A 精确增强 Batch2 继续使用主链路黄金基线，避免新增 A 只停留在行为回归层。
        for item in _load_json(A_PRECISE_WAVE4_BATCH2_BASELINE_PATH).get("items", []):
            if item.get("question_id"):
                precise_ids.add(item["question_id"])
    if A_PRECISE_WAVE5_BATCH3_BASELINE_PATH.exists():
        # Wave5 A 精确增强 Batch3 继续扩大当前 A=656 的黄金答案覆盖面。
        for item in _load_json(A_PRECISE_WAVE5_BATCH3_BASELINE_PATH).get("items", []):
            if item.get("question_id"):
                precise_ids.add(item["question_id"])
    if A_PRECISE_ACCEPTANCE_BATCH4_BASELINE_PATH.exists():
        # 验收交付版 Batch4 继续扩大 A=656 的精确答案覆盖面，服务试运行交付。
        for item in _load_json(A_PRECISE_ACCEPTANCE_BATCH4_BASELINE_PATH).get("items", []):
            if item.get("question_id"):
                precise_ids.add(item["question_id"])
    return precise_ids


def _load_behavior_regression_ids() -> set[str]:
    """读取已进入 A 类行为级自动回归的题号集合。"""

    return {
        item["question_id"]
        for item in _load_json(A_BEHAVIOR_REPORT_PATH)["items"]
    }


def _load_topn_v2_items() -> dict[str, dict[str, Any]]:
    """读取 TopN v2 清单。"""

    payload = _load_json(TOPN_V2_CONFIG_PATH)
    return {item["question_id"]: item for item in payload["items"]}


def _load_b_long_round5_items() -> dict[tuple[str, str], dict[str, Any]]:
    """读取 B-长期澄清池 Round5 收尾结论。

    说明：
        1. Round5 会把尾部题分流为继续澄清、迁入 A、转入 C；
        2. 台账必须按“题号 + 原题”覆盖，避免重复题号被错误合并；
        3. 如果报告尚不存在，则不影响总台账生成。
    """

    if not B_LONG_ROUND5_REPORT_PATH.exists():
        return {}
    payload = _load_json(B_LONG_ROUND5_REPORT_PATH)
    return {
        (item["question_id"], item["question"]): item
        for item in payload.get("items", [])
    }


def _load_c_round2_migration_items() -> dict[tuple[str, str], dict[str, Any]]:
    """读取 C Round2 迁移复核候选。

    说明：
        1. A_candidate 只代表 planner 当前可答，必须结合行为回归通过结果才能迁入 A；
        2. B_candidate 代表当前应从 C 迁回 B，并进入后续澄清模板复检；
        3. 仍按“题号 + 原题”定位，避免重复题号导致误迁移。
    """

    source_path = (
        C_ROUND2_ACCEPTED_MIGRATION_PATH
        if C_ROUND2_ACCEPTED_MIGRATION_PATH.exists()
        else C_ROUND2_MIGRATION_CANDIDATES_PATH
    )
    if not source_path.exists():
        return {}
    payload = _load_json(source_path)
    return {
        (item["question_id"], item["question"]): item
        for item in payload.get("items", [])
    }


def _load_c_round2_passed_a_items() -> dict[tuple[str, str], dict[str, Any]]:
    """读取 C Round2 已通过行为回归的 A_candidate。

    说明：
        只有通过真实行为回归的 A_candidate 才允许写入正式总账 A 类；
        未通过或缺失回归记录的题，不能只凭静态候选结果迁入 A。
    """

    if C_ROUND2_ACCEPTED_MIGRATION_PATH.exists():
        payload = _load_json(C_ROUND2_ACCEPTED_MIGRATION_PATH)
        return {
            (item["question_id"], item["question"]): item
            for item in payload.get("items", [])
            if item.get("migration_type") == "A_candidate"
            and item.get("accepted_status") == "A"
            and item.get("passed") is True
        }

    if not C_ROUND2_A_CANDIDATE_QUESTIONS_PATH.exists():
        return {}
    payload = _load_json(C_ROUND2_A_CANDIDATE_QUESTIONS_PATH)
    return {
        (item["question_id"], item["question"]): item
        for item in payload.get("items", [])
        if item.get("passed") is True
    }


def _load_b2a_migration_items() -> dict[tuple[str, str], dict[str, Any]]:
    """读取 B->A 已通过行为复核并允许正式迁移的候选。

    说明：
        1. 这 85 条来自 903 全量语义回归后的真实 data-qa 行为复核；
        2. 后续重建总账时必须吸收这份配置，否则会把已迁入 A 的题回滚到 B；
        3. 只读取 recommended_status=A 的题，数据基线阻塞题不会进入该配置。
    """

    if not B2A_MIGRATION_CANDIDATES_PATH.exists():
        return {}
    payload = _load_json(B2A_MIGRATION_CANDIDATES_PATH)
    return {
        (item["question_id"], item["question"]): item
        for item in payload.get("items", [])
        if item.get("recommended_status") == "A"
    }


def _load_b_gap_wave1_migration_items() -> dict[tuple[str, str], dict[str, Any]]:
    """读取 B-gap Wave1 已通过行为复核并允许正式迁移的候选。

    说明：
        1. 这批题来自 P1 query_key_gap 能力建设后的真实 data-qa 复核；
        2. 后续重建总账时必须吸收这份配置，否则会把已迁入 A 的题回滚到 B；
        3. 只读取 recommended_status=A 的题，仍需澄清或缺数据/业务口径的题不会进入该配置。
    """

    if not B_GAP_WAVE1_MIGRATION_CANDIDATES_PATH.exists():
        return {}
    payload = _load_json(B_GAP_WAVE1_MIGRATION_CANDIDATES_PATH)
    return {
        (item["question_id"], item["question"]): item
        for item in payload.get("items", [])
        if item.get("recommended_status") == "A"
    }


def _load_b_gap_wave1_summary() -> dict[str, Any]:
    """读取 B-gap Wave1 专项报告汇总，保证总账报告与专项报告计数一致。"""

    if not B_GAP_WAVE1_REPORT_PATH.exists():
        return {}
    payload = _load_json(B_GAP_WAVE1_REPORT_PATH)
    return payload.get("summary", {})


def _load_b_gap_wave2_migration_items() -> dict[tuple[str, str], dict[str, Any]]:
    """读取 B-gap Wave2 已通过行为复核并允许正式迁移的候选。

    说明：
        1. Wave2 面向剩余 B 类 P1/P2 query_key_gap 继续收口；
        2. 只有真实 data-qa 行为回归通过的题才允许迁入 A；
        3. 读取时仍按“题号 + 原题”定位，避免重复题号误迁移。
    """

    if not B_GAP_WAVE2_MIGRATION_CANDIDATES_PATH.exists():
        return {}
    payload = _load_json(B_GAP_WAVE2_MIGRATION_CANDIDATES_PATH)
    return {
        (item["question_id"], item["question"]): item
        for item in payload.get("items", [])
        if item.get("recommended_status") == "A"
    }


def _load_b_gap_wave2_summary() -> dict[str, Any]:
    """读取 B-gap Wave2 专项报告汇总，保证总账报告与专项报告计数一致。"""

    if not B_GAP_WAVE2_REPORT_PATH.exists():
        return {}
    payload = _load_json(B_GAP_WAVE2_REPORT_PATH)
    return payload.get("summary", {})


def _load_b_gap_wave3_migration_items() -> dict[tuple[str, str], dict[str, Any]]:
    """读取 B-gap Wave3 已通过行为复核并允许正式迁移的候选。

    说明：
        1. Wave3 面向剩余 B 类中可工程化修复的 query_key_gap 继续收口；
        2. 只有真实 data-qa 行为回归通过的题才允许迁入 A；
        3. 读取时仍按“题号 + 原题”定位，避免重复题号误迁移。
    """

    if not B_GAP_WAVE3_MIGRATION_CANDIDATES_PATH.exists():
        return {}
    payload = _load_json(B_GAP_WAVE3_MIGRATION_CANDIDATES_PATH)
    return {
        (item["question_id"], item["question"]): item
        for item in payload.get("items", [])
        if item.get("recommended_status") == "A"
    }


def _load_b_gap_wave3_summary() -> dict[str, Any]:
    """读取 B-gap Wave3 专项报告汇总，保证总账报告与专项报告计数一致。"""

    if not B_GAP_WAVE3_REPORT_PATH.exists():
        return {}
    payload = _load_json(B_GAP_WAVE3_REPORT_PATH)
    return payload.get("summary", {})


def _load_b_gap_wave4_migration_items() -> dict[tuple[str, str], dict[str, Any]]:
    """读取 B-gap Wave4 已通过行为复核并允许正式迁移的候选。

    说明：
        1. Wave4 面向剩余 B=182 做最终分层和可工程化缺口补齐；
        2. 只有真实 data-qa 行为回归通过的题才允许迁入 A；
        3. 读取时仍按“题号 + 原题”定位，避免重复题号误迁移。
    """

    if not B_GAP_WAVE4_MIGRATION_CANDIDATES_PATH.exists():
        return {}
    payload = _load_json(B_GAP_WAVE4_MIGRATION_CANDIDATES_PATH)
    return {
        (item["question_id"], item["question"]): item
        for item in payload.get("items", [])
        if item.get("recommended_status") == "A"
    }


def _load_b_gap_wave4_summary() -> dict[str, Any]:
    """读取 B-gap Wave4 专项报告汇总，保证总账报告与专项报告计数一致。"""

    if not B_GAP_WAVE4_REPORT_PATH.exists():
        return {}
    payload = _load_json(B_GAP_WAVE4_REPORT_PATH)
    return payload.get("summary", {})


def _load_b_gap_wave5_migration_items() -> dict[tuple[str, str], dict[str, Any]]:
    """读取 B-gap Wave5 已通过行为复核并允许正式迁移的候选。

    说明：
        Wave5 重点是剩余 B=178 的追问闭环和最终可执行性复核；如果脚本发现
        真实链路已经稳定可答的题，才允许通过该配置写入总账 A 类。
    """

    if not B_GAP_WAVE5_MIGRATION_CANDIDATES_PATH.exists():
        return {}
    payload = _load_json(B_GAP_WAVE5_MIGRATION_CANDIDATES_PATH)
    return {
        (item["question_id"], item["question"]): item
        for item in payload.get("items", [])
        if item.get("recommended_status") == "A"
    }


def _load_b_gap_wave5_summary() -> dict[str, Any]:
    """读取 B-gap Wave5 专项报告汇总，保证总账报告与专项报告计数一致。"""

    if not B_GAP_WAVE5_REPORT_PATH.exists():
        return {}
    payload = _load_json(B_GAP_WAVE5_REPORT_PATH)
    return payload.get("summary", {})


def _derive_pool(
    current_status: str,
    in_topn_v2: bool,
    topn_item: dict[str, Any] | None,
) -> str:
    """把题目切进四个治理池。"""

    if current_status == "A":
        return "A-稳定增强池"
    if current_status == "B":
        if in_topn_v2 and topn_item and topn_item["lane"] == "B-候选收口":
            return "B-候选收口池"
        return "B-长期澄清池"
    if current_status == "C":
        return "C-边界观察池"
    return "D-待业务/数据修订池"


def _derive_next_action(pool_name: str, current_status: str, in_precise: bool) -> str:
    """生成下一处理动作。"""

    if pool_name == "A-稳定增强池":
        if in_precise:
            return "保持当前 A 类稳定支持，并纳入固定复检流程。"
        return "优先纳入更严格精确断言或更稳定的鲁棒性回归。"
    if pool_name == "B-候选收口池":
        return "按题族和能力矩阵进入下一波批量收口，成熟后再推进进 A。"
    if pool_name == "B-长期澄清池":
        return "继续保持业务化澄清，不强行推进进 A。"
    if pool_name == "C-边界观察池":
        return "保持不支持边界，等待业务口径或数据条件成熟后再议。"
    return "需要业务或数据 owner 先修订标准答案或统计口径。"


def _derive_blocker_reason(
    current_status: str,
    current_reason: str,
    question: str,
    in_precise: bool,
) -> str:
    """生成更适合总台账阅读的阻塞说明。"""

    if current_status == "A":
        if in_precise:
            return "当前已进入 A 且已纳入更严格精确断言。"
        return "当前已进入 A，但尚未纳入更严格精确断言。"
    if current_reason:
        return current_reason
    if current_status == "B":
        if not _contains_any(question, ["2023", "2024", "2025", "2026", "23年", "24年", "25年", "26年", "本月", "今年"]):
            return "缺少明确统计时间范围，当前仍需先澄清年份或月份。"
        if _contains_any(question, ["最近", "近期", "最差", "异常", "有没有问题", "哪些有问题"]):
            return "缺少评价标准或异常定义，当前仍需先澄清。"
        return "当前仍缺少关键统计口径，暂不宜直接推进。"
    if current_status == "C":
        return "当前问题超出现有物流结构化查询能力边界。"
    return "当前需要业务或数据 owner 先修订口径。"


def _derive_current_priority(
    question_id: str,
    top200_item: dict[str, Any] | None,
    topn_item: dict[str, Any] | None,
    current_status: str,
) -> str:
    """确定当前优先级。"""

    if topn_item:
        return topn_item["priority"]
    if top200_item:
        return top200_item["priority"]
    if current_status == "A":
        return "P2"
    return "P3"


def _rebuild_master_ledger() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """重建 903 全量总台账，并返回汇总信息。"""

    classification_payload = _load_json(CLASSIFICATION_PATH)
    raw_items = classification_payload["items"]
    baseline_distribution = classification_payload["summary"]["counts"]
    top200_items = _load_current_top200_state()
    behavior_regression_ids = _load_behavior_regression_ids()
    precise_ids = _load_precise_ids()
    topn_v2_items = _load_topn_v2_items()
    b_long_round5_items = _load_b_long_round5_items()
    c_round2_migration_items = _load_c_round2_migration_items()
    c_round2_passed_a_items = _load_c_round2_passed_a_items()
    b2a_migration_items = _load_b2a_migration_items()
    b_gap_wave1_migration_items = _load_b_gap_wave1_migration_items()
    b_gap_wave1_summary = _load_b_gap_wave1_summary()
    b_gap_wave2_migration_items = _load_b_gap_wave2_migration_items()
    b_gap_wave2_summary = _load_b_gap_wave2_summary()
    b_gap_wave3_migration_items = _load_b_gap_wave3_migration_items()
    b_gap_wave3_summary = _load_b_gap_wave3_summary()
    b_gap_wave4_migration_items = _load_b_gap_wave4_migration_items()
    b_gap_wave4_summary = _load_b_gap_wave4_summary()
    b_gap_wave5_migration_items = _load_b_gap_wave5_migration_items()
    b_gap_wave5_summary = _load_b_gap_wave5_summary()

    duplicate_counter = Counter(item["question_id"] for item in raw_items)
    duplicate_ids = {question_id for question_id, count in duplicate_counter.items() if count > 1}

    master_items: list[dict[str, Any]] = []
    migration_counter: Counter[str] = Counter()
    pool_counter: Counter[str] = Counter()
    unique_pool_members: defaultdict[str, set[str]] = defaultdict(set)
    theme_counter: Counter[str] = Counter()
    current_distribution: Counter[str] = Counter()
    unique_distribution_members: defaultdict[str, set[str]] = defaultdict(set)

    for index, raw_item in enumerate(raw_items, start=1):
        question_id = raw_item["question_id"]
        top200_item = top200_items.get(question_id)
        topn_item = topn_v2_items.get(question_id)
        b_long_round5_item = b_long_round5_items.get((question_id, raw_item["question"]))
        c_round2_migration_item = c_round2_migration_items.get((question_id, raw_item["question"]))
        c_round2_passed_a_item = c_round2_passed_a_items.get((question_id, raw_item["question"]))
        b2a_migration_item = b2a_migration_items.get((question_id, raw_item["question"]))
        b_gap_wave1_migration_item = b_gap_wave1_migration_items.get((question_id, raw_item["question"]))
        b_gap_wave2_migration_item = b_gap_wave2_migration_items.get((question_id, raw_item["question"]))
        b_gap_wave3_migration_item = b_gap_wave3_migration_items.get((question_id, raw_item["question"]))
        b_gap_wave4_migration_item = b_gap_wave4_migration_items.get((question_id, raw_item["question"]))
        b_gap_wave5_migration_item = b_gap_wave5_migration_items.get((question_id, raw_item["question"]))

        current_status = top200_item["final_status"] if top200_item else raw_item["classification"]
        current_reason = top200_item["final_reason"] if top200_item else raw_item["reason"]
        current_query_key = top200_item["final_query_key"] if top200_item else raw_item.get("query_key")
        c_round2_migration_note = ""
        c_round2_next_action_override = ""
        b2a_migration_note = ""
        b2a_next_action_override = ""
        b_gap_wave1_migration_note = ""
        b_gap_wave1_next_action_override = ""
        b_gap_wave2_migration_note = ""
        b_gap_wave2_next_action_override = ""
        b_gap_wave3_migration_note = ""
        b_gap_wave3_next_action_override = ""
        b_gap_wave4_migration_note = ""
        b_gap_wave4_next_action_override = ""
        b_gap_wave5_migration_note = ""
        b_gap_wave5_next_action_override = ""
        if not top200_item and b_long_round5_item:
            current_status = b_long_round5_item["final_status"]
            current_reason = b_long_round5_item["closure_reason"]
            current_query_key = b_long_round5_item.get("actual_query_key") or current_query_key
        if c_round2_passed_a_item:
            current_status = "A"
            current_reason = "C Round2 A_candidate 已通过行为回归，迁入 A 类；后续需挑选高价值题进入精确断言。"
            current_query_key = (
                c_round2_passed_a_item.get("actual_query_key")
                or c_round2_passed_a_item.get("expected_query_key")
                or current_query_key
            )
            c_round2_migration_note = "C Round2 A_candidate 行为回归已通过，已从旧 C 迁入 A。"
            c_round2_next_action_override = "纳入新增 A 精确断言候选池，按业务价值分批建立更严格基线。"
        elif (
            c_round2_migration_item
            and c_round2_migration_item.get("migration_type") == "B_candidate"
        ):
            current_status = "B"
            current_reason = "C Round2 迁移复核判定当前应返回澄清，迁入 B 类并纳入后续澄清模板复检。"
            current_query_key = None
            c_round2_migration_note = "C Round2 B_candidate 已从旧 C 迁入 B，后续纳入澄清模板复检。"
            c_round2_next_action_override = "纳入 B_candidate 澄清模板复检，优先优化业务化追问而不是强行回答。"
        if b2a_migration_item:
            current_status = "A"
            current_reason = "B->A 迁移复核已通过，当前已进入 A；尚未纳入更严格精确断言。"
            current_query_key = b2a_migration_item.get("query_key") or current_query_key
            b2a_migration_note = "B->A 迁移复核通过并正式迁入 A。"
            b2a_next_action_override = "纳入新增 A 行为回归固定集，并按 B2A-P1/P2/P3 建立更严格精确断言。"
        if b_gap_wave1_migration_item:
            current_status = "A"
            current_reason = "B-gap Wave1 P1 query_key_gap 迁移复核已通过，当前已进入 A；后续需纳入新增 A 行为回归和精确断言候选池。"
            current_query_key = b_gap_wave1_migration_item.get("query_key") or current_query_key
            b_gap_wave1_migration_note = "B-gap Wave1 行为复核通过并正式迁入 A。"
            b_gap_wave1_next_action_override = "纳入 B-gap Wave1 新增 A 行为回归固定集，并按价值分批建立更严格精确断言。"
        if b_gap_wave2_migration_item:
            current_status = "A"
            current_reason = "B-gap Wave2 P1/P2 query_key_gap 迁移复核已通过，当前已进入 A；后续需纳入新增 A 行为回归和精确断言候选池。"
            current_query_key = b_gap_wave2_migration_item.get("query_key") or current_query_key
            b_gap_wave2_migration_note = "B-gap Wave2 行为复核通过并正式迁入 A。"
            b_gap_wave2_next_action_override = "纳入 B-gap Wave2 新增 A 行为回归固定集，并按价值分批建立更严格精确断言。"
        if b_gap_wave3_migration_item:
            current_status = "A"
            current_reason = "B-gap Wave3 query_key_gap 工程修复与迁移复核已通过，当前已进入 A；后续需纳入新增 A 行为回归和精确断言候选池。"
            current_query_key = b_gap_wave3_migration_item.get("query_key") or current_query_key
            b_gap_wave3_migration_note = "B-gap Wave3 行为复核通过并正式迁入 A。"
            b_gap_wave3_next_action_override = "纳入 B-gap Wave3 新增 A 行为回归固定集，并按价值分批建立更严格精确断言。"
        if b_gap_wave4_migration_item:
            current_status = "A"
            current_reason = "B-gap Wave4 最终分层和可工程化收口复核已通过，当前已进入 A；后续需纳入新增 A 行为回归和精确断言候选池。"
            current_query_key = b_gap_wave4_migration_item.get("query_key") or current_query_key
            b_gap_wave4_migration_note = "B-gap Wave4 行为复核通过并正式迁入 A。"
            b_gap_wave4_next_action_override = "纳入 B-gap Wave4 新增 A 行为回归固定集，并按价值分批建立更严格精确断言。"
        if b_gap_wave5_migration_item:
            current_status = "A"
            current_reason = "B-gap Wave5 最终可执行性复核已通过，当前已进入 A；后续需纳入新增 A 行为回归和精确断言候选池。"
            current_query_key = b_gap_wave5_migration_item.get("query_key") or current_query_key
            b_gap_wave5_migration_note = "B-gap Wave5 行为复核通过并正式迁入 A。"
            b_gap_wave5_next_action_override = "纳入 B-gap Wave5 新增 A 行为回归固定集，并按价值分批建立更严格精确断言。"
        in_behavior_regression = (
            question_id in behavior_regression_ids
            or c_round2_passed_a_item is not None
            or b2a_migration_item is not None
            or b_gap_wave1_migration_item is not None
            or b_gap_wave2_migration_item is not None
            or b_gap_wave3_migration_item is not None
            or b_gap_wave4_migration_item is not None
            or b_gap_wave5_migration_item is not None
        )
        in_precise_assertion = question_id in precise_ids
        in_top200 = question_id in top200_items
        in_topn_v2 = question_id in topn_v2_items
        pool_name = _derive_pool(current_status, in_topn_v2, topn_item)
        current_priority = _derive_current_priority(question_id, top200_item, topn_item, current_status)
        family = _derive_family(raw_item["question"])
        theme_tags = _derive_theme_tags(raw_item["question"])

        baseline_status = raw_item["classification"]
        migration_counter[f"{baseline_status}->{current_status}"] += 1
        pool_counter[pool_name] += 1
        current_distribution[current_status] += 1
        unique_distribution_members[current_status].add(question_id)
        unique_pool_members[pool_name].add(question_id)
        for tag in theme_tags:
            theme_counter[tag] += 1

        remarks = "题号在原始题库中重复出现，当前按逐条题目保留在总台账中。" if question_id in duplicate_ids else ""
        if c_round2_migration_note:
            remarks = "；".join(filter(None, [remarks, c_round2_migration_note]))
        if b2a_migration_note:
            remarks = "；".join(filter(None, [remarks, b2a_migration_note]))
        if b_gap_wave1_migration_note:
            remarks = "；".join(filter(None, [remarks, b_gap_wave1_migration_note]))
        if b_gap_wave2_migration_note:
            remarks = "；".join(filter(None, [remarks, b_gap_wave2_migration_note]))
        if b_gap_wave3_migration_note:
            remarks = "；".join(filter(None, [remarks, b_gap_wave3_migration_note]))
        if b_gap_wave4_migration_note:
            remarks = "；".join(filter(None, [remarks, b_gap_wave4_migration_note]))
        if b_gap_wave5_migration_note:
            remarks = "；".join(filter(None, [remarks, b_gap_wave5_migration_note]))

        master_items.append(
            {
                "ledger_index": index,
                "question_id": question_id,
                "question": raw_item["question"],
                "source_group": raw_item["source_group"],
                "source_label": raw_item["source_label"],
                "category_label": raw_item["category_label"],
                "difficulty": raw_item["difficulty"],
                "baseline_status": baseline_status,
                "current_status": current_status,
                "current_priority": current_priority,
                "family": family,
                "theme_tags": theme_tags,
                "current_query_key": current_query_key,
                "in_behavior_regression": in_behavior_regression,
                "in_precise_assertion": in_precise_assertion,
                "current_blocker_reason": _derive_blocker_reason(
                    current_status=current_status,
                    current_reason=current_reason,
                    question=raw_item["question"],
                    in_precise=in_precise_assertion,
                ),
                "next_action": b_gap_wave5_next_action_override
                or b_gap_wave4_next_action_override
                or b_gap_wave2_next_action_override
                or b_gap_wave3_next_action_override
                or b_gap_wave1_next_action_override
                or b2a_next_action_override
                or c_round2_next_action_override
                or _derive_next_action(
                    pool_name=pool_name,
                    current_status=current_status,
                    in_precise=in_precise_assertion,
                ),
                "in_top200": in_top200,
                "in_topn_v2": in_topn_v2,
                "topn_v2_lane": topn_item["lane"] if topn_item else None,
                "remarks": remarks,
                "governance_pool": pool_name,
            }
        )

    summary = {
        "raw_question_total": classification_payload["summary"]["total_questions"],
        "unique_question_id_total": len({item["question_id"] for item in raw_items}),
        "duplicate_question_ids": sorted(duplicate_ids),
        "baseline_distribution": baseline_distribution,
        "current_distribution": {
            status: current_distribution.get(status, 0)
            for status in ("A", "B", "C", "D")
        },
        "current_unique_distribution": {
            status: len(unique_distribution_members.get(status, set()))
            for status in ("A", "B", "C", "D")
        },
        "migration_breakdown": dict(migration_counter),
        "net_change_vs_baseline": {
            status: current_distribution.get(status, 0) - baseline_distribution.get(status, 0)
            for status in ("A", "B", "C", "D")
        },
        "pool_breakdown": {
            pool_name: pool_counter.get(pool_name, 0)
            for pool_name in (
                "A-稳定增强池",
                "B-候选收口池",
                "B-长期澄清池",
                "C-边界观察池",
                "D-待业务/数据修订池",
            )
        },
        "pool_unique_breakdown": {
            pool_name: len(unique_pool_members.get(pool_name, set()))
            for pool_name in (
                "A-稳定增强池",
                "B-候选收口池",
                "B-长期澄清池",
                "C-边界观察池",
                "D-待业务/数据修订池",
            )
        },
        "theme_breakdown": dict(theme_counter),
        "top200_net_impact": {
            "baseline_top200": {"A": 75, "B": 100, "C": 25},
            "current_top200": {"A": 170, "B": 0, "C": 30},
            "net_change": {"A": 95, "B": -100, "C": 5},
        },
        "c_round2_migration_impact": {
            "a_candidate_passed_to_a": len(c_round2_passed_a_items),
            "b_candidate_to_b": sum(
                1
                for item in c_round2_migration_items.values()
                if item.get("migration_type") == "B_candidate"
            ),
            "c_confirmed_remaining_c": current_distribution.get("C", 0),
            "distribution_after_migration": {
                status: current_distribution.get(status, 0)
                for status in ("A", "B", "C", "D")
            },
            "policy": "A_candidate 必须行为回归通过后才迁入 A；B_candidate 迁回 B 后纳入澄清模板复检；C_confirmed 继续保持拒答边界。",
        },
        "b2a_migration_review_impact": {
            "reviewed_candidates": 86,
            "migrated_to_a": len(b2a_migration_items),
            "kept_b_due_to_data_baseline": 1 if b2a_migration_items else 0,
            "distribution_after_migration": {
                status: current_distribution.get(status, 0)
                for status in ("A", "B", "C", "D")
            },
            "policy": "只有 903 语义回归识别且真实 data-qa 行为复核通过的 B->A 候选，才允许写入正式总账 A 类。",
        },
        "b_gap_wave1_migration_impact": {
            "reviewed_candidates": b_gap_wave1_summary.get("reviewed_questions", 0),
            "migrated_to_a": len(b_gap_wave1_migration_items),
            "remain_b": b_gap_wave1_summary.get("remain_b_total", 0),
            "distribution_after_migration": {
                status: current_distribution.get(status, 0)
                for status in ("A", "B", "C", "D")
            },
            "policy": "只有 B-gap Wave1 P1 query_key_gap 能力建设后真实 data-qa 行为复核通过的题，才允许写入正式总账 A 类。",
        },
        "b_gap_wave2_migration_impact": {
            "reviewed_candidates": b_gap_wave2_summary.get("reviewed_questions", 0),
            "candidate_pool_total": b_gap_wave2_summary.get("candidate_pool_total", 0),
            "candidate_pool_migrated_to_a": b_gap_wave2_summary.get("candidate_pool_migrated_to_a", 0),
            "candidate_pool_remain_b": b_gap_wave2_summary.get("candidate_pool_remain_b", 0),
            "migrated_to_a": len(b_gap_wave2_migration_items),
            "remain_b": b_gap_wave2_summary.get("remain_b_total", 0),
            "distribution_after_migration": {
                status: current_distribution.get(status, 0)
                for status in ("A", "B", "C", "D")
            },
            "policy": "只有 B-gap Wave2 P1/P2 query_key_gap 能力建设后真实 data-qa 行为复核通过的题，才允许写入正式总账 A 类。",
        },
        "b_gap_wave3_migration_impact": {
            "reviewed_candidates": b_gap_wave3_summary.get("reviewed_questions", 0),
            "migrated_to_a": len(b_gap_wave3_migration_items),
            "remain_b": b_gap_wave3_summary.get("remain_b_total", 0),
            "handled_capability_items": b_gap_wave3_summary.get("handled_capability_items", {}),
            "distribution_after_migration": {
                status: current_distribution.get(status, 0)
                for status in ("A", "B", "C", "D")
            },
            "policy": "只有 B-gap Wave3 query_key_gap 工程修复后真实 data-qa 行为复核通过的题，才允许写入正式总账 A 类。",
        },
        "b_gap_wave4_migration_impact": {
            "reviewed_candidates": b_gap_wave4_summary.get("reviewed_questions", 0),
            "migrated_to_a": len(b_gap_wave4_migration_items),
            "remain_b": b_gap_wave4_summary.get("remain_b_total", 0),
            "handled_capability_items": b_gap_wave4_summary.get("handled_capability_items", {}),
            "distribution_after_migration": {
                status: current_distribution.get(status, 0)
                for status in ("A", "B", "C", "D")
            },
            "policy": "只有 B-gap Wave4 最终分层和可工程化收口后真实 data-qa 行为复核通过的题，才允许写入正式总账 A 类。",
        },
        "b_gap_wave5_migration_impact": {
            "reviewed_candidates": b_gap_wave5_summary.get("total_b_questions", 0),
            "migrated_to_a": len(b_gap_wave5_migration_items),
            "remain_b": b_gap_wave5_summary.get("remain_b", 0),
            "c_review_candidates": b_gap_wave5_summary.get("c_review_candidates", 0),
            "distribution_after_migration": {
                status: current_distribution.get(status, 0)
                for status in ("A", "B", "C", "D")
            },
            "policy": "只有 B-gap Wave5 最终可执行性复核中真实 data-qa 主链路稳定可答的题，才允许写入正式总账 A 类；追问可答题原题仍保留 B。",
        },
        "recommended_next_pool": "A-稳定增强池 / B-长期澄清池",
        "recommended_next_pool_reason": (
            f"C Round2 迁移已把 {len(c_round2_passed_a_items)} 条 A_candidate 写入 A；"
            f"B->A 迁移复核又把 {len(b2a_migration_items)} 条行为复核通过题写入 A；"
            f"B-gap Wave1 又把 {len(b_gap_wave1_migration_items)} 条 P1 query_key_gap 复核通过题写入 A；"
            f"B-gap Wave2 继续把 {len(b_gap_wave2_migration_items)} 条 P1/P2 query_key_gap 复核通过题写入 A；"
            f"B-gap Wave3 继续把 {len(b_gap_wave3_migration_items)} 条 query_key_gap 工程修复题写入 A；"
            f"B-gap Wave4 继续把 {len(b_gap_wave4_migration_items)} 条最终分层后工程化可答题写入 A；"
            f"B-gap Wave5 继续把 {len(b_gap_wave5_migration_items)} 条最终可执行性复核通过题写入 A；"
            f"同时仍有 {sum(1 for item in c_round2_migration_items.values() if item.get('migration_type') == 'B_candidate')} "
            "条 B_candidate 和剩余 B 题需要继续澄清模板复检。"
        ),
    }
    return master_items, summary


def _write_markdown(master_items: list[dict[str, Any]], summary: dict[str, Any]) -> None:
    """写出 903 全量收口工程文档。"""

    a_examples = [item for item in master_items if item["governance_pool"] == "A-稳定增强池"][:10]
    b_candidate_examples = [item for item in master_items if item["governance_pool"] == "B-候选收口池"][:10]
    b_clarify_examples = [item for item in master_items if item["governance_pool"] == "B-长期澄清池"][:10]
    c_examples = [item for item in master_items if item["governance_pool"] == "C-边界观察池"][:10]

    lines = [
        "# 物流域 903 题全量收口总台账",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "## 当前为什么要从 Top200 切到 903 全量治理",
        "",
        "- Top200 高价值 B 题已经阶段性清零，说明“高价值先吃掉”的阶段已经结束。",
        "- 后续如果还要继续留在物流域，就不能再只靠零散 Top200/TopN 名单推进，而必须把 903 条题统一放进一份可管理的总台账。",
        "- 903 全量收口不等于 903 条都进入 A，而是要求每条题都有明确状态、明确边界、明确回归保护。",
        "",
        "## 最新 903 全量分布",
        "",
        f"- 基线分布：{summary['baseline_distribution']}",
        f"- 当前最新分布：{summary['current_distribution']}",
        f"- 当前去重后的唯一题号分布：{summary['current_unique_distribution']}",
        f"- 相对基线净变化：{summary['net_change_vs_baseline']}",
        f"- 迁移明细：{summary['migration_breakdown']}",
        "",
        "## C Round2 迁移更新",
        "",
        f"- A_candidate 行为回归通过并迁入 A：{summary['c_round2_migration_impact']['a_candidate_passed_to_a']}",
        f"- B_candidate 迁入 B 并纳入澄清模板复检：{summary['c_round2_migration_impact']['b_candidate_to_b']}",
        f"- C_confirmed 继续保持拒答边界：{summary['c_round2_migration_impact']['c_confirmed_remaining_c']}",
        f"- 迁移策略：{summary['c_round2_migration_impact']['policy']}",
        "",
        "## B->A 迁移复核更新",
        "",
        f"- 行为复核候选：{summary['b2a_migration_review_impact']['reviewed_candidates']}",
        f"- 正式迁入 A：{summary['b2a_migration_review_impact']['migrated_to_a']}",
        f"- 因数据基线继续留 B：{summary['b2a_migration_review_impact']['kept_b_due_to_data_baseline']}",
        f"- 迁移策略：{summary['b2a_migration_review_impact']['policy']}",
        "",
        "## B-gap Wave1 迁移更新",
        "",
        f"- Wave1 复核题：{summary['b_gap_wave1_migration_impact']['reviewed_candidates']}",
        f"- 正式迁入 A：{summary['b_gap_wave1_migration_impact']['migrated_to_a']}",
        f"- 迁移策略：{summary['b_gap_wave1_migration_impact']['policy']}",
        "",
        "## B-gap Wave2 迁移更新",
        "",
        f"- Wave2 复核题：{summary['b_gap_wave2_migration_impact']['reviewed_candidates']}",
        f"- B-候选收口池复核：{summary['b_gap_wave2_migration_impact']['candidate_pool_total']}",
        f"- 候选池正式迁入 A：{summary['b_gap_wave2_migration_impact']['candidate_pool_migrated_to_a']}",
        f"- 候选池继续留 B：{summary['b_gap_wave2_migration_impact']['candidate_pool_remain_b']}",
        f"- Wave2 全量正式迁入 A：{summary['b_gap_wave2_migration_impact']['migrated_to_a']}",
        f"- Wave2 继续留 B：{summary['b_gap_wave2_migration_impact']['remain_b']}",
        f"- 迁移策略：{summary['b_gap_wave2_migration_impact']['policy']}",
        "",
        "## B-gap Wave3 迁移更新",
        "",
        f"- Wave3 复核题：{summary['b_gap_wave3_migration_impact']['reviewed_candidates']}",
        f"- Wave3 正式迁入 A：{summary['b_gap_wave3_migration_impact']['migrated_to_a']}",
        f"- Wave3 继续留 B：{summary['b_gap_wave3_migration_impact']['remain_b']}",
        f"- 处理能力项：{summary['b_gap_wave3_migration_impact']['handled_capability_items']}",
        f"- 迁移策略：{summary['b_gap_wave3_migration_impact']['policy']}",
        "",
        "## B-gap Wave4 迁移更新",
        "",
        f"- Wave4 复核题：{summary['b_gap_wave4_migration_impact']['reviewed_candidates']}",
        f"- Wave4 正式迁入 A：{summary['b_gap_wave4_migration_impact']['migrated_to_a']}",
        f"- Wave4 继续留 B：{summary['b_gap_wave4_migration_impact']['remain_b']}",
        f"- 处理能力项：{summary['b_gap_wave4_migration_impact']['handled_capability_items']}",
        f"- 迁移策略：{summary['b_gap_wave4_migration_impact']['policy']}",
        "",
        "## B-gap Wave5 迁移更新",
        "",
        f"- Wave5 复核题：{summary['b_gap_wave5_migration_impact']['reviewed_candidates']}",
        f"- Wave5 正式迁入 A：{summary['b_gap_wave5_migration_impact']['migrated_to_a']}",
        f"- Wave5 继续留 B：{summary['b_gap_wave5_migration_impact']['remain_b']}",
        f"- Wave5 应转 C 复核候选：{summary['b_gap_wave5_migration_impact']['c_review_candidates']}",
        f"- 迁移策略：{summary['b_gap_wave5_migration_impact']['policy']}",
        "",
        "## 四个治理池",
        "",
        f"- A-稳定增强池：{summary['pool_breakdown'].get('A-稳定增强池', 0)}",
        f"- B-候选收口池：{summary['pool_breakdown'].get('B-候选收口池', 0)}",
        f"- B-长期澄清池：{summary['pool_breakdown'].get('B-长期澄清池', 0)}",
        f"- C-边界观察池：{summary['pool_breakdown'].get('C-边界观察池', 0)}",
        f"- D-待业务/数据修订池：{summary['pool_breakdown'].get('D-待业务/数据修订池', 0)}",
        f"- 去重后的唯一题号池分布：{summary['pool_unique_breakdown']}",
        "",
        "## Phase 路线图",
        "",
        "### Phase A：A-稳定增强",
        "- 目标：把已进入 A 但尚未进入更严格精确断言的题继续纳入固定复检流程。",
        f"- 当前重点：C Round2 新迁入 A 的 {summary['c_round2_migration_impact']['a_candidate_passed_to_a']} 条题，先按业务价值挑选高价值题进入精确断言。",
        "",
        "### Phase B：B-候选收口",
        "- 目标：保留一小批仍值得继续推进的问题，按题族和能力矩阵批量推进。",
        "- 当前规模：仅保留 TopN v2 中的候选题，不再发起新一轮 Top200 攻坚。",
        "",
        "### Phase C：B-长期澄清",
        "- 目标：继续稳定业务化澄清，不强行拉进 A。",
        "- 当前重点：C Round2 新迁入 B 的 290 条 B_candidate，后续纳入澄清模板复检。",
        "",
        "### Phase D：C-边界观察",
        "- 目标：继续维持不支持边界和业务理由，不让这类题反复混入主攻清单。",
        "",
        "## 当前最应优先推进的池",
        "",
        f"- 推荐优先池：{summary['recommended_next_pool']}",
        f"- 原因：{summary['recommended_next_pool_reason']}",
        "",
        "## 各池代表样例",
        "",
        "### A-稳定增强池",
    ]
    for item in a_examples:
        lines.append(f"- {item['question_id']} | {item['question']}")
    lines.extend(["", "### B-候选收口池"])
    for item in b_candidate_examples:
        lines.append(f"- {item['question_id']} | {item['question']}")
    lines.extend(["", "### B-长期澄清池"])
    for item in b_clarify_examples:
        lines.append(f"- {item['question_id']} | {item['question']}")
    lines.extend(["", "### C-边界观察池"])
    for item in c_examples:
        lines.append(f"- {item['question_id']} | {item['question']}")
    lines.extend(
        [
            "",
            "## 当前结论",
            "",
            "- 903 条全量题库已经升级成一份可管理、可分池、可分波次推进、可持续复检的正式总账。",
            (
                "- 当前正式总账已经吸收 C Round2 迁移结果："
                f"{summary['c_round2_migration_impact']['a_candidate_passed_to_a']} 条 A_candidate 入 A，"
                f"{summary['c_round2_migration_impact']['b_candidate_to_b']} 条 B_candidate 入 B，"
                f"{summary['c_round2_migration_impact']['c_confirmed_remaining_c']} 条保持 C 边界。"
            ),
            (
                "- 当前正式总账也已吸收 B->A 迁移复核结果："
                f"{summary['b2a_migration_review_impact']['migrated_to_a']} 条行为复核通过题入 A，"
                f"{summary['b2a_migration_review_impact']['kept_b_due_to_data_baseline']} 条因数据基线继续留 B。"
            ),
            (
                "- 当前正式总账已吸收 B-gap Wave1 迁移复核结果："
                f"{summary['b_gap_wave1_migration_impact']['migrated_to_a']} 条 P1 query_key_gap 复核通过题入 A。"
            ),
            (
                "- 当前正式总账已吸收 B-gap Wave2 迁移复核结果："
                f"{summary['b_gap_wave2_migration_impact']['migrated_to_a']} 条 P1/P2 query_key_gap 复核通过题入 A。"
            ),
            (
                "- 当前正式总账已吸收 B-gap Wave3 迁移复核结果："
                f"{summary['b_gap_wave3_migration_impact']['migrated_to_a']} 条 query_key_gap 工程修复题入 A。"
            ),
            (
                "- 当前正式总账已吸收 B-gap Wave4 迁移复核结果："
                f"{summary['b_gap_wave4_migration_impact']['migrated_to_a']} 条最终分层后工程化可答题入 A。"
            ),
            "- 后续队列必须继续执行新增 A 精确断言补强、B 缺口能力建设和 B 长期澄清模板复检，不得把缺口径题硬迁 A。",
        ]
    )
    MASTER_LEDGER_DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    """生成 903 全量收口总台账、报告和路线图。"""

    master_items, summary = _rebuild_master_ledger()
    generated_at = datetime.now().isoformat(timespec="seconds")

    ledger_payload = {
        "generated_at": generated_at,
        "summary": summary,
        "items": master_items,
    }
    report_payload = {
        "generated_at": generated_at,
        "summary": summary,
        "wave_plan": {
            "phase_a": "A-稳定增强池",
            "phase_b": "B-候选收口池",
            "phase_c": "B-长期澄清池",
            "phase_d": "C-边界观察池",
        },
        "answers": {
            "latest_full_distribution": summary["current_distribution"],
            "should_continue_large_scale_logistics": False,
            "most_valuable_next_pool": summary["recommended_next_pool"],
            "full_closure_should_be_wave_based": True,
        },
    }

    MASTER_LEDGER_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    MASTER_LEDGER_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    MASTER_LEDGER_CONFIG_PATH.write_text(json.dumps(ledger_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    MASTER_LEDGER_REPORT_PATH.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_markdown(master_items, summary)

    print(
        json.dumps(
            {
                "raw_question_total": summary["raw_question_total"],
                "current_distribution": summary["current_distribution"],
                "pool_breakdown": summary["pool_breakdown"],
                "recommended_next_pool": summary["recommended_next_pool"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
