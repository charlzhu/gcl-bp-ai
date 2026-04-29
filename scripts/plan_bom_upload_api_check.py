from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterator

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.api.deps import get_db
from backend.app.db.base import Base
from backend.app.main import create_application
from plan_bom_runtime import TMP_DIR, extract_bom_zip


REQUIRED_RESPONSE_FIELDS = {
    "success",
    "message",
    "import_batch_id",
    "file_name",
    "file_size",
    "parsed_orders_count",
    "parsed_materials_count",
    "warning_count",
    "error_count",
    "data_quality_summary",
    "report_path",
    "next_action",
}


def parse_args() -> argparse.Namespace:
    """解析上传接口验收参数。

    返回：
        argparse.Namespace，包含可选 BOM 源数据 zip 路径。
    """

    parser = argparse.ArgumentParser(description="通过 FastAPI TestClient 验证计划 BOM 上传接口")
    parser.add_argument("--source-zip", default=None, help="BOM 源数据 zip 路径；未传时读取项目内默认路径")
    return parser.parse_args()


def build_test_client() -> TestClient:
    """构造带 SQLite 覆盖依赖的 TestClient。

    返回：
        可直接请求 `/api/v1/plan-bom/upload` 的 TestClient。
    """

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)

    def override_get_db() -> Iterator[Session]:
        """为 TestClient 提供隔离数据库会话。

        返回：
            SQLAlchemy Session 生成器。
        """

        session = testing_session()
        try:
            yield session
            session.commit()
        finally:
            session.close()

    app = create_application()
    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


def post_upload(client: TestClient, url: str, file_path: Path, *, business_type: str = "plan_bom") -> dict:
    """发送 multipart 上传请求。

    参数：
        client: FastAPI TestClient；
        url: 上传 URL；
        file_path: 本地文件路径；
        business_type: 业务类型字段。

    返回：
        ApiResponse JSON。
    """

    with file_path.open("rb") as handle:
        response = client.post(
            url,
            files={"file": (file_path.name, handle, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"business_type": business_type, "source": "testclient_check", "overwrite": "true", "remark": "计划 BOM 上传接口验收"},
        )
    response.raise_for_status()
    return response.json()


def make_temp_file(suffix: str, content: bytes) -> Path:
    """生成错误场景临时文件。

    参数：
        suffix: 文件后缀；
        content: 文件内容。

    返回：
        临时文件路径。
    """

    temp = NamedTemporaryFile(delete=False, suffix=suffix)
    temp.write(content)
    temp.close()
    return Path(temp.name)


def main() -> None:
    """执行上传接口真实 TestClient 验收。

    返回：
        无返回值；脚本输出 `tmp/plan_bom/plan_bom_upload_api_check_report.json`。
    """

    args = parse_args()
    files = extract_bom_zip(args.source_zip)
    sample_file = files[0]
    client = build_test_client()
    route_paths = sorted({route.path for route in client.app.routes})
    route_registered = "/api/v1/plan-bom/upload" in route_paths and "/api/v1/plan-bom/import/excel" in route_paths

    success_payload = post_upload(client, "/api/v1/plan-bom/upload", sample_file)
    success_data = success_payload.get("data") or {}
    required_fields_present = sorted(REQUIRED_RESPONSE_FIELDS.intersection(success_data))

    invalid_text = make_temp_file(".txt", b"not excel")
    empty_xlsx = make_temp_file(".xlsx", b"")
    huge_xlsx = make_temp_file(".xlsx", b"0" * (21 * 1024 * 1024))
    broken_xlsx = make_temp_file(".xlsx", b"broken excel payload")
    scenarios = [
        {"name": "legacy_route_success", "payload": post_upload(client, "/api/v1/plan-bom/import/excel", sample_file)},
        {"name": "invalid_business_type", "payload": post_upload(client, "/api/v1/plan-bom/upload", sample_file, business_type="wrong_type")},
        {"name": "non_excel", "payload": post_upload(client, "/api/v1/plan-bom/upload", invalid_text)},
        {"name": "empty_file", "payload": post_upload(client, "/api/v1/plan-bom/upload", empty_xlsx)},
        {"name": "oversized_file", "payload": post_upload(client, "/api/v1/plan-bom/upload", huge_xlsx)},
        {"name": "parse_failed_file", "payload": post_upload(client, "/api/v1/plan-bom/upload", broken_xlsx)},
    ]
    report = {
        "endpoint": "POST /api/v1/plan-bom/upload",
        "legacy_endpoint": "POST /api/v1/plan-bom/import/excel",
        "route_registered": route_registered,
        "sample_file": str(sample_file),
        "required_fields_present": required_fields_present,
        "required_fields_missing": sorted(REQUIRED_RESPONSE_FIELDS.difference(success_data)),
        "success_case": success_payload,
        "error_scenarios": scenarios,
        "passed": route_registered and not REQUIRED_RESPONSE_FIELDS.difference(success_data) and bool(success_data.get("success")),
    }
    (TMP_DIR / "plan_bom_upload_api_check_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
