# Review Input: TASK-logistics-entruster-dept-field-clarification

## User issue
Question: `26年 经营计划 刘娟 用车总费用是多少`
Business rule:
- `经营计划` means field `扩充部门` (`expand_dept`) value.
- `刘娟` means field `委托人` (`entrusted_person`) value.
- Unknown business/person scope terms must ask clarification instead of guessing.

## Implemented behavior to review
- Planner maps controlled aliases to `sys_total_fee_by_filters` with filters `year=2026`, `expand_dept=经营计划`, `entrusted_person=刘娟`.
- Planner gives `needs_clarification=True`, category `field_scope_mapping`, when a 2026 total-fee car-use question contains unknown scope terms such as `张三`.
- Repository/service use deterministic SQL and answer text for `sys_total_fee_by_filters`; LLM does not calculate totals.
- Existing special-scope `sys_special_total_fee` remains for known legacy narrow questions like `2026年经营计划用车总费用是多少` without extra field filters.

## Current git status
```text
## agent/TASK-logistics-route-year-compare-2023-fix
 M backend/app/domains/logistics/repositories/data_qa_repository.py
 M backend/app/domains/logistics/repositories/sync_repository.py
 M backend/app/domains/logistics/services/data_qa_planner.py
 M backend/app/domains/logistics/services/data_qa_service.py
 M backend/app/domains/logistics/services/llm_answer_presentation_service.py
 M backend/app/domains/plan_bom/services/answer_presentation_service.py
 M frontend/src/views/business-chat/BusinessChatPage.vue
 M tests/business_acceptance/test_logistics_e2e_failure_repair_round1.py
 M tests/business_acceptance/test_logistics_system_sync_normalization.py
 M tests/business_acceptance/test_plan_power_docx_question_regression.py
 M tests/business_acceptance/test_plan_power_m5_qa_integration.py
?? "2023\345\271\264\345\256\211\345\276\275\345\220\210\350\202\245\345\217\221\350\277\220\345\217\260\350\264\246.xlsx"
?? "2023\345\271\264\345\256\211\345\276\275\351\230\234\345\256\201\347\211\251\346\265\201\345\217\221\350\277\220\345\217\260\350\264\246.xlsx"
?? "2024\345\271\264\347\211\251\346\265\201\345\217\221\350\277\220\346\200\273\345\217\260\350\264\246.xlsx"
?? "2025\345\271\264\347\211\251\346\265\201\345\217\221\350\277\220\346\200\273\345\217\260\350\264\246.xlsx"
?? ai/eval/runs/run_20260507_001940_full_all/clarification_batch_state.md
?? ai/eval/scripts/cron_batch_recover_plan_power_branch_prompt.md
?? ai/tasks/running/TASK-ai-answer-stream/
?? ai/tasks/running/TASK-bom-layout-v2/
?? ai/tasks/running/TASK-bom-query-log/
?? ai/tasks/running/TASK-bom-typography/
?? ai/tasks/running/TASK-bom-visual-polish/
?? ai/tasks/running/TASK-business-chat-markdown-rendering/
?? ai/tasks/running/TASK-business-feedback-excel-qa-fix/
?? ai/tasks/running/TASK-logistics-2025-hefei-guangzhou-17_5-price/
?? ai/tasks/running/TASK-logistics-city-carrier-scope-fix/
?? ai/tasks/running/TASK-logistics-city-fee-topn/
?? ai/tasks/running/TASK-logistics-composite-decomposition/
?? ai/tasks/running/TASK-logistics-entruster-dept-field-clarification/
?? ai/tasks/running/TASK-logistics-explicit-month-caveat/
?? ai/tasks/running/TASK-logistics-explicit-year-scope/
?? ai/tasks/running/TASK-logistics-railway-sync-scope/
?? ai/tasks/running/TASK-logistics-ranking-topn-generalization/
?? ai/tasks/running/TASK-plan-bom-batch-upload/
?? ai/tasks/running/TASK-plan-power-exact-bom-disambiguation/
?? ai/tasks/running/TASK-plan-power-fall-ratio-excel-like-table/
?? ai/tasks/running/TASK-plan-power-fall-ratio-real-subrows/
?? ai/tasks/running/TASK-plan-power-fall-ratio-subrows/
?? ai/tasks/running/TASK-plan-power-no-bom-explicit-config/
?? ai/tasks/running/TASK-plan-power-real-business-qa-fix/
?? ai/tasks/running/TASK-plan-power-recommendation-export-polish/
?? ai/tasks/running/TASK-plan-power-recommendation-table-polish/
?? ai/tasks/running/TASK-smart-chat-detail-excel-export/
?? ai/tasks/running/TASK-smart-chat-excel-alignment/
?? ai/tasks/running/TASK-smart-chat-new-session-button/
?? ai/tasks/running/TASK-smart-chat-single-fallback/
?? backend/app/services/business_answer_stream_service.py
?? frontend/src/utils/businessMarkdown.ts
?? frontend/src/utils/streamingApi.ts
?? screenshot-1778555840892.png
?? screenshot-1778558137607.png
?? screenshot-1778562130026.png
?? tests/business_acceptance/test_business_chat_answer_format_preference.py
?? tests/business_acceptance/test_logistics_field_scope_clarification.py
?? tests/business_acceptance/test_logistics_llm_led_composite_decomposition.py
```

