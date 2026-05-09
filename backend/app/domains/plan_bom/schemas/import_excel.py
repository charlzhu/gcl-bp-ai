from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


PlanBomImportStatus = Literal["success", "failed"]


class PlanBomImportIssue(BaseModel):
    """计划 BOM 导入问题项。

    参数说明：
    - level: 问题级别，error 会影响行入库，warning 只提示风险；
    - stage: 问题发生阶段，例如 PARSE_HEADER / MATERIAL_CONFLICT；
    - sheet_name: Excel sheet 名；
    - row_no: Excel 原始行号，无法定位时为空；
    - message: 面向技术排查的中文说明；
    - key: 相关唯一键或业务键；
    - raw_payload: 原始行快照，便于排查字段错位。
    """

    level: Literal["error", "warning"]
    stage: str
    sheet_name: str | None = None
    row_no: int | None = None
    message: str
    key: str | None = None
    raw_payload: dict[str, Any] | None = None


class PlanBomImportReport(BaseModel):
    """计划 BOM Excel 导入报告。

    返回值说明：
    - 本报告只描述 Excel 解析与批次入库结果；
    - 不包含查询、导出或 SAP 接入结果；
    - errors / warnings 用于前端或联调人员定位资料问题。
    - rollback_applied 表示失败批次是否已按整批回滚策略处理；
    - persisted_business_data 表示 BOM 头、材料行、修订区是否真的落库。
    """

    batch_id: str
    status: PlanBomImportStatus
    file_name: str
    file_hash: str | None = None
    sheet_count: int = 0
    header_count: int = 0
    material_line_count: int = 0
    revision_count: int = 0
    error_count: int = 0
    warning_count: int = 0
    rollback_applied: bool = False
    persisted_business_data: bool = False
    errors: list[PlanBomImportIssue] = Field(default_factory=list)
    warnings: list[PlanBomImportIssue] = Field(default_factory=list)


class PlanBomUploadHistoryItem(BaseModel):
    """计划 BOM 上传历史摘要。"""

    batch_id: str
    source_type: str
    source_tag: str
    file_name: str
    file_hash: str | None = None
    status: str
    total_files: int = 0
    total_headers: int = 0
    total_lines: int = 0
    error_message: str | None = None
    created_at: str | None = None
    finished_at: str | None = None


class PlanBomUploadHistoryResponse(BaseModel):
    """计划 BOM 上传历史响应。"""

    items: list[PlanBomUploadHistoryItem]
    total: int


__all__ = [
    "PlanBomImportIssue",
    "PlanBomImportReport",
    "PlanBomImportStatus",
    "PlanBomUploadHistoryItem",
    "PlanBomUploadHistoryResponse",
]
