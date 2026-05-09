from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from zipfile import ZipFile

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

from backend.app.api.deps import require_plan_power_write_access
from backend.app.core.config import Settings
from backend.app.db.base import Base
from backend.app.domains.plan_bom.models import (
    PlanPowerBenchmarkFactor,
    PlanPowerModelVersion,
    PlanPowerParseIssue,
    PlanPowerPowerBin,
    PlanPowerSupplierEfficiencyDistribution,
)
from backend.app.domains.plan_bom.repositories.power_model_repository import PowerModelRepository
from backend.app.domains.plan_bom.services.power_excel_parser_service import FORMULA_POLICY, PowerExcelParserService
from backend.app.domains.plan_bom.services.power_model_service import PowerModelImportError, PowerModelService


POWER_XLSM = Path("ai/inbox/attachments/GCL功率测试基准（V2.1）TOPCon 26.04.13.xlsm")


def test_power_model_schema_import_has_no_pydantic_protected_namespace_warning() -> None:
    """启动加载功率模型响应模型时不应输出 model_ 保护命名空间 warning。"""
    python = Path("backend/.venv/bin/python")
    interpreter = str(python) if python.exists() else sys.executable
    env = {**os.environ, "PYTHONPATH": f".{os.pathsep}{os.environ.get('PYTHONPATH', '')}"}
    result = subprocess.run(
        [
            interpreter,
            "-W",
            "default",
            "-c",
            "from backend.app.domains.plan_bom.schemas.power_model import PowerModelVersionSummary; print(PowerModelVersionSummary.__name__)",
        ],
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "PowerModelVersionSummary" in result.stdout
    assert "protected namespace" not in result.stderr
    assert "model_sheet_count" not in result.stderr


def test_plan_power_write_access_allows_non_prod_and_blocks_prod_until_user_permission_module() -> None:
    """功率模型写接口不再使用旧 token，但生产环境应在用户权限模块接管前阻断写操作。"""
    require_plan_power_write_access(Settings(app_env="local"))
    require_plan_power_write_access(Settings(app_env="test"))

    with pytest.raises(HTTPException) as exc_info:
        require_plan_power_write_access(Settings(app_env="prod"))

    assert exc_info.value.status_code == 403
    assert "用户权限模块" in str(exc_info.value.detail)


def test_power_model_write_endpoints_use_environment_write_guard_without_legacy_token() -> None:
    """功率模型导入/激活接口应挂载环境门禁，但不能恢复旧管理 token。"""
    endpoint_source = Path("backend/app/domains/plan_bom/api/endpoints/power_model.py").read_text(encoding="utf-8")

    assert "require_plan_power_write_access" in endpoint_source
    assert endpoint_source.count("Depends(require_plan_power_write_access)") >= 2
    assert "X-Plan-Power-Admin-Token" not in endpoint_source
    assert "plan_power_admin_token" not in endpoint_source


@pytest.fixture()
def db_session():
    """创建 SQLite 临时数据库会话。

    返回：
        SQLAlchemy Session。测试只建 ORM 表，不连接真实 MySQL。
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


def _service(db_session) -> PowerModelService:
    """构造功率模型服务。"""
    return PowerModelService(repository=PowerModelRepository(db_session), parser=PowerExcelParserService())


def test_parse_topcon_xlsm_structure_and_vba_presence() -> None:
    """解析新版 xlsm，校验 sheet 数、模型页数量、公式策略和 VBA 工程存在。"""
    parsed = PowerExcelParserService().parse_file(POWER_XLSM)

    assert parsed.sheet_count == 12
    assert parsed.model_sheet_count == 10
    assert parsed.formula_policy == FORMULA_POLICY
    assert parsed.has_vba_project is True
    assert parsed.vba_project_sha256 == "7138e906f9f7b7eb244bf270dd19411f018839dcdb9a7ce0c76b83f7f7674b38"
    assert parsed.parse_summary["power_bin_count"] == 92
    assert parsed.parse_summary["supplier_distribution_count"] > 0
    assert parsed.parse_summary["benchmark_factor_count"] == 36
    assert parsed.parse_summary["change_history_count"] == 19
    assert parsed.parse_summary["latest_change_date"] == "2026.04.13"


def test_parse_records_semantic_formula_fix_and_invalid_supplier_issues() -> None:
    """解析新版 xlsm，校验 R30/R32 语义修正和异常供应商标题 warning。"""
    parsed = PowerExcelParserService().parse_file(POWER_XLSM)
    semantic_issues = [
        issue for issue in parsed.issues if issue.issue_code == "SEMANTIC_FORMULA_FIX_REQUIRED"
    ]
    invalid_supplier_issues = [
        issue for issue in parsed.issues if issue.issue_code == "INVALID_SUPPLIER_TITLE"
    ]

    assert {(issue.source_sheet_name, issue.source_cell_ref) for issue in semantic_issues} == {
        ("NT12R-66GDF", "R30"),
        ("NT12R-66GDF", "R32"),
    }
    assert any("#REF!" in str(issue.raw) for issue in invalid_supplier_issues)
    assert any("厂家" in str(issue.raw) for issue in invalid_supplier_issues)


def test_import_persists_model_version_children_and_formula_policy(db_session) -> None:
    """导入新版 xlsm，校验版本、功率档、供应商分布、标板和 issue 已落库。"""
    service = _service(db_session)
    result = service.import_file(POWER_XLSM)
    version_id = result.version["id"]

    version = db_session.get(PlanPowerModelVersion, version_id)
    assert result.import_status == "created"
    assert version is not None
    assert version.formula_policy == FORMULA_POLICY
    assert version.vba_project_sha256 == "7138e906f9f7b7eb244bf270dd19411f018839dcdb9a7ce0c76b83f7f7674b38"
    assert version.sheet_count == 12
    assert version.model_sheet_count == 10
    assert version.file_hash == "97207519ff88a2cb58c79e75fb94381331a953affd0685099ccd7bf2145f36a7"
    assert result.version["change_histories"][-1]["change_date"] == "2026.04.13"
    assert result.version["parse_summary"]["change_history_count"] == 19
    assert db_session.query(PlanPowerPowerBin).filter_by(version_id=version_id).count() == 92
    assert db_session.query(PlanPowerSupplierEfficiencyDistribution).filter_by(version_id=version_id).count() > 0
    assert db_session.query(PlanPowerBenchmarkFactor).filter_by(version_id=version_id).count() == 36
    assert (
        db_session.query(PlanPowerBenchmarkFactor)
        .filter_by(version_id=version_id, benchmark_name="功率最优")
        .count()
        == 9
    )
    assert (
        db_session.query(PlanPowerParseIssue)
        .filter_by(version_id=version_id, issue_code="SEMANTIC_FORMULA_FIX_REQUIRED")
        .count()
        == 2
    )
    assert (
        db_session.query(PlanPowerParseIssue)
        .filter_by(version_id=version_id, issue_code="INVALID_SUPPLIER_TITLE")
        .count()
        > 0
    )


def test_import_same_file_hash_returns_existing_without_duplicate(db_session) -> None:
    """同一 xlsm hash 重复导入时返回 existing，不新增模型版本。"""
    service = _service(db_session)
    first = service.import_file(POWER_XLSM)
    second = service.import_file(POWER_XLSM)

    assert first.import_status == "created"
    assert second.import_status == "existing"
    assert second.version["id"] == first.version["id"]
    assert db_session.query(PlanPowerModelVersion).count() == 1


def test_activate_version_switch_keeps_single_active_version(db_session) -> None:
    """激活版本切换时最多保留一个 active 版本。"""
    service = _service(db_session)
    content = POWER_XLSM.read_bytes()
    first = service.import_bytes(content, file_name=POWER_XLSM.name)
    second = service.import_bytes(content + b"\nM2-active-switch-copy", file_name="GCL功率测试基准（V2.1）TOPCon 26.04.13-copy.xlsm")

    activated_first = service.activate_version(first.version["id"])
    assert activated_first["is_active"] is True
    assert PowerModelRepository(db_session).count_active_versions() == 1

    activated_second = service.activate_version(second.version["id"])
    assert activated_second["is_active"] is True
    assert PowerModelRepository(db_session).count_active_versions() == 1
    assert db_session.get(PlanPowerModelVersion, first.version["id"]).is_active == 0
    assert db_session.get(PlanPowerModelVersion, second.version["id"]).is_active == 1

    reactivated_second = service.activate_version(second.version["id"])
    assert reactivated_second["is_active"] is True
    assert PowerModelRepository(db_session).count_active_versions() == 1


def test_import_rejects_empty_or_invalid_xlsm_with_controlled_error(db_session) -> None:
    """空文件、损坏文件和超出 ZIP 成员限制的文件应返回受控导入异常。"""
    service = _service(db_session)

    with pytest.raises(PowerModelImportError, match="为空"):
        service.import_bytes(b"", file_name="empty.xlsm")

    with pytest.raises(PowerModelImportError, match="解析失败"):
        service.import_bytes(b"not-a-zip", file_name="broken.xlsm")

    oversized_zip = Path("tmp/too_many_members.xlsm")
    oversized_zip.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(oversized_zip, "w") as zf:
        for index in range(501):
            zf.writestr(f"xl/fake-{index}.xml", "x")
    try:
        with pytest.raises(PowerModelImportError, match="ZIP 成员数"):
            service.import_file(oversized_zip)
    finally:
        oversized_zip.unlink(missing_ok=True)


def test_activate_failed_version_is_rejected(db_session) -> None:
    """解析失败版本不能被激活，避免把不可用模型设为生产活动版本。"""
    failed = PlanPowerModelVersion(
        file_name="failed.xlsm",
        file_hash="failed-hash",
        source_type="xlsm",
        formula_policy=FORMULA_POLICY,
        parse_status="failed",
        sheet_count=0,
        model_sheet_count=0,
        warning_count=0,
        error_count=1,
    )
    db_session.add(failed)
    db_session.commit()

    service = _service(db_session)
    with pytest.raises(ValueError, match="解析失败"):
        service.activate_version(failed.id)



def test_import_integrity_conflict_returns_existing_version() -> None:
    """并发同 hash 导入触发唯一键冲突时应回查已有版本并返回 existing。"""

    class FakeRepository:
        def __init__(self) -> None:
            self.calls = 0
            self.existing = SimpleNamespace(id=7, parse_status="success", error_count=0)

        def get_by_file_hash(self, file_hash: str):
            self.calls += 1
            return None if self.calls == 1 else self.existing

        def create_from_parsed(self, parsed):
            raise IntegrityError("insert plan_power_model_version", {}, Exception("duplicate"))

        def get_version(self, version_id: int):
            return self.existing if version_id == self.existing.id else None

        def activate_version(self, version_id: int):
            self.existing.is_active = 1
            return self.existing

        def version_to_dict(self, version):
            return {"id": version.id, "file_hash": "race-hash"}

        def get_detail_payload(self, version_id: int):
            return {"version_id": version_id}

    class FakeParser:
        def parse_bytes(self, content: bytes, *, file_name: str, file_hash: str | None = None):
            return SimpleNamespace(file_hash=file_hash, file_name=file_name)

    service = PowerModelService(repository=FakeRepository(), parser=FakeParser())
    result = service.import_bytes(b"race-content", file_name="race.xlsm")

    assert result.import_status == "existing"
    assert result.version["id"] == 7
