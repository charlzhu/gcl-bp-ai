from __future__ import annotations

import json
import logging
import sys
import uuid
from datetime import datetime
from math import isnan
from pathlib import Path

import pandas as pd
from fastapi import UploadFile
from sqlalchemy.orm import Session

from backend.app.core.exceptions import AppException
from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.etl.history_field_mapping import map_hist_row
from backend.app.domains.logistics.repositories.import_repository import LogisticsHistoryImportRepository
from backend.app.domains.logistics.schemas.import_history import (
    LogisticsHistoryImportRequest,
    LogisticsHistoryImportResult,
    LogisticsServingRefreshRequest,
)
from backend.app.domains.logistics.services.serving_refresh_service import LogisticsServingRefreshService
from backend.app.services.upload_service import UploadService
from backend.app.utils.time_utils import now_str

logger = logging.getLogger(__name__)


class LogisticsHistoryImportService:
    """历史 Excel 导入服务。

    这里同时保留两段能力：
    1. 上传 Excel 到本地文件目录；
    2. 从本地文件或 `upload_id` 执行真实导入 ETL。
    """

    WRITE_CHUNK_SIZE = 200

    def __init__(self, upload_service: UploadService) -> None:
        self.upload_service = upload_service

    async def import_excel(self, file: UploadFile) -> dict:
        upload = await self.upload_service.save_history_file(file=file, operator=None)
        return {
            "upload_id": upload.upload_id,
            "file_name": upload.file_name,
            "saved_to": upload.file_path,
            "status": upload.task.status,
            "next_step": "POST /api/v1/logistics/history-import/run or /api/v1/logistics/data/hist/import",
            "task": upload.task.model_dump(),
            "time": now_str(),
        }

    def run_import(self, req: LogisticsHistoryImportRequest) -> LogisticsHistoryImportResult:
        """历史 ETL 功能：解析 Excel、写 ODS/DWD，并按需刷新服务层。

        风险说明：
        1. `pandas` 读整 sheet 时会把整个工作表加载到内存，大文件需控制 sheet/行数；
        2. 历史 Excel 表头若超出当前映射字典，会导致字段空缺但不会覆盖正式系统数据；
        3. 导入只写 HIST 链路，不会覆盖 2026+ SYS 正式数据。
        """

        task_id = f"hist-import-{uuid.uuid4().hex[:12]}"
        import_batch_no = req.import_batch_no or f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:6]}"
        actual_file_path = self._resolve_file_path(req)

        db: Session = SessionLocal()
        repo = LogisticsHistoryImportRepository(db)
        total_sheets = 0
        imported_sheets = 0
        raw_row_count = 0
        dwd_row_count = 0
        skipped_row_count = 0

        try:
            repo.create_task_log(
                task_id=task_id,
                task_name="history excel import",
                source_code="hist_excel",
            )
            file_path = Path(actual_file_path)
            if not file_path.exists():
                raise AppException(
                    f"导入文件不存在: {actual_file_path}",
                    code=4043,
                    status_code=404,
                )
            if file_path.suffix.lower() not in {".xlsx", ".xls"}:
                raise AppException(
                    "历史 ETL 当前仅支持 xlsx/xls 文件",
                    code=4006,
                    status_code=400,
                    details={"suffix": file_path.suffix.lower()},
                )

            if req.truncate_current_batch_before_import:
                repo.delete_batch(import_batch_no)

            excel_book = pd.ExcelFile(actual_file_path)
            sheet_names = req.sheet_names or excel_book.sheet_names
            total_sheets = len(sheet_names)
            file_md5_value = repo.file_md5(actual_file_path)

            for sheet_index, sheet_name in enumerate(sheet_names, start=1):
                logger.info("import historical excel file=%s sheet=%s", actual_file_path, sheet_name)
                data_frame = excel_book.parse(sheet_name=sheet_name)
                data_frame = data_frame.where(pd.notnull(data_frame), None)
                sheet_total_rows = len(data_frame)
                file_id = repo.create_excel_file_record(
                    import_batch_no=import_batch_no,
                    source_year=req.source_year,
                    source_factory=req.source_factory,
                    file_path=actual_file_path,
                    sheet_name=sheet_name,
                    row_count=sheet_total_rows,
                    file_md5_value=file_md5_value,
                )
                imported_sheets += 1

                ods_rows: list[dict] = []
                dwd_rows: list[dict] = []
                progress_step = self._progress_step(sheet_total_rows)
                sheet_processed_rows = 0
                self._emit_progress(
                    sheet_index=sheet_index,
                    total_sheets=total_sheets,
                    sheet_name=sheet_name,
                    completed=0,
                    total=sheet_total_rows,
                    stage="parsing",
                    done=sheet_total_rows == 0,
                )
                for index, row in data_frame.iterrows():
                    sheet_processed_rows += 1
                    raw = {str(key): value for key, value in row.to_dict().items()}
                    raw_json = json.dumps(self._json_safe_value(raw), ensure_ascii=False, default=str)
                    row_no = int(index) + 2
                    ods_rows.append(
                        {
                            "import_batch_no": import_batch_no,
                            "file_id": file_id,
                            "source_year": req.source_year,
                            "source_factory": req.source_factory,
                            "file_name": file_path.name,
                            "sheet_name": sheet_name,
                            "row_no": row_no,
                            "raw_row_json": raw_json,
                        }
                    )

                    try:
                        mapped = map_hist_row(raw, source_year=req.source_year)
                    except Exception as exc:
                        skipped_row_count += 1
                        repo.create_error_log(
                            task_id=task_id,
                            error_stage="ROW_MAPPING",
                            error_message=str(exc),
                            source_file_name=file_path.name,
                            source_sheet_name=sheet_name,
                            row_no=row_no,
                            raw_payload=self._json_safe_value(raw),
                        )
                        continue

                    if not mapped.get("biz_date") and not mapped.get("customer_name") and not mapped.get("logistics_company_name"):
                        skipped_row_count += 1
                        continue

                    dwd_rows.append(
                        {
                            "import_batch_no": import_batch_no,
                            "source_year": req.source_year,
                            "source_factory": req.source_factory,
                            "source_file_name": file_path.name,
                            "source_sheet_name": sheet_name,
                            "source_row_no": row_no,
                            **mapped,
                            "raw_row_json": raw_json,
                        }
                    )

                    if sheet_processed_rows % progress_step == 0 or sheet_processed_rows == sheet_total_rows:
                        self._emit_progress(
                            sheet_index=sheet_index,
                            total_sheets=total_sheets,
                            sheet_name=sheet_name,
                            completed=sheet_processed_rows,
                            total=sheet_total_rows,
                            stage="parsing",
                            done=sheet_processed_rows == sheet_total_rows,
                )

                ods_total = len(ods_rows)
                dwd_total = len(dwd_rows)
                ods_chunks = self._chunked(ods_rows, self.WRITE_CHUNK_SIZE)
                dwd_chunks = self._chunked(dwd_rows, self.WRITE_CHUNK_SIZE)

                ods_written = 0
                self._emit_progress(
                    sheet_index=sheet_index,
                    total_sheets=total_sheets,
                    sheet_name=sheet_name,
                    completed=0,
                    total=ods_total,
                    stage="writing ods",
                )
                for chunk_index, ods_chunk in enumerate(ods_chunks, start=1):
                    logger.info(
                        "writing ods chunk sheet=%s chunk=%s/%s rows=%s",
                        sheet_name,
                        chunk_index,
                        len(ods_chunks),
                        len(ods_chunk),
                    )
                    raw_row_count += repo.batch_insert_ods_rows(ods_chunk)
                    ods_written += len(ods_chunk)
                    self._emit_progress(
                        sheet_index=sheet_index,
                        total_sheets=total_sheets,
                        sheet_name=sheet_name,
                        completed=ods_written,
                        total=ods_total,
                        stage="writing ods",
                        done=ods_written == ods_total,
                    )

                dwd_written = 0
                self._emit_progress(
                    sheet_index=sheet_index,
                    total_sheets=total_sheets,
                    sheet_name=sheet_name,
                    completed=0,
                    total=dwd_total,
                    stage="writing dwd",
                )
                for chunk_index, dwd_chunk in enumerate(dwd_chunks, start=1):
                    logger.info(
                        "writing dwd chunk sheet=%s chunk=%s/%s rows=%s",
                        sheet_name,
                        chunk_index,
                        len(dwd_chunks),
                        len(dwd_chunk),
                    )
                    dwd_row_count += repo.batch_insert_dwd_rows(dwd_chunk)
                    dwd_written += len(dwd_chunk)
                    self._emit_progress(
                        sheet_index=sheet_index,
                        total_sheets=total_sheets,
                        sheet_name=sheet_name,
                        completed=dwd_written,
                        total=dwd_total,
                        stage="writing dwd",
                        done=dwd_written == dwd_total,
                    )

                self._emit_progress(
                    sheet_index=sheet_index,
                    total_sheets=total_sheets,
                    sheet_name=sheet_name,
                    completed=sheet_total_rows,
                    total=sheet_total_rows,
                    stage="sheet done",
                    done=True,
                )

            if req.refresh_serving:
                LogisticsServingRefreshService().refresh(
                    LogisticsServingRefreshRequest(
                        refresh_hist=True,
                        refresh_sys=False,
                        rebuild_dm=True,
                        target_year_month_list=None,
                    )
                )

            repo.finish_task_log(
                task_id=task_id,
                status="SUCCESS",
                total_count=raw_row_count,
                success_count=dwd_row_count,
                fail_count=skipped_row_count,
                message=(
                    f"imported_sheets={imported_sheets}, raw_rows={raw_row_count}, "
                    f"dwd_rows={dwd_row_count}, skipped={skipped_row_count}"
                ),
            )
            logger.info(
                "history import finished task_id=%s import_batch_no=%s raw_rows=%s dwd_rows=%s skipped=%s",
                task_id,
                import_batch_no,
                raw_row_count,
                dwd_row_count,
                skipped_row_count,
            )
            return LogisticsHistoryImportResult(
                task_id=task_id,
                import_batch_no=import_batch_no,
                source_year=req.source_year,
                file_path=actual_file_path,
                total_sheets=total_sheets,
                imported_sheets=imported_sheets,
                raw_row_count=raw_row_count,
                dwd_row_count=dwd_row_count,
                skipped_row_count=skipped_row_count,
                message="history excel import finished",
            )
        except AppException as exc:
            db.rollback()
            self._safe_log_failure(
                repo=repo,
                task_id=task_id,
                error_message=exc.message,
                file_name=Path(actual_file_path).name if actual_file_path else None,
            )
            raise
        except Exception as exc:
            logger.exception("history import failed")
            db.rollback()
            self._safe_log_failure(
                repo=repo,
                task_id=task_id,
                error_message=str(exc),
                file_name=Path(actual_file_path).name if actual_file_path else None,
            )
            raise
        finally:
            db.close()

    def _resolve_file_path(self, req: LogisticsHistoryImportRequest) -> str:
        if req.file_path:
            return req.file_path
        if req.upload_id is None:
            raise AppException("缺少导入文件路径或 upload_id", code=4007, status_code=400)
        upload_task = self.upload_service.task_repository.get_task(req.upload_id)
        if upload_task is None or upload_task.task_type != "history_upload":
            raise AppException("上传任务不存在，请先完成文件上传", code=4041, status_code=404)
        stored_file_path = upload_task.payload.get("stored_file_path")
        if not stored_file_path:
            raise AppException("上传任务缺少文件路径信息", code=5005, status_code=500)
        return str(stored_file_path)

    @staticmethod
    def _safe_log_failure(
        *,
        repo: LogisticsHistoryImportRepository,
        task_id: str,
        error_message: str,
        file_name: str | None,
    ) -> None:
        try:
            repo.create_error_log(
                task_id=task_id,
                error_stage="IMPORT",
                error_message=error_message,
                source_file_name=file_name,
            )
        except Exception:
            logger.exception("failed to write history import error log")
        try:
            repo.finish_task_log(
                task_id=task_id,
                status="FAILED",
                total_count=0,
                success_count=0,
                fail_count=1,
                message=error_message,
            )
        except Exception:
            logger.exception("failed to update history import task log")

    @staticmethod
    def _json_safe_value(value: object) -> object:
        """把 pandas / Excel 读出来的值清洗成合法 JSON 可序列化结构。

        关键点是把 `NaN` / `NaT` 统一转成 `None`，否则 MySQL JSON 列会拒绝写入。
        """

        if value is None:
            return None
        if isinstance(value, float) and isnan(value):
            return None
        if isinstance(value, dict):
            return {str(key): LogisticsHistoryImportService._json_safe_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [LogisticsHistoryImportService._json_safe_value(item) for item in value]
        if isinstance(value, tuple):
            return [LogisticsHistoryImportService._json_safe_value(item) for item in value]
        try:
            if pd.isna(value):
                return None
        except Exception:
            pass
        return value

    @staticmethod
    def _progress_step(total: int) -> int:
        if total <= 0:
            return 1
        return max(1, total // 100)

    @staticmethod
    def _chunked(items: list[dict], size: int) -> list[list[dict]]:
        return [items[index : index + size] for index in range(0, len(items), size)]

    @staticmethod
    def _emit_progress(
        *,
        sheet_index: int,
        total_sheets: int,
        sheet_name: str,
        completed: int,
        total: int,
        stage: str,
        done: bool = False,
    ) -> None:
        """向控制台打印单行进度条。

        这里用 `stdout` 实时刷新，便于 uvicorn 控制台直接观察导入进度。
        """

        if total <= 0:
            total = 1
        ratio = min(max(completed / total, 0.0), 1.0)
        bar_width = 28
        filled = int(bar_width * ratio)
        bar = "#" * filled + "-" * (bar_width - filled)
        message = (
            f"[{bar}] {ratio * 100:6.2f}% "
            f"| sheet {sheet_index}/{total_sheets} {sheet_name} "
            f"| {completed}/{total} rows "
            f"| {stage}"
        )
        sys.stdout.write("\r" + message)
        sys.stdout.flush()
        if done:
            sys.stdout.write("\n")
            sys.stdout.flush()
