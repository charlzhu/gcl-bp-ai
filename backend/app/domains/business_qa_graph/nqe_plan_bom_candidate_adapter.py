"""NQE BOM 候选消歧适配器。

NQE-SQL-MAIN-25：非侵入式接入。包装 PlanBomNluCenterService，
输出统一 NqeBomCandidateResult。不修改旧 BOM 生产逻辑。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NqeBomCandidate:
    """NQE 统一 BOM 候选实体。"""
    entity_type: str = ""
    entity_value: str = ""
    display_name: str = ""
    scope: str = ""
    confidence: float = 0.0
    resolved: bool = False
    source: str = "nlu_center"


@dataclass
class NqeBomCandidateResult:
    """NQE BOM 候选消歧统一输出。"""
    domain: str = "plan_bom"
    candidates: list[NqeBomCandidate] = field(default_factory=list)
    disambiguation_required: bool = False
    selected_candidate: NqeBomCandidate | None = None
    candidate_scope: str = ""
    fallback_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "candidates": [
                {"entity_type": c.entity_type, "entity_value": c.entity_value,
                 "display_name": c.display_name, "scope": c.scope,
                 "confidence": c.confidence, "resolved": c.resolved, "source": c.source}
                for c in self.candidates
            ],
            "disambiguation_required": self.disambiguation_required,
            "selected_candidate": (
                {"entity_type": self.selected_candidate.entity_type,
                 "entity_value": self.selected_candidate.entity_value}
                if self.selected_candidate else None
            ),
            "candidate_scope": self.candidate_scope,
            "fallback_reason": self.fallback_reason,
        }


class NqePlanBomCandidateAdapter:
    """NQE BOM 候选消歧适配器。

    只读包装 PlanBomNluCenterService.understand()。不修改旧链路。
    """

    def resolve_candidates(self, question: str, *, trace_id: str = "") -> NqeBomCandidateResult:
        """解析 BOM 候选实体。

        参数：
            question: 用户自然语言问题。
            trace_id: 查询追踪号。
        返回：
            统一 NqeBomCandidateResult。
        """
        result = NqeBomCandidateResult()

        try:
            from backend.app.domains.plan_bom.services.nlu_center_service import (
                PlanBomNluCenterService,
            )

            nlu = PlanBomNluCenterService()
            nlu_candidate = nlu.understand(question, use_llm=False)

            if nlu_candidate is None:
                result.fallback_reason = "nlu_service_no_result"
                return result

            slots = nlu_candidate.slots or {}

            # 订单候选
            order_no = slots.get("order_no") or slots.get("order_candidate")
            if order_no:
                result.candidates.append(NqeBomCandidate(
                    entity_type="order", entity_value=str(order_no),
                    display_name=str(order_no), scope="order_identity",
                    confidence=0.9, resolved=True))

            # BOM 评审号候选
            bom_no = slots.get("bom_no") or slots.get("bom_candidate") or slots.get("review_no")
            if bom_no:
                result.candidates.append(NqeBomCandidate(
                    entity_type="bom_file", entity_value=str(bom_no),
                    display_name=str(bom_no), scope="bom",
                    confidence=0.85, resolved=True))

            # 物料候选
            material = slots.get("material_code") or slots.get("material_name")
            if material:
                result.candidates.append(NqeBomCandidate(
                    entity_type="material", entity_value=str(material),
                    display_name=str(material), scope="material",
                    confidence=0.7, resolved=True))

            # 版本候选
            version = slots.get("version") or slots.get("bom_version")
            if version:
                result.candidates.append(NqeBomCandidate(
                    entity_type="version", entity_value=str(version),
                    display_name=str(version), scope="bom",
                    confidence=0.8, resolved=True))

            # 判断状态
            n = len(result.candidates)
            if n == 0:
                result.fallback_reason = "no_candidate_extracted"
            elif n == 1:
                result.selected_candidate = result.candidates[0]
            else:
                result.disambiguation_required = True
                result.candidate_scope = self._scope(result.candidates)

        except Exception as exc:
            result.fallback_reason = f"nlu_service_error: {exc}"

        return result

    @staticmethod
    def _scope(candidates: list[NqeBomCandidate]) -> str:
        entities = {c.entity_type for c in candidates}
        return "mixed" if len(entities) > 1 else {
            "order": "order_identity", "material": "material",
            "bom_file": "bom", "version": "bom"
        }.get(next(iter(entities)), "unknown")
