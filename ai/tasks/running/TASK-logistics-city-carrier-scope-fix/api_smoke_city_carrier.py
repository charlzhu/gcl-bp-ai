"""API smoke：验证“常州的物流公司”不再退化为全国总发运量。

该脚本通过 FastAPI TestClient 注入受控 LogisticsDataQaService，
只验证 API 层到 planner/service 的确定性链路是否保留 city + carrier 分组语义，
不连接真实数据库，不读取任何密钥或外部服务。
"""

from __future__ import annotations

import json
from typing import Any

from fastapi.testclient import TestClient

from backend.app.api.deps import get_logistics_data_qa_service
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.logistics.services.llm_answer_presentation_service import LogisticsLlmAnswerPresentationService
from backend.app.main import app


class _FakeDb:
    """供服务写查询日志时使用的数据库替身。"""

    def commit(self) -> None:
        """模拟提交。"""

    def rollback(self) -> None:
        """模拟回滚。"""


class _FakeQueryLogRepository:
    """供服务写查询日志时使用的日志仓储替身。"""

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        """返回固定日志 ID，避免依赖真实数据库。"""

        return 1


class _FakeCarrierRepository:
    """只提供本 smoke 所需的承运商 KPI 仓储方法。"""

    def __init__(self) -> None:
        """记录 API 链路下推的 city 参数。"""

        self.last_kwargs: dict[str, Any] | None = None

    def hist_carrier_kpi_by_year(
        self,
        *,
        year: int,
        region_name: str | None = None,
        city: str | None = None,
    ) -> dict[str, Any]:
        """返回城市范围内的承运商分组结果。"""

        self.last_kwargs = {"year": year, "region_name": region_name, "city": city}
        if city != "常州":
            raise AssertionError(f"city filter lost or wrong: {city!r}")
        return {
            "total_shipment_mw": 300.0,
            "items": [
                {"carrier_name": "常州A物流", "shipment_mw": 200.0, "shipment_share_pct": 66.67, "total_fee": 1000.0},
                {"carrier_name": "常州B物流", "shipment_mw": 100.0, "shipment_share_pct": 33.33, "total_fee": 500.0},
            ],
        }


_repo = _FakeCarrierRepository()


def _build_service() -> LogisticsDataQaService:
    """构造受控服务实例。"""

    return LogisticsDataQaService(
        db=_FakeDb(),
        repository=_repo,
        query_log_repository=_FakeQueryLogRepository(),
        answer_presentation_service=LogisticsLlmAnswerPresentationService(enabled=False, base_url=None, api_key=None, model=""),
    )


app.dependency_overrides[get_logistics_data_qa_service] = _build_service

with TestClient(app) as client:
    response = client.post(
        "/api/v1/logistics/data-qa/query",
        json={"question": "2025年常州的物流公司发运多少量？"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    data = payload["data"]
    assert data["query_plan"]["query_key"] == "hist_carrier_kpi_by_year"
    assert data["query_plan"]["filters"]["city"] == "常州"
    assert data["result_table"]["columns"] == ["carrier_name", "shipment_mw", "shipment_share_pct", "total_fee"]
    assert len(data["result_table"]["rows"]) == 2
    assert "常州" in data["answer_summary"]
    assert "总发运量" not in data["answer_summary"]
    assert _repo.last_kwargs == {"year": 2025, "region_name": None, "city": "常州"}
    print(json.dumps({
        "status_code": response.status_code,
        "query_key": data["query_plan"]["query_key"],
        "filters": data["query_plan"]["filters"],
        "columns": data["result_table"]["columns"],
        "row_count": len(data["result_table"]["rows"]),
        "answer_summary": data["answer_summary"],
    }, ensure_ascii=False, indent=2))

app.dependency_overrides.clear()
