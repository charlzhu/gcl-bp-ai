from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import or_, text
from sqlalchemy.orm import Session

from backend.app.domains.plan_bom.models import PlanBomHeader, PlanBomMaterialLine


class PlanBomQueryRepository:
    """计划 BOM 基础查询仓储。

    职责边界：
    1. 只封装 BOM 头和材料行的数据库读取；
    2. 不做当前版本判定、候选列表裁剪或响应组装；
    3. 不实现两订单差异对比、导出和 SAP 接入。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active_headers(
        self,
        *,
        order_identity_key: str | None = None,
        file_instance_key: str | None = None,
        order_no: str | None = None,
        order_no_like: str | None = None,
        order_name_like: str | None = None,
    ) -> list[PlanBomHeader]:
        """按订单号、订单号片段或订单名称片段查询有效 BOM 头。

        参数：
            order_identity_key: Excel 开发期内部实例键，命中候选后可直接精确定位；
            file_instance_key: Excel 开发期文件实例键，命中文件实例候选后可直接精确定位；
            order_no: 完整订单号，走精确匹配；
            order_no_like: 短订单号或评审号别名，走 LIKE 匹配；
            order_name_like: 订单名称片段，走 LIKE 匹配。

        返回：
            有效 BOM 头列表，排序和去重由服务层统一处理。
        """
        query = self.db.query(PlanBomHeader).filter(PlanBomHeader.is_active == 1)
        if file_instance_key:
            query = query.filter(PlanBomHeader.file_instance_key == file_instance_key)
        elif order_identity_key:
            query = query.filter(PlanBomHeader.order_identity_key == order_identity_key)
        elif order_no:
            query = query.filter(PlanBomHeader.order_no == order_no)
        elif order_no_like and order_name_like:
            query = query.filter(
                or_(
                    PlanBomHeader.order_no.contains(order_no_like),
                    PlanBomHeader.order_name.contains(order_name_like),
                )
            )
        elif order_no_like:
            query = query.filter(PlanBomHeader.order_no.contains(order_no_like))
        elif order_name_like:
            query = query.filter(PlanBomHeader.order_name.contains(order_name_like))
        return query.all()

    def list_headers_by_scope(
        self,
        *,
        year: int | None = None,
        model: str | None = None,
        country: str | None = None,
        limit: int = 200,
    ) -> list[PlanBomHeader]:
        """按年份、型号、国家等范围检索有效 BOM 头。

        参数：
            year: 年份，优先匹配订单号和订单名称中的年份；
            model: 产品型号，按订单名称模糊匹配；
            country: 国家或地区，按订单名称模糊匹配；
            limit: 最大返回数量，避免脚本或接口无界读取。

        返回：
            有效 BOM 头列表，服务层继续负责版本去重和排序。
        """
        query = self.db.query(PlanBomHeader).filter(PlanBomHeader.is_active == 1)
        if year:
            year_text = str(year)
            query = query.filter(or_(PlanBomHeader.order_no.contains(year_text), PlanBomHeader.order_name.contains(year_text)))
        if model:
            query = query.filter(PlanBomHeader.order_name.contains(model))
        if country:
            query = query.filter(PlanBomHeader.order_name.contains(country))
        return query.order_by(PlanBomHeader.order_no.asc(), PlanBomHeader.version_no.asc()).limit(limit).all()

    def list_all_active_headers(self, *, limit: int = 500) -> list[PlanBomHeader]:
        """读取有效 BOM 头清单。

        参数：
            limit: 最大返回数量。

        返回：
            有效 BOM 头列表，用于数据质量报告、材料缺失扫描和回归脚本。
        """
        return (
            self.db.query(PlanBomHeader)
            .filter(PlanBomHeader.is_active == 1)
            .order_by(PlanBomHeader.order_no.asc(), PlanBomHeader.version_no.asc())
            .limit(limit)
            .all()
        )

    def list_material_lines_for_header(
        self,
        *,
        header: PlanBomHeader,
        material_categories: Iterable[str] | None = None,
    ) -> list[PlanBomMaterialLine]:
        """按 BOM 头读取材料行。

        参数：
            header: 已定位的 BOM 头；
            material_categories: 可选材料类别过滤，为空时返回该版本全部材料行。

        返回：
            按原始行号稳定排序的材料行。
        """
        query = self.db.query(PlanBomMaterialLine).filter(
            PlanBomMaterialLine.order_identity_key == header.order_identity_key,
            PlanBomMaterialLine.file_instance_key == header.file_instance_key,
            PlanBomMaterialLine.version_no == header.version_no,
            PlanBomMaterialLine.source_type == header.source_type,
        )
        category_list = list(material_categories or [])
        if category_list:
            query = query.filter(PlanBomMaterialLine.material_category.in_(category_list))
        return query.order_by(PlanBomMaterialLine.raw_row_no.asc(), PlanBomMaterialLine.sap_code.asc()).all()

    def list_compare_headers(
        self,
        *,
        order_identity_key: str | None = None,
        file_instance_key: str | None = None,
        order_no: str | None = None,
        order_no_like: str | None = None,
        order_name_like: str | None = None,
    ) -> list[PlanBomHeader]:
        """查询 compare 单侧所需的 BOM 头列表。

        说明：
        - compare 里程碑 1 只需要最小 BOM 头读取能力；
        - 当前仍复用 active header 过滤口径；
        - 后续如果 compare 需要补更细的版本链或历史版本读取，再在该方法上扩展。
        """
        return self.list_active_headers(
            order_identity_key=order_identity_key,
            file_instance_key=file_instance_key,
            order_no=order_no,
            order_no_like=order_no_like,
            order_name_like=order_name_like,
        )

    def list_material_lines(
        self,
        *,
        order_identity_key: str,
        file_instance_key: str,
        version_no: str,
        source_type: str,
        material_categories: Iterable[str],
    ) -> list[PlanBomMaterialLine]:
        """查询指定订单版本下的材料行。

        参数：
            order_identity_key: Excel 开发期内部实例键，避免同订单号不同实例串数据；
            file_instance_key: Excel 开发期文件实例键，避免同一实例同版本多文件串数据；
            version_no: BOM 版本号；
            source_type: 来源类型，确保 SAP / Excel 不混查；
            material_categories: 需要返回的材料类别。

        返回：
            按原始行号和 SAP 编码稳定排序的材料行。
        """
        category_list = list(material_categories)
        query = self.db.query(PlanBomMaterialLine).filter(
            PlanBomMaterialLine.order_identity_key == order_identity_key,
            PlanBomMaterialLine.file_instance_key == file_instance_key,
            PlanBomMaterialLine.version_no == version_no,
            PlanBomMaterialLine.source_type == source_type,
        )
        if category_list:
            query = query.filter(PlanBomMaterialLine.material_category.in_(category_list))
        return query.order_by(PlanBomMaterialLine.raw_row_no.asc(), PlanBomMaterialLine.sap_code.asc()).all()

    def write_query_log(self, payload: dict[str, Any]) -> int:
        """写入 compare 查询日志。

        参数：
            payload: `sys_query_log` 所需的插入字段。

        返回：
            新生成的日志主键；若驱动未返回主键，则兜底为 0。
        """
        sql = text(
            """
            INSERT INTO sys_query_log (
                trace_id, query_type, question_text, request_payload, route_type,
                metric_type, result_count, status, message
            )
            VALUES (
                :trace_id, :query_type, :question_text, :request_payload, :route_type,
                :metric_type, :result_count, :status, :message
            )
            """
        )
        result = self.db.execute(sql, payload)
        self.db.flush()
        return int(result.lastrowid or 0)

    def get_query_log_detail(self, *, log_id: int) -> dict[str, Any] | None:
        """读取单条 compare 查询日志详情。

        参数：
            log_id: `sys_query_log.id`。

        返回：
            日志字典；不存在时返回 `None`。
        """
        sql = text(
            """
            SELECT
                id,
                trace_id,
                query_type,
                question_text,
                request_payload,
                route_type,
                metric_type,
                result_count,
                status,
                message,
                created_at
            FROM sys_query_log
            WHERE id = :log_id
            LIMIT 1
            """
        )
        row = self.db.execute(sql, {"log_id": log_id}).mappings().first()
        return dict(row) if row else None


__all__ = ["PlanBomQueryRepository"]
