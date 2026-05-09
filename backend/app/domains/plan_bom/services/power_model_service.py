from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import anyio
from fastapi import UploadFile
from sqlalchemy.exc import IntegrityError

from backend.app.domains.plan_bom.repositories.power_model_repository import PowerModelRepository
from backend.app.domains.plan_bom.services.power_excel_parser_service import FORMULA_POLICY, MAX_XLSM_BYTES, PowerExcelParserService


class PowerModelImportError(ValueError):
    """功率模型导入失败异常。"""


@dataclass(slots=True)
class PowerModelImportResult:
    """功率模型导入结果。"""

    import_status: str
    version: dict[str, Any]
    detail: dict[str, Any] | None


class PowerModelService:
    """计划 BOM 功率模型版本服务。

    职责边界：
    1. 调用解析器读取 xlsm 并调用仓储落库；
    2. 按 file_hash 防重复导入；
    3. 提供版本列表、详情和激活能力；
    4. 不实现正式功率预测计算、推荐和 BOM 配置映射。
    """

    def __init__(
        self,
        *,
        repository: PowerModelRepository,
        parser: PowerExcelParserService | None = None,
    ) -> None:
        self.repository = repository
        self.parser = parser or PowerExcelParserService()

    async def import_upload(self, file: UploadFile) -> PowerModelImportResult:
        """导入上传的 xlsm 文件。

        参数：
            file: FastAPI UploadFile。

        返回：
            PowerModelImportResult，包含新建或已存在版本信息。
        """
        content = await file.read(MAX_XLSM_BYTES + 1)
        if len(content) > MAX_XLSM_BYTES:
            raise PowerModelImportError(f"功率模型文件超过 {MAX_XLSM_BYTES} bytes 限制。")
        file_name = file.filename or "plan_power_model.xlsm"
        return await anyio.to_thread.run_sync(lambda: self.import_bytes(content, file_name=file_name))

    def import_file(self, file_path: str | Path) -> PowerModelImportResult:
        """导入本地 xlsm 文件。

        参数：
            file_path: 本地文件路径。

        返回：
            PowerModelImportResult，供测试和运维脚本使用。
        """
        path = Path(file_path)
        return self.import_bytes(path.read_bytes(), file_name=path.name)

    def import_bytes(self, content: bytes, *, file_name: str) -> PowerModelImportResult:
        """导入 xlsm 字节内容。

        参数：
            content: xlsm 文件字节；
            file_name: 原始文件名。

        返回：
            导入结果。若同 hash 已存在，则返回 existing，不新增版本。
        """
        if not content:
            raise PowerModelImportError("功率模型文件为空。")
        file_hash = hashlib.sha256(content).hexdigest()
        existing = self.repository.get_by_file_hash(file_hash)
        if existing is not None:
            return self._activate_imported_version(import_status="existing", version_id=existing.id)

        try:
            parsed = self.parser.parse_bytes(content, file_name=file_name, file_hash=file_hash)
        except Exception as exc:
            raise PowerModelImportError(f"功率模型 xlsm 解析失败：{exc}") from exc
        try:
            version = self.repository.create_from_parsed(parsed)
        except IntegrityError:
            existing_after_race = self.repository.get_by_file_hash(file_hash)
            if existing_after_race is not None:
                return self._activate_imported_version(import_status="existing", version_id=existing_after_race.id)
            raise
        return self._activate_imported_version(import_status="created", version_id=version.id)

    def _activate_imported_version(self, *, import_status: str, version_id: int) -> PowerModelImportResult:
        """将本次上传对应的功率模型版本设为生效并组装导入结果。

        参数：
            import_status: created / existing，保留幂等导入语义；
            version_id: 本次上传对应的版本 ID。

        返回：
            含 active 状态的导入结果。

        关键业务逻辑：
            业务要求“默认生效最新上传版本”。因此本次上传若解析成功或仅有 warning，
            就把该上传对应版本切为 active，保证后续功率预测链路读取到用户最后上传的有效版本。
            若解析失败，则只保留失败版本历史，不覆盖当前可用 active 版本。
        """
        version = self.repository.get_version(version_id)
        if version is None:
            raise ValueError(f"功率模型版本不存在：{version_id}")
        if version.parse_status == "failed" or version.error_count:
            return PowerModelImportResult(
                import_status=import_status,
                version=self.repository.version_to_dict(version),
                detail=self.repository.get_detail_payload(version_id),
            )
        activated = self.repository.activate_version(version_id)
        return PowerModelImportResult(
            import_status=import_status,
            version=self.repository.version_to_dict(activated),
            detail=self.repository.get_detail_payload(version_id),
        )

    def list_versions(self) -> list[dict[str, Any]]:
        """查询功率模型版本列表。

        返回：
            版本摘要字典列表。
        """
        return [self.repository.version_to_dict(version) for version in self.repository.list_versions()]

    def get_version_detail(self, version_id: int) -> dict[str, Any]:
        """查询功率模型版本详情。

        参数：
            version_id: 模型版本 ID。

        返回：
            版本详情字典；不存在时抛出 ValueError。
        """
        detail = self.repository.get_detail_payload(version_id)
        if detail is None:
            raise ValueError(f"功率模型版本不存在：{version_id}")
        return detail

    def activate_version(self, version_id: int) -> dict[str, Any]:
        """激活功率模型版本。

        参数：
            version_id: 模型版本 ID。

        返回：
            激活后的版本摘要。
        """
        version = self.repository.activate_version(version_id)
        return self.repository.version_to_dict(version)

    def current_formula_policy(self) -> str:
        """返回 M2 固定公式策略。

        返回：
            `semantic_fixed_mode`。
        """
        return FORMULA_POLICY


__all__ = ["PowerModelImportError", "PowerModelImportResult", "PowerModelService"]
