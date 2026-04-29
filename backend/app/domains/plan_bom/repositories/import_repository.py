from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from backend.app.domains.plan_bom.models import (
    PlanBomHeader,
    PlanBomImportBatch,
    PlanBomMaterialLine,
    PlanBomRevision,
)


class PlanBomImportRepository:
    """计划 BOM Excel 入库仓储。

    职责边界：
    1. 只负责批次、BOM 头、材料行、修订区的落库；
    2. 不实现查询逻辑；
    3. 不处理导出任务；
    4. SAP 与 Excel 的来源优先级只在数据保留层面预留，不在本仓储做查询折算。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def save_import_result(
        self,
        *,
        batch: PlanBomImportBatch,
        headers: Iterable[PlanBomHeader],
        material_lines: Iterable[PlanBomMaterialLine],
        revisions: Iterable[PlanBomRevision],
    ) -> None:
        """保存一次 BOM Excel 导入结果。

        参数：
            batch: 导入批次对象；
            headers: 本批次解析出的 BOM 头；
            material_lines: 本批次解析出的材料行；
            revisions: 本批次解析出的修订区记录。

        返回值：
            无。成功时提交事务，失败时回滚并向上抛出异常。

        关键逻辑：
            新批次导入同一“业务实例键 + 文件实例键 + 版本号 + source_type”时，先清理旧业务数据，
            再写入本批次结果，避免 Excel 开发期重复导入同一文件实例时产生冲突。
        """
        header_list = list(headers)
        material_line_list = list(material_lines)
        revision_list = list(revisions)

        try:
            self._delete_existing_versions(header_list)
            self.db.merge(batch)
            self.db.add_all(header_list)
            self.db.add_all(material_line_list)
            self.db.add_all(revision_list)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def save_batch_only(self, *, batch: PlanBomImportBatch) -> None:
        """只保存批次记录，不保留业务数据。

        参数：
            batch: 已标记状态的导入批次对象。

        返回值：
            无。成功时只提交批次记录，失败时回滚并向上抛出异常。

        关键逻辑：
            小样本抽验阶段要求失败批次整批回滚，因此失败时只允许保留批次级追踪信息，
            不允许在 BOM 头、材料行、修订区中残留半成品数据。
        """
        try:
            self.db.merge(batch)
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise

    def _delete_existing_versions(self, headers: list[PlanBomHeader]) -> None:
        """删除本批次覆盖的旧 BOM 版本数据。

        参数：
            headers: 本批次解析出的 BOM 头列表。

        返回值：
            无。
        """
        seen_keys: set[tuple[str, str, str, str]] = set()
        for header in headers:
            key = (header.order_identity_key, header.file_instance_key, header.version_no, header.source_type)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            self.db.query(PlanBomMaterialLine).filter(
                PlanBomMaterialLine.order_identity_key == header.order_identity_key,
                PlanBomMaterialLine.file_instance_key == header.file_instance_key,
                PlanBomMaterialLine.version_no == header.version_no,
                PlanBomMaterialLine.source_type == header.source_type,
            ).delete(synchronize_session=False)
            self.db.query(PlanBomRevision).filter(
                PlanBomRevision.order_identity_key == header.order_identity_key,
                PlanBomRevision.file_instance_key == header.file_instance_key,
                PlanBomRevision.version_no == header.version_no,
                PlanBomRevision.source_type == header.source_type,
            ).delete(synchronize_session=False)
            self.db.query(PlanBomHeader).filter(
                PlanBomHeader.order_identity_key == header.order_identity_key,
                PlanBomHeader.file_instance_key == header.file_instance_key,
                PlanBomHeader.version_no == header.version_no,
                PlanBomHeader.source_type == header.source_type,
            ).delete(synchronize_session=False)


__all__ = ["PlanBomImportRepository"]
