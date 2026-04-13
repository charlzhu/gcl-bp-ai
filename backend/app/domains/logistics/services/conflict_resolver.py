from __future__ import annotations

from typing import Any


class LogisticsTemplateConflictResolver:
    """模板冲突消解器（V6）。

    作用：
    1. 当多个模板同时命中时，明确选择谁；
    2. 对“为什么选中 A 而不是 B”给出解释；
    3. 把冲突类型结构化返回，方便前端展示与调试。
    """

    def resolve(self, candidates: list[dict[str, Any]]) -> dict[str, Any] | None:
        if not candidates:
            return None

        # 先按得分，再按模板 priority 排序。
        ordered = sorted(
            candidates,
            key=lambda item: (
                item.get('score', 0),
                int((item.get('template') or {}).get('priority', 0) or 0),
            ),
            reverse=True,
        )

        selected = ordered[0]
        discarded = ordered[1:]
        conflict_type = 'single_hit'
        explanation = '仅命中一个可用模板，直接采用。'

        if len(ordered) > 1:
            top_score = ordered[0].get('score', 0)
            second_score = ordered[1].get('score', 0)
            if top_score == second_score:
                conflict_type = 'same_score_priority_win'
                explanation = '多个模板得分相同，按模板优先级和排序规则选择当前模板。'
            elif top_score - second_score <= 10:
                conflict_type = 'close_score_best_effort'
                explanation = '多个模板得分接近，按综合得分最高原则选择当前模板。'
            else:
                conflict_type = 'high_score_win'
                explanation = '存在多个候选模板，但当前模板综合得分明显更高。'

        return {
            'selected': selected,
            'discarded': [
                {
                    'template_id': (item.get('template') or {}).get('id'),
                    'template_name': (item.get('template') or {}).get('name'),
                    'template_domain': (item.get('template') or {}).get('domain'),
                    'score': item.get('score', 0),
                    'reasons': item.get('reasons', []),
                }
                for item in discarded[:5]
            ],
            'conflict_type': conflict_type,
            'explanation': explanation,
        }
