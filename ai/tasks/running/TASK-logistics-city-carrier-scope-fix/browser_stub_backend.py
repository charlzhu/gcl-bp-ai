"""浏览器 smoke 用受控后端。

该脚本启动真实 FastAPI app，并覆盖物流 data-qa 依赖，
用于浏览器验证智能问答页面是否通过 `/query/stream` 得到城市 + 物流公司分组结果。
"""

from __future__ import annotations

from typing import Any

import uvicorn

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
        """返回固定日志 ID。"""

        return 1


class _FakeCarrierRepository:
    """只提供浏览器 smoke 需要的承运商 KPI 仓储方法。"""

    def hist_carrier_kpi_by_year(
        self,
        *,
        year: int,
        region_name: str | None = None,
        city: str | None = None,
    ) -> dict[str, Any]:
        """返回城市范围内的承运商分组结果；如果 city 丢失则主动失败。"""

        if city != "常州":
            raise AssertionError(f"city filter lost or wrong: {city!r}")
        return {
            "total_shipment_mw": 300.0,
            "items": [
                {"carrier_name": "常州A物流", "shipment_mw": 200.0, "shipment_share_pct": 66.67, "total_fee": 1000.0},
                {"carrier_name": "常州B物流", "shipment_mw": 100.0, "shipment_share_pct": 33.33, "total_fee": 500.0},
            ],
        }


def _build_service() -> LogisticsDataQaService:
    """构造受控物流问答服务。"""

    return LogisticsDataQaService(
        db=_FakeDb(),
        repository=_FakeCarrierRepository(),
        query_log_repository=_FakeQueryLogRepository(),
        answer_presentation_service=LogisticsLlmAnswerPresentationService(enabled=False, base_url=None, api_key=None, model=""),
    )


app.dependency_overrides[get_logistics_data_qa_service] = _build_service

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=18080, log_level="info")
