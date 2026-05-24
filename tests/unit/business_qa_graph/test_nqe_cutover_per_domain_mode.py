"""四域 on-mode 配置隔离测试。"""

from backend.app.core.config import Settings


def test_logistics_default_on() -> None:
    assert Settings().nqe_logistics_mode == "on"


def test_business_analysis_default_on() -> None:
    assert Settings().nqe_business_analysis_mode == "on"


def test_plan_bom_default_on() -> None:
    assert Settings().nqe_plan_bom_mode == "on"


def test_power_default_on() -> None:
    assert Settings().nqe_power_prediction_mode == "on"


def test_production_guard() -> None:
    s = Settings()
    assert s.IS_PRODUCTION is False
    assert s.app_env == "local"


def test_one_domain_off_does_not_affect_others() -> None:
    s = Settings(nqe_logistics_mode="off")
    assert s.nqe_logistics_mode == "off"
    assert s.nqe_business_analysis_mode == "on"
    assert s.nqe_plan_bom_mode == "on"
    assert s.nqe_power_prediction_mode == "on"


def test_production_env_forced_off() -> None:
    """production 环境可以通过 env var 覆盖为 off。"""
    s = Settings(app_env="prod", nqe_logistics_mode="off")
    assert s.IS_PRODUCTION is True
    assert s.nqe_logistics_mode == "off"
