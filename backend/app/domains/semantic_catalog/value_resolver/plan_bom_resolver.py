"""
计划 BOM 域实体值解析器（PlanBomValueResolver）。

业务逻辑：
    本解析器负责计划 BOM 域的实体值解析，支持以下实体类型：
    - order_identity: 订单 identity 解析（按订单号/订单名模糊匹配）
    - filename: 文件名解析（按 raw_file_name 模糊匹配）
    - customer_instance: 客户实例解析（从订单名中提取客户名）
    - version: 版本号解析（按 version_no 精确匹配）

    设计原则：
        1. 复用现有 PlanBomQueryRepository 的 MySQL 查询模式。
        2. 仅查询 is_active=1 的有效记录。
        3. 误匹配时返回多候选，不做硬路由。
        4. entity_type 未知时返回空列表，不抛异常。
        5. 不依赖 Milvus（向量检索为可选增强，当前以 keyword 为主）。
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.app.domains.semantic_catalog.value_resolver.base import BusinessValueResolver


class PlanBomValueResolver(BusinessValueResolver):
    """计划 BOM 域业务值解析器。

    业务逻辑：
        复用 PlanBomQueryRepository 查询 is_active 记录，
        支持按订单号、订单名、文件名、版本号做实体值解析。

    参数：
        db: SQLAlchemy Session，用于查询中间库。
        repo: 可选注入的 PlanBomQueryRepository 实例（测试用）。
    """

    domain = "plan_bom"

    def __init__(self, db: Session, repo: Any = None) -> None:
        """初始化计划 BOM 域解析器。

        参数：
            db: SQLAlchemy Session 实例。
            repo: 可选预构造的 PlanBomQueryRepository（测试注入用）。
        """
        super().__init__()
        self.db = db
        self._repo = repo
        self._headers_cache: list[Any] | None = None

    def _get_repo(self) -> Any:
        """延迟获取 PlanBomQueryRepository 实例。

        返回：
            PlanBomQueryRepository 实例。

        业务逻辑：
            支持测试注入 repo，避免测试需要真实 DB。
        """
        if self._repo is not None:
            return self._repo
        from backend.app.domains.plan_bom.repositories.query_repository import (
            PlanBomQueryRepository,
        )
        self._repo = PlanBomQueryRepository(self.db)
        return self._repo

    # 缓存加载的默认上限，首次加载时使用该值避免缓存过小导致漏匹配
    _DEFAULT_CACHE_LIMIT: int = 500

    def _load_headers(self, limit: int = 500) -> list[Any]:
        """加载有效 BOM 头记录（带缓存，DB 异常安全降级）。

        参数：
            limit: 最大返回数量。

        返回：
            PlanBomHeader 对象列表。

        业务逻辑：
            1. 首次加载时使用 self._DEFAULT_CACHE_LIMIT 作为缓存上限，
               避免先以较小 limit 初始化缓存导致后续查询漏匹配。
            2. 若请求的 limit 大于已缓存的数据量，自动重新加载更大数据集。
            3. DB 异常时缓存空列表并降级，不向调用方传播异常。
        """
        cache_limit = max(limit, self._DEFAULT_CACHE_LIMIT)
        if self._headers_cache is not None:
            if len(self._headers_cache) >= limit:
                return self._headers_cache[:limit]
            # 已缓存数据量不足，需要重新加载
            cache_limit = max(limit, len(self._headers_cache) * 2, self._DEFAULT_CACHE_LIMIT)

        try:
            repo = self._get_repo()
            self._headers_cache = repo.list_all_active_headers(limit=cache_limit)
        except Exception:
            # DB 连接失败或表不存在时缓存空列表，不阻断调用方
            if self._headers_cache is None:
                self._headers_cache = []
        return self._headers_cache[:limit]

    # ── resolve：按用户输入解析实体值 ──

    def resolve(self, entity_type: str, user_input: str) -> list[dict]:
        """按用户输入解析计划 BOM 域实体值候选。

        参数：
            entity_type: 实体类型（order_identity、filename、customer_instance、version）。
            user_input: 用户输入的实体值或关键词。

        返回：
            候选实体值列表。无匹配时返回空列表。
        """
        if entity_type == "order_identity":
            return self._resolve_order_identity(user_input)
        if entity_type == "filename":
            return self._resolve_filename(user_input)
        if entity_type == "customer_instance":
            return self._resolve_customer_instance(user_input)
        if entity_type == "version":
            return self._resolve_version(user_input)
        return []

    # ── candidates：获取候选值列表 ──

    def candidates(self, entity_type: str, limit: int = 20) -> list[dict]:
        """获取计划 BOM 域某实体类型下的候选值列表。

        参数：
            entity_type: 实体类型。
            limit: 最大返回数量。

        返回：
            候选值列表。
        """
        if entity_type == "order_identity":
            return self._candidates_order_identity(limit)
        if entity_type == "filename":
            return self._candidates_filename(limit)
        if entity_type == "customer_instance":
            return self._candidates_customer_instance(limit)
        if entity_type == "version":
            return self._candidates_version(limit)
        return []

    # ── 具体实体解析方法 ──

    def _resolve_order_identity(self, user_input: str) -> list[dict]:
        """按订单号或订单名解析订单 identity。

        参数：
            user_input: 用户输入的订单号或订单名片段。

        返回：
            匹配的订单候选列表，每项包含 order_no 和 order_name。
        """
        if not user_input or not user_input.strip():
            return []

        normalized = user_input.strip().lower()
        headers = self._load_headers()

        # 精确匹配订单号
        exact_order: list[dict] = []
        for h in headers:
            if normalized == (h.order_no or "").strip().lower():
                exact_order.append(self._header_to_dict("order_identity", h))
        if exact_order:
            return exact_order

        # 模糊匹配订单号或订单名
        fuzzy: list[dict] = []
        for h in headers:
            order_no = (h.order_no or "").strip().lower()
            order_name = (h.order_name or "").strip().lower()
            if normalized in order_no or normalized in order_name:
                fuzzy.append(self._header_to_dict("order_identity", h))
        return fuzzy

    def _resolve_filename(self, user_input: str) -> list[dict]:
        """按文件名解析。

        参数：
            user_input: 用户输入的文件名或片段。

        返回：
            匹配的文件名候选列表。
        """
        if not user_input or not user_input.strip():
            return []

        normalized = user_input.strip().lower()
        headers = self._load_headers()

        fuzzy: list[dict] = []
        for h in headers:
            raw_name = (h.raw_file_name or "").strip().lower()
            if normalized in raw_name:
                fuzzy.append(self._header_to_dict("filename", h))
        return fuzzy

    def _resolve_customer_instance(self, user_input: str) -> list[dict]:
        """按客户名解析客户实例。

        参数：
            user_input: 用户输入的客户名或片段。

        返回：
            匹配的客户实例候选列表。

        业务逻辑：
            从订单名称中提取客户名进行匹配（如"华为2025年光伏项目"→"华为"）。
            多个订单可能属于同一客户，不做去重，让上游决定消歧。
        """
        if not user_input or not user_input.strip():
            return []

        normalized = user_input.strip().lower()
        headers = self._load_headers()

        fuzzy: list[dict] = []
        for h in headers:
            order_name = (h.order_name or "").strip().lower()
            if normalized in order_name:
                fuzzy.append(self._header_to_dict("customer_instance", h))
        return fuzzy

    def _resolve_version(self, user_input: str) -> list[dict]:
        """按版本号解析。

        参数：
            user_input: 用户输入的版本号（如 A0、A1、B0）。

        返回：
            匹配的版本候选列表。
        """
        if not user_input or not user_input.strip():
            return []

        normalized = user_input.strip()
        headers = self._load_headers()

        exact: list[dict] = []
        for h in headers:
            version = (h.version_no or "").strip()
            if normalized == version:
                exact.append(self._header_to_dict("version", h))
        return exact

    # ── candidates 具体方法 ──

    def _candidates_order_identity(self, limit: int) -> list[dict]:
        """订单 identity 候选列表。"""
        headers = self._load_headers(limit)
        return [self._header_to_dict("order_identity", h) for h in headers]

    def _candidates_filename(self, limit: int) -> list[dict]:
        """文件名候选列表。"""
        headers = self._load_headers(limit)
        result: list[dict] = []
        for h in headers:
            if h.raw_file_name:
                result.append(self._header_to_dict("filename", h))
        return result[:limit]

    def _candidates_customer_instance(self, limit: int) -> list[dict]:
        """客户实例候选列表（按唯一客户名去重）。

        业务逻辑：
            从订单名中提取已知客户名。多个同一客户的订单只保留一个代表。
        """
        headers = self._load_headers(limit * 2)  # 多取一些以便去重后仍有足够数量
        seen: set[str] = set()
        result: list[dict] = []
        for h in headers:
            order_name = (h.order_name or "").strip()
            if not order_name:
                continue
            # 提取客户名（取订单名中第一个非数字/非年份词作为客户名简写）
            customer_label = self._extract_customer_label(order_name)
            if customer_label and customer_label not in seen:
                seen.add(customer_label)
                result.append({
                    "entity_type": "customer_instance",
                    "value": customer_label,
                    "label": f"{customer_label}（{order_name}）",
                })
            if len(result) >= limit:
                break
        return result

    def _candidates_version(self, limit: int) -> list[dict]:
        """版本号候选列表。"""
        headers = self._load_headers(limit * 3)  # 多取以覆盖多个版本
        seen: set[str] = set()
        result: list[dict] = []
        for h in headers:
            version = (h.version_no or "").strip()
            if version and version not in seen:
                seen.add(version)
                result.append({
                    "entity_type": "version",
                    "value": version,
                    "label": f"版本 {version}",
                })
            if len(result) >= limit:
                break
        return result

    # ── 辅助方法 ──

    @staticmethod
    def _header_to_dict(entity_type: str, header: Any) -> dict:
        """将 PlanBomHeader 对象转为标准 dict 格式。

        参数：
            entity_type: 实体类型。
            header: PlanBomHeader 对象或 mock。

        返回：
            包含 entity_type、value、label 的标准 dict。
        """
        order_no = (header.order_no or "").strip()
        order_name = (header.order_name or "").strip()
        version_no = (header.version_no or "").strip()
        raw_file_name = (header.raw_file_name or "").strip()

        if entity_type == "order_identity":
            return {
                "entity_type": entity_type,
                "value": order_no,
                "label": f"{order_no} {order_name}".strip(),
            }
        if entity_type == "filename":
            return {
                "entity_type": entity_type,
                "value": raw_file_name,
                "label": raw_file_name or order_no,
            }
        if entity_type == "customer_instance":
            return {
                "entity_type": entity_type,
                "value": order_name,
                "label": order_name or order_no,
            }
        if entity_type == "version":
            return {
                "entity_type": entity_type,
                "value": version_no,
                "label": f"{order_no} (v{version_no})",
            }
        return {
            "entity_type": entity_type,
            "value": order_no,
            "label": order_no,
        }

    @staticmethod
    def _extract_customer_label(order_name: str) -> str:
        """从订单名中提取客户标签。

        参数：
            order_name: 订单名称（如"华为2025年光伏项目"）。

        返回：
            客户标签（如"华为"）。

        业务逻辑：
            简单启发式：取订单名中第一个中文公司名片段。
            实际生产应由上游 NLU 提取后传入，这里仅做兜底。
        """
        if not order_name:
            return ""
        # 简单策略：取前几个中文字符作为客户标签
        # 更精确的提取应在 NLU 层完成
        import re
        # 尝试匹配"公司名+年份"模式
        match = re.match(r"^([^\d]+?)\d{4}", order_name)
        if match:
            return match.group(1).strip()
        # fallback：返回订单名前 6 个字符
        return order_name[:6].strip()


__all__ = ["PlanBomValueResolver"]
