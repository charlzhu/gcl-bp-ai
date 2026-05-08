from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


PowerModelImportStatus = Literal["created", "existing"]


class PowerModelVersionSummary(BaseModel):
    """功率模型版本摘要。

    返回值说明：
    - 只描述版本级状态；
    - 详情中的配置项、供应商、功率档和 issue 由详情接口返回。
    """

    id: int
    file_name: str
    file_hash: str
    source_type: str
    business_version_label: str | None = None
    formula_policy: str
    vba_project_sha256: str | None = None
    is_active: bool
    parse_status: str
    sheet_count: int
    model_sheet_count: int
    warning_count: int
    error_count: int
    parse_summary: dict[str, Any] | None = None
    warnings: list[dict[str, Any]] | None = None
    change_histories: list[dict[str, Any]] | None = None
    created_at: str | None = None
    activated_at: str | None = None


class PowerModelImportResponse(BaseModel):
    """功率模型导入响应。"""

    import_status: PowerModelImportStatus = Field(..., description="created 表示新建版本，existing 表示同 hash 已存在")
    version: PowerModelVersionSummary
    detail: dict[str, Any] | None = None


class PowerModelVersionListResponse(BaseModel):
    """功率模型版本列表响应。"""

    items: list[PowerModelVersionSummary]
    total: int


class PowerModelVersionDetailResponse(BaseModel):
    """功率模型版本详情响应。"""

    version: PowerModelVersionSummary
    sheets: list[dict[str, Any]]
    factor_options: list[dict[str, Any]]
    supplier_distributions: list[dict[str, Any]]
    power_bins: list[dict[str, Any]]
    benchmark_factors: list[dict[str, Any]]
    issues: list[dict[str, Any]]
    validation_cases: list[dict[str, Any]]


__all__ = [
    "PowerModelImportResponse",
    "PowerModelImportStatus",
    "PowerModelVersionDetailResponse",
    "PowerModelVersionListResponse",
    "PowerModelVersionSummary",
]
