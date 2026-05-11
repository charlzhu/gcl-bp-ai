from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

import yaml
from sqlalchemy.orm import Session

from backend.app.domains.plan_bom.constants import CORE_MATERIAL_CATEGORIES
from backend.app.domains.plan_bom.models import (
    PlanBomHeader,
    PlanBomMaterialLine,
    PlanPowerFactorOption,
    PlanPowerModelSheet,
    PlanPowerModelVersion,
)
from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository


CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"
DEFAULT_MAPPING_PATH = CONFIG_DIR / "power_bom_mapping.yaml"
DEFAULT_ALIASES_PATH = CONFIG_DIR / "power_aliases.json"
RESOLVED_STATUS = "resolved"
PARTIAL_STATUS = "partial"
NOT_FOUND_STATUS = "not_found"
CANDIDATE_REQUIRED_STATUS = "candidate_required"
NO_ACTIVE_MODEL_STATUS = "no_active_power_model"
CANDIDATE_LIMIT = 20


@dataclass(frozen=True)
class PowerBomSourceLine:
    """BOM 原始材料行追溯信息。"""

    id: int
    material_category: str | None
    material_name: str
    description: str | None
    sap_code: str
    standard_usage: str | None
    raw_row_no: int | None

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。"""
        return {
            "id": self.id,
            "material_category": self.material_category,
            "material_name": self.material_name,
            "description": self.description,
            "sap_code": self.sap_code,
            "standard_usage": self.standard_usage,
            "raw_row_no": self.raw_row_no,
        }


@dataclass(frozen=True)
class PowerBomResolvedItem:
    """单个功率配置项的映射结果。"""

    factor_key: str
    value: str
    source: str
    confidence: float
    source_line_ids: list[int] = field(default_factory=list)
    source_description: str | None = None
    rule_id: str | None = None
    alternatives: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。"""
        return {
            "factor_key": self.factor_key,
            "value": self.value,
            "source": self.source,
            "confidence": self.confidence,
            "source_line_ids": self.source_line_ids,
            "source_description": self.source_description,
            "rule_id": self.rule_id,
            "alternatives": self.alternatives,
        }


@dataclass(frozen=True)
class PowerBomUnresolvedItem:
    """无法自动映射的配置项，必须追问或人工确认。"""

    factor_key: str
    reason: str
    source_line_ids: list[int] = field(default_factory=list)
    source_descriptions: list[str] = field(default_factory=list)
    candidate_options: list[str] = field(default_factory=list)
    strategy: str = "ask_confirmation"

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。"""
        return {
            "factor_key": self.factor_key,
            "reason": self.reason,
            "source_line_ids": self.source_line_ids,
            "source_descriptions": self.source_descriptions,
            "candidate_options": self.candidate_options,
            "strategy": self.strategy,
        }


@dataclass(frozen=True)
class PowerBomCandidate:
    """订单或文件实例候选项。"""

    order_no: str
    version_no: str
    order_name: str | None
    order_identity_key: str
    file_instance_key: str
    source_type: str

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。"""
        return {
            "order_no": self.order_no,
            "version_no": self.version_no,
            "order_name": self.order_name,
            "order_identity_key": self.order_identity_key,
            "file_instance_key": self.file_instance_key,
            "source_type": self.source_type,
        }


@dataclass(frozen=True)
class PowerBomConfigResolution:
    """BOM 配置自动映射总结果。"""

    status: str
    message: str
    order_no: str | None = None
    version_no: str | None = None
    order_name: str | None = None
    order_identity_key: str | None = None
    file_instance_key: str | None = None
    model_code: str | None = None
    resolved_config: dict[str, PowerBomResolvedItem] = field(default_factory=dict)
    unresolved_items: list[PowerBomUnresolvedItem] = field(default_factory=list)
    source_lines: list[PowerBomSourceLine] = field(default_factory=list)
    candidates: list[PowerBomCandidate] = field(default_factory=list)
    candidate_total_count: int = 0
    candidate_has_more: bool = False
    warnings: list[str] = field(default_factory=list)

    def to_prediction_configuration(self) -> dict[str, str]:
        """输出可直接传给 M3 PowerPredictionEngine 的 configuration。

        返回：
            仅包含已解析配置项的 `{factor_key: value}` 字典；未解析项不会被填入，避免瞎猜。
        """
        return {key: item.value for key, item in self.resolved_config.items() if key != "model_code"}

    def to_dict(self) -> dict[str, Any]:
        """转换为可序列化字典。"""
        return {
            "status": self.status,
            "message": self.message,
            "order_no": self.order_no,
            "version_no": self.version_no,
            "order_name": self.order_name,
            "order_identity_key": self.order_identity_key,
            "file_instance_key": self.file_instance_key,
            "model_code": self.model_code,
            "resolved_config": {key: value.to_dict() for key, value in self.resolved_config.items()},
            "unresolved_items": [item.to_dict() for item in self.unresolved_items],
            "source_lines": [line.to_dict() for line in self.source_lines],
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "candidate_total_count": self.candidate_total_count,
            "candidate_has_more": self.candidate_has_more,
            "warnings": self.warnings,
        }


