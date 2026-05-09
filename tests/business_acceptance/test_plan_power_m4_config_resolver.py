from __future__ import annotations

from collections import Counter

import pytest

from backend.app.db.session import SessionLocal
from backend.app.domains.plan_bom.models import PlanBomHeader, PlanBomMaterialLine, PlanPowerFactorOption, PlanPowerModelSheet, PlanPowerModelVersion
from backend.app.domains.plan_bom.services.power_config_resolver_service import (
    CANDIDATE_LIMIT,
    CANDIDATE_REQUIRED_STATUS,
    PARTIAL_STATUS,
    RESOLVED_STATUS,
    PlanBomPowerConfigResolverService,
)
from backend.app.domains.plan_bom.services.power_prediction_engine import PowerPredictionEngine


@pytest.fixture()
def live_db_session():
    """连接当前项目真实数据库，供 M4 验收从真实 BOM 中动态抽题。"""
    session = SessionLocal()
    try:
        try:
            session.query(PlanBomHeader).limit(1).all()
        except Exception as exc:  # pragma: no cover - 仅用于缺少本地验收库时跳过。
            pytest.skip(f"当前环境无法连接真实 BOM 数据库，跳过 M4 真实数据验收：{exc}")
        yield session
    finally:
        session.close()


def _active_version(session) -> PlanPowerModelVersion:
    """读取当前 active 功率模型版本。"""
    version = session.query(PlanPowerModelVersion).filter_by(is_active=1).first()
    if version is None:
        pytest.skip("当前数据库没有 active 功率模型版本，无法执行 M4 验收。")
    return version


def _valid_option_labels(session, model_code: str, factor_key: str) -> set[str]:
    """读取某版型某配置项的有效 option，用于验证 M4 输出没有编造。"""
    version = _active_version(session)
    sheet = session.query(PlanPowerModelSheet).filter_by(version_id=version.id, normalized_model_code=model_code).first()
    assert sheet is not None
    return {
        row.option_label
        for row in session.query(PlanPowerFactorOption)
        .filter_by(sheet_id=sheet.id, factor_key=factor_key, is_valid=1)
        .all()
    }


def _resolve_first_real_order(session):
    """从真实 BOM 中动态寻找一条能完整映射的订单。"""
    service = PlanBomPowerConfigResolverService(session)
    headers = session.query(PlanBomHeader).filter_by(is_active=1).order_by(PlanBomHeader.id.asc()).all()
    for header in headers:
        result = service.resolve(
            order_identity_key=header.order_identity_key,
            file_instance_key=header.file_instance_key,
            version_no=header.version_no,
        )
        required = {"model_code", "glass", "ribbon", "busbar", "cable", "cell_size", "supplier", "benchmark"}
        if result.status == RESOLVED_STATUS and required.issubset(result.resolved_config):
            return header, result
    pytest.fail("当前真实 BOM 数据中未找到可完整映射到 active 功率模型的订单。")


def test_resolves_real_order_to_power_configuration(live_db_session) -> None:
    """真实订单应能映射出版型、玻璃、焊带、汇流条、线缆、置信度和原始 BOM 描述。"""
    session = live_db_session
    header, result = _resolve_first_real_order(session)

    assert result.status == RESOLVED_STATUS
    assert result.order_no == header.order_no
    assert result.model_code in {row.normalized_model_code for row in session.query(PlanPowerModelSheet).filter_by(version_id=_active_version(session).id).all()}
    assert result.source_lines

    for factor_key in ["glass", "ribbon", "busbar", "cable"]:
        item = result.resolved_config[factor_key]
        assert item.value in _valid_option_labels(session, result.model_code, factor_key)
        assert item.source_line_ids
        assert item.source_description
        assert 0.0 < item.confidence <= 1.0

    prediction_config = result.to_prediction_configuration()
    assert "model_code" not in prediction_config
    assert prediction_config["glass"] == result.resolved_config["glass"].value
    assert prediction_config["ribbon"] == result.resolved_config["ribbon"].value
    assert prediction_config["busbar"] == result.resolved_config["busbar"].value
    assert prediction_config["cable"] == result.resolved_config["cable"].value


