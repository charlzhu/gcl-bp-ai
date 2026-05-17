from __future__ import annotations

from pathlib import Path
from decimal import Decimal
import json
import re
import sys
from typing import Any

ROOT = Path('/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai')
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.db.session import SessionLocal
from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
from backend.app.domains.plan_bom.services.nlu_center_service import PlanBomNluCenterService
from backend.app.domains.plan_bom.services.power_config_resolver_service import PlanBomPowerConfigResolverService
from backend.app.domains.plan_bom.services.power_prediction_engine import PowerPredictionEngine
from backend.app.domains.plan_bom.services.power_recommendation_service import PowerRecommendationService
from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService

ROOT = Path('/Users/zhuchangchao/Work/PythonProject/project/gcl-bp-ai')
TASK_DIR = ROOT / 'ai/tasks/running/TASK-business-feedback-excel-qa-fix'


def json_safe(value: Any) -> Any:
    """把 Decimal/Pydantic 对象转换为 JSON 可写结构。"""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if hasattr(value, 'model_dump'):
        return json_safe(value.model_dump(mode='json'))
    return value


def compact(text: str, limit: int = 320) -> str:
    """生成用于报告的单行摘要。"""
    text = re.sub(r'\s+', ' ', str(text or '')).strip()
    return text[:limit] + ('…' if len(text) > limit else '')


def split_questions(raw: str) -> list[str]:
    """把 Excel 单元格中明显并列的多问法拆成可单独复现的问题。"""
    text = str(raw or '').strip()
    if not text:
        return []
    normalized = text.replace('\r', '\n')
    parts: list[str] = []
    if re.search(r'问题\s*\d+[：:.]', normalized):
        for chunk in re.split(r'问题\s*\d+[：:.]', normalized):
            chunk = chunk.strip(' /\n\t，,；;')
            if chunk:
                parts.append(chunk)
    else:
        # 业务反馈里常用“？ / ”或“？26年”连续写两个等价问法，拆开便于定位哪个问法退化。
        chunks = re.split(r'(?:\?\s*/\s*|？\s*/\s*|\n+)', normalized)
        for chunk in chunks:
            chunk = chunk.strip(' /\n\t，,；;')
            if chunk:
                # 如果同一段里连续出现多个问号并且后面紧接年份/客户/项目，继续拆。
                sub_chunks = re.split(r'(?<=[？?])(?=(?:\d{2,4}年|客户|项目|帮我|请|统计|对比|NT|订单|总共|25年|26年|24年|23年))', chunk)
                for sub in sub_chunks:
                    sub = sub.strip(' /\n\t，,；;')
                    if sub:
                        parts.append(sub)
    # 去重但保序；过短片段舍弃。
    dedup: list[str] = []
    seen: set[str] = set()
    for part in parts or [text]:
        part = part.strip()
        if len(part) < 4 or part in seen:
            continue
        seen.add(part)
        dedup.append(part)
    return dedup


def route_domain(question: str, excel_domain: str) -> str:
    """确定使用物流 QA 还是计划 BOM QA 复现。"""
    text = question
    plan_bom_keywords = ('订单', 'BOM', 'Bill of materials', '焊带', '玻璃', '汇流条', '线盒', '接线盒', '线长', '电池效率', '供应商', '间隙贴膜', '起投', 'NT12', 'NT10', 'NT15')
    logistics_keywords = ('物流', '发运', '运费', '运量', '车次', '承运', '区域', 'MW', '单W', '单瓦', '线路', '运输', '经营计划', '派车', '任务', '报价', '运价')
    if any(keyword in text for keyword in plan_bom_keywords) and not any(keyword in text for keyword in ('单W运输成本', '运输总量', '总运费', '发运量')):
        return 'plan_bom'
    if any(keyword in text for keyword in logistics_keywords):
        return 'logistics'
    return excel_domain if excel_domain in {'logistics', 'plan_bom'} else 'logistics'


def summarize_logistics(result: Any) -> dict[str, Any]:
    """提取物流问答响应中的关键复现信息。"""
    presentation = result.presentation
    chart_type = None
    display_type = None
    if presentation:
        display_type = presentation.display_type
        chart_type = presentation.chart_spec.chart_type if presentation.chart_spec else None
    return {
        'status': result.status.code if result.status else None,
        'supported': result.supported,
        'needs_clarification': result.needs_clarification,
        'query_key': result.query_plan.query_key,
        'intent': result.query_plan.intent,
        'metrics': result.query_plan.metrics,
        'dimensions': result.query_plan.dimensions,
        'filters': result.query_plan.filters,
        'columns': result.result_table.columns,
        'row_count': len(result.result_table.rows),
        'first_rows': result.result_table.rows[:5],
        'summary': result.answer_summary,
        'warnings': result.warnings,
        'display_type': display_type,
        'chart_type': chart_type,
        'calculation_logic': result.calculation_logic,
    }