## Scoped diff for current review
```diff
diff --git a/backend/app/domains/logistics/repositories/data_qa_repository.py b/backend/app/domains/logistics/repositories/data_qa_repository.py
index 423a559..6c373a8 100644
--- a/backend/app/domains/logistics/repositories/data_qa_repository.py
+++ b/backend/app/domains/logistics/repositories/data_qa_repository.py
@@ -1474,6 +1474,7 @@ class LogisticsDataQaRepository:
         origin_place: str | None = None,
         province: str | None = None,
         city: str | None = None,
+        price_metric: str = "total_fee",
     ) -> dict[str, Any]:
         """历史线路/城市运价分析。
 
@@ -1490,11 +1491,12 @@ class LogisticsDataQaRepository:
 
         说明：
             1. 该方法服务于 Round2 的历史线路运价题族；
-            2. 统计口径固定使用历史台账 total_fee；
-            3. 如果目的地给的是城市，则优先按 city 过滤；否则按 province 过滤。
+            2. 统计口径按 price_metric 选择：报价/运价使用 unit_price_per_vehicle（单价/车），运费类默认使用 total_fee；
+            3. 如果目的地给的是城市，则优先按 city 模糊过滤；否则按 province 过滤。
         """
         filters = ["required_vehicle_type LIKE :vehicle_type"]
         params: dict[str, Any] = {"vehicle_type": f"%{vehicle_type}%"}
+        metric_column = "unit_price_per_vehicle" if price_metric == "unit_price_per_vehicle" else "total_fee"
         year_placeholders = ", ".join(f":year_{idx}" for idx, _ in enumerate(years))
         filters.append(f"biz_year IN ({year_placeholders})")
         for idx, year in enumerate(years):
@@ -1503,8 +1505,8 @@ class LogisticsDataQaRepository:
             filters.append("origin_place = :origin_place")
             params["origin_place"] = origin_place
         if city:
-            filters.append("city = :city")
-            params["city"] = city
+            filters.append("city LIKE :city")
+            params["city"] = f"%{city}%"
         elif province:
             filters.append("province = :province")
             params["province"] = province
@@ -1516,7 +1518,7 @@ class LogisticsDataQaRepository:
                     f"""
                     SELECT
                         DATE_FORMAT(biz_date, '%Y-%m') AS biz_month,
-                        ROUND(AVG(total_fee), 0) AS avg_fee,
+                        ROUND(AVG({metric_column}), 0) AS avg_fee,
                         COUNT(*) AS row_count
                     FROM dwd_logistics_hist_shipment_detail
                     WHERE {where_sql}
@@ -1535,7 +1537,7 @@ class LogisticsDataQaRepository:
                     f"""
                     SELECT
                         biz_year,
-                        ROUND(AVG(total_fee), 0) AS avg_fee,
+                        ROUND(AVG({metric_column}), 0) AS avg_fee,
                         COUNT(*) AS row_count
                     FROM dwd_logistics_hist_shipment_detail
                     WHERE {where_sql}
@@ -1545,16 +1547,28 @@ class LogisticsDataQaRepository:
                 ),
                 params,
             ).mappings().all()
-            return {"view_mode": view_mode, "items": [dict(row) for row in rows], "summary_row": None}
+            rows_by_year = {int(row["biz_year"]): dict(row) for row in rows if row.get("biz_year") is not None}
+            items: list[dict[str, Any]] = []
+            missing_years: list[int] = []
+            for requested_year in years:
+                # 用户明确要求“23/24/25 年分别”时，结果表必须逐年对齐请求年份；
+                # 某一年没有匹配记录也保留空值行，避免前端/摘要看起来像系统漏查了该年份。
+                year_row = rows_by_year.get(int(requested_year))
+                if year_row is None:
+                    items.append({"biz_year": int(requested_year), "avg_fee": None, "row_count": 0})
+                    missing_years.append(int(requested_year))
+                else:
+                    items.append(year_row)
+            return {"view_mode": view_mode, "items": items, "summary_row": None, "missing_years": missing_years}
 
         if view_mode == "fee_extremes":
             row = self.db.execute(
                 text(
                     f"""
                     SELECT
-                        ROUND(MIN(total_fee), 0) AS min_fee,
-                        ROUND(MAX(total_fee), 0) AS max_fee,
-                        ROUND(AVG(total_fee), 0) AS avg_fee,
+                        ROUND(MIN({metric_column}), 0) AS min_fee,
+                        ROUND(MAX({metric_column}), 0) AS max_fee,
+                        ROUND(AVG({metric_column}), 0) AS avg_fee,
                         COUNT(*) AS row_count
                     FROM dwd_logistics_hist_shipment_detail
                     WHERE {where_sql}
@@ -1568,7 +1582,7 @@ class LogisticsDataQaRepository:
             text(
                 f"""
                 SELECT
-                    ROUND(AVG(total_fee), 0) AS avg_fee,
+                    ROUND(AVG({metric_column}), 0) AS avg_fee,
                     COUNT(*) AS row_count
                 FROM dwd_logistics_hist_shipment_detail
                 WHERE {where_sql}
@@ -2506,6 +2520,8 @@ class LogisticsDataQaRepository:
         special_scope: str | None = None,
         base_code: str | None = None,
         procurement_type: str | None = None,
+        expand_dept: str | None = None,
+        entrusted_person: str | None = None,
         monthly_breakdown: bool = False,
     ) -> dict[str, Any]:
         """2026 系统按过滤条件统计总运费。
@@ -2517,7 +2533,8 @@ class LogisticsDataQaRepository:
             4. 若题目限定基地，则统一按 dwd_logistics_ship_task.base_code 过滤。
             5. transport_mode 仅用于用户明确说“公路运输/铁路运输”等运输方式时过滤。
             6. procurement_type 仅用于用户明确说“招标/询比价”等系统侧采购方式时过滤。
-            7. monthly_breakdown 只控制返回是否增加按月明细，不改变总费用计算口径。
+            7. expand_dept / entrusted_person 用于业务已确认的扩充部门、委托人字段过滤。
+            8. monthly_breakdown 只控制返回是否增加按月明细，不改变总费用计算口径。
         """
         filters = ["st.biz_year = :year"]
         params: dict[str, Any] = {"year": year}
@@ -2543,6 +2560,14 @@ class LogisticsDataQaRepository:
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
index 605c7b2..6dc769c 100644
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
@@ -118,6 +125,7 @@ class LogisticsDataQaPlanner:
         "sys_driver_phone_name_consistency",
         "sys_driver_id_phone_consistency",
         "sys_special_total_fee",
+        "composite_decomposed",
     }
 
     def __init__(self, *, slot_extractor: LogisticsSlotExtractor | None = None) -> None:
@@ -166,11 +174,10 @@ class LogisticsDataQaPlanner:
                 clarification_reason="用户要求吨口径，但当前稳定数据链路只支持瓦数 / MW 发运量。",
             )
 
-        composite_plan = self._build_decomposable_composite_plan(compact)
-        if composite_plan is not None:
-            # 复合问题如果能被拆成多个已审计 A 类子问题，应先走拆分执行，
-            # 避免后续 C 类策略把整句误判为“历史采购方式拆分”。
-            return composite_plan
+        # 综合型问题“是否可拆、如何拆”必须由 LLM 语义理解层主导。
+        # 规则 planner 不再按关键词直接拆分，只保留吨口径、历史字段缺失等硬边界；
+        # 若 Guardrail 收到 LLM 的可信拆分候选，再由 build_plan_from_guardrail_candidate
+        # 回构白名单子计划并执行安全校验。
 
         # 不支持边界必须先于高置信 A 类候选生效。
         # 例如“预测未来 3 个月各区域发运量”虽然包含“年份+各区域+发运量”，
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
@@ -978,10 +1020,12 @@ class LogisticsDataQaPlanner:
             2. 只有当原始问题缺少的槽位能通过问句抽取或 LLM 结构化输出稳定补齐时，才返回 plan；
             3. 如果任何关键口径仍不明确，必须返回 None，让主链路继续保持原规则结果。
         """
+        compact = re.sub(r"\s+", "", question.strip())
+        if candidate_query_key == "composite_decomposed":
+            return self._build_composite_plan_from_llm_result(compact=compact, llm_result=llm_result)
         if candidate_query_key not in self.ASSIST_SUPPORTED_QUERY_KEYS:
             return None
 
-        compact = re.sub(r"\s+", "", question.strip())
         year = self._resolve_assist_year(compact, llm_result)
         months = self._resolve_assist_months(compact, llm_result)
         region = self._resolve_assist_region(compact, llm_result)
@@ -1147,41 +1191,71 @@ class LogisticsDataQaPlanner:
             )
         return None
 
-    def _build_decomposable_composite_plan(self, compact: str) -> LogisticsDataQaPlan | None:
-        """识别可拆分成多个确定性子查询的复合物流问题。
+    def _build_composite_plan_from_llm_result(
+        self,
+        *,
+        compact: str,
+        llm_result: LogisticsLlmUnderstandingResult,
+    ) -> LogisticsDataQaPlan | None:
+        """根据 LLM 拆分结果回构可执行的复合查询计划。
 
         参数：
             compact: 已去除空白的用户问题。
+            llm_result: Guardrail 放行的 LLM 结构化理解结果。
         返回值：
             可执行的 composite_decomposed 查询计划；无法安全拆分时返回 None。
         业务说明：
-            当前只把“历史高运费地址清单 + 2026 系统采购方式发运量”这类
-            顶层并列问题拆开执行；如果用户要求在历史高运费地址内部按采购方式拆分，
-            仍交给既有 C 类边界拒答，避免伪造历史采购方式字段。
+            LLM 负责判断顶层并列子问题和给出子计划候选；本方法只做白名单、
+            字段能力、年份来源和回指安全校验，不能再按关键词自行决定拆分。
         """
 
-        clauses = self._split_composite_clauses(compact)
-        if len(clauses) < 2:
+        if "吨" in compact and any(keyword in compact for keyword in ("发运量", "运量", "发货量")):
+            return None
+
+        decomposition = llm_result.filters if isinstance(llm_result.filters, dict) else {}
+        sub_plan_payloads = decomposition.get("sub_plans")
+        if not isinstance(sub_plan_payloads, list) or len(sub_plan_payloads) < 2:
+            return None
+        if decomposition.get("decomposition_strategy") not in {"top_level_conjunction", "llm_top_level_conjunction"}:
+            return None
+
+        high_fee_payload = self._find_llm_sub_plan_payload(
+            sub_plan_payloads,
+            query_key="hist_high_fee_addresses_by_customer",
+        )
+        procurement_payload = self._find_llm_sub_plan_payload(
+            sub_plan_payloads,
+            query_key="sys_mw_by_procurement_type",
+        )
+        if high_fee_payload is None or procurement_payload is None:
             return None
 
-        high_fee_clause = next((clause for clause in clauses if self._is_high_fee_address_clause(clause)), None)
-        procurement_clause = next((clause for clause in clauses if self._is_procurement_mw_clause(clause)), None)
+        high_fee_clause = self._extract_llm_source_clause(high_fee_payload)
+        procurement_clause = self._extract_llm_source_clause(procurement_payload)
         if not high_fee_clause or not procurement_clause:
             return None
+        if not self._is_high_fee_address_clause(high_fee_clause):
+            return None
+        if not self._is_procurement_mw_clause(procurement_clause):
+            return None
         if self._is_historical_procurement_split_request(compact, high_fee_clause, procurement_clause):
             return None
 
-        high_fee_year = self._extract_year(high_fee_clause) or self._extract_year(compact)
+        high_fee_filters = high_fee_payload.get("filters") if isinstance(high_fee_payload.get("filters"), dict) else {}
+        procurement_filters = procurement_payload.get("filters") if isinstance(procurement_payload.get("filters"), dict) else {}
+
+        high_fee_year = self._coerce_int(high_fee_filters.get("year")) or self._extract_year(high_fee_clause)
         if high_fee_year not in {2023, 2024, 2025}:
             return None
-        customer_name = self._extract_high_fee_customer_name(high_fee_clause) or self._extract_customer_name(high_fee_clause)
+        customer_name = str(high_fee_filters.get("customer_name") or "").strip()
+        customer_name = customer_name or self._extract_high_fee_customer_name(high_fee_clause) or self._extract_customer_name(high_fee_clause)
         if not customer_name or len(customer_name) <= 1:
             return None
-        threshold_fee = self._extract_fee_threshold_yuan(high_fee_clause) or self._extract_fee_threshold_yuan(compact)
+        threshold_fee = self._coerce_int(high_fee_filters.get("threshold_fee")) or self._extract_fee_threshold_yuan(high_fee_clause)
         if not threshold_fee:
             return None
 
-        procurement_year = self._extract_year(procurement_clause)
+        procurement_year = self._coerce_int(procurement_filters.get("year")) or self._extract_year(procurement_clause)
         if procurement_year in {2023, 2024, 2025}:
             return None
         procurement_year = procurement_year or 2026
@@ -1213,6 +1287,8 @@ class LogisticsDataQaPlanner:
             dimensions=["section"],
             filters={
                 "decomposition_strategy": "top_level_conjunction",
+                "decomposition_source": "llm_guardrail",
+                "llm_confidence": llm_result.confidence,
                 "sub_query_keys": ["hist_high_fee_addresses_by_customer", "sys_mw_by_procurement_type"],
                 "sub_plans": [
                     {"section_label": "历史高运费收货地址", **high_fee_plan.model_dump(mode="json")},
@@ -1221,6 +1297,52 @@ class LogisticsDataQaPlanner:
             },
         )
 
+    @staticmethod
+    def _find_llm_sub_plan_payload(sub_plan_payloads: list[Any], *, query_key: str) -> dict[str, Any] | None:
+        """从 LLM 拆分结果中查找指定 query_key 的子计划。
+
+        参数：
+            sub_plan_payloads: LLM 返回的子计划候选列表。
+            query_key: 需要匹配的受控查询键。
+        返回值：
+            匹配到的子计划字典；未匹配时返回 None。
+        """
+
+        for payload in sub_plan_payloads:
+            if isinstance(payload, dict) and payload.get("query_key") == query_key:
+                return payload
+        return None
+
+    @staticmethod
+    def _extract_llm_source_clause(payload: dict[str, Any]) -> str:
+        """提取 LLM 子计划对应的原始子句。
+
+        参数：
+            payload: 单个 LLM 子计划候选。
+        返回值：
+            去空白后的原始子句；如果没有可审计子句则返回空字符串。
+        """
+
+        source_clause = payload.get("source_clause") or payload.get("clause") or payload.get("question")
+        return re.sub(r"\s+", "", str(source_clause or "").strip())
+
+    @staticmethod
+    def _coerce_int(value: Any) -> int | None:
+        """把 LLM 输出中的整数槽位安全转成 int。
+
+        参数：
+            value: LLM 输出的候选值。
+        返回值：
+            可用整数；转换失败或值为空时返回 None。
+        """
+
+        if value in {None, ""}:
+            return None
+        try:
+            return int(float(value))
+        except (TypeError, ValueError):
+            return None
+
     @staticmethod
     def _split_composite_clauses(compact: str) -> list[str]:
         """按顶层并列连接词拆分复合问题子句。"""
@@ -1931,10 +2053,16 @@ class LogisticsDataQaPlanner:
             and route_years
             and all(item in {2023, 2024, 2025} for item in route_years)
         ):
+            price_metric = (
+                "unit_price_per_vehicle"
+                if any(keyword in compact for keyword in ("报价", "运价", "单价", "单价/车"))
+                else "total_fee"
+            )
             filters: dict[str, Any] = {
                 "years": route_years,
                 "vehicle_type": vehicle_type,
                 "view_mode": route_view_mode,
+                "price_metric": price_metric,
             }
             if not years:
                 filters["default_year_scope_label"] = "2023-2025历史累计"
@@ -2647,6 +2775,64 @@ class LogisticsDataQaPlanner:
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
index 1e5de38..764fdb7 100644
--- a/backend/app/domains/logistics/services/data_qa_service.py
+++ b/backend/app/domains/logistics/services/data_qa_service.py
@@ -1336,8 +1336,12 @@ class LogisticsDataQaService:
                 origin_place=filters.get("origin_place"),
                 province=filters.get("province"),
                 city=filters.get("city"),
+                price_metric=filters.get("price_metric", "total_fee"),
             )
             view_mode = filters["view_mode"]
+            price_metric = filters.get("price_metric", "total_fee")
+            price_metric_label = "单价/车" if price_metric == "unit_price_per_vehicle" else "总费用"
+            price_summary_label = "报价" if price_metric == "unit_price_per_vehicle" else "运费"
             if filters.get("default_year_scope_label"):
                 scope_parts = [filters["default_year_scope_label"]]
                 warnings.append(
@@ -1356,21 +1360,28 @@ class LogisticsDataQaService:
             scope_parts.append(f"{filters['vehicle_type']}车")
             scope_text = "".join(scope_parts)
             if view_mode == "monthly_avg":
-                summary = f"{scope_text}每月平均运费已按月份返回。"
+                summary = f"{scope_text}每月平均{price_summary_label}已按月份返回。"
                 table_columns = ["biz_month", "avg_fee", "row_count"]
             elif view_mode == "year_compare":
-                summary = f"{scope_text}运价对比已按年份返回。"
+                missing_years = [int(year) for year in data.get("missing_years") or []]
+                summary = f"{scope_text}{price_summary_label}对比已按年份返回。"
+                if missing_years:
+                    missing_year_text = "、".join(f"{year}年" for year in missing_years)
+                    summary = f"{summary}其中{missing_year_text}无匹配记录。"
+                    warnings.append(
+                        f"{scope_text}在{missing_year_text}无匹配记录，已保留空值行，避免显式年份被静默遗漏。"
+                    )
                 table_columns = ["biz_year", "avg_fee", "row_count"]
             elif view_mode == "fee_extremes":
                 summary_row = data["summary_row"] or {}
                 summary = (
-                    f"{scope_text}最高价为{int(summary_row.get('max_fee') or 0):,}元，"
-                    f"最低价为{int(summary_row.get('min_fee') or 0):,}元。"
+                    f"{scope_text}最高{price_summary_label}为{int(summary_row.get('max_fee') or 0):,}元，"
+                    f"最低{price_summary_label}为{int(summary_row.get('min_fee') or 0):,}元。"
                 )
                 table_columns = ["min_fee", "max_fee", "avg_fee", "row_count"]
             else:
                 summary_row = data["summary_row"] or {}
-                summary = f"{scope_text}平均运费为{int(summary_row.get('avg_fee') or 0):,}元。"
+                summary = f"{scope_text}平均{price_summary_label}为{int(summary_row.get('avg_fee') or 0):,}元。"
                 table_columns = ["avg_fee", "row_count"]
             return self._build_result(
                 answer_summary=summary,
@@ -1378,8 +1389,8 @@ class LogisticsDataQaService:
                 table_columns=table_columns,
                 table_rows=data["items"],
                 calculation_logic=[
-                    "历史线路运价统一按 dwd_logistics_hist_shipment_detail.total_fee 统计。",
-                    "当问题指定城市时优先按 city 过滤；否则按 province 过滤。",
+                    f"历史线路{price_summary_label}按 dwd_logistics_hist_shipment_detail.{price_metric}（{price_metric_label}）统计。",
+                    "当问题指定城市时优先按 city 模糊过滤，兼容广州/广州市等同一城市写法；否则按 province 过滤。",
                     "车型口径通过 required_vehicle_type 模糊匹配实现。",
                 ],
                 data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
@@ -2126,6 +2137,8 @@ class LogisticsDataQaService:
                 special_scope=filters.get("special_scope"),
                 base_code=filters.get("base_code"),
                 procurement_type=filters.get("procurement_type"),
+                expand_dept=filters.get("expand_dept"),
+                entrusted_person=filters.get("entrusted_person"),
                 monthly_breakdown=bool(filters.get("monthly_breakdown")),
             )
             if data.get("parse_fail_count"):
@@ -2141,6 +2154,10 @@ class LogisticsDataQaService:
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
@@ -2151,6 +2168,13 @@ class LogisticsDataQaService:
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
@@ -2161,27 +2185,26 @@ class LogisticsDataQaService:
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
             )
@@ -2529,12 +2552,13 @@ class LogisticsDataQaService:
         sub_results: list[dict[str, Any]] = []
         merged_rows: list[dict[str, Any]] = []
         merged_columns: list[str] = ["section"]
+        decomposition_source = str(plan.filters.get("decomposition_source") or "rule_guardrail")
         calculation_logic = [
-            "先识别顶层并列子问题，再把每个子问题映射到既有受控 query_key。",
+            "由 LLM 先识别顶层并列子问题，规则层再把每个子问题映射到既有受控 query_key。",
             "每个子查询独立执行仓储层确定性统计，最终仅在表达层合并结果，不做跨来源二次推理。",
         ]
         warnings = [
-            f"已将复合问题拆成 {len(sub_plan_payloads)} 个可独立审计的子问题分别查询后合并返回。",
+            f"已基于 {decomposition_source} 拆成 {len(sub_plan_payloads)} 个可独立审计的子问题分别查询后合并返回。",
             "历史高运费地址使用 2023-2025 历史台账口径；2026 系统侧采购方式发运量使用正式系统采购方式字段，两者不做跨源混算。",
         ]
         answer_parts: list[str] = []
```

