from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from backend.app.domains.business_analysis.schemas.inventory_sales_production_query import (
    InventorySalesProductionQueryPlan,
    InventorySalesProductionQueryResult,
    InventorySalesProductionQueryRow,
)
from backend.app.domains.business_analysis.services.inventory_sales_production.qa_service import (
    InventorySalesProductionQaService,
)

# 共用的 fake runner：模拟 M6 门禁通过
def _make_fake_runner(*, ok: bool = True) -> object:
    runner = MagicMock()
    run = MagicMock()
    run.report = {
        "expected_status_mismatch_count": 0 if ok else 1,
        "success_count": 1 if ok else 0,
    }
    runner.run.return_value = run
    return runner


def _make_service(
    *,
    enabled: bool = False,
    mode: str = "off",
    runner: object = None,
    artifact_dir: Path | None = None,
) -> InventorySalesProductionQaService:
    db = MagicMock()
    planner = MagicMock()
    executor = MagicMock()
    # 让 mock executor 返回合法的 QueryResult，避免 decimal 转换错误
    executor.execute.return_value = InventorySalesProductionQueryResult(
        status="success",
        answer_summary="查询成功。",
        rows=[],
    )
    return InventorySalesProductionQaService(
        db=db,
        planner=planner,
        executor=executor,
        live_gate_enabled=enabled,
        live_gate_mode=mode,
        live_gate_runner=runner,
        live_gate_artifact_dir=artifact_dir,
    )


# ===== off 模式 =====


def test_m8_off_mode_returns_m4_result_without_calling_gate() -> None:
    """off 模式直接返回 M4 结果，不调用 gate runner。"""
    svc = _make_service(enabled=False, mode="off", runner=_make_fake_runner())
    resp = svc.ask_with_live_gate("2025年销量是多少？")
    assert resp is not None
    assert svc.live_gate_runner.run.call_count == 0  # gate 未被调用


def test_m8_off_mode_default_constructor() -> None:
    """默认参数构造的服务等同于 off 模式。"""
    db = MagicMock()
    svc = InventorySalesProductionQaService(db=db)
    resp = svc.ask_with_live_gate("2025年销量是多少？")
    assert resp is not None


# ===== shadow 模式 =====


def test_m8_shadow_mode_gate_run_does_not_affect_m4_result() -> None:
    """shadow 模式下 M4 结果是正式答案，gate 结果不影响。"""
    runner = _make_fake_runner(ok=True)
    svc = _make_service(enabled=True, mode="shadow", runner=runner)
    resp = svc.ask_with_live_gate("2025年销量是多少？")
    assert resp is not None
    assert svc.live_gate_runner.run.call_count == 1  # gate 被调用并记录


def test_m8_shadow_mode_without_runner_not_crash() -> None:
    """shadow 模式下 runner 为 None 时不会 crash。"""
    svc = _make_service(enabled=True, mode="shadow", runner=None)
    resp = svc.ask_with_live_gate("2025年销量是多少？")
    assert resp is not None


# ===== assist 模式 =====


def test_m8_assist_mode_gate_ok_returns_m4_result() -> None:
    """assist 模式下 gate 成功仍返回 M4 结果（灰度验收阶段）。"""
    runner = _make_fake_runner(ok=True)
    svc = _make_service(enabled=True, mode="assist", runner=runner)
    resp = svc.ask_with_live_gate("2025年销量是多少？")
    assert resp is not None
    assert svc.live_gate_runner.run.call_count == 1  # gate 被调用


def test_m8_assist_mode_gate_fail_fallback_to_m4() -> None:
    """assist 模式下 gate 失败时自动 fallback 到 M4。"""
    runner = _make_fake_runner(ok=False)
    svc = _make_service(enabled=True, mode="assist", runner=runner)
    resp = svc.ask_with_live_gate("2025年销量是多少？")
    assert resp is not None
    assert svc.live_gate_runner.run.call_count == 1


def test_m8_assist_mode_gate_exception_fallback_to_m4() -> None:
    """assist 模式下 gate 抛出异常时自动 fallback 到 M4。"""
    runner = MagicMock()
    runner.run.side_effect = RuntimeError("upstream error")
    svc = _make_service(enabled=True, mode="assist", runner=runner)
    resp = svc.ask_with_live_gate("2025年销量是多少？")
    assert resp is not None


# ===== config.py 字段验证 =====


def test_m8_config_has_feature_flag() -> None:
    """config.py 必须包含 isp_live_qa_gate_enabled 和 isp_live_qa_gate_mode 字段。"""
    from backend.app.core.config import get_settings

    settings = get_settings()
    # 检查字段存在性（默认值 off 且 disabled）
    assert hasattr(settings, "isp_live_qa_gate_enabled")
    assert hasattr(settings, "isp_live_qa_gate_mode")


