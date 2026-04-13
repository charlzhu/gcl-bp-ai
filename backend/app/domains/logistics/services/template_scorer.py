from __future__ import annotations

from typing import Any


class LogisticsTemplateScorer:
    """模板优先级评分器（V6）。

    这一层专门负责“候选模板打分”，不直接负责最终冲突消解。
    这样做的好处：
    1. 评分逻辑和冲突决策逻辑分离；
    2. 后续如果要引入更多因子，不会把 matcher 写得过于臃肿；
    3. 便于单元测试按“输入 -> 分数/原因”做验证。
    """

    def score(
        self,
        question: str,
        parsed: dict[str, Any],
        template: dict[str, Any],
        route_result: dict[str, Any] | None = None,
    ) -> tuple[int, list[str]]:
        """对单个模板打分。

        返回：
        - score: 综合得分
        - reasons: 详细打分原因，便于命中解释
        """
        score = 0
        reasons: list[str] = []

        # 1. 模板基础优先级
        base_priority = int(template.get('priority', 0) or 0)
        if base_priority:
            score += base_priority
            reasons.append(f'模板基础优先级：{base_priority} 分')

        # 2. 业务域加分：如果模板所属域和当前路由域一致，则额外加分。
        selected_domain = (route_result or {}).get('selected_domain')
        template_domain = template.get('domain')
        if selected_domain and template_domain and selected_domain == template_domain:
            score += 25
            reasons.append(f'模板域与路由域一致：{template_domain}，加 25 分')

        # 3. 模式匹配加分
        template_mode = template.get('mode')
        parsed_mode = parsed.get('mode')
        if template_mode and parsed_mode == template_mode:
            score += 30
            reasons.append(f'查询模式命中：{template_mode}，加 30 分')

        # 4. 指标匹配加分
        metric_candidates = template.get('metric_candidates', []) or []
        metric_type = parsed.get('metric_type')
        if metric_type and metric_type in metric_candidates:
            score += 20
            reasons.append(f'指标命中：{metric_type}，加 20 分')

        # 5. 关键词命中加分
        lower_question = question.lower()
        for keyword in template.get('keywords_any', []) or []:
            if keyword and keyword.lower() in lower_question:
                score += 8
                reasons.append(f'关键词命中：{keyword}，加 8 分')

        # 6. 槽位校验。必填槽位不满足则直接淘汰。
        required_slots = template.get('required_slots', []) or []
        for slot in required_slots:
            if self._slot_satisfied(slot, parsed):
                score += 20
                reasons.append(f'必填槽位满足：{slot}，加 20 分')
            else:
                reasons.append(f'必填槽位不满足：{slot}，模板淘汰')
                return -1, reasons

        # 7. 轻量细节加分：如果模板显式要求 group_by 且当前解析已具备同类维度，则加少量分。
        template_group_by = template.get('group_by') or []
        parsed_group_by = parsed.get('group_by') or []
        if template_group_by and parsed_group_by and template_group_by == parsed_group_by:
            score += 6
            reasons.append('分组维度与规则解析结果一致，加 6 分')

        return score, reasons

    @staticmethod
    def _slot_satisfied(slot: str, parsed: dict[str, Any]) -> bool:
        if slot == 'two_periods':
            return bool(parsed.get('left') and parsed.get('right'))
        if slot == 'single_period':
            return bool(parsed.get('year_month_list') or (parsed.get('start_date') and parsed.get('end_date')))
        if slot == 'single_period_or_year':
            return bool(parsed.get('year_month_list') or parsed.get('start_date'))
        if slot == 'business_no':
            return any(parsed.get(key) for key in ('contract_no', 'inquiry_no', 'ship_instruction_no', 'sap_order_no', 'vehicle_no', 'task_id'))
        return False
