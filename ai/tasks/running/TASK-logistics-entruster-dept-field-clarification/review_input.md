# Review input: TASK-logistics-entruster-dept-field-clarification

## User bug
`26年 经营计划 刘娟 用车总费用是多少` answered with legacy locked planning scope and dropped 刘娟.

## Required business mapping
- 经营计划 / 经营计划部 => field `expand_dept` (扩充部门)
- 刘娟 => field `entrusted_person` (委托人)
- Known filters can combine.
- Unknown terms/person names must trigger clarification instead of full-scope answer or unrelated special scope.

## Validation summary
- focused: `PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_field_scope_clarification.py --tb=short` => 6 passed
- logistics business acceptance: `PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics*.py --tb=short` => 42 passed
- sync focused: `PYTHONPATH=. pytest -q tests/business_acceptance/test_logistics_system_sync_normalization.py --tb=short` => 2 passed
- compileall relevant files => passed
- API smoke => passed
- frontend build => passed
- browser smoke => passed (real Vite page with stub backend; answer contains 扩充部门=经营计划 and 委托人=刘娟; no JS errors)
- full business acceptance: 139 passed, 6 failed. Failures are unrelated current-worktree Plan BOM / business chat presentation expectations (`presentation.table_spec is None`, frontend fallback marker), not in logistics field-scope path.

