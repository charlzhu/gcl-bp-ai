from __future__ import annotations

from typing import Any

from backend.app.domains.logistics.repositories.data_qa_repository import LogisticsDataQaRepository
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision
from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService


class _FakeScalarResult:
    """模拟 SQLAlchemy execute 返回值，便于检查 SQL 与参数。

    参数：
        row: first()/all() 需要返回的伪造行。
    返回值：
        提供 mappings().first()/all()/scalar() 的最小对象。
    """

    def __init__(self, row: dict[str, Any] | None = None) -> None:
        self._row = row or {
            "total_fee": 1234.56,
            "task_count": 2,
            "parse_fail_count": 0,
            "price_missing_count": 0,
        }

    def mappings(self) -> "_FakeScalarResult":
        return self

    def first(self) -> dict[str, Any]:
        return self._row

    def all(self) -> list[dict[str, Any]]:
        return [self._row]

    def scalar(self) -> int:
        return 0


class _SqlCaptureDb:
    """捕获 repository 生成的 SQL 和参数，不连接真实数据库。"""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeScalarResult:
        self.calls.append((str(statement), dict(params or {})))
        return _FakeScalarResult()


class _NoopHistoryDb:
    """服务层测试用数据库替身，只提供历史写入需要的事务方法。"""

    def commit(self) -> None:
        return None

    def rollback(self) -> None:
        return None


class _NoopQueryLogRepository:
    """禁用历史落库，避免服务层测试依赖真实数据库。"""

    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
        return 0


class _FakeTotalFeeRepository:
    """服务层测试替身：只允许走字段过滤版总费用查询。"""

    def __init__(self) -> None:
        self.total_fee_calls: list[dict[str, Any]] = []
        self.special_fee_calls: list[dict[str, Any]] = []

    def sys_total_fee_by_filters(self, **kwargs: Any) -> dict[str, Any]:
        self.total_fee_calls.append(dict(kwargs))
        return {
            "total_fee": 1234.56,
            "task_count": 2,
            "parse_fail_count": 0,
            "price_missing_count": 0,
        }

    def sys_special_total_fee(self, **kwargs: Any) -> dict[str, Any]:
        self.special_fee_calls.append(dict(kwargs))
        return {
            "total_fee": 999999.0,
            "task_count": 99,
            "parse_fail_count": 0,
            "price_missing_count": 0,
        }


class _NoopGuardrail:
    """禁用 LLM guardrail，让验收测试只验证确定性规则链路。"""

    def evaluate(self, **kwargs: Any) -> LogisticsLlmGuardrailDecision:
        rule_plan = kwargs["rule_plan"]
        return LogisticsLlmGuardrailDecision(
            question=kwargs["question"],
            rule_intent=rule_plan.intent,
            rule_query_key=rule_plan.query_key,
            rule_needs_clarification=rule_plan.needs_clarification,
            final_intent=rule_plan.intent,
            final_query_key=rule_plan.query_key,
            final_needs_clarification=rule_plan.needs_clarification,
            final_supported=not rule_plan.needs_clarification,
        )

    def write_audit_log(self, **kwargs: Any) -> None:
        return None


def test_planner_maps_business_words_to_expand_dept_and_entrusted_person() -> None:
    """经营计划和刘娟必须分别映射到扩充部门、委托人字段，并可叠加过滤。"""

    plan = LogisticsDataQaPlanner().build_plan("26年 经营计划 刘娟 用车总费用是多少")

    assert plan.query_key == "sys_total_fee_by_filters"
    assert plan.filters["year"] == 2026
    assert plan.filters["expand_dept"] == "经营计划"
    assert plan.filters["entrusted_person"] == "刘娟"
    assert "special_scope" not in plan.filters
    assert not plan.needs_clarification


