from __future__ import annotations

from copy import deepcopy
from typing import Any


class LogisticsQueryPlanner:
    """物流查询计划器（V6）。

    V6 重点增强：
    1. 把配置版本快照信息挂到最终解析结果；
    2. 增加模板冲突消解解释；
    3. 增加“被放弃的候选模板”信息，便于排查为什么没命中另一个模板。
    """

    def apply_template(
        self,
        parsed: dict[str, Any],
        matched: dict[str, Any] | None,
        route_result: dict[str, Any] | None = None,
        config_version: str | None = None,
        config_version_detail: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = deepcopy(parsed)

        # 先挂域路由信息。即使模板没命中，也要保留路由结论与原因。
        if route_result:
            result['selected_domain'] = route_result.get('selected_domain')
            result['domain_candidates'] = route_result.get('candidate_domains', [])
            result['domain_route_reason'] = route_result.get('reason')

        if config_version:
            result['config_version'] = config_version
        if config_version_detail:
            result['config_version_detail'] = config_version_detail

        if not matched:
            result['template_hit'] = False
            result['template_candidates'] = []
            result['discarded_template_candidates'] = []
            result['template_conflict_type'] = 'no_template_hit'
            result['template_conflict_explanation'] = '未命中任何模板，继续使用规则解析结果。'
            result['template_match_explanation'] = '未命中任何模板，继续使用规则解析结果。'
            return result

        template = matched['template']
        result['template_hit'] = True
        result['template_id'] = template.get('id')
        result['template_name'] = template.get('name')
        result['template_domain'] = template.get('domain')
        result['template_score'] = matched.get('score', 0)
        result['template_match_reasons'] = matched.get('reasons', [])
        result['template_candidates'] = matched.get('candidates', [])
        result['discarded_template_candidates'] = matched.get('discarded_candidates', [])
        result['template_conflict_type'] = matched.get('conflict_type')
        result['template_conflict_explanation'] = matched.get('conflict_explanation')
        result['template_match_explanation'] = '已命中模板，并按模板规则修正查询计划。'

        # V7：把模板绑定的 SQL 模板标识带入最终查询计划。
        # 当前只做绑定和解释，不直接在这里执行 SQL。
        if template.get('sql_template_id'):
            result['sql_template_id'] = template.get('sql_template_id')

        if template.get('mode'):
            result['mode'] = template['mode']
        if template.get('group_by'):
            current_group_by = result.get('group_by')
            template_group_by = template['group_by']
            # 模板只负责把“默认月份聚合”升级成更具体的维度。
            if not current_group_by or current_group_by == ['biz_month'] or current_group_by == template_group_by:
                result['group_by'] = template_group_by
        if template.get('order_by') == 'metric':
            result['order_by'] = result.get('metric_type')
        elif template.get('order_by'):
            result['order_by'] = template['order_by']
        if template.get('order_direction'):
            result['order_direction'] = template['order_direction']
        if template.get('limit'):
            result['limit'] = template['limit']
        if 'compare_dim' in template:
            result['compare_dim'] = template.get('compare_dim')
        return result