def test_resolved_configuration_can_drive_m3_prediction(live_db_session) -> None:
    """M4 输出的 configuration 必须能直接喂给 M3 确定性计算引擎。"""
    session = live_db_session
    _, result = _resolve_first_real_order(session)

    prediction = PowerPredictionEngine(session).predict(model_code=result.model_code, configuration=result.to_prediction_configuration())

    assert prediction.model_code == result.model_code
    assert prediction.center_power > 0
    assert prediction.power_bins
    assert abs(sum(prediction.weighted_distribution.values()) - 1.0) <= 0.02


def test_unknown_cable_length_returns_unresolved_item(live_db_session) -> None:
    """真实 BOM 中无法映射的接线盒线长不能瞎猜，必须返回 unresolved_items。"""
    session = live_db_session
    line = (
        session.query(PlanBomMaterialLine)
        .filter(PlanBomMaterialLine.material_category == "junction_box", PlanBomMaterialLine.description.contains("1000mm"))
        .order_by(PlanBomMaterialLine.id.asc())
        .first()
    )
    if line is None:
        pytest.skip("当前真实 BOM 中没有 1000mm 接线盒样本，跳过无法映射用例。")
    header = (
        session.query(PlanBomHeader)
        .filter_by(
            order_identity_key=line.order_identity_key,
            file_instance_key=line.file_instance_key,
            version_no=line.version_no,
            source_type=line.source_type,
            is_active=1,
        )
        .first()
    )
    assert header is not None

    result = PlanBomPowerConfigResolverService(session).resolve(
        order_identity_key=header.order_identity_key,
        file_instance_key=header.file_instance_key,
        version_no=header.version_no,
    )

    assert result.status == PARTIAL_STATUS
    cable_unresolved = [item for item in result.unresolved_items if item.factor_key == "cable"]
    assert cable_unresolved
    assert cable_unresolved[0].strategy == "ask_confirmation"
    assert cable_unresolved[0].candidate_options
    assert any("1000mm" in description for description in cable_unresolved[0].source_descriptions)


def test_model_aliases_normalize_bom_order_name(live_db_session) -> None:
    """订单名称中的 NT12R/66GDF 必须归一化为功率模型版型 NT12R-66GDF。"""
    session = live_db_session
    header = (
        session.query(PlanBomHeader)
        .filter(PlanBomHeader.is_active == 1, PlanBomHeader.order_name.contains("NT12R/66GDF"))
        .order_by(PlanBomHeader.id.asc())
        .first()
    )
    if header is None:
        pytest.skip("当前真实 BOM 中没有 NT12R/66GDF 订单，跳过别名验收。")

    result = PlanBomPowerConfigResolverService(session).resolve(
        order_identity_key=header.order_identity_key,
        file_instance_key=header.file_instance_key,
        version_no=header.version_no,
    )

    assert result.model_code == "NT12R-66GDF"
    assert result.resolved_config["model_code"].source == "bom_header.order_name"


