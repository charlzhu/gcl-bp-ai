from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


class LogisticsDomainRouter:
    """业务域路由器（V5）。

    作用：
    1. 根据用户问题判断更可能落在哪个业务域；
    2. 为模板匹配阶段提供“候选域优先级”；
    3. 给最终返回增加“命中解释”，便于排查为什么走到这个域。

    说明：
    当前真正可执行的域仍然只有 logistics。
    但 V5 先把多域识别框架搭起来，为后续 plan_bom / business_analysis / material_management 预留能力。
    """

    def __init__(self, config_path: str | None = None) -> None:
        default_path = Path(__file__).resolve().parent.parent / 'config' / 'global' / 'domain_keywords.yaml'
        self.config_path = Path(config_path) if config_path else default_path

    def _load_keywords(self) -> dict[str, list[str]]:
        if not self.config_path.exists():
            return {}
        data = yaml.safe_load(self.config_path.read_text(encoding='utf-8')) or {}
        return data.get('domains', {}) or {}

    def route(self, question: str, normalized_question: str, parsed: dict[str, Any]) -> dict[str, Any]:
        """返回域路由结果。

        返回结构示例：
        {
          "selected_domain": "logistics",
          "candidate_domains": [{"domain": "logistics", "score": 25, "hit_keywords": [...]}, ...],
          "reason": "命中关键词 + 默认回退"
        }
        """
        keywords_map = self._load_keywords()
        candidates: list[dict[str, Any]] = []
        text = f"{question} {normalized_question}"

        for domain, keywords in keywords_map.items():
            score = 0
            hit_keywords: list[str] = []
            for keyword in keywords or []:
                if keyword and keyword in text:
                    score += 10
                    hit_keywords.append(keyword)

            # 当前物流域额外加一层兜底：
            # 只要识别出了物流相关维度或指标，就给一定基础分，避免没有显式域关键词时完全失分。
            if domain == 'logistics':
                if parsed.get('metric_type'):
                    score += 5
                if parsed.get('logistics_company_name') or parsed.get('transport_mode') or parsed.get('region_name'):
                    score += 5
                if parsed.get('contract_no') or parsed.get('ship_instruction_no') or parsed.get('sap_order_no'):
                    score += 5

            candidates.append({
                'domain': domain,
                'score': score,
                'hit_keywords': hit_keywords,
            })

        # 默认一定保底回退到 logistics，保证当前版本始终可执行。
        if not candidates:
            candidates = [{'domain': 'logistics', 'score': 1, 'hit_keywords': []}]

        candidates.sort(key=lambda item: item['score'], reverse=True)
        selected = candidates[0]['domain'] if candidates else 'logistics'

        # 如果最高分为 0，也回退到 logistics。
        if candidates and candidates[0]['score'] <= 0:
            selected = 'logistics'

        reason = '根据域关键词命中情况进行路由；若未命中则默认回退物流域。'
        return {
            'selected_domain': selected,
            'candidate_domains': candidates,
            'reason': reason,
        }
