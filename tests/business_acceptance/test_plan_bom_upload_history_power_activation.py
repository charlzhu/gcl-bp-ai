from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.base import Base
from backend.app.domains.plan_bom.models import PlanBomImportBatch, PlanPowerModelVersion
from backend.app.domains.plan_bom.repositories.import_repository import PlanBomImportRepository
from backend.app.domains.plan_bom.repositories.power_model_repository import PowerModelRepository
from backend.app.domains.plan_bom.services.power_excel_parser_service import FORMULA_POLICY
from backend.app.domains.plan_bom.services.power_model_service import PowerModelService


@pytest.fixture()
def db_session():
    """创建 SQLite 临时数据库会话，避免依赖本地 MySQL。"""
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


class FakePowerParser:
    """构造最小可落库的功率模型解析结果，用于验证版本生效逻辑。"""

    def parse_bytes(self, content: bytes, *, file_name: str, file_hash: str | None = None):
        return SimpleNamespace(
            file_name=file_name,
            file_hash=file_hash,
            business_version_label=file_name.removesuffix(".xlsm"),
            formula_policy=FORMULA_POLICY,
            vba_project_sha256=None,
            sheet_count=0,
            model_sheet_count=0,
            warning_count=0,
            error_count=0,
            parse_summary={"fake_content_size": len(content)},
            issues=[],
            sheets=[],
            benchmark_factors=[],
            change_histories=[],
        )


class FailedPowerParser(FakePowerParser):
    """构造解析失败版本，用于验证失败模型不会覆盖当前生效版本。"""

    def parse_bytes(self, content: bytes, *, file_name: str, file_hash: str | None = None):
        parsed = super().parse_bytes(content, file_name=file_name, file_hash=file_hash)
        parsed.error_count = 1
        parsed.parse_summary = {"fake_content_size": len(content), "forced_status": "failed"}
        return parsed


def test_bom_upload_history_repository_lists_previous_uploads_newest_first(db_session) -> None:
    """BOM 上传历史应按创建时间倒序返回以往上传文件和解析统计。"""
    db_session.add_all(
        [
            PlanBomImportBatch(
                batch_id="BATCH-old",
                source_type="EXCEL",
                source_tag="manual_upload",
                file_name="old-bom.xlsx",
                file_hash="old-hash",
                status="success",
                total_files=1,
                total_headers=2,
                total_lines=20,
                error_message=None,
                created_at=datetime(2026, 5, 1, 9, 0, 0),
                finished_at=datetime(2026, 5, 1, 9, 1, 0),
            ),
            PlanBomImportBatch(
                batch_id="BATCH-new",
                source_type="EXCEL",
                source_tag="manual_upload",
                file_name="new-bom.xlsx",
                file_hash="new-hash",
                status="failed",
                total_files=1,
                total_headers=0,
                total_lines=0,
                error_message="模板不匹配",
                created_at=datetime(2026, 5, 2, 9, 0, 0),
                finished_at=datetime(2026, 5, 2, 9, 1, 0),
            ),
        ]
    )
    db_session.commit()

    items = PlanBomImportRepository(db_session).list_batches(limit=10)

    assert [item["batch_id"] for item in items] == ["BATCH-new", "BATCH-old"]
    assert items[0]["file_name"] == "new-bom.xlsx"
    assert items[0]["status"] == "failed"
    assert items[0]["total_headers"] == 0
    assert items[0]["total_lines"] == 0
    assert items[0]["error_message"] == "模板不匹配"
    assert items[1]["file_hash"] == "old-hash"
    assert items[1]["created_at"].startswith("2026-05-01T09:00:00")


def test_power_model_import_defaults_latest_uploaded_version_active(db_session) -> None:
    """功率模型上传后应默认让最新上传版本生效，且始终最多一个 active 版本。"""
    service = PowerModelService(repository=PowerModelRepository(db_session), parser=FakePowerParser())

    first = service.import_bytes(b"power-model-v1", file_name="GCL功率测试基准-v1.xlsm")
    second = service.import_bytes(b"power-model-v2", file_name="GCL功率测试基准-v2.xlsm")

    assert first.import_status == "created"
    assert second.import_status == "created"
    assert first.version["is_active"] is True
    assert second.version["is_active"] is True
    assert PowerModelRepository(db_session).count_active_versions() == 1
    assert db_session.get(PlanPowerModelVersion, first.version["id"]).is_active == 0
    assert db_session.get(PlanPowerModelVersion, second.version["id"]).is_active == 1


def test_power_model_existing_reupload_can_become_active_again(db_session) -> None:
    """重复上传已有 hash 时不新增版本，但该上传对应的已有版本应可重新成为生效版本。"""
    service = PowerModelService(repository=PowerModelRepository(db_session), parser=FakePowerParser())

    first = service.import_bytes(b"power-model-v1", file_name="GCL功率测试基准-v1.xlsm")
    second = service.import_bytes(b"power-model-v2", file_name="GCL功率测试基准-v2.xlsm")
    existing = service.import_bytes(b"power-model-v1", file_name="GCL功率测试基准-v1.xlsm")

    assert existing.import_status == "existing"
    assert existing.version["id"] == first.version["id"]
    assert existing.version["is_active"] is True
    assert PowerModelRepository(db_session).count_active_versions() == 1
    assert db_session.get(PlanPowerModelVersion, first.version["id"]).is_active == 1
    assert db_session.get(PlanPowerModelVersion, second.version["id"]).is_active == 0


def test_power_model_failed_upload_does_not_replace_current_active_version(db_session) -> None:
    """解析失败的功率模型应保留历史记录，但不能覆盖当前生效版本。"""
    repository = PowerModelRepository(db_session)
    valid_service = PowerModelService(repository=repository, parser=FakePowerParser())
    failed_service = PowerModelService(repository=repository, parser=FailedPowerParser())

    active = valid_service.import_bytes(b"power-model-valid", file_name="GCL功率测试基准-valid.xlsm")
    failed = failed_service.import_bytes(b"power-model-failed", file_name="GCL功率测试基准-failed.xlsm")

    assert failed.import_status == "created"
    assert failed.version["parse_status"] == "failed"
    assert failed.version["is_active"] is False
    assert PowerModelRepository(db_session).count_active_versions() == 1
    assert db_session.get(PlanPowerModelVersion, active.version["id"]).is_active == 1
    assert db_session.get(PlanPowerModelVersion, failed.version["id"]).is_active == 0
