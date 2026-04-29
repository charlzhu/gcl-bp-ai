from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.db.base import Base
from backend.app.domains.plan_bom.identity import build_file_instance_key, build_order_identity_key
from backend.app.domains.plan_bom.constants import (
    CANDIDATE_SCOPE_FILE_INSTANCE,
    CANDIDATE_SCOPE_ORDER_IDENTITY,
    CANDIDATE_SCOPE_VERSION,
    MATERIAL_CATEGORY_BUSBAR,
    MATERIAL_CATEGORY_GAP_FILM,
    MATERIAL_CATEGORY_GLASS,
    MATERIAL_CATEGORY_INTERCONNECT_BAR,
    MATERIAL_CATEGORY_JUNCTION_BOX,
    QUERY_TYPE_PLAN_BOM_COMPARE,
    SOURCE_TAG_MANUAL_IMPORT,
    SOURCE_TYPE_EXCEL,
    STATUS_CODE_CANDIDATE_REQUIRED,
    STATUS_CODE_OK,
    STATUS_CODE_VERSION_NEED_CONFIRM,
)
from backend.app.domains.plan_bom.models import PlanBomHeader, PlanBomMaterialLine
from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
from backend.app.domains.plan_bom.schemas.query import (
    PlanBomCompareQueryRequest,
    PlanBomCompareSideRequest,
    PlanBomDetailQueryRequest,
)
from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService
from backend.app.models.sys_query_log import SysQueryLog


