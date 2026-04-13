from __future__ import annotations

from typing import Any

from backend.app.domains.logistics.services.template_scorer import LogisticsTemplateScorer
from backend.app.domains.logistics.services.conflict_resolver import LogisticsTemplateConflictResolver


class LogisticsTemplateMatcher:
    """物流模板匹配器（V6）。

    V6 相比 V5 的升级点：
    1. 把“打分”抽到独立评分器；
    2. 把“冲突消解”抽到独立决策器；
    3. 让返回结构明确包含：候选、选中、放弃原因、冲突类型。
    """

    def __init__(
        self,
        scorer: LogisticsTemplateScorer | None = None,
        resolver: LogisticsTemplateConflictResolver | None = None,
    ) -> None:
        self.scorer = scorer or LogisticsTemplateScorer()
        self.resolver = resolver or LogisticsTemplateConflictResolver()

    def match(
        self,
        question: str,
        parsed: dict[str, Any],
        templates: list[dict[str, Any]],
        route_result: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        """执行模板匹配。

        返回结构示例：
        {
          "template": {...},
          "score": 97,
          "reasons": [...],
          "candidates": [...],
          "discarded_candidates": [...],
          "conflict_type": "high_score_win",
          "conflict_explanation": "..."
        }
        """
        candidates: list[dict[str, Any]] = []
        for template in templates:
            score, reasons = self.scorer.score(question, parsed, template, route_result=route_result)
            if score > 0:
                candidates.append({
                    'template': template,
                    'score': score,
                    'reasons': reasons,
                })

        if not candidates:
            return None

        resolution = self.resolver.resolve(candidates)
        if not resolution:
            return None

        selected = resolution['selected']
        # 对外仍保留“候选摘要”，方便上层统一展示。
        candidates_summary = [
            {
                'template_id': (item.get('template') or {}).get('id'),
                'template_name': (item.get('template') or {}).get('name'),
                'template_domain': (item.get('template') or {}).get('domain'),
                'score': item.get('score', 0),
                'reasons': item.get('reasons', []),
            }
            for item in sorted(candidates, key=lambda x: x.get('score', 0), reverse=True)[:5]
        ]

        return {
            'template': selected['template'],
            'score': selected['score'],
            'reasons': selected['reasons'],
            'candidates': candidates_summary,
            'discarded_candidates': resolution.get('discarded', []),
            'conflict_type': resolution.get('conflict_type'),
            'conflict_explanation': resolution.get('explanation'),
        }