def test_cable_length_without_wire_size_returns_unresolved(live_db_session) -> None:
    """接线盒只给线长但未给线径时不能默认猜 4mm²。"""
    session = live_db_session
    line = (
        session.query(PlanBomMaterialLine)
        .filter(
            PlanBomMaterialLine.material_category == "junction_box",
            PlanBomMaterialLine.description.contains("+400/-200mm"),
            ~PlanBomMaterialLine.description.contains("4mm²"),
            ~PlanBomMaterialLine.description.contains("6mm²"),
            ~PlanBomMaterialLine.description.contains("4mm2"),
            ~PlanBomMaterialLine.description.contains("6mm2"),
        )
        .order_by(PlanBomMaterialLine.id.asc())
        .first()
    )
    if line is None:
        pytest.skip("当前真实 BOM 中没有只写线长但未写线径的接线盒样本，跳过 fail-closed 用例。")
    header = (
        session.query(PlanBomHeader)
        .filter_by(
            order_identity_key=line.order_identity_key,
            file_instance_key=line.file_instance_key,
            version_no=line.version_no,
            source_type=line.source_type,
            is_active=1,
        )
        .first()
    )
    assert header is not None

    result = PlanBomPowerConfigResolverService(session).resolve(
        order_identity_key=header.order_identity_key,
        file_instance_key=header.file_instance_key,
        version_no=header.version_no,
    )

    cable_items = [item for item in result.unresolved_items if item.factor_key == "cable"]
    assert cable_items
    assert "cable" not in result.to_prediction_configuration()
    assert cable_items[0].candidate_options


def test_invalid_explicit_benchmark_returns_unresolved(live_db_session) -> None:
    """显式输入的标板基准无效时，不能悄悄回退模型默认值。"""
    session = live_db_session
    _, baseline = _resolve_first_real_order(session)

    result = PlanBomPowerConfigResolverService(session).resolve(
        order_identity_key=baseline.order_identity_key,
        file_instance_key=baseline.file_instance_key,
        version_no=baseline.version_no,
        benchmark="不存在的标板基准",
    )

    benchmark_items = [item for item in result.unresolved_items if item.factor_key == "benchmark"]
    assert result.status == PARTIAL_STATUS
    assert benchmark_items
    assert benchmark_items[0].candidate_options
    assert result.resolved_config.get("benchmark") is None


def test_glass_negative_words_do_not_match_glazed_rules(live_db_session) -> None:
    """显式非镀釉/非镀膜文本不能因包含“镀釉”子串而误命中镀釉规则。"""
    service = PlanBomPowerConfigResolverService(live_db_session)
    rules = {
        rule["id"]: rule
        for rule in service.mapping["factor_mappings"]["glass"]["rules"]
    }

    text = "光伏玻璃 双镀膜 非镀釉 非镀膜"
    assert not service._text_matches_rule(text, "", rules["double_glazed"])
    assert service._text_matches_rule(text, "", rules["double_non_glazed"])

    single_text = "光伏玻璃 单镀 非镀釉"
    assert not service._text_matches_rule(single_text, "", rules["single_glazed"])
    assert service._text_matches_rule(single_text, "", rules["single_non_glazed"])


def test_cable_aliases_do_not_default_missing_wire_size(live_db_session) -> None:
    """配置别名中不得保留裸线长 -> 4mm² 的默认转换。"""
    service = PlanBomPowerConfigResolverService(live_db_session)
    cable_aliases = service.aliases["option_aliases"].get("cable") or {}
    assert "300/200" not in cable_aliases
    assert "+300/-200mm" not in cable_aliases
    assert "400/200" not in cable_aliases
    assert "+400/-200mm" not in cable_aliases


def test_multiple_real_orders_return_candidate_required(live_db_session) -> None:
    """同一订单号命中多个真实订单实例时，M4 只能返回候选，不能自动猜一个。"""
    session = live_db_session
    rows = session.query(PlanBomHeader).filter_by(is_active=1).all()
    order_counts = Counter(row.order_no for row in rows)
    order_no = next((key for key, count in order_counts.items() if count > 1), None)
    if order_no is None:
        pytest.skip("当前真实 BOM 中没有多实例订单，跳过候选态验收。")

    result = PlanBomPowerConfigResolverService(session).resolve(order_no=order_no)

    assert result.status == CANDIDATE_REQUIRED_STATUS
    assert 2 <= len(result.candidates) <= CANDIDATE_LIMIT
    assert result.candidate_total_count >= len(result.candidates)
    assert result.candidate_has_more == (result.candidate_total_count > CANDIDATE_LIMIT)
    assert all(candidate.order_no == order_no for candidate in result.candidates)
