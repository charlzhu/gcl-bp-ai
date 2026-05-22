"""计划功率预测问法评测样例集（首批）。

业务逻辑：
    本文件定义功率预测业务域的首批评测用例，覆盖以下问法类型：
    1. 功率预测查询（指定版型+目标功率的档位分布）
    2. 供应商效率推荐（指定目标功率的电池片供应商匹配）
    3. 功率配置影响值对比（同因子不同选项的功率差异）
    4. 澄清场景（缺少版型号/功率值等关键槽位）
    5. 暂不支持场景（导出请求、非功率问法）
    6. 空结果场景（不存在的版型号）

    参考：计划 BOM 域 power_prediction capability 的三类子能力。
    每条 case 附带业务口径（caliber）和分类标签（tags），
    便于后续按标签筛选运行。

使用：
    >>> from tests.evaluation.plan_power.samples import load_power_suite
    >>> suite = load_power_suite()
    >>> print(f"共 {len(suite.cases)} 条用例")
"""

from __future__ import annotations

from backend.app.domains.qa_evaluation.schema import EvaluationCase, EvaluationSuite


def load_power_suite() -> EvaluationSuite:
    """加载计划功率预测业务域首批评测套件。

    参数：无。
    返回：EvaluationSuite，包含 10 条功率评测 case。
    业务逻辑：
        覆盖成功回答（功率预测/供应商推荐/配置对比）、
        澄清（缺少版型号/配置参数）、不支持、空结果四种预期状态。
    """
    cases: list[EvaluationCase] = [
        # ============================================================
        # 功率预测 —— success（预期能直接回答）
        # ============================================================

        EvaluationCase(
            question="615W 版型功率预测",
            domain="power_prediction",
            expected_status="success",
            expected_text="功率",
            caliber="plan_power_prediction：用户提供版型号 615W，应由确定性功率预测引擎计算档位分布",
            tags=["smoke", "power_prediction"],
        ),
        EvaluationCase(
            question="620瓦 电池片功率档位",
            domain="power_prediction",
            expected_status="success",
            expected_text="功率",
            caliber="plan_power_prediction：用户提供目标功率 620W，计算各档位比例",
            tags=["power_prediction", "bin_distribution"],
        ),

        # ============================================================
        # 供应商功率匹配推荐 —— success
        # ============================================================

        EvaluationCase(
            question="推荐适合 615W 的电池片供应商",
            domain="power_prediction",
            expected_status="success",
            expected_text="推荐",
            caliber="plan_power_supplier_recommendation：根据目标功率 615W 匹配供应商效率",
            tags=["smoke", "power_supplier"],
        ),
        EvaluationCase(
            question="哪些供应商能达到 620W 的目标比例",
            domain="power_prediction",
            expected_status="success",
            expected_text="比例",
            caliber="plan_power_supplier_recommendation：按目标功率筛选供应商并评估达标比例",
            tags=["power_supplier", "target_ratio"],
        ),

        # ============================================================
        # 功率配置影响值对比 —— success
        # ============================================================

        EvaluationCase(
            question="对比玻璃和背板对 615W 功率的影响值",
            domain="power_prediction",
            expected_status="success",
            expected_text="影响",
            caliber="plan_power_factor_effect_compare：对比玻璃/背板因子对 615W 版型的功率影响值差异",
            tags=["power_factor_compare", "glass_backsheet"],
        ),
        EvaluationCase(
            question="接线盒配置差异对功率的影响",
            domain="power_prediction",
            expected_status="success",
            expected_text="影响",
            caliber="plan_power_factor_effect_compare：对比不同接线盒选项对功率的影响值",
            tags=["power_factor_compare", "junction_box"],
        ),

        # ============================================================
        # 澄清场景 —— clarification（缺少关键参数）
        # ============================================================

        EvaluationCase(
            question="功率预测",
            domain="power_prediction",
            expected_status="clarification",
            caliber="缺少版型号/目标功率等关键槽位，应澄清后再计算",
            tags=["clarify", "missing_model"],
        ),
        EvaluationCase(
            question="帮我看看功率",
            domain="power_prediction",
            expected_status="clarification",
            caliber="问题过于模糊，缺少版型号/供应商/配置等任何关键信息",
            tags=["clarify", "too_vague"],
        ),

        # ============================================================
        # 不支持场景 —— unsupported（导出、超范围）
        # ============================================================

        EvaluationCase(
            question="导出所有功率预测数据到Excel",
            domain="power_prediction",
            expected_status="unsupported",
            caliber="导出类请求暂不支持，应由不支持的终端节点处理",
            tags=["unsupported", "export"],
        ),
        EvaluationCase(
            question="把所有版型的功率都算一遍",
            domain="power_prediction",
            expected_status="unsupported",
            caliber="全量计算请求超出单次问答范围，应拒绝并引导用户指定具体版型",
            tags=["unsupported", "bulk_calculation"],
        ),
    ]

    return EvaluationSuite(
        name="功率问法评测集（首批）",
        domain="power_prediction",
        cases=cases,
        description="功率预测域首批评测用例，共10条，覆盖功率预测/供应商推荐/配置对比/澄清/不支持五种场景",
    )
