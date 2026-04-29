from __future__ import annotations

import argparse
import json
from collections.abc import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_db
from backend.app.db.base import Base
from backend.app.domains.plan_bom.repositories.import_repository import PlanBomImportRepository
from backend.app.domains.plan_bom.services.excel_import_service import PlanBomExcelImportService
from backend.app.main import create_application
from plan_bom_runtime import CONFIG_DIR, TMP_DIR, extract_bom_zip


SEED_CASES = [
    {"id": "A_SINGLE", "question": "订单00104的玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述？", "expected": {"A"}},
    {"id": "A_SCOPE", "question": "把 2026 年所有 NT10/78GDF 订单的五类关键材料做成一张清单。", "expected": {"A"}},
    {"id": "A_PRESENCE", "question": "哪些订单没有接线盒材料？", "expected": {"A"}},
    {"id": "B_CLARIFY", "question": "多个订单的玻璃、间隙贴膜、焊带、汇流条、接线盒规格并用 Excel 表格形式展现。", "expected": {"B"}},
    {"id": "B_COMPARE_AMBIGUOUS", "question": "订单00067和订单00106玻璃、间隙贴膜、焊带、汇流条、接线盒有什么不一样，并用表格统计出来。", "expected": {"B", "A"}},
    {"id": "C_UNSUPPORTED", "question": "使用功率预测来问询 BOM 配置的情况下需要什么样的电池可以满足订单需求功率。", "expected": {"C"}},
    {"id": "C_EMPTY", "question": "订单99999的接线盒规格是什么？", "expected": {"B", "C"}},
    {"id": "B_NON_CORE_CELL", "question": "订单00104的电池片规格是什么？", "expected": {"B", "C"}},
    {"id": "B_NON_CORE_EVA", "question": "订单00104的EVA胶膜规格是什么？", "expected": {"B", "C"}},
]


def build_cases() -> list[dict]:
    """构造不少于 25 条 API E2E 用例。

    返回：
        覆盖 A/B/C、表格、对比、追问、拒答和空结果的用例列表。
    """

    cases = list(SEED_CASES)
    ledger = json.loads((CONFIG_DIR / "plan_bom_master_ledger.json").read_text(encoding="utf-8"))
    used_questions = {case["question"] for case in cases}
    for classification, limit in (("A", 14), ("B", 8), ("C", 3)):
        picked = 0
        for item in ledger.get("items", []):
            if item.get("classification") != classification or item["question"] in used_questions:
                continue
            cases.append({"id": f"{classification}_LEDGER_{picked+1:02d}", "question": item["question"], "expected": {classification}})
            used_questions.add(item["question"])
            picked += 1
            if picked >= limit:
                break
    return cases[:30]


def parse_args() -> argparse.Namespace:
    """解析 QA API E2E 参数。

    返回：
        argparse.Namespace，包含可选 BOM 源数据 zip 路径。
    """

    parser = argparse.ArgumentParser(description="通过 TestClient 验证计划 BOM QA API")
    parser.add_argument("--source-zip", default=None, help="BOM 源数据 zip 路径；未传时读取项目内默认路径")
    return parser.parse_args()


def build_seeded_client(source_zip: str | None) -> TestClient:
    """构建已导入真实 BOM 数据的 TestClient。

    参数：
        source_zip: BOM 源数据 zip 路径。

    返回：
        可请求 `/api/v1/plan-bom/qa/ask` 的 TestClient。
    """

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)
    seed_session = testing_session()
    import_service = PlanBomExcelImportService(repository=PlanBomImportRepository(seed_session))
    for file_path in extract_bom_zip(source_zip):
        import_service.import_file(file_path)
    seed_session.commit()
    seed_session.close()

    def override_get_db() -> Iterator[Session]:
        """为 API E2E 提供同一 SQLite 数据库会话。

        返回：
            SQLAlchemy Session 生成器。
        """

        session = testing_session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    app = create_application()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def main() -> None:
    """执行计划 BOM QA API E2E 验收。

    返回：
        无返回值；脚本输出 JSON 报告。
    """

    args = parse_args()
    client = build_seeded_client(args.source_zip)
    route_paths = sorted({route.path for route in client.app.routes})
    items = []
    cases = build_cases()
    for case in cases:
        try:
            response = client.post("/api/v1/plan-bom/qa/ask", json={"question": case["question"], "trace_id": f"qa-e2e-{case['id']}"})
            payload = response.json() if response.content else {}
        except Exception as exc:  # noqa: BLE001
            # API E2E 需要把异常写入报告，避免接口 500 被脚本中断后丢失定位信息。
            items.append(
                {
                    "id": case["id"],
                    "question": case["question"],
                    "expected": sorted(case["expected"]),
                    "http_status": "exception",
                    "classification": None,
                    "status_code": None,
                    "intent": None,
                    "row_count": 0,
                    "display_type": None,
                    "presentation_source": None,
                    "passed": False,
                    "error": str(exc),
                }
            )
            continue
        data = payload.get("data") or {}
        presentation = data.get("presentation") or {}
        passed = response.status_code < 500 and data.get("classification") in case["expected"] and bool(presentation.get("display_type"))
        items.append(
            {
                "id": case["id"],
                "question": case["question"],
                "expected": sorted(case["expected"]),
                "http_status": response.status_code,
                "classification": data.get("classification"),
                "status_code": (data.get("status") or {}).get("code"),
                "intent": ((data.get("nlu") or {}).get("intent")),
                "row_count": len((data.get("result_table") or {}).get("rows") or []),
                "display_type": presentation.get("display_type"),
                "presentation_source": (presentation.get("debug") or {}).get("presentation_source"),
                "passed": passed,
            }
        )
    report = {
        "endpoint": "POST /api/v1/plan-bom/qa/ask",
        "route_registered": "/api/v1/plan-bom/qa/ask" in route_paths,
        "total": len(items),
        "passed": sum(1 for item in items if item["passed"]),
        "failed": sum(1 for item in items if not item["passed"]),
        "items": items,
    }
    (TMP_DIR / "plan_bom_qa_api_e2e_check_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
