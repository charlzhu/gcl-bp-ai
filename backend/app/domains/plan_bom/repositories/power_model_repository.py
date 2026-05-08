from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.domains.plan_bom.models import (
    PlanPowerBenchmarkFactor,
    PlanPowerFactorOption,
    PlanPowerModelSheet,
    PlanPowerModelValidationCase,
    PlanPowerModelVersion,
    PlanPowerParseIssue,
    PlanPowerPowerBin,
    PlanPowerSupplierEfficiencyDistribution,
)
from backend.app.domains.plan_bom.services.power_excel_parser_service import ParsedPowerModelWorkbook, dumps_power_json


class PowerModelRepository:
    """计划 BOM 功率模型版本仓储。

    职责边界：
    1. 负责 `plan_power_*` 版本化数据的落库和查询；
    2. 不解析 Excel，不做功率预测计算；
    3. 激活版本时在一个事务内保证最多一个 active 版本。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_file_hash(self, file_hash: str) -> PlanPowerModelVersion | None:
        """按文件 hash 查询模型版本。

        参数：
            file_hash: xlsm SHA256。

        返回：
            已存在版本；不存在时返回 None。
        """
        return self.db.query(PlanPowerModelVersion).filter(PlanPowerModelVersion.file_hash == file_hash).first()

    def get_version(self, version_id: int) -> PlanPowerModelVersion | None:
        """按 ID 查询模型版本。

        参数：
            version_id: 模型版本 ID。

        返回：
            模型版本；不存在时返回 None。
        """
        return self.db.query(PlanPowerModelVersion).filter(PlanPowerModelVersion.id == version_id).first()

    def list_versions(self) -> list[PlanPowerModelVersion]:
        """查询模型版本列表。

        返回：
            按创建时间倒序排列的模型版本。
        """
        return self.db.query(PlanPowerModelVersion).order_by(PlanPowerModelVersion.created_at.desc(), PlanPowerModelVersion.id.desc()).all()

    def create_from_parsed(self, parsed: ParsedPowerModelWorkbook) -> PlanPowerModelVersion:
        """保存解析结果。

        参数：
            parsed: PowerExcelParserService 输出的内存解析结构。

        返回：
            新创建的 PlanPowerModelVersion。失败时回滚事务并向上抛出异常。
        """
        try:
            version = PlanPowerModelVersion(
                file_name=parsed.file_name,
                file_hash=parsed.file_hash,
                source_type="xlsm",
                business_version_label=parsed.business_version_label,
                formula_policy=parsed.formula_policy,
                vba_project_sha256=parsed.vba_project_sha256,
                is_active=0,
                parse_status=self._parse_status(parsed),
                sheet_count=parsed.sheet_count,
                model_sheet_count=parsed.model_sheet_count,
                warning_count=parsed.warning_count,
                error_count=parsed.error_count,
                parse_summary_json=dumps_power_json(parsed.parse_summary),
                warning_json=dumps_power_json([self._issue_to_dict(issue) for issue in parsed.issues if issue.level == "warning"]),
                change_history_json=dumps_power_json([self._change_history_to_dict(row) for row in parsed.change_histories]),
            )
            self.db.add(version)
            self.db.flush()

            sheet_id_by_name: dict[str, int] = {}
            for parsed_sheet in parsed.sheets:
                sheet = PlanPowerModelSheet(
                    version_id=version.id,
                    sheet_name=parsed_sheet.sheet_name,
                    normalized_model_code=parsed_sheet.normalized_model_code,
                    cell_count=parsed_sheet.cell_count,
                    base_power=parsed_sheet.base_power,
                    center_power_cell=parsed_sheet.center_power_cell,
                    area_default=parsed_sheet.area_default,
                    std_dev_default=parsed_sheet.std_dev_default,
                    source_range=parsed_sheet.source_range,
                    raw_meta_json=dumps_power_json(parsed_sheet.raw_meta),
                )
                self.db.add(sheet)
                self.db.flush()
                sheet_id_by_name[parsed_sheet.sheet_name] = sheet.id

                self.db.add_all(
                    [
                        PlanPowerFactorOption(
                            version_id=version.id,
                            sheet_id=sheet.id,
                            factor_key=option.factor_key,
                            option_label=option.option_label,
                            normalized_option_label=option.normalized_option_label,
                            effect_value=option.effect_value,
                            area_value=option.area_value,
                            std_dev_value=option.std_dev_value,
                            source_cell_ref=option.source_cell_ref,
                            is_default=1 if option.is_default else 0,
                            is_valid=1 if option.is_valid else 0,
                            invalid_reason=option.invalid_reason,
                            raw_json=dumps_power_json(option.raw),
                        )
                        for option in parsed_sheet.factor_options
                    ]
                )
                self.db.add_all(
                    [
                        PlanPowerSupplierEfficiencyDistribution(
                            version_id=version.id,
                            sheet_id=sheet.id,
                            supplier_name=distribution.supplier_name,
                            normalized_supplier_name=distribution.normalized_supplier_name,
                            efficiency_value=distribution.efficiency_value,
                            ratio_value=distribution.ratio_value,
                            source_cell_ref=distribution.source_cell_ref,
                            is_valid=1,
                        )
                        for distribution in parsed_sheet.supplier_distributions
                    ]
                )
                self.db.add_all(
                    [
                        PlanPowerPowerBin(
                            version_id=version.id,
                            sheet_id=sheet.id,
                            power_bin=power_bin.power_bin,
                            bin_order=power_bin.bin_order,
                            source_cell_ref=power_bin.source_cell_ref,
                            is_valid=1 if power_bin.is_valid else 0,
                        )
                        for power_bin in parsed_sheet.power_bins
                    ]
                )

            self.db.add_all(
                [
                    PlanPowerBenchmarkFactor(
                        version_id=version.id,
                        model_code=benchmark.model_code,
                        benchmark_name=benchmark.benchmark_name,
                        normalized_benchmark_name=benchmark.normalized_benchmark_name,
                        effect_value=benchmark.effect_value,
                        source_sheet_name=benchmark.source_sheet_name,
                        source_cell_ref=benchmark.source_cell_ref,
                        raw_json=dumps_power_json(benchmark.raw),
                    )
                    for benchmark in parsed.benchmark_factors
                ]
            )
            self.db.flush()

            self.db.add_all(
                [
                    PlanPowerParseIssue(
                        version_id=version.id,
                        sheet_id=sheet_id_by_name.get(issue.source_sheet_name or ""),
                        level=issue.level,
                        issue_code=issue.issue_code,
                        message=issue.message,
                        source_sheet_name=issue.source_sheet_name,
                        source_cell_ref=issue.source_cell_ref,
                        raw_json=dumps_power_json(issue.raw),
                    )
                    for issue in parsed.issues
                ]
            )
            self.db.commit()
            self.db.refresh(version)
            return version
        except Exception:
            self.db.rollback()
            raise

    def activate_version(self, version_id: int) -> PlanPowerModelVersion:
        """激活模型版本。

        参数：
            version_id: 待激活版本 ID。

        返回：
            激活后的模型版本。不存在时抛出 ValueError。

        关键业务逻辑：
            先通过 MySQL 命名锁 / 行锁保护激活流程，再把所有版本置为 inactive，
            最后激活目标版本；事务失败时整体回滚。SQLite 测试环境会忽略行锁，
            MySQL 生产环境通过 `plan_power_model_activation` GET_LOCK 降低并发双 active 风险。
        """
        lock_connection = None
        try:
            lock_connection = self._acquire_activation_lock()
            version = (
                self.db.query(PlanPowerModelVersion)
                .filter(PlanPowerModelVersion.id == version_id)
                .with_for_update()
                .first()
            )
            if version is None:
                raise ValueError(f"功率模型版本不存在：{version_id}")
            if version.parse_status == "failed" or version.error_count:
                raise ValueError(f"功率模型版本解析失败，不允许激活：{version_id}")
            self.db.query(PlanPowerModelVersion).filter(
                PlanPowerModelVersion.is_active == 1,
                PlanPowerModelVersion.id != version_id,
            ).update(
                {"is_active": 0, "activated_at": None},
                synchronize_session=False,
            )
            version.is_active = 1
            version.activated_at = datetime.now()
            self.db.add(version)
            self.db.commit()
            self._release_activation_lock(lock_connection)
            self.db.refresh(version)
            return version
        except Exception:
            self.db.rollback()
            self._release_activation_lock(lock_connection)
            raise

    def _acquire_activation_lock(self):
        """获取功率模型激活全局锁。

        返回：
            MySQL/MariaDB 下返回持有 GET_LOCK 的专用连接；其他数据库返回 None。

        关键业务逻辑：
            MySQL 环境使用专用连接持有 GET_LOCK，串行化 active 切换，避免两个请求并发激活不同版本；
            SQLite 单测环境不支持命名锁，继续依赖事务顺序执行。
        """
        bind = self.db.get_bind()
        if bind is None or bind.dialect.name not in {"mysql", "mariadb"}:
            return None
        lock_connection = bind.connect()
        try:
            acquired = lock_connection.execute(text("SELECT GET_LOCK('plan_power_model_activation', 10)")).scalar()
            if acquired != 1:
                raise ValueError("获取功率模型激活锁超时，请稍后重试。")
            return lock_connection
        except Exception:
            lock_connection.close()
            raise

    def _release_activation_lock(self, lock_connection) -> None:
        """释放功率模型激活全局锁。

        参数：
            lock_connection: `_acquire_activation_lock` 返回的专用连接。

        返回：
            无返回值。释放失败只忽略，避免覆盖主业务异常。
        """
        if lock_connection is None:
            return
        try:
            lock_connection.execute(text("SELECT RELEASE_LOCK('plan_power_model_activation')"))
        except Exception:  # noqa: BLE001
            return
        finally:
            lock_connection.close()

    def count_active_versions(self) -> int:
        """统计 active 模型版本数量。

        返回：
            is_active=1 的版本数量，用于测试和运行期自检。
        """
        return self.db.query(PlanPowerModelVersion).filter(PlanPowerModelVersion.is_active == 1).count()

    def get_detail_payload(self, version_id: int) -> dict[str, Any] | None:
        """读取版本详情并组装为字典。

        参数：
            version_id: 模型版本 ID。

        返回：
            可直接序列化的详情字典；不存在时返回 None。
        """
        version = self.get_version(version_id)
        if version is None:
            return None
        sheets = (
            self.db.query(PlanPowerModelSheet)
            .filter(PlanPowerModelSheet.version_id == version_id)
            .order_by(PlanPowerModelSheet.id.asc())
            .all()
        )
        return {
            "version": self.version_to_dict(version),
            "sheets": [self.sheet_to_dict(sheet) for sheet in sheets],
            "factor_options": [
                self.factor_option_to_dict(row)
                for row in self.db.query(PlanPowerFactorOption)
                .filter(PlanPowerFactorOption.version_id == version_id)
                .order_by(PlanPowerFactorOption.sheet_id.asc(), PlanPowerFactorOption.id.asc())
                .all()
            ],
            "supplier_distributions": [
                self.supplier_distribution_to_dict(row)
                for row in self.db.query(PlanPowerSupplierEfficiencyDistribution)
                .filter(PlanPowerSupplierEfficiencyDistribution.version_id == version_id)
                .order_by(
                    PlanPowerSupplierEfficiencyDistribution.sheet_id.asc(),
                    PlanPowerSupplierEfficiencyDistribution.supplier_name.asc(),
                    PlanPowerSupplierEfficiencyDistribution.source_cell_ref.asc(),
                )
                .all()
            ],
            "power_bins": [
                self.power_bin_to_dict(row)
                for row in self.db.query(PlanPowerPowerBin)
                .filter(PlanPowerPowerBin.version_id == version_id)
                .order_by(PlanPowerPowerBin.sheet_id.asc(), PlanPowerPowerBin.bin_order.asc())
                .all()
            ],
            "benchmark_factors": [
                self.benchmark_factor_to_dict(row)
                for row in self.db.query(PlanPowerBenchmarkFactor)
                .filter(PlanPowerBenchmarkFactor.version_id == version_id)
                .order_by(PlanPowerBenchmarkFactor.model_code.asc(), PlanPowerBenchmarkFactor.id.asc())
                .all()
            ],
            "issues": [
                self.parse_issue_to_dict(row)
                for row in self.db.query(PlanPowerParseIssue)
                .filter(PlanPowerParseIssue.version_id == version_id)
                .order_by(PlanPowerParseIssue.level.desc(), PlanPowerParseIssue.id.asc())
                .all()
            ],
            "validation_cases": [
                self.validation_case_to_dict(row)
                for row in self.db.query(PlanPowerModelValidationCase)
                .filter(PlanPowerModelValidationCase.version_id == version_id)
                .order_by(PlanPowerModelValidationCase.id.asc())
                .all()
            ],
        }

    def version_to_dict(self, version: PlanPowerModelVersion) -> dict[str, Any]:
        """将版本 ORM 转为字典。

        参数：
            version: PlanPowerModelVersion ORM 对象。

        返回：
            接口可序列化的版本摘要字典。
        """
        return {
            "id": version.id,
            "file_name": version.file_name,
            "file_hash": version.file_hash,
            "source_type": version.source_type,
            "business_version_label": version.business_version_label,
            "formula_policy": version.formula_policy,
            "vba_project_sha256": version.vba_project_sha256,
            "is_active": bool(version.is_active),
            "parse_status": version.parse_status,
            "sheet_count": version.sheet_count,
            "model_sheet_count": version.model_sheet_count,
            "warning_count": version.warning_count,
            "error_count": version.error_count,
            "parse_summary": self._loads_json(version.parse_summary_json),
            "warnings": self._loads_json(version.warning_json),
            "change_histories": self._loads_json(version.change_history_json) or [],
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "activated_at": version.activated_at.isoformat() if version.activated_at else None,
        }

    def sheet_to_dict(self, sheet: PlanPowerModelSheet) -> dict[str, Any]:
        """将 Sheet ORM 转为字典。

        参数：
            sheet: PlanPowerModelSheet ORM 对象。

        返回：
            接口可序列化的模型页字典。
        """
        return {
            "id": sheet.id,
            "version_id": sheet.version_id,
            "sheet_name": sheet.sheet_name,
            "normalized_model_code": sheet.normalized_model_code,
            "cell_count": sheet.cell_count,
            "base_power": self._decimal_to_float(sheet.base_power),
            "center_power_cell": sheet.center_power_cell,
            "area_default": self._decimal_to_float(sheet.area_default),
            "std_dev_default": self._decimal_to_float(sheet.std_dev_default),
            "source_range": sheet.source_range,
            "raw_meta": self._loads_json(sheet.raw_meta_json),
        }

    def factor_option_to_dict(self, option: PlanPowerFactorOption) -> dict[str, Any]:
        """将配置选项 ORM 转为字典。

        参数：
            option: PlanPowerFactorOption ORM 对象。

        返回：
            接口可序列化的配置选项字典。
        """
        return {
            "id": option.id,
            "version_id": option.version_id,
            "sheet_id": option.sheet_id,
            "factor_key": option.factor_key,
            "option_label": option.option_label,
            "normalized_option_label": option.normalized_option_label,
            "effect_value": self._decimal_to_float(option.effect_value),
            "area_value": self._decimal_to_float(option.area_value),
            "std_dev_value": self._decimal_to_float(option.std_dev_value),
            "source_cell_ref": option.source_cell_ref,
            "is_default": bool(option.is_default),
            "is_valid": bool(option.is_valid),
            "invalid_reason": option.invalid_reason,
            "raw": self._loads_json(option.raw_json),
        }

    def supplier_distribution_to_dict(self, row: PlanPowerSupplierEfficiencyDistribution) -> dict[str, Any]:
        """将供应商效率分布 ORM 转为字典。

        参数：
            row: PlanPowerSupplierEfficiencyDistribution ORM 对象。

        返回：
            接口可序列化的供应商效率分布字典。
        """
        return {
            "id": row.id,
            "version_id": row.version_id,
            "sheet_id": row.sheet_id,
            "supplier_name": row.supplier_name,
            "normalized_supplier_name": row.normalized_supplier_name,
            "efficiency_value": self._decimal_to_float(row.efficiency_value),
            "ratio_value": self._decimal_to_float(row.ratio_value),
            "source_cell_ref": row.source_cell_ref,
            "is_valid": bool(row.is_valid),
            "invalid_reason": row.invalid_reason,
        }

    def power_bin_to_dict(self, row: PlanPowerPowerBin) -> dict[str, Any]:
        """将功率档 ORM 转为字典。

        参数：
            row: PlanPowerPowerBin ORM 对象。

        返回：
            接口可序列化的功率档字典。
        """
        return {
            "id": row.id,
            "version_id": row.version_id,
            "sheet_id": row.sheet_id,
            "power_bin": self._decimal_to_float(row.power_bin),
            "bin_order": row.bin_order,
            "source_cell_ref": row.source_cell_ref,
            "is_valid": bool(row.is_valid),
        }

    def benchmark_factor_to_dict(self, row: PlanPowerBenchmarkFactor) -> dict[str, Any]:
        """将标板基准 ORM 转为字典。

        参数：
            row: PlanPowerBenchmarkFactor ORM 对象。

        返回：
            接口可序列化的标板基准字典。
        """
        return {
            "id": row.id,
            "version_id": row.version_id,
            "model_code": row.model_code,
            "benchmark_name": row.benchmark_name,
            "normalized_benchmark_name": row.normalized_benchmark_name,
            "effect_value": self._decimal_to_float(row.effect_value),
            "source_sheet_name": row.source_sheet_name,
            "source_cell_ref": row.source_cell_ref,
            "raw": self._loads_json(row.raw_json),
        }

    def parse_issue_to_dict(self, row: PlanPowerParseIssue) -> dict[str, Any]:
        """将解析问题 ORM 转为字典。

        参数：
            row: PlanPowerParseIssue ORM 对象。

        返回：
            接口可序列化的解析问题字典。
        """
        return {
            "id": row.id,
            "version_id": row.version_id,
            "sheet_id": row.sheet_id,
            "level": row.level,
            "issue_code": row.issue_code,
            "message": row.message,
            "source_sheet_name": row.source_sheet_name,
            "source_cell_ref": row.source_cell_ref,
            "raw": self._loads_json(row.raw_json),
        }

    def validation_case_to_dict(self, row: PlanPowerModelValidationCase) -> dict[str, Any]:
        """将校验用例 ORM 转为字典。

        参数：
            row: PlanPowerModelValidationCase ORM 对象。

        返回：
            接口可序列化的预留校验用例字典。
        """
        return {
            "id": row.id,
            "version_id": row.version_id,
            "model_code": row.model_code,
            "case_name": row.case_name,
            "input": self._loads_json(row.input_json),
            "excel_expected": self._loads_json(row.excel_expected_json),
            "system_result": self._loads_json(row.system_result_json),
            "diff": self._loads_json(row.diff_json),
            "status": row.status,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }

    def _parse_status(self, parsed: ParsedPowerModelWorkbook) -> str:
        """根据解析问题计算版本状态。

        参数：
            parsed: 内存 Workbook 解析结果。

        返回：
            failed / warning / success 三种解析状态。
        """
        if parsed.error_count:
            return "failed"
        if parsed.warning_count:
            return "warning"
        return "success"

    def _issue_to_dict(self, issue) -> dict[str, Any]:
        """将内存 issue 转为字典。

        参数：
            issue: ParsedPowerIssue 内存对象。

        返回：
            可序列化的 issue 字典。
        """
        return {
            "level": issue.level,
            "issue_code": issue.issue_code,
            "message": issue.message,
            "source_sheet_name": issue.source_sheet_name,
            "source_cell_ref": issue.source_cell_ref,
            "raw": issue.raw,
        }

    def _change_history_to_dict(self, row) -> dict[str, Any]:
        """将内存更改履历转为字典。

        参数：
            row: ParsedChangeHistory 内存对象。

        返回：
            可序列化的更改履历字典，用于模型版本追溯。
        """
        return {
            "sequence_no": row.sequence_no,
            "change_content": row.change_content,
            "reviser": row.reviser,
            "change_date": row.change_date,
            "source_cell_ref": row.source_cell_ref,
        }

    def _loads_json(self, value: str | None) -> Any:
        """解析 JSON 文本。

        参数：
            value: JSON 字符串或 None。

        返回：
            解析后的 Python 对象；空值返回 None。
        """
        if not value:
            return None
        return json.loads(value)

    def _decimal_to_float(self, value) -> float | None:
        """将 Decimal 值转成接口友好的 float。

        参数：
            value: Decimal 或 None。

        返回：
            float 或 None，便于 ApiResponse JSON 序列化。
        """
        if value is None:
            return None
        return float(value)


__all__ = ["PowerModelRepository"]
