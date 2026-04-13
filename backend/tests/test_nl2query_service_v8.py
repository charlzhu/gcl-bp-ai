
from __future__ import annotations

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.app.domains.logistics.services.nl2query_service import LogisticsNL2QueryService


class DummyQueryService:
    """V8 单测使用的假 QueryService。

    目的：
    1. 避免测试依赖真实数据库；
    2. 验证 V8 的参数校验、白名单、审计信息是否挂回 parsed；
    3. 保证导入 nl2query_service 时，不会再因为 SQLAlchemy 缺失而失败。
    """

    def aggregate(self, payload, trace_id=None):
        return {"query_type": "aggregate", "execution_mode": "database", "total": 1, "items": [{"metric": payload.metric_type}]}

    def compare(self, payload, trace_id=None):
        return {"query_type": "compare", "execution_mode": "database", "total": 2, "items": [{"left": payload.left.label, "right": payload.right.label}]}

    def detail(self, payload, trace_id=None):
        return {"query_type": "detail", "execution_mode": "database", "total": 1, "items": [{"contract_no": payload.contract_no}]}


def test_v8_sql_template_binding_and_whitelist():
    service = LogisticsNL2QueryService(query_service=DummyQueryService())
    result = service.parse_and_query(type("Payload", (), {"question": "合同编号GCL5010ZJ202503015的明细"})(), trace_id="t-v8-1")

    parsed = result["parsed"]
    assert parsed["template_hit"] is True
    assert parsed["sql_template_id"] == "logistics.detail_by_business_no"
    assert parsed["execution_binding"]["sql_template"]["exists"] is True
    assert parsed["execution_binding"]["sql_whitelist"]["allowed"] is True
    assert parsed["execution_audit"]["sql_whitelist_allowed"] is True


def test_v8_sql_preview_should_render_sql_literal():
    service = LogisticsNL2QueryService(query_service=DummyQueryService())
    result = service.parse_and_query(type("Payload", (), {"question": "合同编号GCL5010ZJ202503015的明细"})(), trace_id="t-v8-2")

    rendered = result["parsed"]["execution_binding"]["sql_preview"]["rendered"]
    assert "'GCL5010ZJ202503015'" in rendered
    assert "NULL" in rendered


def test_v8_validation_should_keep_group_by_safe():
    service = LogisticsNL2QueryService(query_service=DummyQueryService())
    result = service.parse_and_query(type("Payload", (), {"question": "2025年各承运商发货量分别是多少"})(), trace_id="t-v8-3")

    parsed = result["parsed"]
    assert parsed["validation"]["ok"] is True
    assert parsed["group_by"] == ["logistics_company_name"]


def test_v8_import_without_sqlalchemy_dependency():
    # 这个测试的意义很简单：
    # 如果这个文件能正常 import 并执行到这里，说明 query_executor / query_plan_store 的 import 优化生效了。
    service = LogisticsNL2QueryService(query_service=DummyQueryService())
    result = service.parse_and_query(type("Payload", (), {"question": "2025年3月运量是多少"})(), trace_id="t-v8-4")
    assert result["query_result"]["query_type"] == "aggregate"

