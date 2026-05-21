#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

logger = logging.getLogger(__name__)


def _json_print(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


def _fake_m4_ask(question: str) -> dict[str, Any]:
    """Fake M4 QA ask：不连接数据库，仅返回占位响应。

    适用于离线验证对比逻辑。真实模式使用 M4_QA_SERVICE.m4_ask_factory 替换。
    """
    from backend.app.domains.business_analysis.services.inventory_sales_production.nl_query_planner import (
        InventorySalesProductionNlQueryPlanner,
        InventorySalesProductionPlanningError,
    )

    planner = InventorySalesProductionNlQueryPlanner()
    try:
        plan = planner.build_plan(question)
    except InventorySalesProductionPlanningError:
        return {
            "status": {
                "code": "UNSUPPORTED",
                "message": "当前产销存版本暂不支持此类问题。",
                "success": False,
                "severity": "warning",
            },
            "answer_summary": "当前产销存版本暂不支持此类问题。",
            "result_table": None,
        }
    except Exception:
        return {"status": {"code": "EXECUTION_ERROR"}, "answer_summary": "执行失败", "result_table": None}

    return {
        "status": {"code": "OK"},
        "answer_summary": f"{plan.period.year} 已按 QueryPlan 完成分析。",
        "result_table": {"columns": [], "rows": [{"year": plan.period.year, "value": "placeholder"}]},
    }


def _fake_m6_run(question: str) -> dict[str, Any]:
    """Fake M6 shadow gate run：不连接 LLM，仅返回占位响应。

    离线模式下，使用 M6 FaskSqlPlanGenerator 代替真实 provider。
    """
    from backend.app.domains.business_analysis.services.inventory_sales_production.m6_live_provider_gate import (
        InventorySalesProductionM6CatalogRecallDocumentBuilder,
        InventorySalesProductionM6CatalogRecallService,
        InventorySalesProductionM6FakeSqlPlanGenerator,
        InventorySalesProductionM6FakeReadonlyShadowExecutor,
        InventorySalesProductionM6LiveShadowGateRunner,
        InventorySalesProductionM6LiveShadowSample,
    )

    documents = InventorySalesProductionM6CatalogRecallDocumentBuilder().build_documents()
    recall_service = InventorySalesProductionM6CatalogRecallService.from_documents(documents)
    runner = InventorySalesProductionM6LiveShadowGateRunner(
        sqlplan_generator=InventorySalesProductionM6FakeSqlPlanGenerator.success_for_metric("shipment_volume"),
        readonly_shadow_executor=InventorySalesProductionM6FakeReadonlyShadowExecutor(rows=[]),
    )
    run = runner.run(
        samples=[
            InventorySalesProductionM6LiveShadowSample(
                sample_id="m7_offline",
                question=question,
                expected_status="matched",
            )
        ],
        artifact_dir=Path("/tmp/hermes/m7_offline"),
    )
    record = json.loads(run.records_path.read_text(encoding="utf-8").splitlines()[0])
    return record


def run_dual_track_offline(*, samples: list[dict[str, Any]], artifact_dir: Path) -> int:
    """离线模式下执行 M4 vs M6 双轨对比，使用 fake M4 和 fake M6。

    参数：
        samples: 样本列表，每项含 sample_id 和 question。
        artifact_dir: 验收材料目录。
    返回：
        退出码（0=逻辑跑通，2=严重错误）。离线模式下 mismatch 是预期的（fake M6 无真实数据）。
        真实环境需使用 --live 模式或注入真实 M4 和 M6 回调。
    """
    from backend.app.domains.business_analysis.services.inventory_sales_production.m7_dual_track import (
        run_dual_track_comparison,
    )

    report = run_dual_track_comparison(
        samples=samples,
        m4_ask=_fake_m4_ask,
        m6_run_sample=_fake_m6_run,
        artifact_dir=artifact_dir,
    )

    print("=== M7 Dual-Track Report ===")
    _json_print(report.model_dump(mode="json"))

    if report.mismatch_count > 0:
        logger.warning("mismatch_count=%s (expected in offline mode with fake M6)", report.mismatch_count)

    if not report.all_technical_leak_clean:
        logger.error("technical leak detected")
        return 2

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run ISP M7 dual-track offline comparison")
    parser.add_argument("--artifact-dir", default="ai/outbox/kanban/isp_m7", help="验收材料目录")
    args = parser.parse_args()

    artifacts = Path(args.artifact_dir)

    # 加载 M6.2 的默认样本
    from scripts.dev.run_inventory_sales_production_m6_live_provider_gate import (
        _default_live_shadow_samples,
    )

    all_samples = _default_live_shadow_samples(99)
    samples = [
        {"sample_id": s.sample_id, "question": s.question}
        for s in all_samples
    ]

    return run_dual_track_offline(samples=samples, artifact_dir=artifacts)


if __name__ == "__main__":
    raise SystemExit(main())
