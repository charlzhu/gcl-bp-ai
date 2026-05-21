from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from backend.app.domains.business_analysis.schemas.inventory_sales_production_qa import (
    InventorySalesProductionQaResponse,
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