class PlanBomPowerConfigResolverService:
    """计划 BOM 到功率预测配置的确定性映射服务。

    职责边界：
    1. 只读取真实 BOM 与 active 功率模型数据；
    2. 只做材料规格到功率模型 option 的规则化映射；
    3. 不调用 LLM、不执行 Excel 宏、不计算功率数值；
    4. 无法确认时返回 unresolved_items，由 M5 问答层追问或提示人工确认。
    """

    def __init__(
        self,
        db: Session,
        *,
        repository: PlanBomQueryRepository | None = None,
        mapping_path: Path | str = DEFAULT_MAPPING_PATH,
        aliases_path: Path | str = DEFAULT_ALIASES_PATH,
    ) -> None:
        self.db = db
        self.repository = repository or PlanBomQueryRepository(db)
        self.mapping = self._load_yaml(Path(mapping_path))
        self.aliases = self._load_json(Path(aliases_path))

    def resolve(
        self,
        *,
        order_no: str | None = None,
        order_identity_key: str | None = None,
        file_instance_key: str | None = None,
        order_name: str | None = None,
        version_no: str | None = None,
        benchmark: str | None = None,
        explicit_configuration: Mapping[str, Any] | None = None,
    ) -> PowerBomConfigResolution:
        """解析真实 BOM 对应的功率预测配置。

        参数：
            order_no: 完整订单号或评审号；
            order_identity_key: 已确认候选后的内部订单实例键；
            file_instance_key: 已确认候选后的文件实例键；
            order_name: 订单名称片段；
            version_no: 指定 BOM 版本号；
            benchmark: 可选标板基准，若不传则使用 active 模型默认值。
            explicit_configuration: 用户在订单问题中直接给出的功率配置；用于覆盖 BOM 中缺失线径等可确定配置。

        返回：
            `PowerBomConfigResolution`，包含配置、原始 BOM 追溯、未识别项和候选项。
        """
        active_version = self._active_power_version()
        if active_version is None:
            return PowerBomConfigResolution(status=NO_ACTIVE_MODEL_STATUS, message="当前没有 active 功率模型版本，无法执行 BOM 配置映射。")

        located = self._locate_header(
            order_no=order_no,
            order_identity_key=order_identity_key,
            file_instance_key=file_instance_key,
            order_name=order_name,
            version_no=version_no,
        )
        if isinstance(located, PowerBomConfigResolution):
            return located
        header = located

        lines = self.repository.list_material_lines_for_header(header=header, material_categories=CORE_MATERIAL_CATEGORIES)
        source_lines = [self._source_line(line) for line in lines]
        grouped = self._group_lines(lines)
        unresolved: list[PowerBomUnresolvedItem] = []
        warnings: list[str] = []

        model_code_item = self._resolve_model_code(header=header, version_id=active_version.id)
        if model_code_item is None:
            unresolved.append(
                PowerBomUnresolvedItem(
                    factor_key="model_code",
                    reason="订单名称中未识别到当前 active 功率模型支持的版型。",
                    source_descriptions=[header.order_name or header.order_no],
                    candidate_options=self._active_model_codes(active_version.id),
                )
            )
            return self._build_result(header, None, {}, unresolved, source_lines, warnings)

        sheet = self._get_sheet(active_version.id, model_code_item.value)
        if sheet is None:
            unresolved.append(
                PowerBomUnresolvedItem(
                    factor_key="model_code",
                    reason="订单版型未命中当前 active 功率模型。",
                    source_descriptions=[header.order_name or header.order_no],
                    candidate_options=self._active_model_codes(active_version.id),
                )
            )
            return self._build_result(header, model_code_item.value, {}, unresolved, source_lines, warnings)

        resolved: dict[str, PowerBomResolvedItem] = {"model_code": model_code_item}
        material_resolvers = {
            "glass": self._resolve_glass,
            "ribbon": self._resolve_ribbon,
            "busbar": self._resolve_busbar,
            "cable": self._resolve_cable,
        }
        for factor_key, resolver in material_resolvers.items():
            item = resolver(sheet, grouped)
            if item is None:
                unresolved.append(self._unresolved_for_factor(factor_key, sheet, grouped))
            else:
                resolved[factor_key] = item

        self._apply_explicit_configuration_overrides(
            sheet=sheet,
            explicit_configuration=explicit_configuration,
            resolved=resolved,
            unresolved=unresolved,
            warnings=warnings,
        )

        for factor_key, default_rule in (self.mapping.get("model_defaults") or {}).items():
            if factor_key == "benchmark" and benchmark:
                benchmark_value = self._canonical_benchmark(benchmark)
                option = self._coerce_to_valid_option(sheet.id, factor_key, benchmark_value)
                if option is None:
                    unresolved.append(
                        PowerBomUnresolvedItem(
                            factor_key="benchmark",
                            reason="显式输入的标板基准未命中当前功率模型有效选项，不能回退默认值。",
                            candidate_options=self._option_labels(sheet.id, "benchmark"),
                            strategy="ask_confirmation",
                        )
                    )
                    continue
                default_item = PowerBomResolvedItem(
                    factor_key="benchmark",
                    value=option.option_label,
                    source="explicit_input",
                    confidence=0.95,
                    source_description=benchmark,
                    rule_id="explicit.benchmark",
                )
            else:
                default_item = self._resolve_default_option(
                    sheet,
                    factor_key,
                    input_value=None,
                    source=str(default_rule.get("source") or "model_default"),
                    confidence=float(default_rule.get("confidence") or 0.85),
                )
            if default_item is not None:
                resolved[factor_key] = default_item
            elif factor_key in {"cell_size", "supplier", "benchmark"}:
                warnings.append(f"功率模型缺少默认 {factor_key} 选项，M3 调用时可能需要显式补充。")

        return self._build_result(header, model_code_item.value, resolved, unresolved, source_lines, warnings)

    def _apply_explicit_configuration_overrides(
        self,
        *,
        sheet: PlanPowerModelSheet,
        explicit_configuration: Mapping[str, Any] | None,
        resolved: dict[str, PowerBomResolvedItem],
        unresolved: list[PowerBomUnresolvedItem],
        warnings: list[str],
    ) -> None:
        """把用户显式给出的功率配置覆盖到订单 BOM 解析结果中。

        参数：
            sheet: 当前订单命中的功率模型页。
            explicit_configuration: NLU 从问题原文抽取的 ribbon/glass/cable 等配置。
            resolved: 已解析配置字典，原地更新。
            unresolved: 未解析配置列表，原地移除被显式配置解决的项目。
            warnings: 解析警告列表，原地追加降级说明。

        返回：
            无返回值。该方法只做 M4 确定性 option 校验，不计算功率数值。
        """
        if not explicit_configuration:
            return
        for factor_key in ("ribbon", "glass", "busbar", "cable", "cell_size", "supplier", "benchmark"):
            raw_value = explicit_configuration.get(factor_key)
            if raw_value is None or self._stringify(raw_value) == "":
                continue
            option = self._coerce_explicit_option(sheet, factor_key, self._stringify(raw_value), warnings)
            # 用户显式给出配置时，其语义优先于 BOM 自动反查；若无法命中真实 option，必须 fail-closed。
            unresolved[:] = [item for item in unresolved if item.factor_key != factor_key]
            if option is None:
                unresolved.append(
                    PowerBomUnresolvedItem(
                        factor_key=factor_key,
                        reason="显式输入配置未命中当前功率模型有效选项，不能用 BOM 或默认值静默替代。",
                        source_descriptions=[self._stringify(raw_value)],
                        candidate_options=self._option_labels(sheet.id, factor_key),
                        strategy="ask_confirmation",
                    )
                )
                resolved.pop(factor_key, None)
                continue
            resolved[factor_key] = PowerBomResolvedItem(
                factor_key=factor_key,
                value=option.option_label,
                source="explicit_input",
                confidence=0.95,
                source_description=self._stringify(raw_value),
                rule_id=f"explicit.{factor_key}",
            )

    def resolve_explicit_configuration(
        self,
        *,
        model_code: str | None,
        configuration: Mapping[str, Any] | None = None,
    ) -> PowerBomConfigResolution:
        """解析用户显式输入的功率预测配置。

        参数：
            model_code: 用户自然语言中给出的版型编码，例如 `NT12R-66GDF` 或 `NT12R/66GDF`。
            configuration: 用户显式给出的配置项，支持 ribbon/glass/busbar/cable/benchmark/supplier/cell_size。

        返回：
            `PowerBomConfigResolution`。该结果不绑定 BOM 订单，order_no 为空，但仍复用 M4 的 option 校验、别名归一和追溯结构。
        """
        active_version = self._active_power_version()
        if active_version is None:
            return PowerBomConfigResolution(status=NO_ACTIVE_MODEL_STATUS, message="当前没有 active 功率模型版本，无法执行显式配置映射。")
        if not model_code or not self._stringify(model_code):
            return PowerBomConfigResolution(
                status=PARTIAL_STATUS,
                message="显式配置功率问答缺少版型编码。",
                unresolved_items=[
                    PowerBomUnresolvedItem(
                        factor_key="model_code",
                        reason="用户问题中未识别到当前功率模型支持的版型。",
                        candidate_options=self._active_model_codes(active_version.id),
                    )
                ],
            )

        normalized_model_code = self._normalize_model_code(model_code)
        sheet = self._get_sheet(active_version.id, normalized_model_code)
        if sheet is None:
            return PowerBomConfigResolution(
                status=PARTIAL_STATUS,
                message="显式输入的版型未命中当前 active 功率模型。",
                model_code=normalized_model_code,
                unresolved_items=[
                    PowerBomUnresolvedItem(
                        factor_key="model_code",
                        reason="版型未命中当前 active 功率模型，不能编造模型页。",
                        source_descriptions=[self._stringify(model_code)],
                        candidate_options=self._active_model_codes(active_version.id),
                    )
                ],
            )

        raw_config = dict(configuration or {})
        unresolved: list[PowerBomUnresolvedItem] = []
        warnings: list[str] = []
        resolved: dict[str, PowerBomResolvedItem] = {
            "model_code": PowerBomResolvedItem(
                factor_key="model_code",
                value=sheet.normalized_model_code,
                source="explicit_input",
                confidence=0.96,
                source_description=self._stringify(model_code),
                rule_id="explicit.model_code",
            )
        }

        for factor_key in ("ribbon", "glass", "busbar", "cable", "cell_size", "supplier", "benchmark"):
            raw_value = raw_config.get(factor_key)
            if raw_value is None or self._stringify(raw_value) == "":
                continue
            option = self._coerce_explicit_option(sheet, factor_key, self._stringify(raw_value), warnings)
            if option is None:
                unresolved.append(
                    PowerBomUnresolvedItem(
                        factor_key=factor_key,
                        reason="显式输入配置未命中当前功率模型有效选项。",
                        source_descriptions=[self._stringify(raw_value)],
                        candidate_options=self._option_labels(sheet.id, factor_key),
                        strategy="ask_confirmation",
                    )
                )
                continue
            resolved[factor_key] = PowerBomResolvedItem(
                factor_key=factor_key,
                value=option.option_label,
                source="explicit_input",
                confidence=0.95,
                source_description=self._stringify(raw_value),
                rule_id=f"explicit.{factor_key}",
            )

        # 显式配置问法常只提供影响功率的差异项；未显式给出的基础项仍使用 active 模型默认值，
        # 并在追溯中标明来源，避免让 LLM 或前端补数。
        for factor_key, default_rule in (self.mapping.get("model_defaults") or {}).items():
            if factor_key in resolved:
                continue
            default_item = self._resolve_default_option(
                sheet,
                factor_key,
                input_value=None,
                source=str(default_rule.get("source") or "model_default"),
                confidence=float(default_rule.get("confidence") or 0.85),
            )
            if default_item is not None:
                resolved[factor_key] = default_item
            elif factor_key in {"cell_size", "supplier", "benchmark"}:
                warnings.append(f"功率模型缺少默认 {factor_key} 选项，M3 调用时可能需要显式补充。")

        status = RESOLVED_STATUS if not unresolved else PARTIAL_STATUS
        message = "显式配置已成功映射到功率模型。" if status == RESOLVED_STATUS else "显式配置存在未识别项，需要追问或人工确认。"
        return PowerBomConfigResolution(
            status=status,
            message=message,
            model_code=sheet.normalized_model_code,
            resolved_config=resolved,
            unresolved_items=unresolved,
            warnings=warnings,
        )

    def _locate_header(
        self,
        *,
        order_no: str | None,
        order_identity_key: str | None,
        file_instance_key: str | None,
        order_name: str | None,
        version_no: str | None,
    ) -> PlanBomHeader | PowerBomConfigResolution:
        """定位唯一 BOM 头，无法唯一定位时返回候选响应。"""
        headers = self.repository.list_active_headers(
            order_identity_key=order_identity_key,
            file_instance_key=file_instance_key,
            order_no=order_no if order_no and not order_identity_key and not file_instance_key else None,
            order_name_like=order_name,
        )
        # 业务员可能输入评审号尾号或订单号片段。完整订单号精确查询无结果时，
        # 再降级到 LIKE；如果精确查询已命中，则不混入其他候选，避免误扩范围。
        if not headers and order_no and not order_identity_key and not file_instance_key:
            headers = self.repository.list_active_headers(order_no_like=order_no, order_name_like=order_name)
        if not headers:
            return PowerBomConfigResolution(status=NOT_FOUND_STATUS, message="未找到匹配的有效 BOM。")

        if version_no:
            headers = [header for header in headers if header.version_no == version_no]
            if not headers:
                return PowerBomConfigResolution(status=NOT_FOUND_STATUS, message="已找到订单，但指定 BOM 版本不存在。")

        if order_name:
            hinted_headers = self._filter_headers_by_order_name_hint(headers, order_name)
            if hinted_headers:
                headers = hinted_headers

        identity_keys = {header.order_identity_key for header in headers}
        if len(identity_keys) > 1 and not order_identity_key:
            return self._candidate_required("命中多个订单实例，请先确认订单。", headers)

        selected_version = self._select_latest_header(headers)
        same_version_headers = [
            header
            for header in headers
            if header.order_identity_key == selected_version.order_identity_key and header.version_no == selected_version.version_no
        ]
        file_keys = {header.file_instance_key for header in same_version_headers}
        if len(file_keys) > 1 and not file_instance_key:
            return self._candidate_required("命中同一订单版本的多个文件实例，请先确认文件实例。", same_version_headers)
        return selected_version

    def _resolve_model_code(self, *, header: PlanBomHeader, version_id: int) -> PowerBomResolvedItem | None:
        """从订单名称中识别并校验功率模型版型。"""
        raw_text = " ".join(part for part in [header.order_name, header.order_no] if part)
        alias_map = self.aliases.get("model_aliases") or {}
        for alias, target in alias_map.items():
            if alias in raw_text or target in raw_text:
                value = str(target)
                if value in self._active_model_codes(version_id):
                    return PowerBomResolvedItem(
                        factor_key="model_code",
                        value=value,
                        source="bom_header.order_name",
                        confidence=0.96,
                        source_description=header.order_name or header.order_no,
                        rule_id="model_aliases",
                    )
        model_cfg = self.mapping.get("model_code") or {}
        pattern = model_cfg.get("regex")
        replacement = model_cfg.get("replacement")
        if pattern and replacement:
            match = re.search(pattern, raw_text, flags=re.IGNORECASE)
            if match:
                value = match.expand(str(replacement))
                if value in self._active_model_codes(version_id):
                    return PowerBomResolvedItem(
                        factor_key="model_code",
                        value=value,
                        source="bom_header.order_name",
                        confidence=0.92,
                        source_description=header.order_name or header.order_no,
                        rule_id="model_code.regex",
                    )
        return None

    def _resolve_glass(self, sheet: PlanPowerModelSheet, grouped: Mapping[str, list[PlanBomMaterialLine]]) -> PowerBomResolvedItem | None:
        """解析玻璃 + 间隙膜组合并映射到 glass option。"""
        glass_lines = grouped.get("glass", [])
        if not glass_lines:
            return None
        gap_lines = grouped.get("gap_film", [])
        glass_text = self._joined_text(glass_lines)
        gap_text = self._joined_text(gap_lines)
        combined_text = f"{glass_text}\n{gap_text}"
        rules = ((self.mapping.get("factor_mappings") or {}).get("glass") or {}).get("rules") or []
        for rule in rules:
            if not self._text_matches_rule(combined_text, gap_text, rule):
                continue
            candidate = self._coerce_to_valid_option(sheet.id, "glass", str(rule["value"]))
            if candidate is None:
                continue
            all_lines = glass_lines + gap_lines
            return PowerBomResolvedItem(
                factor_key="glass",
                value=candidate.option_label,
                source="bom_material_line.glass+gap_film",
                confidence=float(rule.get("confidence") or 0.8),
                source_line_ids=[line.id for line in all_lines],
                source_description=self._source_description(all_lines),
                rule_id=str(rule.get("id") or "glass_rule"),
            )
        return None

    def _resolve_ribbon(self, sheet: PlanPowerModelSheet, grouped: Mapping[str, list[PlanBomMaterialLine]]) -> PowerBomResolvedItem | None:
        """解析互联条直径并映射到 ribbon option。"""
        lines = grouped.get("interconnect_bar", [])
        if not lines:
            return None
        cfg = ((self.mapping.get("factor_mappings") or {}).get("ribbon") or {})
        pattern = re.compile(str(cfg.get("diameter_regex") or r"φ\s*([0-9.]+)\s*mm"), flags=re.IGNORECASE)
        buckets: dict[str, Decimal] = {}
        line_ids_by_value: dict[str, list[int]] = {}
        for line in lines:
            match = pattern.search(self._line_text(line))
            if not match:
                continue
            value = self._format_number(match.group(1))
            buckets[value] = buckets.get(value, Decimal("0")) + (line.standard_usage or Decimal("0"))
            line_ids_by_value.setdefault(value, []).append(line.id)
        if not buckets:
            return None
        selected = max(buckets.items(), key=lambda item: (item[1], Decimal(item[0])))[0]
        option = self._coerce_to_valid_option(sheet.id, "ribbon", selected)
        if option is None:
            return None
        alternatives = [value for value in sorted(buckets.keys(), key=lambda item: Decimal(item), reverse=True) if value != selected]
        confidence = float(cfg.get("confidence_single") or 0.94) if not alternatives else float(cfg.get("confidence_multiple") or 0.82)
        return PowerBomResolvedItem(
            factor_key="ribbon",
            value=option.option_label,
            source="bom_material_line.interconnect_bar",
            confidence=confidence,
            source_line_ids=line_ids_by_value.get(selected, []),
            source_description=self._source_description(lines),
            rule_id="ribbon.dominant_usage",
            alternatives=alternatives,
        )

    def _resolve_busbar(self, sheet: PlanPowerModelSheet, grouped: Mapping[str, list[PlanBomMaterialLine]]) -> PowerBomResolvedItem | None:
        """解析汇流条宽度/厚度组合并映射到 busbar option。"""
        lines = grouped.get("busbar", [])
        if not lines:
            return None
        cfg = ((self.mapping.get("factor_mappings") or {}).get("busbar") or {})
        pattern = re.compile(str(cfg.get("size_regex") or r"([0-9.]+)\s*\*\s*([0-9.]+)\s*mm"), flags=re.IGNORECASE)
        width_order = [str(item) for item in cfg.get("width_order") or ["6", "4"]]
        by_width: dict[str, dict[str, Decimal]] = {width: {} for width in width_order}
        line_ids_by_part: dict[tuple[str, str], list[int]] = {}
        reflective = False
        for line in lines:
            text = self._line_text(line)
            reflective = reflective or "反光" in text
            match = pattern.search(text)
            if not match:
                continue
            thickness = self._format_number(match.group(1))
            width = self._format_number(match.group(2))
            if width not in by_width:
                continue
            by_width[width][thickness] = by_width[width].get(thickness, Decimal("0")) + (line.standard_usage or Decimal("0"))
            line_ids_by_part.setdefault((width, thickness), []).append(line.id)
        selected_parts: list[str] = []
        selected_line_ids: list[int] = []
        for width in width_order:
            if not by_width.get(width):
                return None
            thickness = max(by_width[width].items(), key=lambda item: (item[1], Decimal(item[0])))[0]
            selected_parts.append(f"{width}*{thickness}")
            selected_line_ids.extend(line_ids_by_part.get((width, thickness), []))
        suffix = str(cfg.get("suffix_when_reflective") or "反光") if reflective else ""
        candidate_value = "+".join(selected_parts) + suffix
        option = self._coerce_to_valid_option(sheet.id, "busbar", candidate_value)
        if option is None:
            return None
        return PowerBomResolvedItem(
            factor_key="busbar",
            value=option.option_label,
            source="bom_material_line.busbar",
            confidence=float(cfg.get("confidence_complete") or 0.9),
            source_line_ids=selected_line_ids,
            source_description=self._source_description(lines),
            rule_id="busbar.dominant_thickness_by_width",
        )

    def _resolve_cable(self, sheet: PlanPowerModelSheet, grouped: Mapping[str, list[PlanBomMaterialLine]]) -> PowerBomResolvedItem | None:
        """解析接线盒线缆长度/线径并映射到 cable option。"""
        lines = grouped.get("junction_box", [])
        if not lines:
            return None
        cfg = ((self.mapping.get("factor_mappings") or {}).get("cable") or {})
        length_value: str | None = None
        wire_size: str | None = None
        source_line_ids: list[int] = []
        for line in lines:
            text = self._line_text(line)
            for pattern_cfg in cfg.get("length_patterns") or []:
                if re.search(str(pattern_cfg.get("pattern")), text, flags=re.IGNORECASE):
                    length_value = str(pattern_cfg.get("normalized"))
                    source_line_ids.append(line.id)
                    break
            for pattern_cfg in cfg.get("wire_size_patterns") or []:
                if re.search(str(pattern_cfg.get("pattern")), text, flags=re.IGNORECASE):
                    wire_size = str(pattern_cfg.get("normalized"))
                    break
            if length_value:
                break
        if not length_value or not wire_size:
            return None
        template = str(cfg.get("option_template") or "{length}（{wire_size}）")
        candidate_value = template.format(length=length_value, wire_size=wire_size)
        option = self._coerce_to_valid_option(sheet.id, "cable", candidate_value)
        if option is None:
            return None
        return PowerBomResolvedItem(
            factor_key="cable",
            value=option.option_label,
            source="bom_material_line.junction_box",
            confidence=float(cfg.get("confidence") or 0.9),
            source_line_ids=source_line_ids or [line.id for line in lines],
            source_description=self._source_description(lines),
            rule_id="cable.length_and_wire_size",
        )

    def _resolve_default_option(
        self,
        sheet: PlanPowerModelSheet,
        factor_key: str,
        *,
        input_value: str | None,
        source: str,
        confidence: float,
    ) -> PowerBomResolvedItem | None:
        """读取模型默认 option 或显式输入 option。"""
        option = self._coerce_to_valid_option(sheet.id, factor_key, input_value) if input_value else None
        if option is None:
            option = self._default_option(sheet.id, factor_key)
        if option is None:
            return None
        return PowerBomResolvedItem(
            factor_key=factor_key,
            value=option.option_label,
            source=source,
            confidence=confidence,
            source_line_ids=[],
            source_description=f"active_power_model:{sheet.normalized_model_code}",
            rule_id=f"default.{factor_key}",
        )

    def _unresolved_for_factor(
        self,
        factor_key: str,
        sheet: PlanPowerModelSheet,
        grouped: Mapping[str, list[PlanBomMaterialLine]],
    ) -> PowerBomUnresolvedItem:
        """构造无法映射项，附带候选 option 和原始描述。"""
        factor_cfg = ((self.mapping.get("factor_mappings") or {}).get(factor_key) or {})
        categories = list(factor_cfg.get("source_categories") or [])
        lines = [line for category in categories for line in grouped.get(category, [])]
        return PowerBomUnresolvedItem(
            factor_key=factor_key,
            reason="BOM 材料规格无法映射到当前功率模型有效配置项，需追问或人工确认。",
            source_line_ids=[line.id for line in lines],
            source_descriptions=[self._line_text(line) for line in lines],
            candidate_options=self._option_labels(sheet.id, factor_key),
            strategy=str(factor_cfg.get("unresolved_strategy") or "ask_confirmation"),
        )

    def _build_result(
        self,
        header: PlanBomHeader,
        model_code: str | None,
        resolved: dict[str, PowerBomResolvedItem],
        unresolved: list[PowerBomUnresolvedItem],
        source_lines: list[PowerBomSourceLine],
        warnings: list[str],
    ) -> PowerBomConfigResolution:
        """组装最终映射结果。"""
        status = RESOLVED_STATUS if not unresolved else PARTIAL_STATUS
        message = "BOM 配置已成功映射到功率模型。" if status == RESOLVED_STATUS else "BOM 配置存在未识别项，需要追问或人工确认。"
        return PowerBomConfigResolution(
            status=status,
            message=message,
            order_no=header.order_no,
            version_no=header.version_no,
            order_name=header.order_name,
            order_identity_key=header.order_identity_key,
            file_instance_key=header.file_instance_key,
            model_code=model_code,
            resolved_config=resolved,
            unresolved_items=unresolved,
            source_lines=source_lines,
            warnings=warnings,
        )

    def _candidate_required(self, message: str, headers: list[PlanBomHeader]) -> PowerBomConfigResolution:
        """返回受控候选列表，避免宽泛查询一次性暴露过多候选。"""
        total_count = len(headers)
        limited_headers = headers[:CANDIDATE_LIMIT]
        has_more = total_count > CANDIDATE_LIMIT
        warnings = [f"候选数量 {total_count} 超过上限 {CANDIDATE_LIMIT}，仅返回前 {CANDIDATE_LIMIT} 条，请补充订单/文件条件。"] if has_more else []
        return PowerBomConfigResolution(
            status=CANDIDATE_REQUIRED_STATUS,
            message=message,
            candidates=[self._candidate(header) for header in limited_headers],
            candidate_total_count=total_count,
            candidate_has_more=has_more,
            warnings=warnings,
        )

    def _coerce_to_valid_option(self, sheet_id: int, factor_key: str, value: str | None) -> PlanPowerFactorOption | None:
        """把候选值校验并转换成当前模型真实 option。"""
        if value is None or self._stringify(value) == "":
            return None
        canonical_value = self._canonical_option(factor_key, value)
        for option in self._options(sheet_id, factor_key):
            option_labels = [option.option_label, option.normalized_option_label]
            for label in option_labels:
                if self._normalize_label(self._canonical_option(factor_key, label)) == self._normalize_label(canonical_value):
                    return option
        return None

    def _coerce_explicit_option(
        self,
        sheet: PlanPowerModelSheet,
        factor_key: str,
        value: str,
        warnings: list[str],
    ) -> PlanPowerFactorOption | None:
        """把显式自然语言配置归一到当前模型真实 option。

        参数：
            sheet: 当前功率模型页。
            factor_key: 配置项 key。
            value: 用户原文中的配置值。
            warnings: 输出警告列表；当使用确定性降级规则时记录原因。

        返回：
            命中的真实 `PlanPowerFactorOption`；无法安全命中时返回 None。
        """
        option = self._coerce_to_valid_option(sheet.id, factor_key, value)
        if option is not None:
            return option
        normalized = self._normalize_label(value)
        if factor_key == "benchmark":
            return self._coerce_to_valid_option(sheet.id, factor_key, self._canonical_benchmark(value))
        if factor_key == "ribbon":
            # docx 中“0.24+0.26”表示混用焊带；M4 显式配置按较大直径作为模型选择项，
            # 与 BOM 映射中按主用量/较大规格收敛到单一 Excel option 的原则一致。
            values = re.findall(r"\d+(?:\.\d+)?", value)
            if values:
                selected = max(values, key=lambda item: Decimal(item))
                option = self._coerce_to_valid_option(sheet.id, factor_key, self._format_number(selected))
                if option is not None:
                    if len(set(values)) > 1:
                        warnings.append(f"显式焊带包含多个规格 {value}，已按较大直径 {option.option_label} 映射到功率模型单选项。")
                    return option
        if factor_key == "glass":
            # 用户只说“双镀/单镀/超高透”等玻璃大类时，优先选择 active 模型默认玻璃中相同前缀的选项；
            # 默认项前缀不一致时，再在当前模型候选里寻找唯一/首个同前缀选项，仍以模型真实 option 为准。
            default_option = self._default_option(sheet.id, factor_key)
            coating_prefix = None
            for candidate_prefix in ("超高透", "高透", "双镀", "单镀"):
                if candidate_prefix in value:
                    coating_prefix = candidate_prefix
                    break
            if coating_prefix and default_option and default_option.option_label.startswith(coating_prefix):
                warnings.append(f"显式玻璃仅给出 {coating_prefix}，已沿用 active 模型默认玻璃细分：{default_option.option_label}。")
                return default_option
            if coating_prefix:
                for candidate in self._options(sheet.id, factor_key):
                    if candidate.option_label.startswith(coating_prefix):
                        warnings.append(f"显式玻璃仅给出 {coating_prefix}，已匹配当前模型候选：{candidate.option_label}。")
                        return candidate
        if factor_key == "cable":
            # 显式接线盒可能写“300/200线长”，也可能在无 BOM 方案评估中写“+400/-200mm（4mm²）”。
            # 长度和线径都只用于拼当前模型真实 option；若拼不出有效 option，仍 fail-closed 追问。
            length_match = re.search(r"(\d{2,4})\s*/\s*-?(\d{2,4})", normalized)
            default_option = self._default_option(sheet.id, factor_key)
            if length_match:
                explicit_wire_match = re.search(r"(?P<size>\d+(?:\.\d+)?)\s*mm\s*(?:²|2)", value, flags=re.IGNORECASE)
                explicit_wire_size = f"{self._format_number(explicit_wire_match.group('size'))}mm²" if explicit_wire_match else None
                default_wire_size = self._default_cable_wire_size(default_option)
                wire_candidates = (
                    [(explicit_wire_size, "显式线径")]
                    if explicit_wire_size
                    else [(default_wire_size, "active 模型默认线径")]
                )
                for wire_size, wire_source in wire_candidates:
                    if not wire_size:
                        continue
                    candidate_value = f"+{length_match.group(1)}/-{length_match.group(2)}mm（{wire_size}）"
                    option = self._coerce_to_valid_option(sheet.id, factor_key, candidate_value)
                    if option is not None:
                        warnings.append(f"显式接线盒长度 {value} 已按{wire_source} {wire_size} 映射为 {option.option_label}。")
                        return option
                if explicit_wire_size:
                    return None
                if default_option and f"+{length_match.group(1)}/-{length_match.group(2)}" in self._normalize_label(default_option.option_label):
                    warnings.append(f"显式接线盒只给出长度 {value}，已沿用 active 模型默认选项：{default_option.option_label}。")
                    return default_option
        return None

    @staticmethod
    def _default_cable_wire_size(default_option: PlanPowerFactorOption | None) -> str | None:
        """从 active 模型默认接线盒 option 中解析线径标签。

        参数：
            default_option: 当前模型 `cable` 默认 option。

        返回：
            例如 `4mm²`、`6mm²`；默认项无可解析线径时返回 None。
        """
        if default_option is None:
            return None
        match = re.search(r"(?P<size>\d+(?:\.\d+)?)\s*mm\s*(?:²|2)", default_option.option_label or "", flags=re.IGNORECASE)
        if not match:
            return None
        return f"{PlanBomPowerConfigResolverService._format_number(match.group('size'))}mm²"

    def _default_option(self, sheet_id: int, factor_key: str) -> PlanPowerFactorOption | None:
        """读取模型默认 option；没有默认标记时回退首个有效 option。"""
        options = self._options(sheet_id, factor_key)
        for option in options:
            if int(option.is_default or 0) == 1:
                return option
        return options[0] if options else None

    def _options(self, sheet_id: int, factor_key: str) -> list[PlanPowerFactorOption]:
        """读取某配置项的有效 option。"""
        return (
            self.db.query(PlanPowerFactorOption)
            .filter_by(sheet_id=sheet_id, factor_key=factor_key, is_valid=1)
            .order_by(PlanPowerFactorOption.id.asc())
            .all()
        )

    def _option_labels(self, sheet_id: int, factor_key: str) -> list[str]:
        """读取某配置项候选标签。"""
        return [option.option_label for option in self._options(sheet_id, factor_key)]

    def _active_power_version(self) -> PlanPowerModelVersion | None:
        """读取 active 功率模型版本。"""
        return self.db.query(PlanPowerModelVersion).filter_by(is_active=1).order_by(PlanPowerModelVersion.id.desc()).first()

    def _active_model_codes(self, version_id: int) -> list[str]:
        """读取 active 模型支持的版型编码。"""
        return [
            row.normalized_model_code
            for row in self.db.query(PlanPowerModelSheet).filter_by(version_id=version_id).order_by(PlanPowerModelSheet.id.asc()).all()
        ]

    def _get_sheet(self, version_id: int, model_code: str) -> PlanPowerModelSheet | None:
        """读取指定版型模型页。"""
        normalized = self._normalize_model_code(model_code)
        for row in self.db.query(PlanPowerModelSheet).filter_by(version_id=version_id).all():
            if self._normalize_model_code(row.normalized_model_code) == normalized:
                return row
        return None

    def _select_latest_header(self, headers: list[PlanBomHeader]) -> PlanBomHeader:
        """按生效日期、版本号和 ID 选择当前版本。"""
        return sorted(
            headers,
            key=lambda header: (header.effective_date is not None, header.effective_date, header.version_no or "", header.id),
            reverse=True,
        )[0]

    def _filter_headers_by_order_name_hint(self, headers: list[PlanBomHeader], order_name_hint: str) -> list[PlanBomHeader]:
        """按用户原文中的 BOM 名称/客户实例片段过滤候选。

        参数：
            headers: 已由订单号/评审号和版本初筛后的候选。
            order_name_hint: NLU 从原文抽取的 BOM 文件名或客户实例片段。

        返回：
            命中提示片段的候选列表；若无法可靠命中则返回空列表，由调用方保留原候选并继续澄清。
        业务逻辑：同一个评审号可能对应多个客户实例，不能只靠 `GCL-...-00106` 判定；
            但当用户已经给出 `客户名称-年份-尾号` 或完整 BOM 名称时，应优先用该片段消歧。
        """

        normalized_hint = self._normalize_order_name_hint(order_name_hint)
        if not normalized_hint:
            return []
        matched: list[PlanBomHeader] = []
        for header in headers:
            candidate_text = " ".join(
                part
                for part in [header.order_name, header.raw_file_name, header.order_no, header.file_no]
                if part
            )
            if normalized_hint in self._normalize_order_name_hint(candidate_text):
                matched.append(header)
        return matched

    @staticmethod
    def _normalize_order_name_hint(value: str | None) -> str:
        """归一 BOM 名称提示，去除空白、括号差异和常见分隔符以便包含匹配。"""
        text = PlanBomPowerConfigResolverService._stringify(value)
        return re.sub(
            r"[\s，,。；;：:、（）()\[\]【】/_\-]+",
            "",
            text.replace("－", "-").replace("—", "-").replace("–", "-").lower(),
        )

    @staticmethod
    def _group_lines(lines: list[PlanBomMaterialLine]) -> dict[str, list[PlanBomMaterialLine]]:
        """按 material_category 分组材料行。"""
        grouped: dict[str, list[PlanBomMaterialLine]] = {}
        for line in lines:
            grouped.setdefault(line.material_category or "", []).append(line)
        return grouped

    def _text_matches_rule(self, combined_text: str, gap_text: str, rule: Mapping[str, Any]) -> bool:
        """判断玻璃组合规则是否命中。"""
        if any(keyword in combined_text for keyword in rule.get("require_any_not") or []):
            return False
        if rule.get("require_any") and not any(keyword in combined_text for keyword in rule.get("require_any") or []):
            return False
        if rule.get("require_any_secondary") and not any(keyword in combined_text for keyword in rule.get("require_any_secondary") or []):
            return False
        if rule.get("require_gap_any") and not any(keyword in gap_text for keyword in rule.get("require_gap_any") or []):
            return False
        return True

    def _canonical_benchmark(self, value: str) -> str:
        """归一化用户输入或业务口径中的标板基准。"""
        aliases = self.aliases.get("benchmark_aliases") or {}
        return str(aliases.get(value, value))

    def _canonical_option(self, factor_key: str, value: str | None) -> str:
        """按配置文件别名归一化材料 option。"""
        current = self._stringify(value)
        aliases = ((self.aliases.get("option_aliases") or {}).get(factor_key) or {})
        for _ in range(3):
            next_value = str(aliases.get(current, current))
            if next_value == current:
                return current
            current = next_value
        return current

    @staticmethod
    def _normalize_model_code(value: str | None) -> str:
        """归一化版型编码，兼容 `/` 与 `-`。"""
        text = PlanBomPowerConfigResolverService._stringify(value).upper().replace("/", "-").replace(" ", "")
        return text

    @staticmethod
    def _normalize_label(value: str | None) -> str:
        """归一化 option 标签用于精确匹配。"""
        text = PlanBomPowerConfigResolverService._stringify(value)
        return (
            text.replace("（", "(")
            .replace("）", ")")
            .replace("＋", "+")
            .replace("－", "-")
            .replace("²", "2")
            .replace(" ", "")
            .lower()
        )

    @staticmethod
    def _format_number(value: str) -> str:
        """格式化数字字符串，去除无意义尾零。"""
        decimal_value = Decimal(value)
        normalized = decimal_value.normalize()
        text = format(normalized, "f")
        return text.rstrip("0").rstrip(".") if "." in text else text

    @staticmethod
    def _source_line(line: PlanBomMaterialLine) -> PowerBomSourceLine:
        """转换 BOM 材料行为追溯对象。"""
        return PowerBomSourceLine(
            id=line.id,
            material_category=line.material_category,
            material_name=line.material_name,
            description=line.description,
            sap_code=line.sap_code,
            standard_usage=str(line.standard_usage) if line.standard_usage is not None else None,
            raw_row_no=line.raw_row_no,
        )

    @staticmethod
    def _candidate(header: PlanBomHeader) -> PowerBomCandidate:
        """转换候选 BOM 头。"""
        return PowerBomCandidate(
            order_no=header.order_no,
            version_no=header.version_no,
            order_name=header.order_name,
            order_identity_key=header.order_identity_key,
            file_instance_key=header.file_instance_key,
            source_type=header.source_type,
        )

    @staticmethod
    def _line_text(line: PlanBomMaterialLine) -> str:
        """拼接材料名称和规格描述。"""
        return " ".join(part for part in [line.material_name, line.description, line.remark] if part)

    @staticmethod
    def _joined_text(lines: list[PlanBomMaterialLine]) -> str:
        """拼接多行材料文本。"""
        return "\n".join(PlanBomPowerConfigResolverService._line_text(line) for line in lines)

    @staticmethod
    def _source_description(lines: list[PlanBomMaterialLine]) -> str | None:
        """生成可读的原始 BOM 描述摘要。"""
        descriptions = [PlanBomPowerConfigResolverService._line_text(line) for line in lines]
        return " | ".join(descriptions[:6]) if descriptions else None

    @staticmethod
    def _stringify(value: Any) -> str:
        """宽松转换为去首尾空格字符串。"""
        return "" if value is None else str(value).strip()

    @staticmethod
    def _load_json(path: Path) -> dict[str, Any]:
        """读取 JSON 配置。"""
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _load_yaml(path: Path) -> dict[str, Any]:
        """读取 YAML 配置。"""
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


__all__ = [
    "PlanBomPowerConfigResolverService",
    "PowerBomConfigResolution",
    "PowerBomResolvedItem",
    "PowerBomUnresolvedItem",
    "PowerBomSourceLine",
    "PowerBomCandidate",
]
