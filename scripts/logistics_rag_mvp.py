from __future__ import annotations

import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.app.domains.logistics.schemas.rag import LogisticsRagQueryRequest
from backend.app.domains.logistics.services.rag_service import LogisticsRagService


def main() -> None:
    """运行物流 RAG MVP 最小验证。

    当前脚本做三件事：
    1. 重建本地物流 RAG 索引；
    2. 跑一组代表性物流文档问题；
    3. 输出问答与引用来源到 tmp 报告，便于交付和演示。
    """
    service = LogisticsRagService()
    index_meta = service.rebuild_index()

    sample_questions = [
        {
            "question": "运量默认按什么口径统计？",
            "expected_keywords": ["瓦数口径"],
        },
        {
            "question": "2023到2025年的数据来源是什么？",
            "expected_keywords": ["历史", "Excel"],
        },
        {
            "question": "2026年后的正式数据来自哪里？",
            "expected_keywords": ["MySQL", "正式系统"],
        },
        {
            "question": "仓库维度为什么不是一期可靠统计维度？",
            "expected_keywords": ["allocate", "不作为一期可靠统计维度"],
        },
        {
            "question": "物流公司对应的标准字段是什么？",
            "expected_keywords": ["logistics_company_name"],
        },
        {
            "question": "铁运会标准化成什么？",
            "expected_keywords": ["铁路"],
        },
        {
            "question": "明细查询通常优先识别哪些编号？",
            "expected_keywords": ["contract_no", "sap_order_no"],
        },
        {
            "question": "BOM 替代料规则是什么？",
            "expected_grounded": False,
        },
    ]

    cases = []
    passed = 0
    for item in sample_questions:
        result = service.query(LogisticsRagQueryRequest(question=item["question"]))
        answer = result.answer
        expected_grounded = item.get("expected_grounded", True)
        grounded_ok = result.grounded is expected_grounded
        keywords = item.get("expected_keywords", [])
        keyword_ok = all(keyword in answer for keyword in keywords) if expected_grounded else True
        success = grounded_ok and keyword_ok
        if success:
            passed += 1
        cases.append(
            {
                "question": item["question"],
                "passed": success,
                "grounded": result.grounded,
                "answer": result.answer,
                "citations": [citation.model_dump() for citation in result.citations],
            }
        )

    report_path = Path("tmp/logistics_rag/logistics_rag_validation_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "index_meta": index_meta.model_dump(),
                "summary": {
                    "total": len(sample_questions),
                    "passed": passed,
                    "failed": len(sample_questions) - passed,
                },
                "cases": cases,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"物流 RAG MVP 验证完成：{passed}/{len(sample_questions)} 通过")
    print(f"报告路径：{report_path}")


if __name__ == "__main__":
    main()
