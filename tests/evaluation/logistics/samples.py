"""物流问法评测样例集（首批）。

业务逻辑：
    本文件定义物流业务域的首批评测用例，覆盖以下问法类型：
    1. 基础聚合查询（按基地/年份的发运量、运费总和）
    2. 线路运价查询（始发→目的 + 车型 + 年份）
    3. 承运商分组查询
    4. 澄清场景（缺少关键槽位）
    5. 暂不支持场景（导出、大范围无筛选）

    参考：物流 903 语义回归已验证的稳定问法模式。
    每条 case 附带业务口径（caliber）和分类标签（tags），
    便于后续按标签筛选运行。

使用：
    >>> from tests.evaluation.logistics.samples import load_logistics_suite
    >>> suite = load_logistics_suite()
    >>> print(f"共 {len(suite.cases)} 条用例")
"""

from __future__ import annotations

from backend.app.domains.qa_evaluation.schema import EvaluationCase, EvaluationSuite


def load_logistics_suite() -> EvaluationSuite:
    """加载物流业务域首批评测套件。

    参数：无。
    返回：EvaluationSuite，包含 10 条物流评测 case。
    业务逻辑：
        覆盖成功回答（基础聚合/线路运价/承运商分组）、
        澄清（缺少年份）、不支持（导出请求）三类预期状态。
    """
    cases: list[EvaluationCase] = [
        # ============================================================
        # 基础聚合查询 —— success（预期能直接回答）
        # ============================================================

        EvaluationCase(
            question="2024年合肥基地总发运量是多少？",
            domain="logistics",
            expected_status="success",
            expected_text="车次",
            caliber="发运量=车次数（shipment_trip_count），按合肥基地+2024年筛选",
            tags=["smoke", "logistics_aggregate", "hefei_base"],
        ),
        EvaluationCase(
            question="2023年阜宁基地的总运费",
            domain="logistics",
            expected_status="success",
            expected_text="元",
            caliber="总运费=SUM(total_fee)，按阜宁基地+2023年筛选",
            tags=["smoke", "logistics_aggregate", "funing_base"],
        ),
        EvaluationCase(
            question="2024年按承运商分组的发运量排名",
            domain="logistics",
            expected_status="success",
            expected_row_count=None,
            caliber="按承运商（carrier）维度分组，统计各承运商2024年总车次数并降序排列",
            tags=["logistics_groupby", "carrier_ranking"],
        ),

        # ============================================================
        # 线路运价查询 —— success
        # ============================================================

        EvaluationCase(
            question="2025年合肥至马鞍山17.5米车的平均运费",
            domain="logistics",
            expected_status="success",
            expected_text="1,557",
            caliber="线路运价=SUM(total_fee)/SUM(shipment_trip_count)，按合肥始发→马鞍山+17.5米车型+2025年筛选",
            tags=["smoke", "logistics_route_price", "hefei_maanshan"],
        ),
        EvaluationCase(
            question="2023年合肥到广州的13米车运价",
            domain="logistics",
            expected_status="success",
            expected_text="元/车",
            caliber="线路运价=SUM(total_fee)/SUM(shipment_trip_count)，按合肥→广州+13米车型+2023年筛选",
            tags=["logistics_route_price", "hefei_guangzhou"],
        ),

        # ============================================================
        # 历史线路跨年对比 —— success
        # ============================================================

        EvaluationCase(
            question="23年到25年合肥到深圳13米均价分别是多少",
            domain="logistics",
            expected_status="success",
            expected_text="2023",
            caliber="逐年度（2023/2024/2025）计算合肥→深圳13米车均价，无匹配年份保留空值行",
            tags=["logistics_route_price", "year_comparison", "hefei_shenzhen"],
        ),

        # ============================================================
        # 按经营计划/委托人查询 —— success
        # ============================================================

        EvaluationCase(
            question="刘娟2024年委托的发运情况",
            domain="logistics",
            expected_status="success",
            expected_text="刘娟",
            caliber="按委托人=刘娟+年份=2024筛选，统计车次数和总费用",
            tags=["logistics_filter", "entrusted_person"],
        ),

        # ============================================================
        # 澄清场景 —— clarification（缺少关键时间/地点槽位）
        # ============================================================

        EvaluationCase(
            question="运费是多少？",
            domain="logistics",
            expected_status="clarification",
            caliber="问题缺少年份、始发地、目的地等关键槽位，应澄清后再回答",
            tags=["clarify", "missing_slots"],
        ),
        EvaluationCase(
            question="帮我查一下发运情况",
            domain="logistics",
            expected_status="clarification",
            caliber="问题缺少时间范围、基地等关键筛选条件，应澄清",
            tags=["clarify", "missing_slots"],
        ),

        # ============================================================
        # 不支持场景 —— unsupported（导出、超范围请求）
        # ============================================================

        EvaluationCase(
            question="帮我导出2024年全部发运数据到Excel",
            domain="logistics",
            expected_status="unsupported",
            caliber="导出类请求暂不支持，应由不支持的终端节点处理",
            tags=["unsupported", "export"],
        ),
    ]

    return EvaluationSuite(
        name="物流核心问法评测集（首批）",
        domain="logistics",
        cases=cases,
        description="物流业务域首批评测用例，共10条，覆盖聚合/运价/承运商/澄清/不支持五种场景",
    )
