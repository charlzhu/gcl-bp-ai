"""计划 BOM 问法评测样例集（首批）。

业务逻辑：
    本文件定义计划 BOM 业务域的首批评测用例，覆盖以下问法类型：
    1. 单订单五类材料规格查询（玻璃/间隙贴膜/焊带/汇流条/接线盒）
    2. 双订单材料规格差异对比
    3. 全订单/现有订单材料表格
    4. BOM 版型查询
    5. 澄清场景（缺少订单标识、歧义订单尾号）
    6. 暂不支持场景（导出请求、功率预测）

    参考：BOM 129 语义回归（A=86 / B=40 / C=3 / D=0）已验证的稳定问法模式。
    每条 case 附带业务口径（caliber）和分类标签（tags），
    便于后续按标签筛选运行。

使用：
    >>> from tests.evaluation.plan_bom.samples import load_plan_bom_suite
    >>> suite = load_plan_bom_suite()
    >>> print(f"共 {len(suite.cases)} 条用例")
"""

from __future__ import annotations

from backend.app.domains.qa_evaluation.schema import EvaluationCase, EvaluationSuite


def load_plan_bom_suite() -> EvaluationSuite:
    """加载计划 BOM 业务域首批评测套件。

    参数：无。
    返回：EvaluationSuite，包含 12 条 BOM 评测 case。
    业务逻辑：
        覆盖成功回答（单订单材料查询/双订单对比/全订单表格/版型查询）、
        澄清（缺少订单/歧义尾号）、不支持（导出/功率预测）、空结果四类预期状态。
    """
    cases: list[EvaluationCase] = [
        # ============================================================
        # 单订单五类材料规格查询 —— success（确定性 NLU + DB 查询直达）
        # ============================================================

        EvaluationCase(
            question="请查一下NT10/78GDF(哥伦比亚COEXITO-2026-00067)这单的玻璃、间隙贴膜、焊带、汇流条、接线盒分别用的什么规格。",
            domain="plan_bom",
            expected_status="success",
            caliber="单订单五类材料规格查询，通过订单尾号+客户实例定位唯一BOM后返回材料规格",
            tags=["smoke", "plan_bom_single_order", "material_spec"],
        ),
        EvaluationCase(
            question="帮我把NT12R/66GDF(意大利-2026-00097)这单的玻璃、间隙贴膜、焊带、汇流条、接线盒规格整理出来。",
            domain="plan_bom",
            expected_status="success",
            caliber="单订单五类材料规格整理，NLU 识别 intent=single_order_material_query，直接查中间库",
            tags=["smoke", "plan_bom_single_order", "material_spec"],
        ),

        # ============================================================
        # 双订单材料规格差异对比 —— success
        # ============================================================

        EvaluationCase(
            question="把NT12R/66GDF(法国-2026-00104)和NT12R/66GDF(法国Synapsun-2026-00114)这两单的玻璃、间隙贴膜、焊带、汇流条、接线盒做个差异对比。",
            domain="plan_bom",
            expected_status="success",
            caliber="双订单五类材料对比，NLU 识别 intent=cross_order_material_compare，展开多业务实例逐对比较",
            tags=["smoke", "plan_bom_compare", "material_compare"],
        ),
        EvaluationCase(
            question="NT12R/66GDF（法国Synapsun-2026-00114）和NT12R/66GDF(法国-2026-00104)的玻璃、焊带、汇流条、间隙贴膜线盒的规格对比",
            domain="plan_bom",
            expected_status="success",
            caliber="双订单材料规格对比（非标准问法变体），应映射到 cross_order_material_compare",
            tags=["plan_bom_compare", "material_compare", "nl_variant"],
        ),

        # ============================================================
        # 全订单 / 现有订单材料表格 —— success
        # ============================================================

        EvaluationCase(
            question="针对现有的订单把玻璃、焊带、汇流条、间隙贴膜线盒的规格并用表格的形式呈现",
            domain="plan_bom",
            expected_status="success",
            caliber="现有订单材料表格，NLU 识别 intent=multi_order_material_table，不要求补充订单号",
            tags=["plan_bom_multi_order", "material_table"],
        ),
        EvaluationCase(
            question="所有订单的玻璃规格列成表格",
            domain="plan_bom",
            expected_status="success",
            caliber="全部订单材料表格，'所有订单'是明确范围，不应被误判为需补充对比订单",
            tags=["plan_bom_multi_order", "material_table"],
        ),

        # ============================================================
        # BOM 版型 / 文件查询 —— success
        # ============================================================

        EvaluationCase(
            question="查一下NT12R/66GDF这个版型的BOM有哪些版本",
            domain="plan_bom",
            expected_status="success",
            caliber="版型查询，按版型编码（model_code）筛选所有版本",
            tags=["plan_bom_model", "version_query"],
        ),

        # ============================================================
        # 澄清场景 —— clarification（缺少关键订单或客户实例槽位）
        # ============================================================

        EvaluationCase(
            question="玻璃规格是什么",
            domain="plan_bom",
            expected_status="clarification",
            caliber="问题缺少订单号或版型号，无法确定查询目标，应澄清",
            tags=["clarify", "missing_order"],
        ),
        EvaluationCase(
            question="这个订单的材料清单给我看看",
            domain="plan_bom",
            expected_status="clarification",
            caliber="'这个订单'缺少具体标识，应澄清订单号或客户名",
            tags=["clarify", "missing_order_id"],
        ),

        # ============================================================
        # 暂不支持场景 —— unsupported（导出、功率预测等非 BOM 查询场景）
        # ============================================================

        EvaluationCase(
            question="帮我把所有BOM材料导出到Excel文件",
            domain="plan_bom",
            expected_status="unsupported",
            caliber="导出请求暂不支持，由 unsupported 终端节点处理",
            tags=["unsupported", "export"],
        ),
        EvaluationCase(
            question="NT12R/66GDF 615瓦功率预测",
            domain="plan_bom",
            expected_status="unsupported",
            caliber="功率预测属于 power_prediction 域，BOM 域不直接计算功率，应路由到对应域或返回不支持",
            tags=["unsupported", "power_prediction"],
        ),

        # ============================================================
        # 空结果场景 —— empty_result（不存在的订单）
        # ============================================================

        EvaluationCase(
            question="查一下订单99999的BOM玻璃规格",
            domain="plan_bom",
            expected_status="empty_result",
            caliber="订单99999在数据源中不存在，预期返回空结果",
            tags=["empty_result", "nonexistent_order"],
            allow_empty_substitute=True,
        ),
    ]

    return EvaluationSuite(
        name="计划 BOM 核心问法评测集（首批）",
        domain="plan_bom",
        cases=cases,
        description="计划 BOM 业务域首批评测用例，共12条，覆盖单订单/双订单对比/全订单表格/版型/澄清/不支持/空结果七种场景",
    )