def _build_session() -> Session:
    """创建计划 BOM 查询测试用内存数据库。

    返回：
        已完成建表的 SQLAlchemy Session。
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine)
    return session_factory()


def _query_log_row(session: Session, log_id: int) -> SysQueryLog | None:
    """读取单条 sys_query_log，便于断言 compare 历史快照。"""
    return session.query(SysQueryLog).filter(SysQueryLog.id == log_id).first()


def _add_header(
    session: Session,
    *,
    order_no: str,
    version_no: str,
    order_name: str = "测试订单",
    effective_date: date | None = None,
    raw_file_name: str = "bom.xlsx",
    file_hash: str | None = None,
) -> PlanBomHeader:
    """写入一条 BOM 头测试数据。"""
    order_identity_key = build_order_identity_key(order_no, order_name, raw_file_name)
    header = PlanBomHeader(
        order_no=order_no,
        version_no=version_no,
        order_identity_key=order_identity_key,
        file_instance_key=build_file_instance_key(
            order_identity_key,
            version_no,
            SOURCE_TYPE_EXCEL,
            raw_file_name,
            file_hash,
        ),
        order_name=order_name,
        effective_date=effective_date,
        source_type=SOURCE_TYPE_EXCEL,
        source_tag=SOURCE_TAG_MANUAL_IMPORT,
        import_batch_id="batch-query",
        raw_file_name=raw_file_name,
        raw_sheet_name="BOM",
    )
    session.add(header)
    return header


def _add_material(
    session: Session,
    *,
    order_identity_key: str,
    file_instance_key: str,
    order_no: str,
    version_no: str,
    sap_code: str,
    material_category: str,
    material_name: str,
    raw_row_no: int,
) -> PlanBomMaterialLine:
    """写入一条 BOM 材料行测试数据。"""
    line = PlanBomMaterialLine(
        order_no=order_no,
        version_no=version_no,
        order_identity_key=order_identity_key,
        file_instance_key=file_instance_key,
        sap_code=sap_code,
        line_no=str(raw_row_no),
        material_name=material_name,
        material_category=material_category,
        description=f"{material_name} 规格描述",
        standard_usage=Decimal("1.5"),
        unit="件",
        production_loss="0.01%",
        source_type=SOURCE_TYPE_EXCEL,
        source_tag=SOURCE_TAG_MANUAL_IMPORT,
        import_batch_id="batch-query",
        raw_row_no=raw_row_no,
    )
    session.add(line)
    return line


def _query_service(session: Session) -> PlanBomQueryService:
    """创建计划 BOM 查询服务。"""
    return PlanBomQueryService(repository=PlanBomQueryRepository(session))


def test_plan_bom_query_by_order_no_selects_current_version_and_core_materials() -> None:
    """验证订单号查询会按当前版本规则选择 A10，并返回 5 类核心材料。"""
    session = _build_session()
    _add_header(session, order_no="GCL-2026-001", version_no="A2", effective_date=date(2026, 4, 1))
    selected_header = _add_header(session, order_no="GCL-2026-001", version_no="A10", effective_date=date(2026, 4, 1))
    categories = [
        (MATERIAL_CATEGORY_GLASS, "光伏玻璃"),
        (MATERIAL_CATEGORY_GAP_FILM, "间隙膜"),
        (MATERIAL_CATEGORY_INTERCONNECT_BAR, "互联条"),
        (MATERIAL_CATEGORY_BUSBAR, "汇流条"),
        (MATERIAL_CATEGORY_JUNCTION_BOX, "接线盒"),
    ]
    for index, (category, material_name) in enumerate(categories, start=1):
        _add_material(
            session,
            order_identity_key=selected_header.order_identity_key,
            file_instance_key=selected_header.file_instance_key,
            order_no="GCL-2026-001",
            version_no="A10",
            sap_code=f"SAP-{index}",
            material_category=category,
            material_name=material_name,
            raw_row_no=index,
        )
    session.commit()

    result = _query_service(session).detail(PlanBomDetailQueryRequest(order_no="GCL-2026-001"))

    assert result.status.code == STATUS_CODE_OK
    assert result.selected_version is not None
    assert result.selected_version.version_no == "A10"
    assert result.total == 5
    assert [item.material_category for item in result.items] == [category for category, _ in categories]


def test_plan_bom_query_by_review_no_returns_candidate_list() -> None:
    """验证评审号别名多命中时不会误选订单，而是返回候选列表。"""
    session = _build_session()
    _add_header(session, order_no="创维-01182-A", version_no="A1", order_name="创维订单 A", effective_date=date(2026, 4, 1))
    _add_header(session, order_no="创维-01182-B", version_no="A1", order_name="创维订单 B", effective_date=date(2026, 4, 2))
    session.commit()

    result = _query_service(session).detail(PlanBomDetailQueryRequest(review_no="01182", candidate_limit=1))

    assert result.query_type == "candidate_list"
    assert result.status.code == STATUS_CODE_CANDIDATE_REQUIRED
    assert result.candidate_total_hint == 2
    assert len(result.candidates) == 1
    assert result.response_meta["candidate_truncated"] is True
    assert result.candidates[0].match_reason == "review_no_like"


def test_plan_bom_query_by_order_name_and_material_filter() -> None:
    """验证订单名称查询和指定材料类别过滤。"""
    session = _build_session()
    header = _add_header(
        session,
        order_no="GCL-2026-SYNAPSUN-00114",
        version_no="A1",
        order_name="法国 Synapsun 订单",
        effective_date=date(2026, 4, 1),
    )
    _add_material(
        session,
        order_identity_key=header.order_identity_key,
        file_instance_key=header.file_instance_key,
        order_no="GCL-2026-SYNAPSUN-00114",
        version_no="A1",
        sap_code="GLASS-001",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    )
    _add_material(
        session,
        order_identity_key=header.order_identity_key,
        file_instance_key=header.file_instance_key,
        order_no="GCL-2026-SYNAPSUN-00114",
        version_no="A1",
        sap_code="BUSBAR-001",
        material_category=MATERIAL_CATEGORY_BUSBAR,
        material_name="汇流条",
        raw_row_no=2,
    )
    session.commit()

    result = _query_service(session).detail(
        PlanBomDetailQueryRequest(order_name="Synapsun", material_categories=[MATERIAL_CATEGORY_GLASS])
    )

    assert result.status.code == STATUS_CODE_OK
    assert result.selected_version is not None
    assert result.selected_version.order_no == "GCL-2026-SYNAPSUN-00114"
    assert result.total == 1
    assert result.items[0].material_category == MATERIAL_CATEGORY_GLASS


def test_plan_bom_query_version_need_confirm_when_natural_version_ties() -> None:
    """验证自然序版本无法唯一判定时返回版本候选，不随机选择。"""
    session = _build_session()
    _add_header(session, order_no="GCL-2026-AMB", version_no="A2", effective_date=date(2026, 4, 1))
    _add_header(session, order_no="GCL-2026-AMB", version_no="A02", effective_date=date(2026, 4, 1))
    session.commit()

    result = _query_service(session).detail(PlanBomDetailQueryRequest(order_no="GCL-2026-AMB"))

    assert result.status.code == STATUS_CODE_VERSION_NEED_CONFIRM
    assert result.query_type == "candidate_list"
    assert result.candidate_total_hint == 2


def test_plan_bom_query_by_review_no_matches_order_name_and_filters_noise_lines() -> None:
    """验证评审号别名可命中订单名称，同时查询结果会过滤图纸和标签噪音。"""
    session = _build_session()
    header = _add_header(
        session,
        order_no="GCL-2026-00067",
        version_no="A1",
        order_name="NT10/78GDF（哥伦比亚COEXITO -2026-00067）",
        effective_date=date(2026, 4, 2),
    )
    _add_material(
        session,
        order_identity_key=header.order_identity_key,
        file_instance_key=header.file_instance_key,
        order_no="GCL-2026-00067",
        version_no="A1",
        sap_code="JBOX-001",
        material_category=MATERIAL_CATEGORY_JUNCTION_BOX,
        material_name="接线盒",
        raw_row_no=1,
    ).description = "接线盒\\GCL\\GCL-N1xyz\\有价值"
    _add_material(
        session,
        order_identity_key=header.order_identity_key,
        file_instance_key=header.file_instance_key,
        order_no="GCL-2026-00067",
        version_no="A1",
        sap_code="GCL/XXJC/2-RD-5799",
        material_category=MATERIAL_CATEGORY_JUNCTION_BOX,
        material_name="A1",
        raw_row_no=2,
    ).description = "GCL标准物料标签-接线盒 A1"
    session.commit()

    result = _query_service(session).detail(
        PlanBomDetailQueryRequest(review_no="COEXITO-2026-00067", material_categories=[MATERIAL_CATEGORY_JUNCTION_BOX])
    )

    assert result.status.code == STATUS_CODE_OK
    assert result.selected_version is not None
    assert result.selected_version.order_no == "GCL-2026-00067"
    assert result.total == 1
    assert result.items[0].sap_code == "JBOX-001"


def test_plan_bom_query_same_business_key_returns_candidate_list_by_instance_identity() -> None:
    """验证同一业务键下存在两个 Excel 实例时，短订单号查询返回候选列表而不是误落单。"""
    session = _build_session()
    first_header = _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00106",
        version_no="A0",
        order_name="江苏汉腾",
        raw_file_name="NT1078GDF(江苏汉腾-2026-00106)Billofmaterials-A.xls",
    )
    second_header = _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00106",
        version_no="A0",
        order_name="石家庄科林",
        raw_file_name="NT1078GDF(石家庄科林-2026-00106)Billofmaterials-A.xls",
    )
    _add_material(
        session,
        order_identity_key=first_header.order_identity_key,
        file_instance_key=first_header.file_instance_key,
        order_no=first_header.order_no,
        version_no=first_header.version_no,
        sap_code="GLASS-JSHT",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    )
    _add_material(
        session,
        order_identity_key=second_header.order_identity_key,
        file_instance_key=second_header.file_instance_key,
        order_no=second_header.order_no,
        version_no=second_header.version_no,
        sap_code="GLASS-SJZKL",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    )
    session.commit()

    candidate_result = _query_service(session).detail(PlanBomDetailQueryRequest(order_no="00106"))

    assert candidate_result.query_type == "candidate_list"
    assert candidate_result.status.code == STATUS_CODE_CANDIDATE_REQUIRED
    assert candidate_result.candidate_scope == CANDIDATE_SCOPE_ORDER_IDENTITY
    assert candidate_result.candidate_total_hint == 2
    assert {candidate.order_name for candidate in candidate_result.candidates} == {"江苏汉腾", "石家庄科林"}
    assert all(candidate.order_identity_key for candidate in candidate_result.candidates)

    selected_result = _query_service(session).detail(
        PlanBomDetailQueryRequest(order_identity_key=first_header.order_identity_key, material_categories=[MATERIAL_CATEGORY_GLASS])
    )

    assert selected_result.status.code == STATUS_CODE_OK
    assert selected_result.selected_version is not None
    assert selected_result.selected_version.order_identity_key == first_header.order_identity_key
    assert selected_result.total == 1
    assert selected_result.items[0].sap_code == "GLASS-JSHT"


def test_plan_bom_query_same_identity_same_version_returns_file_instance_candidates() -> None:
    """验证同一业务实例同版本多文件时，会返回文件实例候选而不是直接落单。"""
    session = _build_session()
    first_header = _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00120",
        version_no="A0",
        order_name="肯尼亚 Nationwide",
        raw_file_name="NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (2).xls",
        file_hash="hash-a2",
    )
    second_header = _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00120",
        version_no="A0",
        order_name="肯尼亚 Nationwide",
        raw_file_name="NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (3).xls",
        file_hash="hash-a3",
    )
    _add_material(
        session,
        order_identity_key=first_header.order_identity_key,
        file_instance_key=first_header.file_instance_key,
        order_no=first_header.order_no,
        version_no=first_header.version_no,
        sap_code="GLASS-A2",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    ).description = "光伏玻璃\\GCL\\有价值"
    _add_material(
        session,
        order_identity_key=second_header.order_identity_key,
        file_instance_key=second_header.file_instance_key,
        order_no=second_header.order_no,
        version_no=second_header.version_no,
        sap_code="GLASS-A3",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    ).description = "光伏玻璃\\信义\\有价值"
    session.commit()

    candidate_result = _query_service(session).detail(PlanBomDetailQueryRequest(order_no="2026-00120"))

    assert candidate_result.query_type == "candidate_list"
    assert candidate_result.status.code == STATUS_CODE_CANDIDATE_REQUIRED
    assert candidate_result.candidate_scope == CANDIDATE_SCOPE_FILE_INSTANCE
    assert candidate_result.candidate_total_hint == 2
    assert {candidate.file_instance_key for candidate in candidate_result.candidates} == {
        first_header.file_instance_key,
        second_header.file_instance_key,
    }

    selected_result = _query_service(session).detail(
        PlanBomDetailQueryRequest(
            file_instance_key=first_header.file_instance_key,
            material_categories=[MATERIAL_CATEGORY_GLASS],
        )
    )

    assert selected_result.status.code == STATUS_CODE_OK
    assert selected_result.selected_version is not None
    assert selected_result.selected_version.file_instance_key == first_header.file_instance_key
    assert selected_result.total == 1
    assert selected_result.items[0].sap_code == "GLASS-A2"


def test_plan_bom_compare_returns_order_identity_candidates_for_left_side() -> None:
    """验证 compare 左侧命中多个业务实例时返回 order_identity 候选。"""
    session = _build_session()
    _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00106",
        version_no="A0",
        order_name="江苏汉腾",
        raw_file_name="NT1078GDF(江苏汉腾-2026-00106)Billofmaterials-A.xls",
    )
    _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00106",
        version_no="A0",
        order_name="石家庄科林",
        raw_file_name="NT1078GDF(石家庄科林-2026-00106)Billofmaterials-A.xls",
    )
    _add_header(
        session,
        order_no="GCL-2026-BASE-RIGHT",
        version_no="A1",
        order_name="右侧基准订单",
        effective_date=date(2026, 4, 1),
    )
    session.commit()

    result = _query_service(session).compare(
        PlanBomCompareQueryRequest(
            left=PlanBomCompareSideRequest(order_no="00106"),
            right=PlanBomCompareSideRequest(order_no="GCL-2026-BASE-RIGHT"),
        )
    )

    assert result.query_type == "candidate_list"
    assert result.status.code == STATUS_CODE_CANDIDATE_REQUIRED
    assert result.candidate_scope == CANDIDATE_SCOPE_ORDER_IDENTITY
    assert result.candidate_side == "left"
    assert result.candidate_total_hint == 2


def test_plan_bom_compare_returns_file_instance_candidates_for_left_side() -> None:
    """验证 compare 左侧命中同一版本多个文件实例时返回 file_instance 候选。"""
    session = _build_session()
    _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00120",
        version_no="A0",
        order_name="肯尼亚 Nationwide",
        raw_file_name="NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (2).xls",
        file_hash="hash-a2",
    )
    _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00120",
        version_no="A0",
        order_name="肯尼亚 Nationwide",
        raw_file_name="NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (3).xls",
        file_hash="hash-a3",
    )
    _add_header(
        session,
        order_no="GCL-2026-BASE-RIGHT",
        version_no="A1",
        order_name="右侧基准订单",
        effective_date=date(2026, 4, 1),
    )
    session.commit()

    result = _query_service(session).compare(
        PlanBomCompareQueryRequest(
            left=PlanBomCompareSideRequest(order_no="2026-00120"),
            right=PlanBomCompareSideRequest(order_no="GCL-2026-BASE-RIGHT"),
        )
    )

    assert result.query_type == "candidate_list"
    assert result.status.code == STATUS_CODE_CANDIDATE_REQUIRED
    assert result.candidate_scope == CANDIDATE_SCOPE_FILE_INSTANCE
    assert result.candidate_side == "left"
    assert result.candidate_total_hint == 2


def test_plan_bom_compare_returns_version_candidates_for_ambiguous_current_version() -> None:
    """验证 compare 单侧当前版本无法自动判定时返回 version 候选。"""
    session = _build_session()
    _add_header(session, order_no="GCL-2026-AMB-COMPARE", version_no="A2", effective_date=date(2026, 4, 1))
    _add_header(session, order_no="GCL-2026-AMB-COMPARE", version_no="A02", effective_date=date(2026, 4, 1))
    _add_header(
        session,
        order_no="GCL-2026-BASE-RIGHT",
        version_no="A1",
        order_name="右侧基准订单",
        effective_date=date(2026, 4, 2),
    )
    session.commit()

    result = _query_service(session).compare(
        PlanBomCompareQueryRequest(
            left=PlanBomCompareSideRequest(order_no="GCL-2026-AMB-COMPARE"),
            right=PlanBomCompareSideRequest(order_no="GCL-2026-BASE-RIGHT"),
        )
    )

    assert result.query_type == "candidate_list"
    assert result.status.code == STATUS_CODE_VERSION_NEED_CONFIRM
    assert result.candidate_scope == CANDIDATE_SCOPE_VERSION
    assert result.candidate_side == "left"
    assert result.candidate_total_hint == 2


def test_plan_bom_compare_returns_ready_response_after_explicit_selection() -> None:
    """验证左右两侧都已明确时返回 compare 骨架结果，不误返回候选。"""
    session = _build_session()
    left_header = _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00120",
        version_no="A0",
        order_name="肯尼亚 Nationwide",
        raw_file_name="NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (2).xls",
        file_hash="hash-a2",
        effective_date=date(2026, 4, 1),
    )
    _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00120",
        version_no="A0",
        order_name="肯尼亚 Nationwide",
        raw_file_name="NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (3).xls",
        file_hash="hash-a3",
        effective_date=date(2026, 4, 1),
    )
    right_header = _add_header(
        session,
        order_no="GCL-2026-BASE-RIGHT",
        version_no="A1",
        order_name="右侧基准订单",
        effective_date=date(2026, 4, 2),
    )
    session.commit()

    result = _query_service(session).compare(
        PlanBomCompareQueryRequest(
            left=PlanBomCompareSideRequest(file_instance_key=left_header.file_instance_key),
            right=PlanBomCompareSideRequest(order_identity_key=right_header.order_identity_key),
        )
    )

    assert result.query_type == QUERY_TYPE_PLAN_BOM_COMPARE
    assert result.status.code == STATUS_CODE_OK
    assert result.compare_ready is True
    assert result.left is not None
    assert result.right is not None
    assert result.left.file_instance_key == left_header.file_instance_key
    assert result.right.order_identity_key == right_header.order_identity_key
    assert result.candidate_scope is None


def test_plan_bom_compare_between_two_orders_returns_diff_buckets() -> None:
    """验证两订单 compare 会输出 only_left / only_right / changed / same 结果结构。"""
    session = _build_session()
    left_header = _add_header(
        session,
        order_no="GCL-2026-COMP-LEFT",
        version_no="A1",
        order_name="左侧订单",
        effective_date=date(2026, 4, 1),
    )
    right_header = _add_header(
        session,
        order_no="GCL-2026-COMP-RIGHT",
        version_no="A1",
        order_name="右侧订单",
        effective_date=date(2026, 4, 1),
    )
    _add_material(
        session,
        order_identity_key=left_header.order_identity_key,
        file_instance_key=left_header.file_instance_key,
        order_no=left_header.order_no,
        version_no=left_header.version_no,
        sap_code="GLASS-SAME",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    ).description = "玻璃一致"
    _add_material(
        session,
        order_identity_key=right_header.order_identity_key,
        file_instance_key=right_header.file_instance_key,
        order_no=right_header.order_no,
        version_no=right_header.version_no,
        sap_code="GLASS-SAME",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    ).description = "玻璃一致"
    _add_material(
        session,
        order_identity_key=left_header.order_identity_key,
        file_instance_key=left_header.file_instance_key,
        order_no=left_header.order_no,
        version_no=left_header.version_no,
        sap_code="BUS-CHANGED",
        material_category=MATERIAL_CATEGORY_BUSBAR,
        material_name="汇流条",
        raw_row_no=2,
    ).description = "左侧汇流条"
    _add_material(
        session,
        order_identity_key=right_header.order_identity_key,
        file_instance_key=right_header.file_instance_key,
        order_no=right_header.order_no,
        version_no=right_header.version_no,
        sap_code="BUS-CHANGED",
        material_category=MATERIAL_CATEGORY_BUSBAR,
        material_name="汇流条",
        raw_row_no=2,
    ).description = "右侧汇流条"
    _add_material(
        session,
        order_identity_key=left_header.order_identity_key,
        file_instance_key=left_header.file_instance_key,
        order_no=left_header.order_no,
        version_no=left_header.version_no,
        sap_code="GAP-ONLY-LEFT",
        material_category=MATERIAL_CATEGORY_GAP_FILM,
        material_name="间隙膜",
        raw_row_no=3,
    )
    _add_material(
        session,
        order_identity_key=right_header.order_identity_key,
        file_instance_key=right_header.file_instance_key,
        order_no=right_header.order_no,
        version_no=right_header.version_no,
        sap_code="JBOX-ONLY-RIGHT",
        material_category=MATERIAL_CATEGORY_JUNCTION_BOX,
        material_name="接线盒",
        raw_row_no=3,
    )
    session.commit()

    result = _query_service(session).compare(
        PlanBomCompareQueryRequest(
            left=PlanBomCompareSideRequest(order_no=left_header.order_no),
            right=PlanBomCompareSideRequest(order_no=right_header.order_no),
        )
    )

    assert result.query_type == QUERY_TYPE_PLAN_BOM_COMPARE
    assert result.status.code == STATUS_CODE_OK
    assert result.compare_ready is True
    assert len(result.only_left) == 1
    assert result.only_left[0].item.sap_code == "GAP-ONLY-LEFT"
    assert len(result.only_right) == 1
    assert result.only_right[0].item.sap_code == "JBOX-ONLY-RIGHT"
    assert len(result.changed) == 1
    assert result.changed[0].match_key == f"{MATERIAL_CATEGORY_BUSBAR}|BUS-CHANGED"
    assert "description" in result.changed[0].changed_fields
    assert len(result.same) == 1
    assert result.same[0].match_key == f"{MATERIAL_CATEGORY_GLASS}|GLASS-SAME"
    assert result.diff_summary is not None
    assert result.diff_summary.only_left == 1
    assert result.diff_summary.only_right == 1
    assert result.diff_summary.changed == 1
    assert result.diff_summary.same == 1


def test_plan_bom_compare_same_order_different_versions_returns_changed_rows() -> None:
    """验证同订单不同版本 compare 可在候选已明确后输出差异结果。"""
    session = _build_session()
    left_header = _add_header(
        session,
        order_no="GCL-2026-COMP-VERSION",
        version_no="A0",
        order_name="版本对比订单",
        effective_date=date(2026, 4, 1),
    )
    right_header = _add_header(
        session,
        order_no="GCL-2026-COMP-VERSION",
        version_no="A1",
        order_name="版本对比订单",
        effective_date=date(2026, 4, 2),
    )
    _add_material(
        session,
        order_identity_key=left_header.order_identity_key,
        file_instance_key=left_header.file_instance_key,
        order_no=left_header.order_no,
        version_no=left_header.version_no,
        sap_code="INT-001",
        material_category=MATERIAL_CATEGORY_INTERCONNECT_BAR,
        material_name="互联条",
        raw_row_no=1,
    ).description = "A0 互联条"
    _add_material(
        session,
        order_identity_key=right_header.order_identity_key,
        file_instance_key=right_header.file_instance_key,
        order_no=right_header.order_no,
        version_no=right_header.version_no,
        sap_code="INT-001",
        material_category=MATERIAL_CATEGORY_INTERCONNECT_BAR,
        material_name="互联条",
        raw_row_no=1,
    ).description = "A1 互联条"
    session.commit()

    result = _query_service(session).compare(
        PlanBomCompareQueryRequest(
            left=PlanBomCompareSideRequest(order_no=left_header.order_no, version_no="A0"),
            right=PlanBomCompareSideRequest(order_no=right_header.order_no, version_no="A1"),
        )
    )

    assert result.status.code == STATUS_CODE_OK
    assert result.left is not None and result.left.version_no == "A0"
    assert result.right is not None and result.right.version_no == "A1"
    assert len(result.changed) == 1
    assert result.changed[0].match_key == f"{MATERIAL_CATEGORY_INTERCONNECT_BAR}|INT-001"
    assert "description" in result.changed[0].changed_fields
    assert result.diff_summary is not None
    assert result.diff_summary.changed == 1


def test_plan_bom_compare_between_file_instances_returns_changed_and_only_left() -> None:
    """验证指定 file_instance_key 后 compare 可输出文件实例差异结果。"""
    session = _build_session()
    left_header = _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00120",
        version_no="A0",
        order_name="肯尼亚 Nationwide",
        raw_file_name="NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (2).xls",
        file_hash="hash-a2",
        effective_date=date(2026, 4, 1),
    )
    right_header = _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00120",
        version_no="A0",
        order_name="肯尼亚 Nationwide",
        raw_file_name="NT12R66GDF(肯尼亚Nationwide-2026-00120)Billofmaterials-A (3).xls",
        file_hash="hash-a3",
        effective_date=date(2026, 4, 1),
    )
    _add_material(
        session,
        order_identity_key=left_header.order_identity_key,
        file_instance_key=left_header.file_instance_key,
        order_no=left_header.order_no,
        version_no=left_header.version_no,
        sap_code="GLASS-001",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    ).description = "光伏玻璃\\GCL"
    _add_material(
        session,
        order_identity_key=right_header.order_identity_key,
        file_instance_key=right_header.file_instance_key,
        order_no=right_header.order_no,
        version_no=right_header.version_no,
        sap_code="GLASS-001",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    ).description = "光伏玻璃\\信义"
    _add_material(
        session,
        order_identity_key=left_header.order_identity_key,
        file_instance_key=left_header.file_instance_key,
        order_no=left_header.order_no,
        version_no=left_header.version_no,
        sap_code="GAP-A2",
        material_category=MATERIAL_CATEGORY_GAP_FILM,
        material_name="间隙膜",
        raw_row_no=2,
    )
    session.commit()

    result = _query_service(session).compare(
        PlanBomCompareQueryRequest(
            left=PlanBomCompareSideRequest(file_instance_key=left_header.file_instance_key),
            right=PlanBomCompareSideRequest(file_instance_key=right_header.file_instance_key),
        )
    )

    assert result.status.code == STATUS_CODE_OK
    assert len(result.changed) == 1
    assert result.changed[0].match_key == f"{MATERIAL_CATEGORY_GLASS}|GLASS-001"
    assert len(result.only_left) == 1
    assert result.only_left[0].item.sap_code == "GAP-A2"
    assert len(result.only_right) == 0
    assert result.diff_summary is not None
    assert result.diff_summary.changed == 1
    assert result.diff_summary.only_left == 1


def test_plan_bom_compare_material_categories_filter_applies_before_diff() -> None:
    """验证 compare 的 material_categories 会在差异计算前生效。"""
    session = _build_session()
    left_header = _add_header(
        session,
        order_no="GCL-2026-COMP-FILTER-LEFT",
        version_no="A1",
        order_name="过滤左侧订单",
        effective_date=date(2026, 4, 1),
    )
    right_header = _add_header(
        session,
        order_no="GCL-2026-COMP-FILTER-RIGHT",
        version_no="A1",
        order_name="过滤右侧订单",
        effective_date=date(2026, 4, 1),
    )
    _add_material(
        session,
        order_identity_key=left_header.order_identity_key,
        file_instance_key=left_header.file_instance_key,
        order_no=left_header.order_no,
        version_no=left_header.version_no,
        sap_code="GLASS-FILTER-CHANGED",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    ).description = "左侧玻璃差异"
    _add_material(
        session,
        order_identity_key=right_header.order_identity_key,
        file_instance_key=right_header.file_instance_key,
        order_no=right_header.order_no,
        version_no=right_header.version_no,
        sap_code="GLASS-FILTER-CHANGED",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    ).description = "右侧玻璃差异"
    _add_material(
        session,
        order_identity_key=left_header.order_identity_key,
        file_instance_key=left_header.file_instance_key,
        order_no=left_header.order_no,
        version_no=left_header.version_no,
        sap_code="BUSBAR-FILTER-ONLY-LEFT",
        material_category=MATERIAL_CATEGORY_BUSBAR,
        material_name="汇流条",
        raw_row_no=2,
    )
    _add_material(
        session,
        order_identity_key=right_header.order_identity_key,
        file_instance_key=right_header.file_instance_key,
        order_no=right_header.order_no,
        version_no=right_header.version_no,
        sap_code="JBOX-FILTER-ONLY-RIGHT",
        material_category=MATERIAL_CATEGORY_JUNCTION_BOX,
        material_name="接线盒",
        raw_row_no=2,
    )
    session.commit()

    result = _query_service(session).compare(
        PlanBomCompareQueryRequest(
            left=PlanBomCompareSideRequest(order_no=left_header.order_no),
            right=PlanBomCompareSideRequest(order_no=right_header.order_no),
            material_categories=[MATERIAL_CATEGORY_GLASS],
        )
    )

    assert result.status.code == STATUS_CODE_OK
    assert len(result.only_left) == 0
    assert len(result.only_right) == 0
    assert len(result.same) == 0
    assert len(result.changed) == 1
    assert all(item.material_category == MATERIAL_CATEGORY_GLASS for item in result.only_left)
    assert all(item.material_category == MATERIAL_CATEGORY_GLASS for item in result.only_right)
    assert all(item.material_category == MATERIAL_CATEGORY_GLASS for item in result.changed)
    assert all(item.material_category == MATERIAL_CATEGORY_GLASS for item in result.same)
    assert result.diff_summary is not None
    assert len(result.diff_summary.categories) == 1
    assert result.diff_summary.categories[0].material_category == MATERIAL_CATEGORY_GLASS
    assert result.diff_summary.categories[0].changed == 1


def test_plan_bom_compare_success_writes_history_snapshot_and_supports_replay() -> None:
    """验证 compare 成功态会写入受控快照，并可按日志回放。"""
    session = _build_session()
    left_header = _add_header(
        session,
        order_no="GCL-2026-COMP-HISTORY-LEFT",
        version_no="A1",
        order_name="历史左侧订单",
        effective_date=date(2026, 4, 1),
    )
    right_header = _add_header(
        session,
        order_no="GCL-2026-COMP-HISTORY-RIGHT",
        version_no="A1",
        order_name="历史右侧订单",
        effective_date=date(2026, 4, 1),
    )
    _add_material(
        session,
        order_identity_key=left_header.order_identity_key,
        file_instance_key=left_header.file_instance_key,
        order_no=left_header.order_no,
        version_no=left_header.version_no,
        sap_code="GLASS-HISTORY",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    ).description = "左侧玻璃"
    _add_material(
        session,
        order_identity_key=right_header.order_identity_key,
        file_instance_key=right_header.file_instance_key,
        order_no=right_header.order_no,
        version_no=right_header.version_no,
        sap_code="GLASS-HISTORY",
        material_category=MATERIAL_CATEGORY_GLASS,
        material_name="光伏玻璃",
        raw_row_no=1,
    ).description = "右侧玻璃"
    session.commit()

    service = _query_service(session)
    result = service.compare(
        PlanBomCompareQueryRequest(
            left=PlanBomCompareSideRequest(order_no=left_header.order_no),
            right=PlanBomCompareSideRequest(order_no=right_header.order_no),
            material_categories=[MATERIAL_CATEGORY_GLASS],
        ),
        trace_id="trace-compare-history-success",
    )

    query_log_id = int(result.response_meta.get("query_log_id") or 0)
    assert query_log_id > 0
    row = _query_log_row(session, query_log_id)
    assert row is not None
    assert row.query_type == QUERY_TYPE_PLAN_BOM_COMPARE
    payload_json = json.loads(row.request_payload)
    assert payload_json["response_meta"]["snapshot_ready"] is True
    assert payload_json["query_result"]["compare_ready"] is True
    assert payload_json["query_result"]["diff_summary"]["changed"] == 1

    replay = service.compare_replay(log_id=query_log_id)

    assert replay.compare_ready is True
    assert replay.response_meta["replay_mode"] is True
    assert replay.response_meta["query_log_id"] == query_log_id
    assert replay.diff_summary is not None
    assert replay.diff_summary.changed == 1


def test_plan_bom_compare_candidate_history_snapshot_is_not_final() -> None:
    """验证 compare 候选态会写历史，但不会生成最终差异快照。"""
    session = _build_session()
    _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00106",
        version_no="A0",
        order_name="江苏汉腾",
        raw_file_name="NT1078GDF(江苏汉腾-2026-00106)Billofmaterials-A.xls",
    )
    _add_header(
        session,
        order_no="GCL-XXJC-JSPS-2026-00106",
        version_no="A0",
        order_name="石家庄科林",
        raw_file_name="NT1078GDF(石家庄科林-2026-00106)Billofmaterials-A.xls",
    )
    _add_header(
        session,
        order_no="GCL-2026-COMP-CAND-RIGHT",
        version_no="A1",
        order_name="右侧基准订单",
        effective_date=date(2026, 4, 1),
    )
    session.commit()

    service = _query_service(session)
    result = service.compare(
        PlanBomCompareQueryRequest(
            left=PlanBomCompareSideRequest(order_no="00106"),
            right=PlanBomCompareSideRequest(order_no="GCL-2026-COMP-CAND-RIGHT"),
        ),
        trace_id="trace-compare-history-candidate",
    )

    query_log_id = int(result.response_meta.get("query_log_id") or 0)
    assert query_log_id > 0
    row = _query_log_row(session, query_log_id)
    assert row is not None
    payload_json = json.loads(row.request_payload)
    assert payload_json["query_result"]["compare_ready"] is False
    assert payload_json["query_result"]["diff_summary"] is None
    assert payload_json["response_meta"]["snapshot_ready"] is False

    replay = service.compare_replay(log_id=query_log_id)

    assert replay.query_type == "candidate_list"
    assert replay.compare_ready is False
    assert replay.candidate_scope == CANDIDATE_SCOPE_ORDER_IDENTITY
    assert replay.candidate_side == "left"


def test_plan_bom_compare_history_snapshot_truncates_large_buckets() -> None:
    """验证 compare 历史快照会截断大体积明细桶，避免无限制堆积。"""
    session = _build_session()
    left_header = _add_header(
        session,
        order_no="GCL-2026-COMP-HISTORY-LIMIT-LEFT",
        version_no="A1",
        order_name="快照左侧订单",
        effective_date=date(2026, 4, 1),
    )
    right_header = _add_header(
        session,
        order_no="GCL-2026-COMP-HISTORY-LIMIT-RIGHT",
        version_no="A1",
        order_name="快照右侧订单",
        effective_date=date(2026, 4, 1),
    )
    for index in range(25):
        _add_material(
            session,
            order_identity_key=left_header.order_identity_key,
            file_instance_key=left_header.file_instance_key,
            order_no=left_header.order_no,
            version_no=left_header.version_no,
            sap_code=f"GLASS-LEFT-{index}",
            material_category=MATERIAL_CATEGORY_GLASS,
            material_name="光伏玻璃",
            raw_row_no=index + 1,
        ).description = f"左侧玻璃 {index}"
    for index in range(12):
        _add_material(
            session,
            order_identity_key=left_header.order_identity_key,
            file_instance_key=left_header.file_instance_key,
            order_no=left_header.order_no,
            version_no=left_header.version_no,
            sap_code=f"BUS-SAME-{index}",
            material_category=MATERIAL_CATEGORY_BUSBAR,
            material_name="汇流条",
            raw_row_no=100 + index,
        ).description = f"相同汇流条 {index}"
        _add_material(
            session,
            order_identity_key=right_header.order_identity_key,
            file_instance_key=right_header.file_instance_key,
            order_no=right_header.order_no,
            version_no=right_header.version_no,
            sap_code=f"BUS-SAME-{index}",
            material_category=MATERIAL_CATEGORY_BUSBAR,
            material_name="汇流条",
            raw_row_no=100 + index,
        ).description = f"相同汇流条 {index}"
    session.commit()

    service = _query_service(session)
    result = service.compare(
        PlanBomCompareQueryRequest(
            left=PlanBomCompareSideRequest(order_no=left_header.order_no),
            right=PlanBomCompareSideRequest(order_no=right_header.order_no),
        ),
        trace_id="trace-compare-history-limit",
    )

    query_log_id = int(result.response_meta.get("query_log_id") or 0)
    row = _query_log_row(session, query_log_id)
    assert row is not None
    payload_json = json.loads(row.request_payload)
    snapshot = payload_json["query_result"]
    policy = snapshot["response_meta"]["snapshot_policy"]

    assert len(snapshot["only_left"]) == 20
    assert len(snapshot["same"]) == 10
    assert policy["truncated"]["only_left"] is True
    assert policy["truncated"]["same"] is True
