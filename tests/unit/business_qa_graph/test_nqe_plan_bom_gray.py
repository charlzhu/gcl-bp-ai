"""NQE BOM gray mode tests."""
from __future__ import annotations

from backend.app.core.config import Settings


def test_default_bom_mode_is_off() -> None:
    s = Settings()
    assert s.nqe_plan_bom_mode == "off"


def test_bom_mode_can_be_shadow() -> None:
    s = Settings(nqe_plan_bom_mode="shadow")
    assert s.nqe_plan_bom_mode == "shadow"


def test_all_modes_accepted() -> None:
    for mode in ("off", "shadow", "assist", "on"):
        s = Settings(nqe_plan_bom_mode=mode)
        assert s.nqe_plan_bom_mode == mode
