#!/usr/bin/env python
"""M11-4：Timeout 真实中断语义 focused tests。

目标：
    验证 LogisticsSqlExecutionService 的 executor 层超时机制：
    - 触发超时时正确中断并返回超时错误状态
    - 不触发超时时正常返回结果
"""

from __future__ import annotations

import time

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import LogisticsSemanticCatalogLoader
from backend.app.domains.logistics.services.nl2sql.sql_plan import LogisticsSqlPlanValidator
from backend.app.domains.logistics.services.nl2sql.sql_renderer import LogisticsRenderedSql, render_logistics_sql
from backend.app.domains.logistics.services.nl2sql.sql_safety import LogisticsSqlSafetyChecker
from backend.app.domains.logistics.services.nl2sql.sql_execution import (
    LogisticsSqlExecutionResult,
    LogisticsSqlExecutionService,
)


def _safe_sql() -> LogisticsRenderedSql:
    """构造通过 safety 校验的安全测试用 rendered SQL。"""
    catalog = LogisticsSemanticCatalogLoader().load()
    validator = LogisticsSqlPlanValidator(catalog=catalog)
    plan = {
        "schema_version": "logistics_sqlplan_candidate.v1",
        "domain": "logistics",
        "strategy": "sql_direct",
        "catalog_version": "logistics_nl2sql_catalog.v1",
        "catalog_refs": [
            {"catalog_id": "table:dws_logistics_detail_union", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "metric:shipment_mw", "catalog_version": "logistics_nl2sql_catalog.v1"},
            {"catalog_id": "dimension:biz_year", "catalog_version": "logistics_nl2sql_catalog.v1"},
        ],
        "plan": {
            "query_type": "aggregate",
            "tables": ["dws_logistics_detail_union"],
            "metrics": ["shipment_mw"],
            "dimensions": [],
            "filters": [{"dimension": "biz_year", "operator": "in", "values": [2025]}],
            "group_by": [],
            "order_by": [],
            "business_rules": [],
            "requested_unit": "MW",
            "limit": None,
        },
    }
    validation = validator.validate(plan)
    assert validation.ok, validation.error_codes
    return render_logistics_sql(validation)


class _SlowFakeExecutor:
    """模拟慢 executor。"""

    def __init__(self, delay: float = 0.5) -> None:
        self.delay = delay
        self.calls: list[str] = []

    def explain(self, sql: str, params: dict) -> list[dict]:
        time.sleep(self.delay)
        self.calls.append(sql)
        return [{"select_type": "SIMPLE"}]

    def trial(self, sql: str, params: dict) -> list[dict]:
        time.sleep(self.delay)
        self.calls.append(sql)
        return [{"col": 1}]


class _FastFakeExecutor:
    """模拟快速 executor。"""

    def explain(self, sql: str, params: dict) -> list[dict]:
        return [{"select_type": "SIMPLE"}]

    def trial(self, sql: str, params: dict) -> list[dict]:
        return [{"col": 1}]


# ── 超时触发 ──────────────────────────────────────────────────


def test_timeout_triggers_on_explain() -> None:
    """EXPLAIN 超过超时时返回超时错误状态。"""
    slow = _SlowFakeExecutor(delay=1.0)
    service = LogisticsSqlExecutionService(
        executor=slow,  # type: ignore[arg-type]
        safety_checker=LogisticsSqlSafetyChecker(),
        execute_timeout=0.1,
    )
    result = service.explain(_safe_sql())
    assert result.ok is False
    assert "timeout" in " ".join(result.errors).lower() or "timeout" in str(result.error).lower()


def test_timeout_triggers_on_trial() -> None:
    """Trial 超过超时时返回超时错误状态。"""
    slow = _SlowFakeExecutor(delay=1.0)
    service = LogisticsSqlExecutionService(
        executor=slow,  # type: ignore[arg-type]
        safety_checker=LogisticsSqlSafetyChecker(),
        execute_timeout=0.1,
    )
    result = service.trial(_safe_sql())
    assert result.ok is False
    assert "timeout" in " ".join(result.errors).lower() or "timeout" in str(result.error).lower()


# ── 不触发超时 ──────────────────────────────────────────────────


def test_fast_executor_does_not_timeout_explain() -> None:
    """快速 executor 不触发超时。"""
    fast = _FastFakeExecutor()
    service = LogisticsSqlExecutionService(
        executor=fast,  # type: ignore[arg-type]
        safety_checker=LogisticsSqlSafetyChecker(),
        execute_timeout=5.0,
    )
    result = service.explain(_safe_sql())
    assert result.ok is True


def test_fast_executor_does_not_timeout_trial() -> None:
    """快速 executor 不触发超时。"""
    fast = _FastFakeExecutor()
    service = LogisticsSqlExecutionService(
        executor=fast,  # type: ignore[arg-type]
        safety_checker=LogisticsSqlSafetyChecker(),
        execute_timeout=5.0,
    )
    result = service.trial(_safe_sql())
    assert result.ok is True


def test_default_no_timeout() -> None:
    """不设置超时时使用默认值，不限制执行时间。"""
    fast = _FastFakeExecutor()
    service = LogisticsSqlExecutionService(
        executor=fast,  # type: ignore[arg-type]
        safety_checker=LogisticsSqlSafetyChecker(),
    )
    result = service.explain(_safe_sql())
    assert result.ok is True
