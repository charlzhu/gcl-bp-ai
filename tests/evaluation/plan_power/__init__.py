"""计划功率预测问法评测样例集（NQE-E4）。

业务逻辑：
    本目录存放功率预测业务域的首批评测用例，供 NQE EvalGraphRunner 自动评估。
    功率预测属于计划 BOM 域的子能力（plan_power_prediction / plan_power_supplier_recommendation / plan_power_factor_effect_compare），
    通过 domain_hint="power_prediction" 路由到 plan_bom 域执行。

使用：
    >>> from tests.evaluation.plan_power.samples import load_power_suite
    >>> suite = load_power_suite()
    >>> print(f"共 {len(suite.cases)} 条用例")
"""
