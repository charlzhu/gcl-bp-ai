from __future__ import annotations

from typing import Any

from backend.app.domains.logistics.services.nl2sql.semantic_catalog import (
    LogisticsSemanticCatalog,
    LogisticsSemanticCatalogLoader,
)
from backend.app.domains.logistics.services.nl2sql.sql_plan import DEFAULT_LOGISTICS_YEARS

# 安全默认值
_DEFAULT_LIMIT = 100
_CATALOG_VERSION = "logistics_nl2sql_catalog.v1"


class LogisticsSqlPlanRepairResult:
    """SQLPlan Repair 的确定性返回。

    参数：
        repaired: 是否产生了修复。
        modifications: 修复操作列表，每个操作为 dict。
        patch: 修复后的完整 SQLPlan candidate（仅含修改字段）。
    """

    def __init__(
        self,
        *,
        repaired: bool,
        modifications: list[dict[str, Any]] | None = None,
        patch: dict[str, Any] | None = None,
    ) -> None:
        self.repaired = repaired
        self.modifications = list(modifications or [])
        self.patch = dict(patch or {})


def repair_logistics_sql_plan(
    candidate_payload: dict[str, Any],
    catalog: LogisticsSemanticCatalog | None = None,
) -> LogisticsSqlPlanRepairResult:
    """修复 SQLPlan candidate 中可证明安全的结构问题。

    修复范围（只修不删、只修可证明安全的问题）：
        1. 补充缺失的 default_time_range 业务规则
        2. 补充缺失的 explicit_year_buckets
        3. 补充缺失的 catalog_refs
        4. 补充 plan.dimensions 中缺失的 group_by/order_by 引用维度
        5. 补充缺失的 limit（安全默认值）

    参数：
        candidate_payload: 原始 SQLPlan candidate dict。
        catalog: canonical Semantic Catalog；缺省加载物流目录。
    返回：
        repaired=True 时附带 patch（仅含需修改的字段）。
    """
    resolved_catalog = catalog or LogisticsSemanticCatalogLoader().load()

    modifications: list[dict[str, Any]] = []
    patch: dict[str, Any] = {}
    _patch_plan(patch, "plan", {})

    raw_candidate = dict(candidate_payload)
    raw_plan = dict(raw_candidate.get("plan", {}))
    raw_refs = list(raw_candidate.get("catalog_refs", []))
    existing_ref_ids = {ref["catalog_id"] for ref in raw_refs if isinstance(ref, dict)}

    # ── 1. 补充缺失的业务规则 ──────────────────────────

    business_rules = list(raw_plan.get("business_rules", []))
    if "default_time_range" not in business_rules:
        # 只在有年份过滤条件且年份为默认年份范围时补充
        # 如果用户显式指定了非默认年份（如 `2023-2025`），不应该添加 default_time_range
        year_values = _extract_year_filter_values(raw_plan.get("filters", []))
        if year_values and sorted(year_values) == sorted(DEFAULT_LOGISTICS_YEARS):
            business_rules.append("default_time_range")
            _patch_plan(patch, "plan.business_rules", business_rules)
            modifications.append({
                "type": "add_business_rule",
                "value": "default_time_range",
                "reason": "年份过滤值与默认年份匹配但缺少 default_time_range 规则",
            })

    # ── 2. 补充缺失的 explicit_year_buckets ────────────

    year_values = _extract_year_filter_values(raw_plan.get("filters", []))
    existing_buckets = list(raw_plan.get("explicit_year_buckets", []))
    if year_values and not existing_buckets:
        _patch_plan(patch, "plan.explicit_year_buckets", sorted(year_values))
        modifications.append({
            "type": "add_explicit_year_buckets",
            "value": sorted(year_values),
            "reason": f"年份过滤值存在但缺少 explicit_year_buckets={sorted(year_values)}",
        })
    elif year_values and existing_buckets and sorted(existing_buckets) != sorted(year_values):
        _patch_plan(patch, "plan.explicit_year_buckets", sorted(year_values))
        modifications.append({
            "type": "fix_explicit_year_buckets",
            "value": sorted(year_values),
            "reason": f"explicit_year_buckets 与年份过滤值不一致",
        })

    # ── 3. 补充缺失的 catalog_refs ─────────────────────

    needed_refs: dict[str, str] = {}
    # 从业务规则推断需要的 ref
    for rule_id in business_rules:
        needed_refs[f"rule:{rule_id}"] = _CATALOG_VERSION
    # 从表推断
    for table_name in raw_plan.get("tables", []):
        needed_refs[f"table:{table_name}"] = _CATALOG_VERSION
    # 从指标推断
    for metric_id in raw_plan.get("metrics", []):
        needed_refs[f"metric:{metric_id}"] = _CATALOG_VERSION
    # 从维度推断（dimensions + group_by）
    all_dimensions = set(raw_plan.get("dimensions", [])) | set(raw_plan.get("group_by", []))
    for dim_id in all_dimensions:
        needed_refs[f"dimension:{dim_id}"] = _CATALOG_VERSION
    # 从 order_by 推断
    for order_item in raw_plan.get("order_by", []):
        if "metric" in order_item and order_item["metric"]:
            needed_refs[f"metric:{order_item['metric']}"] = _CATALOG_VERSION
        if "dimension" in order_item and order_item["dimension"]:
            needed_refs[f"dimension:{order_item['dimension']}"] = _CATALOG_VERSION

    added_refs = False
    for catalog_id, version in needed_refs.items():
        if catalog_id not in existing_ref_ids:
            if "catalog_refs" not in patch:
                patch["catalog_refs"] = list(raw_refs)
            patch["catalog_refs"].append({"catalog_id": catalog_id, "catalog_version": version})
            modifications.append({
                "type": "add_catalog_ref",
                "value": catalog_id,
                "reason": f"plan 引用了 {catalog_id} 但缺少对应的 catalog_ref",
            })
            added_refs = True

    # ── 4. 补充缺失的 plan 维度引用 ────────────────────

    plan_dimensions = set(raw_plan.get("dimensions", []))
    group_by = set(raw_plan.get("group_by", []))
    dimensions_to_add: set[str] = set()

    # 从 group_by 引用补入 dimensions
    for dim_id in group_by:
        if dim_id not in plan_dimensions:
            dimensions_to_add.add(dim_id)

    # 从 order_by.dimension 引用补入
    for order_item in raw_plan.get("order_by", []):
        dim = order_item.get("dimension")
        if dim and dim not in plan_dimensions and dim not in dimensions_to_add:
            dimensions_to_add.add(dim)

    if dimensions_to_add:
        new_dimensions = sorted(plan_dimensions | dimensions_to_add)
        _patch_plan(patch, "plan.dimensions", new_dimensions)
        for dim_id in sorted(dimensions_to_add):
            modifications.append({
                "type": "add_dimension",
                "value": dim_id,
                "reason": f"group_by/order_by 引用了维度 {dim_id} 但未在 plan.dimensions 中声明",
            })

    # ── 5. 补充缺失的 limit ────────────────────────────

    query_type = raw_plan.get("query_type", "aggregate")
    current_limit = raw_plan.get("limit")
    if query_type in ("detail", "ranking") and current_limit is None:
        _patch_plan(patch, "plan.limit", _DEFAULT_LIMIT)
        modifications.append({
            "type": "add_limit",
            "value": _DEFAULT_LIMIT,
            "reason": f"{query_type} 类型缺少 limit，使用安全默认值 {_DEFAULT_LIMIT}",
        })

    # ── 结果 ────────────────────────────────────────────

    if not modifications:
        return LogisticsSqlPlanRepairResult(repaired=False, modifications=[], patch={})

    return LogisticsSqlPlanRepairResult(
        repaired=True,
        modifications=modifications,
        patch=dict(patch),
    )


def _patch_plan(patch: dict[str, Any], dotted_path: str, value: Any) -> None:
    """在 patch dict 中设置嵌套值。"""
    keys = dotted_path.split(".")
    current = patch
    for key in keys[:-1]:
        if key not in current:
            current[key] = {}
        current = current[key]
    # 确保 plan 是嵌套 dict
    current[keys[-1]] = value


def _extract_year_filter_values(filters: list[dict[str, Any]]) -> list[int]:
    """从过滤器列表中提取年份值。"""
    years: list[int] = []
    for item in filters:
        if item.get("dimension") != "biz_year":
            continue
        for value in item.get("values", []):
            try:
                parsed = int(value)
                if parsed > 1900 and parsed < 2100:
                    years.append(parsed)
            except (ValueError, TypeError):
                continue
    return sorted(set(years))


__all__ = ["LogisticsSqlPlanRepairResult", "repair_logistics_sql_plan"]