## Verification summary
- focused logistics field scope: exit 0; tail:
```text
......                                                                   [100%]
6 passed in 0.32s
```
- logistics acceptance rerun: exit 0; tail:
```text
.................................................                        [100%]
49 passed in 1.99s
```
- full business_acceptance rerun: exit 0; tail:
```text
........................................................................ [ 47%]
........................................................................ [ 94%]
........                                                                 [100%]
=============================== warnings summary ===============================
tests/business_acceptance/test_plan_power_m3_prediction_engine.py::test_prediction_parity_for_ten_model_default_configurations
  /opt/anaconda3/lib/python3.12/site-packages/openpyxl/reader/excel.py:237: UserWarning: Unknown extension is not supported and will be removed
    ws_parser.bind_all()

tests/business_acceptance/test_plan_power_m3_prediction_engine.py::test_prediction_parity_for_ten_model_default_configurations
  /opt/anaconda3/lib/python3.12/site-packages/openpyxl/reader/excel.py:237: UserWarning: Conditional Formatting extension is not supported and will be removed
    ws_parser.bind_all()

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
152 passed, 2 warnings in 16.29s
```
- previous six failed tests rerun: exit 0; tail:
```text
........                                                                 [100%]
8 passed in 2.42s
```
- API smoke: exit 0; tail:
```text
2026-05-12 13:30:50,106 | INFO | 9e279930a70d40b6b65902ec3da93af7 | backend.app.qa_trace | qa_trace_event={"seq": 1, "time": "2026-05-12T13:30:50.106", "domain": "logistics", "trace_id": "9e279930a70d40b6b65902ec3da93af7", "stage": "input_received", "message": "收到物流问答用户问题。", "payload": {"question": "26年 经营计划 刘娟 用车总费用是多少"}}
2026-05-12 13:30:50,112 | INFO | 9e279930a70d40b6b65902ec3da93af7 | backend.app.qa_trace | qa_trace_event={"seq": 2, "time": "2026-05-12T13:30:50.112", "domain": "logistics", "trace_id": "9e279930a70d40b6b65902ec3da93af7", "stage": "rule_plan_built", "message": "规则 planner 已生成受控查询计划。", "payload": {"intent": "aggregate", "query_key": "sys_total_fee_by_filters", "metrics": ["total_fee"], "dimensions": [], "filters": {"year": 2026, "months": [], "expand_dept": "经营计划", "entrusted_person": "刘娟"}, "group_by": [], "limit": null, "needs_clarification": false, "clarification_missing_slots": [], "unsupported_category": null}}
2026-05-12 13:30:50,112 | INFO | 9e279930a70d40b6b65902ec3da93af7 | backend.app.qa_trace | qa_trace_event={"seq": 3, "time": "2026-05-12T13:30:50.112", "domain": "logistics", "trace_id": "9e279930a70d40b6b65902ec3da93af7", "stage": "guardrail_checked", "message": "LLM 候选理解和 Guardrail 校验已完成。", "payload": {"final_plan": {"intent": "aggregate", "query_key": "sys_total_fee_by_filters", "metrics": ["total_fee"], "dimensions": [], "filters": {"year": 2026, "months": [], "expand_dept": "经营计划", "entrusted_person": "刘娟"}, "group_by": [], "limit": null, "needs_clarification": false, "clarification_missing_slots": [], "unsupported_category": null}, "guardrail": {"assist_applied": false, "final_source": "rule", "final_intent": "aggregate", "final_query_key": "sys_total_fee_by_filters", "final_supported": true, "final_needs_clarification": false, "blocked_reason": null, "rollback_reason": null, "llm_provider_mode": "disabled", "llm_confidence": 0.0}}}
2026-05-12 13:30:50,112 | INFO | 9e279930a70d40b6b65902ec3da93af7 | backend.app.qa_trace | qa_trace_event={"seq": 4, "time": "2026-05-12T13:30:50.112", "domain": "logistics", "trace_id": "9e279930a70d40b6b65902ec3da93af7", "stage": "branch_selected", "message": "问题进入 A 类或空结果确定性查询分支。", "payload": {"intent": "aggregate", "query_key": "sys_total_fee_by_filters"}}
2026-05-12 13:30:50,112 | INFO | 9e279930a70d40b6b65902ec3da93af7 | backend.app.qa_trace | qa_trace_event={"seq": 5, "time": "2026-05-12T13:30:50.112", "domain": "logistics", "trace_id": "9e279930a70d40b6b65902ec3da93af7", "stage": "query_result_ready", "message": "确定性查询结果已生成。", "payload": {"status": {"code": "OK", "message": "2026年扩充部门=经营计划委托人=刘娟按当前系统口径统计的总运费为1,234.56元。", "success": true, "severity": "info"}, "supported": true, "needs_clarification": false, "row_count": 1, "answer_summary": "2026年扩充部门=经营计划委托人=刘娟按当前系统口径统计的总运费为1,234.56元。", "warnings": []}}
2026-05-12 13:30:50,164 | INFO | 9e279930a70d40b6b65902ec3da93af7 | backend.app.qa_trace | qa_trace_event={"seq": 6, "time": "2026-05-12T13:30:50.164", "domain": "logistics", "trace_id": "9e279930a70d40b6b65902ec3da93af7", "stage": "presentation_ready", "message": "答案展示内容已生成。", "payload": {"display_type": "narrative", "title": "查询结果", "answer": "2026年扩充部门=经营计划委托人=刘娟按当前系统口径统计的总运费为1,234.56元。"}}
2026-05-12 13:30:50,164 | INFO | 9e279930a70d40b6b65902ec3da93af7 | backend.app.qa_trace | qa_trace_event={"seq": 7, "time": "2026-05-12T13:30:50.164", "domain": "logistics", "trace_id": "9e279930a70d40b6b65902ec3da93af7", "stage": "history_snapshot_writing", "message": "准备写入统一查询历史快照。", "payload": {"trace_id": "9e279930a70d40b6b65902ec3da93af7", "row_count": 1}}
2026-05-12 13:30:50,164 | INFO | 9e279930a70d40b6b65902ec3da93af7 | backend.app.qa_trace | qa_trace_event={"seq": 8, "time": "2026-05-12T13:30:50.164", "domain": "logistics", "trace_id": "9e279930a70d40b6b65902ec3da93af7", "stage": "history_snapshot_written", "message": "统一查询历史快照写入完成。", "payload": {"history_log_id": null, "history_ready": false}}
2026-05-12 13:30:50,165 | INFO | 9e279930a70d40b6b65902ec3da93af7 | backend.app.middleware.request_context | request_id=9e279930a70d40b6b65902ec3da93af7 method=POST path=/api/v1/logistics/data-qa/query status=200 cost_ms=59.82
2026-05-12 13:30:50,165 | INFO | - | httpx | HTTP Request: POST http://testserver/api/v1/logistics/data-qa/query "HTTP/1.1 200 OK"
2026-05-12 13:30:50,166 | INFO | 36b84b0dd06d470fa1c12e0bcaf1f6ff | backend.app.qa_trace | qa_trace_event={"seq": 1, "time": "2026-05-12T13:30:50.166", "domain": "logistics", "trace_id": "36b84b0dd06d470fa1c12e0bcaf1f6ff", "stage": "input_received", "message": "收到物流问答用户问题。", "payload": {"question": "26年 经营计划 张三 用车总费用是多少"}}
2026-05-12 13:30:50,166 | INFO | 36b84b0dd06d470fa1c12e0bcaf1f6ff | backend.app.qa_trace | qa_trace_event={"seq": 2, "time": "2026-05-12T13:30:50.166", "domain": "logistics", "trace_id": "36b84b0dd06d470fa1c12e0bcaf1f6ff", "stage": "rule_plan_built", "message": "规则 planner 已生成受控查询计划。", "payload": {"intent": "clarification", "query_key": null, "metrics": [], "dimensions": [], "filters": {}, "group_by": [], "limit": null, "needs_clarification": true, "clarification_missing_slots": ["字段口径"], "unsupported_category": null}}
2026-05-12 13:30:50,166 | INFO | 36b84b0dd06d470fa1c12e0bcaf1f6ff | backend.app.qa_trace | qa_trace_event={"seq": 3, "time": "2026-05-12T13:30:50.166", "domain": "logistics", "trace_id": "36b84b0dd06d470fa1c12e0bcaf1f6ff", "stage": "guardrail_checked", "message": "LLM 候选理解和 Guardrail 校验已完成。", "payload": {"final_plan": {"intent": "clarification", "query_key": null, "metrics": [], "dimensions": [], "filters": {}, "group_by": [], "limit": null, "needs_clarification": true, "clarification_missing_slots": ["字段口径"], "unsupported_category": null}, "guardrail": {"assist_applied": false, "final_source": "rule", "final_intent": "clarification", "final_query_key": null, "final_supported": false, "final_needs_clarification": true, "blocked_reason": null, "rollback_reason": null, "llm_provider_mode": "disabled", "llm_confidence": 0.0}}}
2026-05-12 13:30:50,166 | INFO | 36b84b0dd06d470fa1c12e0bcaf1f6ff | backend.app.qa_trace | qa_trace_event={"seq": 4, "time": "2026-05-12T13:30:50.166", "domain": "logistics", "trace_id": "36b84b0dd06d470fa1c12e0bcaf1f6ff", "stage": "branch_selected", "message": "问题进入 B 类追问分支。", "payload": {"intent": "clarification", "missing_slots": ["字段口径"], "clarification_category": "field_scope_mapping"}}
2026-05-12 13:30:50,167 | INFO | 36b84b0dd06d470fa1c12e0bcaf1f6ff | backend.app.qa_trace | qa_trace_event={"seq": 5, "time": "2026-05-12T13:30:50.167", "domain": "logistics", "trace_id": "36b84b0dd06d470fa1c12e0bcaf1f6ff", "stage": "query_result_ready", "message": "确定性查询结果已生成。", "payload": {"status": {"code": "CLARIFICATION_REQUIRED", "message": "问题中的“张三”没有受控字段映射，不能默认查全量或套用其他特殊口径。", "success": false, "severity": "warning"}, "supported": false, "needs_clarification": true, "row_count": 0, "answer_summary": "问题中的“张三”没有受控字段映射，不能默认查全量或套用其他特殊口径。", "warnings": ["当前问题需要澄清后才能继续查询。"]}}
2026-05-12 13:30:50,209 | INFO | 36b84b0dd06d470fa1c12e0bcaf1f6ff | backend.app.qa_trace | qa_trace_event={"seq": 6, "time": "2026-05-12T13:30:50.209", "domain": "logistics", "trace_id": "36b84b0dd06d470fa1c12e0bcaf1f6ff", "stage": "presentation_ready", "message": "答案展示内容已生成。", "payload": {"display_type": "clarification", "title": "还需要补充几个条件", "answer": "问题中的“张三”没有受控字段映射，不能默认查全量或套用其他特殊口径。"}}
2026-05-12 13:30:50,209 | INFO | 36b84b0dd06d470fa1c12e0bcaf1f6ff | backend.app.qa_trace | qa_trace_event={"seq": 7, "time": "2026-05-12T13:30:50.209", "domain": "logistics", "trace_id": "36b84b0dd06d470fa1c12e0bcaf1f6ff", "stage": "history_snapshot_writing", "message": "准备写入统一查询历史快照。", "payload": {"trace_id": "36b84b0dd06d470fa1c12e0bcaf1f6ff", "row_count": 0}}
2026-05-12 13:30:50,209 | INFO | 36b84b0dd06d470fa1c12e0bcaf1f6ff | backend.app.qa_trace | qa_trace_event={"seq": 8, "time": "2026-05-12T13:30:50.209", "domain": "logistics", "trace_id": "36b84b0dd06d470fa1c12e0bcaf1f6ff", "stage": "history_snapshot_written", "message": "统一查询历史快照写入完成。", "payload": {"history_log_id": null, "history_ready": false}}
2026-05-12 13:30:50,209 | INFO | 36b84b0dd06d470fa1c12e0bcaf1f6ff | backend.app.middleware.request_context | request_id=36b84b0dd06d470fa1c12e0bcaf1f6ff method=POST path=/api/v1/logistics/data-qa/query status=200 cost_ms=43.67
2026-05-12 13:30:50,210 | INFO | - | httpx | HTTP Request: POST http://testserver/api/v1/logistics/data-qa/query "HTTP/1.1 200 OK"
API smoke passed: field filters and clarification verified
```
- browser smoke: PASS; see `browser-smoke-final.log`.
- compileall: exit 0; tail:
```text

```
- frontend build: exit 0; tail:
```text
vite v5.4.21 building for production...
transforming...
✓ 1702 modules transformed.
rendering chunks...
computing gzip size...
dist/index.html                                          0.57 kB │ gzip:   0.53 kB
dist/assets/DetailViewPage-DY6vuC3-.css                  0.21 kB │ gzip:   0.14 kB
dist/assets/ResultTable-C3CCB_Jw.css                     0.31 kB │ gzip:   0.20 kB
dist/assets/QueryHistoryPage-C4hz88b1.css                0.52 kB │ gzip:   0.26 kB
dist/assets/TrialGuidePage-Bu03moO8.css                  0.81 kB │ gzip:   0.38 kB
dist/assets/QueryResultCard-CapIsKq4.css                 2.59 kB │ gzip:   0.68 kB
dist/assets/LogisticsDataQaHistoryPage-Dod3diRj.css      3.13 kB │ gzip:   0.88 kB
dist/assets/NLQueryPage-CECbktQu.css                     5.95 kB │ gzip:   1.53 kB
dist/assets/PlanBomDetailQueryPage-CJszgW3Q.css          9.46 kB │ gzip:   2.02 kB
dist/assets/BomDataManagementPage-BPJXPlhE.css          11.26 kB │ gzip:   2.44 kB
dist/assets/BusinessChatPage-C8qOkOSq.css               15.92 kB │ gzip:   3.53 kB
dist/assets/index-CewzllaG.css                         362.19 kB │ gzip:  49.72 kB
dist/assets/queryStorage-DDqzaUkk.js                     0.59 kB │ gzip:   0.27 kB
dist/assets/logistics-Ckzwni0R.js                        0.72 kB │ gzip:   0.32 kB
dist/assets/TrialGuidePage-oul2Hai0.js                   0.93 kB │ gzip:   0.66 kB
dist/assets/planBom-CR6XsoqP.js                          1.38 kB │ gzip:   0.58 kB
dist/assets/TaskPage-Bhb6mTE4.js                         2.19 kB │ gzip:   1.05 kB
dist/assets/ResultTable-Bm7xWjoO.js                      4.50 kB │ gzip:   2.42 kB
dist/assets/LogisticsDataQaHistoryPage-B9SCGbcY.js       6.18 kB │ gzip:   3.09 kB
dist/assets/DetailViewPage-ouv_i0AK.js                   6.87 kB │ gzip:   2.54 kB
dist/assets/StructuredQueryPage-8ClOK7N7.js              6.93 kB │ gzip:   2.55 kB
dist/assets/QueryHistoryPage-uLRpkXRW.js                 9.84 kB │ gzip:   3.88 kB
dist/assets/NLQueryPage-CY3NS4li.js                     10.16 kB │ gzip:   4.50 kB
dist/assets/QueryResultCard-CzGwOgAJ.js                 14.95 kB │ gzip:   5.35 kB
dist/assets/BomDataManagementPage-BtpfFR_e.js           17.06 kB │ gzip:   6.18 kB
dist/assets/PlanBomDetailQueryPage-AQHG0SMJ.js          18.15 kB │ gzip:   6.84 kB
dist/assets/streamingApi-D7Wkp-n8.js                    39.24 kB │ gzip:  15.86 kB
dist/assets/BusinessChatPage-CGo4DUVl.js               659.83 kB │ gzip: 335.94 kB
dist/assets/index-D5bXwcea.js                        1,028.82 kB │ gzip: 339.95 kB

(!) Some chunks are larger than 500 kB after minification. Consider:
- Using dynamic import() to code-split the application
- Use build.rollupOptions.output.manualChunks to improve chunking: https://rollupjs.org/configuration-options/#output-manualchunks
- Adjust chunk size limit for this warning via build.chunkSizeWarningLimit.
✓ built in 3.12s
```

## Review focus
1. Any hardcoding of single answer instead of generic field/alias mapping?
2. Could known aliases wrongly trigger clarification?
3. Could unknown terms be silently ignored and return all-data results?
4. Is repository SQL parameterized and scoped to intended columns?
5. Any regression risk to logistics/Plan BOM tests based on the reruns?
