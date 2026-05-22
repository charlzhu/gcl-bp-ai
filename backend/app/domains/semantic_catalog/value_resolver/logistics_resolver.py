"""
物流域实体值解析器（LogisticsValueResolver）。

业务逻辑：
    本解析器负责物流域的实体值解析，支持以下实体类型：
    - carrier: 承运商名称解析（从历史明细表读取 distinct 值做模糊匹配）
    - customer: 客户/委托人名称解析
    - region: 行政区域解析（标准七大区域 + 省份）
    - route: 物流线路解析（始发地-目的地组合）
    - address: 收货地址解析

    设计原则：
        1. 复用现有 LogisticsDataQaRepository 的 MySQL 查询模式。
        2. 误匹配时返回多候选，不做硬路由。
        3. entity_type 未知时返回空列表，不抛异常。
        4. 不依赖 Milvus（向量检索为可选增强，当前以 MySQL 为主）。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.app.domains.semantic_catalog.value_resolver.base import BusinessValueResolver


# 标准行政区划（七大区域），供 region 实体使用
STANDARD_REGIONS: list[str] = [
    "华东",
    "华南",
    "华中",
    "华北",
    "西南",
    "西北",
    "东北",
]

# 标准省份列表，供 region 实体使用
STANDARD_PROVINCES: list[str] = [
    "上海市", "江苏省", "浙江省", "安徽省", "福建省", "江西省", "山东省",
    "广东省", "广西壮族自治区", "海南省",
    "河南省", "湖北省", "湖南省",
    "北京市", "天津市", "河北省", "山西省", "内蒙古自治区",
    "重庆市", "四川省", "贵州省", "云南省", "西藏自治区",
    "陕西省", "甘肃省", "青海省", "宁夏回族自治区", "新疆维吾尔自治区",
    "辽宁省", "吉林省", "黑龙江省",
]


class LogisticsValueResolver(BusinessValueResolver):
    """物流域业务值解析器。

    业务逻辑：
        从 MySQL 中间库读取承运商、客户等实体值，
        支持模糊匹配和多候选返回。当前以 keyword 匹配为主，
        后续可接入 Milvus 向量检索增强。

    参数：
        db: SQLAlchemy Session，用于查询中间库。
    """

    domain = "logistics"

    def __init__(self, db: Session) -> None:
        """初始化物流域解析器。

        参数：
            db: SQLAlchemy Session 实例。
        """
        super().__init__()
        self.db = db
        # 延迟加载缓存：首次调用时从 DB 拉取并缓存
        self._carrier_cache: list[str] | None = None
        self._customer_cache: list[str] | None = None

    # ── resolve：按用户输入解析实体值 ──

    def resolve(self, entity_type: str, user_input: str) -> list[dict]:
        """按用户输入解析物流域实体值候选。

        参数：
            entity_type: 实体类型（carrier、customer、region、route、address）。
            user_input: 用户输入的实体名称或关键词。

        返回：
            候选实体值列表。无匹配时返回空列表。
        """
        if entity_type == "carrier":
            return self._fuzzy_match(self._load_carriers(), entity_type, user_input)
        if entity_type == "customer":
            return self._fuzzy_match(self._load_customers(), entity_type, user_input)
        if entity_type == "region":
            return self._resolve_region(user_input)
        if entity_type in ("route", "address"):
            # 线路和地址暂不实现模糊匹配，只返回 candidates
            return self._fuzzy_match([], entity_type, user_input)
        return []

    # ── candidates：获取候选值列表 ──

    def candidates(self, entity_type: str, limit: int = 20) -> list[dict]:
        """获取物流域某实体类型下的候选值列表。

        参数：
            entity_type: 实体类型。
            limit: 最大返回数量。

        返回：
            候选值列表。
        """
        if entity_type == "carrier":
            names = self._load_carriers()[:limit]
            return self._names_to_dicts(entity_type, names)
        if entity_type == "customer":
            names = self._load_customers()[:limit]
            return self._names_to_dicts(entity_type, names)
        if entity_type == "region":
            all_regions = STANDARD_REGIONS + STANDARD_PROVINCES
            return self._names_to_dicts(entity_type, all_regions[:limit])
        if entity_type in ("route", "address"):
            # 线路和地址动态量大，不返回全量候选
            return []
        return []

    # ── 内部方法 ──

    def _load_carriers(self) -> list[str]:
        """从 DB 加载承运商名称列表（带缓存）。

        返回：
            去重后的承运商名称列表。
        """
        if self._carrier_cache is not None:
            return self._carrier_cache

        # 复用与 LogisticsDataQaRepository 相同的查询模式：
        # 从 dwd_logistics_hist_shipment_detail 表读取 distinct 承运商名称
        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT DISTINCT TRIM(logistics_company_name) AS carrier_name
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE logistics_company_name IS NOT NULL
                      AND TRIM(logistics_company_name) <> ''
                    ORDER BY carrier_name ASC
                    LIMIT 2000
                    """
                )
            ).mappings().all()
            self._carrier_cache = [str(row["carrier_name"]) for row in rows if row.get("carrier_name")]
        except Exception:
            # 表不存在或连接不可用时返回空列表，不阻断调用方
            self._carrier_cache = []
        return self._carrier_cache

    def _load_customers(self) -> list[str]:
        """从 DB 加载客户/委托人名称列表（带缓存）。

        返回：
            去重后的客户名称列表。
        """
        if self._customer_cache is not None:
            return self._customer_cache

        try:
            rows = self.db.execute(
                text(
                    """
                    SELECT DISTINCT TRIM(customer_name) AS customer_name
                    FROM dwd_logistics_hist_shipment_detail
                    WHERE customer_name IS NOT NULL
                      AND TRIM(customer_name) <> ''
                    ORDER BY customer_name ASC
                    LIMIT 2000
                    """
                )
            ).mappings().all()
            self._customer_cache = [str(row["customer_name"]) for row in rows if row.get("customer_name")]
        except Exception:
            self._customer_cache = []
        return self._customer_cache

    @staticmethod
    def _fuzzy_match(candidates: list[str], entity_type: str, user_input: str) -> list[dict]:
        """在候选列表中对用户输入做模糊匹配。

        参数：
            candidates: 候选实体值列表。
            entity_type: 实体类型。
            user_input: 用户输入的关键词。

        返回：
            匹配的候选列表。精确匹配置信度最高排最前。

        业务逻辑：
            1. 先尝试精确匹配（case-insensitive）。
            2. 精确匹配未命中时做包含匹配。
            3. 返回所有匹配项，让上游决定消歧策略。
        """
        if not user_input or not user_input.strip():
            return []

        normalized = user_input.strip().lower()

        # 精确匹配
        exact: list[str] = [c for c in candidates if c.strip().lower() == normalized]
        if exact:
            return [{"entity_type": entity_type, "value": c, "label": c} for c in exact]

        # 模糊包含匹配
        fuzzy: list[str] = [c for c in candidates if normalized in c.strip().lower()]
        return [{"entity_type": entity_type, "value": c, "label": c} for c in fuzzy]

    @staticmethod
    def _resolve_region(user_input: str) -> list[dict]:
        """区域实体值解析。

        参数：
            user_input: 用户输入的区域名称。

        返回：
            匹配的区域候选列表。

        业务逻辑：
            支持标准七大区域名和省份名匹配，
            "市"/"省" 后缀可容忍。
        """
        entity_type = "region"
        normalized = user_input.strip()
        if not normalized:
            return []

        # 去掉 "市"/"省" 后缀做宽松匹配
        bare = normalized.rstrip("市省")

        # 精确匹配标准区域名
        for region in STANDARD_REGIONS + STANDARD_PROVINCES:
            if region == normalized or region == bare:
                return [{"entity_type": entity_type, "value": region, "label": region}]

        # 包含匹配
        matches: list[str] = []
        all_candidates = STANDARD_REGIONS + STANDARD_PROVINCES
        for candidate in all_candidates:
            if bare in candidate or candidate in bare:
                matches.append(candidate)

        return [{"entity_type": entity_type, "value": m, "label": m} for m in matches]

    @staticmethod
    def _names_to_dicts(entity_type: str, names: list[str]) -> list[dict]:
        """将名称列表转为标准 dict 格式。

        参数：
            entity_type: 实体类型。
            names: 名称列表。

        返回：
            标准格式的候选列表。
        """
        return [{"entity_type": entity_type, "value": n, "label": n} for n in names]


__all__ = ["LogisticsValueResolver"]