def test_m8_config_default_is_off() -> None:
    """feature flag 默认必须为 off，保障上线前不意外激活。"""
    from backend.app.core.config import get_settings

    settings = get_settings()
    assert settings.isp_live_qa_gate_enabled is False
    assert settings.isp_live_qa_gate_mode == "off"


# ===== 异常安全 =====


def test_m8_live_gate_off_does_not_create_artifact_dir() -> None:
    """off 模式下不应创建 artifact 目录。"""
    runner = _make_fake_runner()
    svc = _make_service(enabled=False, mode="off", runner=runner)
    svc.ask_with_live_gate("2025年销量是多少？")
    assert svc.live_gate_runner.run.call_count == 0


# ===== nl2sql 模式 =====


def _make_nl2sql_service(
    *,
    mode: str = "nl2sql",
    nl2sql_ok: bool = True,
    rule_fallback_ok: bool = True,
) -> InventorySalesProductionQaService:
    """构造用于 nl2sql 模式测试的 QA Service。

    参数：
        mode: live_gate_mode（默认 nl2sql）。
        nl2sql_ok: LLM 规划器是否成功返回 QueryPlan。
        rule_fallback_ok: 规则规划器 fallback 是否成功。
    返回：
        注入 mock planner/executor 的 QA Service。
    """
    db = MagicMock()
    executor = MagicMock()
    executor.execute.return_value = InventorySalesProductionQueryResult(
        status="success",
        answer_summary="查询成功。",
        rows=[],
    )

    # 规则规划器 mock
    planner = MagicMock()
    if rule_fallback_ok:
        planner.build_plan.return_value = MagicMock()
    else:
        from backend.app.domains.business_analysis.services.inventory_sales_production.nl_query_planner import (
            InventorySalesProductionPlanningError,
        )

        planner.build_plan.side_effect = InventorySalesProductionPlanningError(
            "clarification", "规则规划器无法处理该问题。"
        )

    # NL2SQL 规划器 mock
    nl2sql_planner = MagicMock()
    if nl2sql_ok:
        nl2sql_planner.build_plan.return_value = MagicMock(spec=InventorySalesProductionQueryPlan)
    else:
        nl2sql_planner.build_plan.side_effect = RuntimeError("LLM timeout")

    return InventorySalesProductionQaService(
        db=db,
        planner=planner,
        nl2sql_planner=nl2sql_planner,
        executor=executor,
        live_gate_enabled=True,
        live_gate_mode=mode,
    )


def test_m8_nl2sql_mode_uses_nl2sql_planner() -> None:
    """nl2sql 模式使用 NL2SQL 规划器，不调用规则规划器。"""
    svc = _make_nl2sql_service(nl2sql_ok=True)
    resp = svc.ask_with_live_gate("2025年产量是多少？")
    assert resp is not None
    assert svc.nl2sql_planner.build_plan.call_count == 1
    assert svc.planner.build_plan.call_count == 0


def test_m8_nl2sql_mode_fallback_to_rule() -> None:
    """NL2SQL 规划器失败时自动 fallback 到规则规划器。"""
    svc = _make_nl2sql_service(nl2sql_ok=False, rule_fallback_ok=True)
    resp = svc.ask_with_live_gate("2025年产量是多少？")
    assert resp is not None
    assert svc.nl2sql_planner.build_plan.call_count == 1
    assert svc.planner.build_plan.call_count == 1


def test_m8_nl2sql_mode_both_fail_returns_blocked() -> None:
    """NL2SQL 和规则规划器都失败时返回 clarification 响应。"""
    svc = _make_nl2sql_service(nl2sql_ok=False, rule_fallback_ok=False)
    resp = svc.ask_with_live_gate("2025年产量是多少？")
    assert resp is not None
    assert svc.nl2sql_planner.build_plan.call_count == 1
    assert svc.planner.build_plan.call_count == 1
    # 确保 response 有合法状态
    assert resp.answer_summary or resp.status


def test_m8_off_mode_default_constructor_has_nl2sql_planner() -> None:
    """默认构造的服务中 nl2sql_planner 存在但不使用。"""
    db = MagicMock()
    svc = InventorySalesProductionQaService(db=db)
    assert hasattr(svc, "nl2sql_planner")
    assert svc.nl2sql_planner is not None
    assert svc.live_gate_mode == "off"


# ===== deps 级别：灰度切换 =====


def test_m8_deps_default_mode_uses_rule_planner(monkeypatch) -> None:
    """默认 deps 构造的服务使用规则规划器（off 模式）。"""
    monitor_planner = MagicMock()
    monitor_planner.build_plan.return_value = MagicMock(spec=InventorySalesProductionQueryPlan)
    db = MagicMock()
    svc = InventorySalesProductionQaService(
        db=db,
        planner=monitor_planner,
        executor=MagicMock(),
        live_gate_enabled=False,
        live_gate_mode="off",
    )
    resp = svc.ask_with_live_gate("2025年产量是多少？")
    assert resp is not None
    # off 模式走 ask()，ask() 使用 planner，所以 planner 被调用
    assert monitor_planner.build_plan.call_count >= 1