def test_planner_keeps_single_known_field_mapping_for_total_fee() -> None:
    """单独出现经营计划或刘娟时也要映射到真实字段，而不是走锁定口径。"""

    planner = LogisticsDataQaPlanner()

    dept_plan = planner.build_plan("2026年经营计划用车总费用是多少")
    assert dept_plan.query_key == "sys_total_fee_by_filters"
    assert dept_plan.filters["expand_dept"] == "经营计划"
    assert "entrusted_person" not in dept_plan.filters
    assert "special_scope" not in dept_plan.filters

    dept_full_name_plan = planner.build_plan("2026年经营计划部用车总费用是多少")
    assert dept_full_name_plan.query_key == "sys_total_fee_by_filters"
    assert dept_full_name_plan.filters["expand_dept"] == "经营计划部"
    assert "special_scope" not in dept_full_name_plan.filters

    person_plan = planner.build_plan("2026年刘娟用车总费用是多少")
    assert person_plan.query_key == "sys_total_fee_by_filters"
    assert person_plan.filters["entrusted_person"] == "刘娟"
    assert "expand_dept" not in person_plan.filters
    assert "special_scope" not in person_plan.filters


def test_unknown_business_person_scope_requires_clarification() -> None:
    """未知人名/范围不能默认全量或套用特殊口径，必须反问字段归属。"""

    plan = LogisticsDataQaPlanner().build_plan("26年 张三 用车总费用是多少")

    assert plan.needs_clarification
    assert plan.query_key is None
    assert plan.clarification_category == "field_scope_mapping"
    assert "张三" in plan.clarification_reason
    assert any("字段" in question or "口径" in question for question in plan.clarification_questions)


def test_known_scope_with_unknown_person_still_requires_clarification() -> None:
    """已知扩充部门旁边还有未知人名时，不能静默丢弃未知条件后直接回答。"""

    plan = LogisticsDataQaPlanner().build_plan("26年 经营计划 张三 用车总费用是多少")

    assert plan.needs_clarification
    assert plan.query_key is None
    assert plan.clarification_category == "field_scope_mapping"
    assert "张三" in plan.clarification_reason
    assert any("张三" in question for question in plan.clarification_questions)


def test_repository_total_fee_downstream_filters_expand_dept_and_entrusted_person() -> None:
    """repository 必须把扩充部门和委托人作为 SQL 参数下推，不能只改文案。"""

    repository = object.__new__(LogisticsDataQaRepository)
    repository.db = _SqlCaptureDb()

    repository.sys_total_fee_by_filters(
        year=2026,
        months=None,
        expand_dept="经营计划",
        entrusted_person="刘娟",
    )

    sql_text = "\n".join(sql for sql, _ in repository.db.calls)
    merged_params: dict[str, Any] = {}
    for _, params in repository.db.calls:
        merged_params.update(params)

    assert "st.expand_dept = :expand_dept" in sql_text
    assert "st.entrusted_person = :entrusted_person" in sql_text
    assert merged_params["expand_dept"] == "经营计划"
    assert merged_params["entrusted_person"] == "刘娟"


def test_service_summary_and_repo_call_preserve_explicit_field_scope() -> None:
    """服务层答案应展示字段过滤范围，并调用字段过滤查询而非特殊锁定口径。"""

    repository = _FakeTotalFeeRepository()
    service = LogisticsDataQaService(
        db=_NoopHistoryDb(),
        repository=repository,
        planner=LogisticsDataQaPlanner(),
        query_log_repository=_NoopQueryLogRepository(),
        guardrail_service=_NoopGuardrail(),
    )

    result = service.query(LogisticsDataQaQueryRequest(question="26年 经营计划 刘娟 用车总费用是多少"))

    assert repository.special_fee_calls == []
    assert repository.total_fee_calls
    call = repository.total_fee_calls[-1]
    assert call["expand_dept"] == "经营计划"
    assert call["entrusted_person"] == "刘娟"
    assert result.query_plan.filters["expand_dept"] == "经营计划"
    assert result.query_plan.filters["entrusted_person"] == "刘娟"
    assert "扩充部门=经营计划" in result.answer_summary
    assert "委托人=刘娟" in result.answer_summary
    assert "锁定口径" not in result.answer_summary