def summarize_plan_bom(result: Any) -> dict[str, Any]:
    """提取计划 BOM 问答响应中的关键复现信息。"""
    presentation = result.presentation
    return {
        'status': result.status.code if result.status else None,
        'classification': result.classification,
        'intent': result.nlu.intent if result.nlu else None,
        'slots': result.nlu.slots if result.nlu else {},
        'columns': result.result_table.columns,
        'row_count': len(result.result_table.rows),
        'first_rows': result.result_table.rows[:5],
        'summary': result.answer_summary,
        'display_type': getattr(presentation, 'display_type', None) if presentation else None,
    }


def main() -> None:
    items = json.loads((TASK_DIR / 'excel-items.json').read_text(encoding='utf-8'))
    results: list[dict[str, Any]] = []
    md: list[str] = ['# 当前系统复现记录', '']
    with SessionLocal() as session:
        logistics = LogisticsDataQaService(db=session)
        repo = PlanBomQueryRepository(session)
        engine = PowerPredictionEngine(session)
        plan_bom = PlanBomQaService(
            repository=repo,
            query_service=PlanBomQueryService(repository=repo),
            nlu_service=PlanBomNluCenterService(repository=repo),
            presentation_service=PlanBomAnswerPresentationService(),
            power_config_resolver=PlanBomPowerConfigResolverService(session, repository=repo),
            power_prediction_engine=engine,
            power_recommendation_service=PowerRecommendationService(session, engine=engine),
        )
        for item in items:
            sub_questions = split_questions(item['question'])
            for idx, question in enumerate(sub_questions, start=1):
                domain = route_domain(question, item.get('domain') or 'unknown')
                record: dict[str, Any] = {
                    'id': f"{item['id']}#{idx}",
                    'source_id': item['id'],
                    'excel_row': item['excel_row'],
                    'question': question,
                    'feedback': item.get('feedback') or '',
                    'domain': domain,
                }
                try:
                    if domain == 'plan_bom':
                        response = plan_bom.ask(question, use_llm=False, trace_id=f"feedback-{item['id']}-{idx}")
                        record.update(summarize_plan_bom(response))
                    else:
                        response = logistics.query(LogisticsDataQaQueryRequest(question=question))
                        record.update(summarize_logistics(response))
                    record['error'] = None
                except Exception as exc:  # noqa: BLE001 - 复现脚本需要记录所有异常，便于任务归因。
                    record['error'] = f'{type(exc).__name__}: {exc}'
                results.append(json_safe(record))

    # Markdown 摘要按 Excel 原顺序输出，便于技术经理逐条核对业务备注。
    for record in results:
        md.append(f"## {record['id']} / {record['domain']}")
        md.append(f"- 问题：{record['question']}")
        if record.get('feedback'):
            md.append(f"- 业务反馈：{record['feedback']}")
        if record.get('error'):
            md.append(f"- 异常：{record['error']}")
            md.append('')
            continue
        md.append(f"- 状态：{record.get('status') or record.get('classification')}；intent/query_key：{record.get('intent')}/{record.get('query_key')}")
        md.append(f"- filters/slots：`{json.dumps(record.get('filters') or record.get('slots') or {}, ensure_ascii=False)}`")
        md.append(f"- 展示：display_type={record.get('display_type')}；chart_type={record.get('chart_type')}；columns={record.get('columns')}；rows={record.get('row_count')}")
        md.append(f"- 摘要：{compact(record.get('summary'))}")
        first_rows = record.get('first_rows') or []
        if first_rows:
            md.append(f"- 前几行：`{json.dumps(first_rows[:2], ensure_ascii=False)[:1000]}`")
        if record.get('warnings'):
            md.append(f"- warnings：{record.get('warnings')}")
        md.append('')

    (TASK_DIR / 'reproduction.json').write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
    (TASK_DIR / 'reproduction.md').write_text('\n'.join(md), encoding='utf-8')
    print(json.dumps({'questions': len(results), 'ok': sum(1 for r in results if not r.get('error')), 'errors': sum(1 for r in results if r.get('error'))}, ensure_ascii=False))


if __name__ == '__main__':
    main()