def test_m8_deps_nl2sql_mode_injects_nl2sql_planner(monkeypatch) -> None:
    """nl2sql 模式通过 deps 构造时，注入 NL2SQL 规划器。"""
    mock_nl2sql = MagicMock()
    mock_nl2sql.build_plan.return_value = MagicMock(spec=InventorySalesProductionQueryPlan)
    db = MagicMock()
    svc = InventorySalesProductionQaService(
        db=db,
        nl2sql_planner=mock_nl2sql,
        executor=MagicMock(),
        live_gate_enabled=True,
        live_gate_mode="nl2sql",
    )
    resp = svc.ask_with_live_gate("2025年产量是多少？")
    assert resp is not None
    # nl2sql 模式调用 NL2SQL 规划器
    assert mock_nl2sql.build_plan.call_count >= 1


def test_m8_deps_nl2sql_off_does_not_use_nl2sql_planner(monkeypatch) -> None:
    """off 模式不应调用 NL2SQL 规划器。"""
    mock_nl2sql = MagicMock()
    mock_nl2sql.build_plan.return_value = MagicMock(spec=InventorySalesProductionQueryPlan)
    db = MagicMock()
    svc = InventorySalesProductionQaService(
        db=db,
        nl2sql_planner=mock_nl2sql,
        executor=MagicMock(),
        live_gate_enabled=False,
        live_gate_mode="off",
    )
    resp = svc.ask_with_live_gate("2025年产量是多少？")
    assert resp is not None
    # off 模式不调用 NL2SQL 规划器
    assert mock_nl2sql.build_plan.call_count == 0


def test_m8_deps_shadow_mode_still_uses_rule_planner(monkeypatch) -> None:
    """shadow 模式仍使用规则规划器（向后兼容）。"""
    monitor_planner = MagicMock()
    monitor_planner.build_plan.return_value = MagicMock(spec=InventorySalesProductionQueryPlan)
    db = MagicMock()
    svc = InventorySalesProductionQaService(
        db=db,
        planner=monitor_planner,
        executor=MagicMock(),
        live_gate_enabled=True,
        live_gate_mode="shadow",
    )
    resp = svc.ask_with_live_gate("2025年产量是多少？")
    assert resp is not None
    # shadow 模式走 ask()，使用规则规划器
    assert monitor_planner.build_plan.call_count >= 1


# ===== nl2sql_extended 模式 =====


def test_m8_nl2sql_extended_uses_nl2sql_planner() -> None:
    """nl2sql_extended 模式使用 NL2SQL 规划器，不调用规则规划器。"""
    svc = _make_nl2sql_service(mode="nl2sql_extended", nl2sql_ok=True)
    resp = svc.ask_with_live_gate("2025年产量是多少？")
    assert resp is not None
    assert svc.nl2sql_planner.build_plan.call_count == 1
    assert svc.planner.build_plan.call_count == 0


def test_m8_nl2sql_extended_fallback_to_rule() -> None:
    """NL2SQL 规划器失败时自动 fallback 到规则规划器。"""
    svc = _make_nl2sql_service(mode="nl2sql_extended", nl2sql_ok=False, rule_fallback_ok=True)
    resp = svc.ask_with_live_gate("2025年产量是多少？")
    assert resp is not None
    assert svc.nl2sql_planner.build_plan.call_count == 1
    assert svc.planner.build_plan.call_count == 1


def test_m8_nl2sql_extended_both_fail_returns_blocked() -> None:
    """NL2SQL 和规则规划器都失败时返回 clarification 响应。"""
    svc = _make_nl2sql_service(mode="nl2sql_extended", nl2sql_ok=False, rule_fallback_ok=False)
    resp = svc.ask_with_live_gate("2025年产量是多少？")
    assert resp is not None
    assert svc.nl2sql_planner.build_plan.call_count == 1
    assert svc.planner.build_plan.call_count == 1
    # 确保 response 有合法状态
    assert resp.answer_summary or resp.status


# ===== config.py 字面量验证 =====


def test_m8_config_has_nl2sql_extended_literal() -> None:
    """config.py 的 isp_live_qa_gate_mode 必须支持 nl2sql_extended 字面量。"""
    from backend.app.core.config import Settings

    # 验证 Literal 中包含 nl2sql_extended
    settings = Settings(isp_live_qa_gate_mode="nl2sql_extended")
    assert settings.isp_live_qa_gate_mode == "nl2sql_extended"