## Scoped diff
```diff
diff --git a/backend/app/domains/logistics/repositories/data_qa_repository.py b/backend/app/domains/logistics/repositories/data_qa_repository.py
index 423a559..6690775 100644
--- a/backend/app/domains/logistics/repositories/data_qa_repository.py
+++ b/backend/app/domains/logistics/repositories/data_qa_repository.py
@@ -2506,6 +2506,8 @@ class LogisticsDataQaRepository:
         special_scope: str | None = None,
         base_code: str | None = None,
         procurement_type: str | None = None,
+        expand_dept: str | None = None,
+        entrusted_person: str | None = None,
         monthly_breakdown: bool = False,
     ) -> dict[str, Any]:
         """2026 系统按过滤条件统计总运费。
@@ -2517,7 +2519,8 @@ class LogisticsDataQaRepository:
             4. 若题目限定基地，则统一按 dwd_logistics_ship_task.base_code 过滤。
             5. transport_mode 仅用于用户明确说“公路运输/铁路运输”等运输方式时过滤。
             6. procurement_type 仅用于用户明确说“招标/询比价”等系统侧采购方式时过滤。
-            7. monthly_breakdown 只控制返回是否增加按月明细，不改变总费用计算口径。
+            7. expand_dept / entrusted_person 用于业务已确认的扩充部门、委托人字段过滤。
+            8. monthly_breakdown 只控制返回是否增加按月明细，不改变总费用计算口径。
         """
         filters = ["st.biz_year = :year"]
         params: dict[str, Any] = {"year": year}
@@ -2543,6 +2546,14 @@ class LogisticsDataQaRepository:
         if procurement_type:
             filters.append("st.procurement_type = :procurement_type")
             params["procurement_type"] = procurement_type
+        if expand_dept:
+            # 经营计划等业务范围词已在 planner 受控映射为扩充部门字段，这里只做参数绑定下推。
+            filters.append("st.expand_dept = :expand_dept")
+            params["expand_dept"] = expand_dept
+        if entrusted_person:
+            # 刘娟等已确认人名按委托人字段过滤，不再通过 special_scope 锁死单一口径。
+            filters.append("st.entrusted_person = :entrusted_person")
+            params["entrusted_person"] = entrusted_person
         if base_code:
             filters.append("st.base_code = :base_code")
             params["base_code"] = base_code
diff --git a/backend/app/domains/logistics/services/data_qa_planner.py b/backend/app/domains/logistics/services/data_qa_planner.py
index 605c7b2..e5b3c1b 100644
--- a/backend/app/domains/logistics/services/data_qa_planner.py
+++ b/backend/app/domains/logistics/services/data_qa_planner.py
@@ -97,6 +97,13 @@ class LogisticsDataQaPlanner:
         "运费多少",
         "运输费用",
     )
+    SYS_TOTAL_FEE_FIELD_FILTER_ALIASES = {
+        # 2026 系统总费用里，“经营计划”是扩充部门字段值，不是旧的锁定特殊口径。
+        "经营计划部": ("expand_dept", "经营计划部"),
+        "经营计划": ("expand_dept", "经营计划"),
+        # “刘娟”是委托人字段值，可与扩充部门等其他字段叠加过滤。
+        "刘娟": ("entrusted_person", "刘娟"),
+    }
     REMARK_SUPPORTED_KEYWORDS = ("倒运", "中转", "换车", "压车", "放空")
     REMARK_FEE_RATIO_KEYWORDS = ("倒运", "中转")
     ASSIST_SUPPORTED_QUERY_KEYS = {
@@ -389,6 +396,7 @@ class LogisticsDataQaPlanner:
         company_name = self._extract_company_name(compact)
         transport_mode = self._extract_transport_mode(compact)
         procurement_type = self._extract_procurement_type(compact)
+        controlled_field_filters = self._extract_sys_total_fee_controlled_field_filters(compact)
         if (
             company_name
             and (
@@ -732,6 +740,40 @@ class LogisticsDataQaPlanner:
                 filters={"year": year, "region_name": region},
             )
 
+        unknown_field_scope_terms = self._extract_unknown_sys_total_fee_field_scope_terms(
+            compact,
+            controlled_field_filters=controlled_field_filters,
+        )
+        if year == 2026 and self._is_total_fee_question(compact) and unknown_field_scope_terms:
+            unknown_text = "、".join(unknown_field_scope_terms)
+            return LogisticsDataQaPlan(
+                intent="clarification",
+                needs_clarification=True,
+                clarification_category="field_scope_mapping",
+                clarification_questions=[
+                    f"请确认“{unknown_text}”对应哪个字段口径：扩充部门、委托人、客户、承运商、项目还是其他字段？",
+                    "字段口径确认后，系统会按该字段与已给出的时间范围叠加过滤统计用车总费用。",
+                ],
+                clarification_missing_slots=["字段口径"],
+                clarification_reason=f"问题中的“{unknown_text}”没有受控字段映射，不能默认查全量或套用其他特殊口径。",
+                clarification_template="field_scope_mapping",
+            )
+
+        if year == 2026 and self._is_total_fee_question(compact) and controlled_field_filters:
+            # 受控业务词优先解释为真实字段过滤；若同句仍残留未知范围词，上方已转澄清，避免静默丢条件。
+            filters: dict[str, Any] = {"year": year, "months": months, **controlled_field_filters}
+            if monthly_breakdown:
+                filters["monthly_breakdown"] = True
+            return LogisticsDataQaPlan(
+                intent="aggregate",
+                query_key="sys_total_fee_by_filters",
+                metrics=["total_fee"],
+                dimensions=["biz_month"] if monthly_breakdown else [],
+                filters=filters,
+                group_by=["biz_month"] if monthly_breakdown else [],
+                sort=[{"field": "biz_month", "direction": "asc"}] if monthly_breakdown else [],
+            )
+
         if year == 2026 and procurement_type and self._is_total_fee_question(compact):
             return LogisticsDataQaPlan(
                 intent="aggregate",
@@ -2647,6 +2689,64 @@ class LogisticsDataQaPlanner:
         # 这里只裁剪常见尾部助词，不改变中间包含“的”的真实名称。
         return customer_name.strip().rstrip("的")
 
+    def _extract_sys_total_fee_controlled_field_filters(self, question: str) -> dict[str, str]:
+        """提取 2026 系统总费用题的受控字段过滤。
+
+        参数：
+            question: 已压缩空白的用户问题。
+
+        返回值：
+            可直接写入 plan.filters 的字段过滤条件。当前只放行已经由业务确认的
+            expand_dept / entrusted_person，避免把开放词随意下推为字段。
+        """
+
+        filters: dict[str, str] = {}
+        sorted_aliases = sorted(self.SYS_TOTAL_FEE_FIELD_FILTER_ALIASES.items(), key=lambda item: len(item[0]), reverse=True)
+        for alias, (field_name, field_value) in sorted_aliases:
+            if alias in question and field_name not in filters:
+                # 同一字段命中多个别名时保留最长别名，例如“经营计划部”不能被“经营计划”覆盖。
+                filters[field_name] = field_value
+        return filters
+
+    def _extract_unknown_sys_total_fee_field_scope_terms(
+        self,
+        question: str,
+        *,
+        controlled_field_filters: dict[str, str],
+    ) -> list[str]:
+        """识别缺少字段口径的 2026 系统用车总费用范围词。
+
+        参数：
+            question: 已压缩空白的用户问题。
+            controlled_field_filters: 已识别出的受控字段过滤，命中时不再把同一词当未知项。
+
+        返回值：
+            需要用户确认字段归属的词列表；为空表示无需触发字段口径澄清。
+
+        业务说明：
+            “张三用车总费用”这类问法只给了人名/业务词，没有说明它属于委托人、
+            客户、承运商还是其他字段。系统不能猜测字段，也不能套用经营计划等旧
+            special_scope，所以这里保守返回澄清。
+        """
+
+        if "用车" not in question:
+            return []
+        metric_positions = [question.find(keyword) for keyword in self.TOTAL_FEE_KEYWORDS if keyword in question]
+        if not metric_positions:
+            return []
+        scope_text = question[: min(position for position in metric_positions if position >= 0)]
+        scope_text = re.sub(r"\d{2,4}年", "", scope_text)
+        scope_text = re.sub(r"\d{1,2}月份?", "", scope_text)
+        scope_text = scope_text.replace("用车", "")
+        for alias in self.SYS_TOTAL_FEE_FIELD_FILTER_ALIASES:
+            scope_text = scope_text.replace(alias, "")
+        for token in ("请问", "帮我", "查一下", "查询", "统计", "一下", "的", "按", "和", "及", "与"):
+            scope_text = scope_text.replace(token, "")
+        scope_text = scope_text.strip(" ：:，,。？！?")
+        if not scope_text:
+            return []
+        return [scope_text]
+
     def _extract_company_name(self, question: str) -> str | None:
         """提取 2026 系统口径下的承运商公司名。
 
diff --git a/backend/app/domains/logistics/services/data_qa_service.py b/backend/app/domains/logistics/services/data_qa_service.py
index 1e5de38..0424e79 100644
--- a/backend/app/domains/logistics/services/data_qa_service.py
+++ b/backend/app/domains/logistics/services/data_qa_service.py
@@ -2126,6 +2126,8 @@ class LogisticsDataQaService:
                 special_scope=filters.get("special_scope"),
                 base_code=filters.get("base_code"),
                 procurement_type=filters.get("procurement_type"),
+                expand_dept=filters.get("expand_dept"),
+                entrusted_person=filters.get("entrusted_person"),
                 monthly_breakdown=bool(filters.get("monthly_breakdown")),
             )
             if data.get("parse_fail_count"):
@@ -2141,6 +2143,10 @@ class LogisticsDataQaService:
                 scope_parts.append("、".join(f"{month}月" for month in filters["months"]))
             if filters.get("base_name"):
                 scope_parts.append(filters["base_name"])
+            if filters.get("expand_dept"):
+                scope_parts.append(f"扩充部门={filters['expand_dept']}")
+            if filters.get("entrusted_person"):
+                scope_parts.append(f"委托人={filters['entrusted_person']}")
             if filters.get("customer_name"):
                 scope_parts.append(f"客户{filters['customer_name']}")
             if filters.get("company_name"):
@@ -2151,6 +2157,13 @@ class LogisticsDataQaService:
                 scope_parts.append(f"{filters['procurement_type']}采购方式")
             scope_text = "".join(scope_parts)
             if filters.get("monthly_breakdown") and data.get("monthly_rows"):
+                calculation_logic = [
+                    "系统总运费口径沿用当前正式系统计算方式：ship_product.price × project_name 解析总车数。",
+                    "按月拆分使用 pickup_date；pickup_date 缺失时按 biz_date 归属月份。",
+                    "按月返回只改变展示颗粒度，不改变总费用计算口径。",
+                ]
+                if filters.get("expand_dept") or filters.get("entrusted_person"):
+                    calculation_logic.append("业务范围词已按受控字段下推过滤：扩充部门使用 expand_dept，委托人使用 entrusted_person。")
                 monthly_rows = list(data["monthly_rows"])
                 summary = (
                     f"{scope_text}总运费已按月返回，"
@@ -2161,27 +2174,26 @@ class LogisticsDataQaService:
                     plan=plan,
                     table_columns=["biz_month", "total_fee", "task_count", "parse_fail_count", "price_missing_count"],
                     table_rows=monthly_rows,
-                    calculation_logic=[
-                        "系统总运费口径沿用当前正式系统计算方式：ship_product.price × project_name 解析总车数。",
-                        "按月拆分使用 pickup_date；pickup_date 缺失时按 biz_date 归属月份。",
-                        "按月返回只改变展示颗粒度，不改变总费用计算口径。",
-                    ],
+                    calculation_logic=calculation_logic,
                     data_scope={"tables": ["dwd_logistics_ship_task", "dwd_logistics_ship_product"], **filters},
                     warnings=warnings,
                 )
             summary = f"{scope_text}按当前系统口径统计的总运费为{float(data.get('total_fee') or 0):,.2f}元。"
+            calculation_logic = [
+                "系统总运费口径沿用当前正式系统计算方式：ship_product.price × project_name 解析总车数。",
+                "月份过滤优先使用 pickup_date，缺失时退回 biz_date。",
+                "客户过滤当前按 project_name 模糊命中，不额外承诺独立 customer 字段。",
+                "运输方式过滤仅在用户明确指定公路、铁路等运输方式时下推。",
+                "采购方式过滤仅在用户明确指定招标、询比价等系统字段时下推。",
+            ]
+            if filters.get("expand_dept") or filters.get("entrusted_person"):
+                calculation_logic.append("业务范围词已按受控字段下推过滤：扩充部门使用 expand_dept，委托人使用 entrusted_person。")
             return self._build_result(
                 answer_summary=summary,
                 plan=plan,
                 table_columns=["total_fee", "task_count", "parse_fail_count", "price_missing_count"],
                 table_rows=[data],
-                calculation_logic=[
-                    "系统总运费口径沿用当前正式系统计算方式：ship_product.price × project_name 解析总车数。",
-                    "月份过滤优先使用 pickup_date，缺失时退回 biz_date。",
-                    "客户过滤当前按 project_name 模糊命中，不额外承诺独立 customer 字段。",
-                    "运输方式过滤仅在用户明确指定公路、铁路等运输方式时下推。",
-                    "采购方式过滤仅在用户明确指定招标、询比价等系统字段时下推。",
-                ],
+                calculation_logic=calculation_logic,
                 data_scope={"tables": ["dwd_logistics_ship_task", "dwd_logistics_ship_product"], **filters},
                 warnings=warnings,
             )diff --git a/tests/business_acceptance/test_logistics_field_scope_clarification.py b/tests/business_acceptance/test_logistics_field_scope_clarification.py
new file mode 100644
index 0000000..9316cf7
--- /dev/null
+++ b/tests/business_acceptance/test_logistics_field_scope_clarification.py
@@ -0,0 +1,223 @@
+from __future__ import annotations
+
+from typing import Any
+
+from backend.app.domains.logistics.repositories.data_qa_repository import LogisticsDataQaRepository
+from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
+from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision
+from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
+from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
+
+
+class _FakeScalarResult:
+    """模拟 SQLAlchemy execute 返回值，便于检查 SQL 与参数。
+
+    参数：
+        row: first()/all() 需要返回的伪造行。
+    返回值：
+        提供 mappings().first()/all()/scalar() 的最小对象。
+    """
+
+    def __init__(self, row: dict[str, Any] | None = None) -> None:
+        self._row = row or {
+            "total_fee": 1234.56,
+            "task_count": 2,
+            "parse_fail_count": 0,
+            "price_missing_count": 0,
+        }
+
+    def mappings(self) -> "_FakeScalarResult":
+        return self
+
+    def first(self) -> dict[str, Any]:
+        return self._row
+
+    def all(self) -> list[dict[str, Any]]:
+        return [self._row]
+
+    def scalar(self) -> int:
+        return 0
+
+
+class _SqlCaptureDb:
+    """捕获 repository 生成的 SQL 和参数，不连接真实数据库。"""
+
+    def __init__(self) -> None:
+        self.calls: list[tuple[str, dict[str, Any]]] = []
+
+    def execute(self, statement: Any, params: dict[str, Any] | None = None) -> _FakeScalarResult:
+        self.calls.append((str(statement), dict(params or {})))
+        return _FakeScalarResult()
+
+
+class _NoopHistoryDb:
+    """服务层测试用数据库替身，只提供历史写入需要的事务方法。"""
+
+    def commit(self) -> None:
+        return None
+
+    def rollback(self) -> None:
+        return None
+
+
+class _NoopQueryLogRepository:
+    """禁用历史落库，避免服务层测试依赖真实数据库。"""
+
+    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
+        return 0
+
+
+class _FakeTotalFeeRepository:
+    """服务层测试替身：只允许走字段过滤版总费用查询。"""
+
+    def __init__(self) -> None:
+        self.total_fee_calls: list[dict[str, Any]] = []
+        self.special_fee_calls: list[dict[str, Any]] = []
+
+    def sys_total_fee_by_filters(self, **kwargs: Any) -> dict[str, Any]:
+        self.total_fee_calls.append(dict(kwargs))
+        return {
+            "total_fee": 1234.56,
+            "task_count": 2,
+            "parse_fail_count": 0,
+            "price_missing_count": 0,
+        }
+
+    def sys_special_total_fee(self, **kwargs: Any) -> dict[str, Any]:
+        self.special_fee_calls.append(dict(kwargs))
+        return {
+            "total_fee": 999999.0,
+            "task_count": 99,
+            "parse_fail_count": 0,
+            "price_missing_count": 0,
+        }
+
+
+class _NoopGuardrail:
+    """禁用 LLM guardrail，让验收测试只验证确定性规则链路。"""
+
+    def evaluate(self, **kwargs: Any) -> LogisticsLlmGuardrailDecision:
+        rule_plan = kwargs["rule_plan"]
+        return LogisticsLlmGuardrailDecision(
+            question=kwargs["question"],
+            rule_intent=rule_plan.intent,
+            rule_query_key=rule_plan.query_key,
+            rule_needs_clarification=rule_plan.needs_clarification,
+            final_intent=rule_plan.intent,
+            final_query_key=rule_plan.query_key,
+            final_needs_clarification=rule_plan.needs_clarification,
+            final_supported=not rule_plan.needs_clarification,
+        )
+
+    def write_audit_log(self, **kwargs: Any) -> None:
+        return None
+
+
+def test_planner_maps_business_words_to_expand_dept_and_entrusted_person() -> None:
+    """经营计划和刘娟必须分别映射到扩充部门、委托人字段，并可叠加过滤。"""
+
+    plan = LogisticsDataQaPlanner().build_plan("26年 经营计划 刘娟 用车总费用是多少")
+
+    assert plan.query_key == "sys_total_fee_by_filters"
+    assert plan.filters["year"] == 2026
+    assert plan.filters["expand_dept"] == "经营计划"
+    assert plan.filters["entrusted_person"] == "刘娟"
+    assert "special_scope" not in plan.filters
+    assert not plan.needs_clarification
+
+
+def test_planner_keeps_single_known_field_mapping_for_total_fee() -> None:
+    """单独出现经营计划或刘娟时也要映射到真实字段，而不是走锁定口径。"""
+
+    planner = LogisticsDataQaPlanner()
+
+    dept_plan = planner.build_plan("2026年经营计划用车总费用是多少")
+    assert dept_plan.query_key == "sys_total_fee_by_filters"
+    assert dept_plan.filters["expand_dept"] == "经营计划"
+    assert "entrusted_person" not in dept_plan.filters
+    assert "special_scope" not in dept_plan.filters
+
+    dept_full_name_plan = planner.build_plan("2026年经营计划部用车总费用是多少")
+    assert dept_full_name_plan.query_key == "sys_total_fee_by_filters"
+    assert dept_full_name_plan.filters["expand_dept"] == "经营计划部"
+    assert "special_scope" not in dept_full_name_plan.filters
+
+    person_plan = planner.build_plan("2026年刘娟用车总费用是多少")
+    assert person_plan.query_key == "sys_total_fee_by_filters"
+    assert person_plan.filters["entrusted_person"] == "刘娟"
+    assert "expand_dept" not in person_plan.filters
+    assert "special_scope" not in person_plan.filters
+
+
+def test_unknown_business_person_scope_requires_clarification() -> None:
+    """未知人名/范围不能默认全量或套用特殊口径，必须反问字段归属。"""
+
+    plan = LogisticsDataQaPlanner().build_plan("26年 张三 用车总费用是多少")
+
+    assert plan.needs_clarification
+    assert plan.query_key is None
+    assert plan.clarification_category == "field_scope_mapping"
+    assert "张三" in plan.clarification_reason
+    assert any("字段" in question or "口径" in question for question in plan.clarification_questions)
+
+
+def test_known_scope_with_unknown_person_still_requires_clarification() -> None:
+    """已知扩充部门旁边还有未知人名时，不能静默丢弃未知条件后直接回答。"""
+
+    plan = LogisticsDataQaPlanner().build_plan("26年 经营计划 张三 用车总费用是多少")
+
+    assert plan.needs_clarification
+    assert plan.query_key is None
+    assert plan.clarification_category == "field_scope_mapping"
+    assert "张三" in plan.clarification_reason
+    assert any("张三" in question for question in plan.clarification_questions)
+
+
+def test_repository_total_fee_downstream_filters_expand_dept_and_entrusted_person() -> None:
+    """repository 必须把扩充部门和委托人作为 SQL 参数下推，不能只改文案。"""
+
+    repository = object.__new__(LogisticsDataQaRepository)
+    repository.db = _SqlCaptureDb()
+
+    repository.sys_total_fee_by_filters(
+        year=2026,
+        months=None,
+        expand_dept="经营计划",
+        entrusted_person="刘娟",
+    )
+
+    sql_text = "\n".join(sql for sql, _ in repository.db.calls)
+    merged_params: dict[str, Any] = {}
+    for _, params in repository.db.calls:
+        merged_params.update(params)
+
+    assert "st.expand_dept = :expand_dept" in sql_text
+    assert "st.entrusted_person = :entrusted_person" in sql_text
+    assert merged_params["expand_dept"] == "经营计划"
+    assert merged_params["entrusted_person"] == "刘娟"
+
+
+def test_service_summary_and_repo_call_preserve_explicit_field_scope() -> None:
+    """服务层答案应展示字段过滤范围，并调用字段过滤查询而非特殊锁定口径。"""
+
+    repository = _FakeTotalFeeRepository()
+    service = LogisticsDataQaService(
+        db=_NoopHistoryDb(),
+        repository=repository,
+        planner=LogisticsDataQaPlanner(),
+        query_log_repository=_NoopQueryLogRepository(),
+        guardrail_service=_NoopGuardrail(),
+    )
+
+    result = service.query(LogisticsDataQaQueryRequest(question="26年 经营计划 刘娟 用车总费用是多少"))
+
+    assert repository.special_fee_calls == []
+    assert repository.total_fee_calls
+    call = repository.total_fee_calls[-1]
+    assert call["expand_dept"] == "经营计划"
+    assert call["entrusted_person"] == "刘娟"
+    assert result.query_plan.filters["expand_dept"] == "经营计划"
+    assert result.query_plan.filters["entrusted_person"] == "刘娟"
+    assert "扩充部门=经营计划" in result.answer_summary
+    assert "委托人=刘娟" in result.answer_summary
+    assert "锁定口径" not in result.answer_summary
diff --git a/ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/task-card.md b/ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/task-card.md
new file mode 100644
index 0000000..b88d0e2
--- /dev/null
+++ b/ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/task-card.md
@@ -0,0 +1,27 @@
+# TASK-logistics-entruster-dept-field-clarification
+
+## 用户反馈
+
+截图问题：`26年 经营计划 刘娟 用车总费用是多少`。
+
+当前回答只按“经营计划用车锁定口径”返回总运费，丢失了 `刘娟` 这个人名条件，也没有明确把业务词映射到真实字段。
+
+## 业务口径
+
+1. `经营计划`：指物流 2026 系统任务字段 `扩充部门`（代码字段：`expand_dept`）里的数据。
+2. `刘娟`：指物流 2026 系统任务字段 `委托人`（代码字段：`entrusted_person`）里的数据。
+3. 当问题里出现不能确定归属字段的业务词、人名或口语化范围时，必须先反问补充字段口径，不能默认套用“锁定口径”或全量总费用。
+
+## 验收标准
+
+- `26年 经营计划 刘娟 用车总费用是多少` 应生成可执行 plan：
+  - `query_key = sys_total_fee_by_filters`
+  - `filters.expand_dept = 经营计划`
+  - `filters.entrusted_person = 刘娟`
+  - 不再使用 `special_scope=planning` 吞掉人名条件。
+- `2026年经营计划用车总费用是多少` 应只按 `expand_dept` 过滤。
+- `2026年刘娟用车总费用是多少` 应只按 `entrusted_person` 过滤。
+- repository SQL 必须把 `expand_dept`、`entrusted_person` 下推到 `dwd_logistics_ship_task`，使用参数绑定。
+- `26年 张三 用车总费用是多少` 等未知人名/范围，如果没有受控字段映射，必须返回 clarification。
+- 不能 hardcode 单题答案；允许维护受控业务词典，但必须以字段映射形式表达。
+- 不 commit / push / deploy。
diff --git a/ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/api_smoke.py b/ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/api_smoke.py
new file mode 100644
index 0000000..6b16790
--- /dev/null
+++ b/ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/api_smoke.py
@@ -0,0 +1,110 @@
+"""API smoke：验证经营计划/刘娟字段口径通过 HTTP 接口保留。
+
+该脚本使用 FastAPI TestClient 和受控 LogisticsDataQaService，不连接真实数据库，
+只验证接口层到 planner/service/repository 替身的确定性链路：
+- 经营计划 -> expand_dept
+- 刘娟 -> entrusted_person
+- 未知人名 -> field_scope_mapping 澄清
+"""
+
+from __future__ import annotations
+
+from typing import Any
+
+from fastapi.testclient import TestClient
+
+from backend.app.api.deps import get_logistics_data_qa_service
+from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision
+from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
+from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
+from backend.app.main import app
+
+
+class _NoopHistoryDb:
+    def commit(self) -> None:
+        return None
+
+    def rollback(self) -> None:
+        return None
+
+
+class _NoopQueryLogRepository:
+    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
+        return 0
+
+
+class _NoopGuardrail:
+    def evaluate(self, **kwargs: Any) -> LogisticsLlmGuardrailDecision:
+        rule_plan = kwargs["rule_plan"]
+        return LogisticsLlmGuardrailDecision(
+            question=kwargs["question"],
+            rule_intent=rule_plan.intent,
+            rule_query_key=rule_plan.query_key,
+            rule_needs_clarification=rule_plan.needs_clarification,
+            final_intent=rule_plan.intent,
+            final_query_key=rule_plan.query_key,
+            final_needs_clarification=rule_plan.needs_clarification,
+            final_supported=not rule_plan.needs_clarification,
+        )
+
+    def write_audit_log(self, **kwargs: Any) -> None:
+        return None
+
+
+class _FakeRepository:
+    def __init__(self) -> None:
+        self.calls: list[dict[str, Any]] = []
+
+    def sys_total_fee_by_filters(self, **kwargs: Any) -> dict[str, Any]:
+        self.calls.append(dict(kwargs))
+        return {
+            "total_fee": 1234.56,
+            "task_count": 2,
+            "parse_fail_count": 0,
+            "price_missing_count": 0,
+        }
+
+    def sys_special_total_fee(self, **kwargs: Any) -> dict[str, Any]:
+        raise AssertionError(f"不应走 special_scope 锁定口径: {kwargs}")
+
+
+repository = _FakeRepository()
+service = LogisticsDataQaService(
+    db=_NoopHistoryDb(),
+    repository=repository,
+    planner=LogisticsDataQaPlanner(),
+    query_log_repository=_NoopQueryLogRepository(),
+    guardrail_service=_NoopGuardrail(),
+)
+
+
+def _override_service() -> LogisticsDataQaService:
+    return service
+
+
+app.dependency_overrides[get_logistics_data_qa_service] = _override_service
+try:
+    with TestClient(app) as client:
+        response = client.post("/api/v1/logistics/data-qa/query", json={"question": "26年 经营计划 刘娟 用车总费用是多少"})
+        assert response.status_code == 200, response.text
+        payload = response.json()
+        data = payload["data"]
+        assert data["query_plan"]["query_key"] == "sys_total_fee_by_filters"
+        assert data["query_plan"]["filters"]["expand_dept"] == "经营计划"
+        assert data["query_plan"]["filters"]["entrusted_person"] == "刘娟"
+        assert repository.calls[-1]["expand_dept"] == "经营计划"
+        assert repository.calls[-1]["entrusted_person"] == "刘娟"
+        assert "扩充部门=经营计划" in data["answer_summary"]
+        assert "委托人=刘娟" in data["answer_summary"]
+        assert "锁定口径" not in data["answer_summary"]
+
+        clarification_response = client.post("/api/v1/logistics/data-qa/query", json={"question": "26年 经营计划 张三 用车总费用是多少"})
+        assert clarification_response.status_code == 200, clarification_response.text
+        clarification_data = clarification_response.json()["data"]
+        assert clarification_data["needs_clarification"] is True
+        assert clarification_data["query_plan"]["clarification_category"] == "field_scope_mapping"
+        assert "张三" in clarification_data["query_plan"]["clarification_reason"]
+finally:
+    app.dependency_overrides.pop(get_logistics_data_qa_service, None)
+
+print("API smoke passed: field filters and clarification verified")
diff --git a/ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/browser_stub_backend.py b/ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/browser_stub_backend.py
new file mode 100644
index 0000000..22388ed
--- /dev/null
+++ b/ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/browser_stub_backend.py
@@ -0,0 +1,93 @@
+"""浏览器 smoke 用受控后端。
+
+启动真实 FastAPI app，并覆盖物流 data-qa 依赖，用于浏览器验证智能问答页面
+对 `26年 经营计划 刘娟 用车总费用是多少` 展示字段过滤答案，而不是锁定口径答案。
+"""
+
+from __future__ import annotations
+
+from typing import Any
+
+import uvicorn
+
+from backend.app.api.deps import get_logistics_data_qa_service
+from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision
+from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
+from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
+from backend.app.main import app
+from backend.app.services import business_answer_stream_service as stream_module
+
+
+class _NoopHistoryDb:
+    def commit(self) -> None:
+        return None
+
+    def rollback(self) -> None:
+        return None
+
+
+class _NoopQueryLogRepository:
+    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:
+        return 0
+
+
+class _NoopGuardrail:
+    def evaluate(self, **kwargs: Any) -> LogisticsLlmGuardrailDecision:
+        rule_plan = kwargs["rule_plan"]
+        return LogisticsLlmGuardrailDecision(
+            question=kwargs["question"],
+            rule_intent=rule_plan.intent,
+            rule_query_key=rule_plan.query_key,
+            rule_needs_clarification=rule_plan.needs_clarification,
+            final_intent=rule_plan.intent,
+            final_query_key=rule_plan.query_key,
+            final_needs_clarification=rule_plan.needs_clarification,
+            final_supported=not rule_plan.needs_clarification,
+        )
+
+    def write_audit_log(self, **kwargs: Any) -> None:
+        return None
+
+
+class _FakeRepository:
+    def sys_total_fee_by_filters(self, **kwargs: Any) -> dict[str, Any]:
+        return {
+            "total_fee": 1234.56,
+            "task_count": 2,
+            "parse_fail_count": 0,
+            "price_missing_count": 0,
+        }
+
+    def sys_special_total_fee(self, **kwargs: Any) -> dict[str, Any]:
+        raise AssertionError(f"不应走 special_scope 锁定口径: {kwargs}")
+
+
+class _StubBusinessAnswerStreamService:
+    """避免浏览器 smoke 依赖外部 LLM，仅回放确定性摘要。"""
+
+    def stream_answer(self, *, fallback_answer: str | None = None, **kwargs: Any):
+        yield fallback_answer or ""
+
+    def apply_streamed_answer(self, *, deterministic_payload: dict[str, Any], streamed_answer: str, **kwargs: Any) -> dict[str, Any]:
+        deterministic_payload["answer_summary"] = streamed_answer or deterministic_payload.get("answer_summary", "")
+        return deterministic_payload
+
+
+service = LogisticsDataQaService(
+    db=_NoopHistoryDb(),
+    repository=_FakeRepository(),
+    planner=LogisticsDataQaPlanner(),
+    query_log_repository=_NoopQueryLogRepository(),
+    guardrail_service=_NoopGuardrail(),
+)
+
+
+def _override_service() -> LogisticsDataQaService:
+    return service
+
+
+app.dependency_overrides[get_logistics_data_qa_service] = _override_service
+stream_module.BusinessAnswerStreamService = _StubBusinessAnswerStreamService
+
+if __name__ == "__main__":
+    uvicorn.run(app, host="127.0.0.1", port=18081, log_level="warning")
```
