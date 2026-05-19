# Review Bundle — LLM 主导综合型问题拆分（第六轮采购方式残留校验后）

## 最新返工说明
第五轮 reviewer 阻塞点：采购方式 source_clause 只检查第一个采购方式词前缀，`询比价和海尔招标` / `询比价和上海招标` 这类限定出现在第二个采购方式词附近时仍可能被静默降级为全局统计。

本轮新增修复：
- `_procurement_clause_has_unsupported_business_residue`：对采购方式 source_clause 做全句残留校验，剥离年份、动作词、连接词、采购方式词、发运量/MW 口径词后，若仍有业务实体残留则 fail-closed。
- 新增测试 `test_llm_led_decomposition_rejects_procurement_clause_with_nonfirst_implicit_qualifier`，覆盖 `询比价和海尔招标`。

## 测试/扫描摘要
```text
19 passed in 0.95s
=============================== warnings summary ===============================
-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
168 passed, 2 warnings in 25.08s
compile checks passed
✓ built in 3.19s
tracked diff whitespace check passed
/opt/anaconda3/bin/python: No module named ruff
added-line static scan findings: 0
```

## Guardrail evaluate 完整关键分支（policy exception + candidate gating）
```python
   90|    def evaluate(
   91|        self,
   92|        *,
   93|        question: str,
   94|        rule_plan: LogisticsDataQaPlan,
   95|        llm_result: LogisticsLlmUnderstandingResult | None = None,
   96|        trace_id: str | None = None,
   97|        write_audit: bool = True,
   98|    ) -> LogisticsLlmGuardrailDecision:
   99|        """评估当前问题是否允许进入 LLM 候选增强。
  100|
  101|        说明：
  102|            1. 先看规则层是否已明确命中支持 / 澄清 / 不支持；
  103|            2. 只有“未命中正式 query_key、且只是通用兜底澄清”的问题才进入候选增强；
  104|            3. 进入增强后仍要求：单候选、高置信、白名单 query_key、非 B/C 语义。
  105|        """
  106|
  107|        sampled_in = self._is_sampled_in(question)
  108|        policy_decision = self.response_policy.match(question)
  109|        composite_policy_assist_allowed = (
  110|            policy_decision is not None
  111|            and policy_decision.decision_type == "unsupported"
  112|            and policy_decision.category in self.COMPOSITE_POLICY_ASSIST_CATEGORIES
  113|        )
  114|        decision = LogisticsLlmGuardrailDecision(
  115|            question=question,
  116|            guardrail_enabled=self.enabled,
  117|            guardrail_mode=self._normalize_mode(self.mode),
  118|            sampled_in=sampled_in,
  119|            rule_intent=rule_plan.intent,
  120|            rule_query_key=rule_plan.query_key,
  121|            rule_needs_clarification=rule_plan.needs_clarification,
  122|            rule_supported=rule_plan.intent not in {"clarification", "unsupported"},
  123|            final_intent=rule_plan.intent,
  124|            final_query_key=rule_plan.query_key,
  125|            final_needs_clarification=rule_plan.needs_clarification,
  126|            final_supported=rule_plan.intent not in {"clarification", "unsupported"},
  127|            allowed_query_key_whitelist=self.allowed_query_key_whitelist,
  128|        )
  129|
  130|        # Guardrail 未启用或当前不在抽样流量内时，直接保持规则裁决。
  131|        if not self.enabled:
  132|            decision.blocked_reason = "guardrail_disabled"
  133|            decision.rollback_reason = "global_switch_off"
  134|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  135|            return decision
  136|        if decision.guardrail_mode == "off":
  137|            decision.blocked_reason = "guardrail_mode_off"
  138|            decision.rollback_reason = "mode_off"
  139|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  140|            return decision
  141|        if not sampled_in:
  142|            decision.blocked_reason = "guardrail_not_sampled_in"
  143|            decision.rollback_reason = "sample_not_hit"
  144|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  145|            return decision
  146|        decision.entered_guardrail = True
  147|
  148|        # B/C 边界一旦被正式策略命中，默认完全锁定，不允许 LLM 继续改写。
  149|        # 例外：高运费地址 + 采购方式这类“可能是两个独立子问”的旧拒答策略，
  150|        # 允许 LLM 先给出顶层复合拆分候选，再由 planner 做字段能力和回指安全校验。
  151|        if policy_decision is not None:
  152|            decision.policy_decision_type = policy_decision.decision_type
  153|            decision.policy_category = policy_decision.category
  154|        if policy_decision is not None and not composite_policy_assist_allowed:
  155|            decision.policy_locked = True
  156|            decision.blocked_reason = f"policy_locked::{policy_decision.decision_type}::{policy_decision.category}"
  157|            decision.rollback_reason = "rule_policy_locked"
  158|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  159|            return decision
  160|
  161|        # 规则已经稳定命中 query_key 时，不需要任何 LLM 增强。
  162|        if rule_plan.query_key:
  163|            decision.blocked_reason = "rule_already_hit_query_key"
  164|            decision.rollback_reason = "rule_already_supported"
  165|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  166|            return decision
  167|
  168|        # 规则若已经明确不支持，也不允许 LLM 反向放行；复合拆分例外仍需后续 planner 校验。
  169|        if rule_plan.intent == "unsupported" and not composite_policy_assist_allowed:
  170|            decision.blocked_reason = "rule_declared_unsupported"
  171|            decision.rollback_reason = "rule_declared_unsupported"
  172|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  173|            return decision
  174|
  175|        # 只允许“通用兜底澄清”进入 A 类候选增强，专属澄清模板不允许被绕过；
  176|        # 复合拆分例外可以从旧拒答策略进入 LLM 候选，但最终必须回构成受控子查询。
  177|        if not rule_plan.needs_clarification and not composite_policy_assist_allowed:
  178|            decision.blocked_reason = "rule_not_in_generic_clarification"
  179|            decision.rollback_reason = "rule_not_generic_clarification"
  180|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  181|            return decision
  182|        if rule_plan.needs_clarification and not self._is_generic_clarification(rule_plan) and not composite_policy_assist_allowed:
  183|            decision.blocked_reason = "rule_specific_clarification_locked"
  184|            decision.rollback_reason = "rule_specific_clarification_locked"
  185|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  186|            return decision
  187|
  188|        decision.eligible_for_assist = True
  189|        decision.llm_invoked = llm_result is None
  190|        llm_output = llm_result or self.llm_service.understand(
  191|            question,
  192|            allowed_query_keys=self.allowed_query_key_whitelist,
  193|        )
  194|        decision.llm_intent = llm_output.intent
  195|        decision.llm_candidate_query_keys = llm_output.candidate_query_keys
  196|        decision.llm_top_query_key = llm_output.candidate_query_keys[0] if llm_output.candidate_query_keys else None
  197|        decision.llm_filters = llm_output.filters
  198|        decision.llm_time_range = llm_output.time_range
  199|        decision.llm_normalized_terms = llm_output.normalized_terms
  200|        decision.llm_confidence = llm_output.confidence
  201|        decision.llm_provider_mode = llm_output.provider_mode
  202|
  203|        # 只接受真实 live 结果，配置缺失或外部错误都不能放大为正式能力。
  204|        if llm_output.provider_mode != "live":
  205|            decision.blocked_reason = "llm_not_live"
  206|            decision.rollback_reason = "llm_not_live"
  207|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  208|            return decision
  209|
  210|        # 如果 LLM 自己判断成 B/C，也不允许它改写规则层，只能继续保持规则结论。
  211|        if llm_output.needs_clarification or llm_output.unsupported_reason:
  212|            decision.blocked_reason = "llm_requested_bc_boundary"
  213|            decision.rollback_reason = "llm_hit_bc_boundary"
  214|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  215|            return decision
  216|
  217|        if llm_output.intent not in self.ASSIST_ALLOWED_INTENTS:
  218|            decision.blocked_reason = "llm_intent_not_allowed"
  219|            decision.rollback_reason = "llm_intent_not_allowed"
  220|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  221|            return decision
  222|
  223|        if llm_output.confidence < self.min_confidence:
  224|            decision.blocked_reason = "llm_low_confidence"
  225|            decision.rollback_reason = "llm_low_confidence"
  226|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  227|            return decision
  228|
  229|        if len(llm_output.candidate_query_keys) != 1:
  230|            decision.blocked_reason = "llm_candidate_count_not_one"
  231|            decision.rollback_reason = "llm_candidate_count_not_one"
  232|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  233|            return decision
  234|
  235|        candidate_query_key = llm_output.candidate_query_keys[0]
  236|        if composite_policy_assist_allowed and candidate_query_key != "composite_decomposed":
  237|            # 复合策略例外只允许 LLM 回答“可拆为受控复合问题”，不能借 unsupported 边界改写成其它 A 类能力。
  238|            decision.blocked_reason = "composite_policy_requires_composite_candidate"
  239|            decision.rollback_reason = "composite_policy_requires_composite_candidate"
  240|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  241|            return decision
  242|        if candidate_query_key not in self.allowed_query_key_whitelist:
  243|            decision.blocked_reason = "llm_query_key_not_allowlisted"
  244|            decision.rollback_reason = "candidate_not_allowlisted"
  245|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  246|            return decision
  247|
  248|        decision.assist_recommended = True
  249|
  250|        # shadow 只记录可放行候选，不允许改动正式结果。
  251|        if decision.guardrail_mode == "shadow":
  252|            decision.blocked_reason = "shadow_mode_no_apply"
  253|            decision.rollback_reason = "shadow_mode_only_audit"
  254|            self._maybe_write_audit_log(trace_id=trace_id, decision=decision, write_audit=write_audit)
  255|            return decision
  256|
  257|        # 满足所有 guardrail 且处于 assist 模式时，才视为“正式受控候选增强”。
  258|        decision.assist_applied = True
  259|        decision.final_source = "llm_assist"
  260|        decision.final_query_key = candidate_query_key
  261|        decision.final_intent = self.ASSIST_ALLOWED_QUERY_KEYS[candidate_query_key]
  262|        decision.final_needs_clarification = False
```

## data_qa_planner.py: composite 回构入口
```python
 1208|            LLM 负责判断顶层并列子问题和给出子计划候选；本方法只做白名单、
 1209|            字段能力、年份来源和回指安全校验，不能再按关键词自行决定拆分。
 1210|        """
 1211|
 1212|        if "吨" in compact and any(keyword in compact for keyword in ("发运量", "运量", "发货量")):
 1213|            return None
 1214|
 1215|        decomposition = llm_result.filters if isinstance(llm_result.filters, dict) else {}
 1216|        sub_plan_payloads = decomposition.get("sub_plans")
 1217|        if not isinstance(sub_plan_payloads, list) or len(sub_plan_payloads) != 2:
 1218|            # LLM 只能给出当前已审计的两个顶层独立子问；额外/重复子问一律拒绝，
 1219|            # 避免静默丢弃用户意图造成漏答。
 1220|            return None
 1221|        if decomposition.get("decomposition_strategy") not in {"top_level_conjunction", "llm_top_level_conjunction"}:
 1222|            return None
 1223|        sub_query_keys = [payload.get("query_key") for payload in sub_plan_payloads if isinstance(payload, dict)]
 1224|        required_query_keys = {"hist_high_fee_addresses_by_customer", "sys_mw_by_procurement_type"}
 1225|        if set(sub_query_keys) != required_query_keys or len(sub_query_keys) != len(required_query_keys):
 1226|            return None
 1227|
 1228|        high_fee_payload = self._find_llm_sub_plan_payload(
 1229|            sub_plan_payloads,
 1230|            query_key="hist_high_fee_addresses_by_customer",
 1231|        )
 1232|        procurement_payload = self._find_llm_sub_plan_payload(
 1233|            sub_plan_payloads,
 1234|            query_key="sys_mw_by_procurement_type",
 1235|        )
 1236|        if high_fee_payload is None or procurement_payload is None:
 1237|            return None
 1238|
 1239|        high_fee_clause = self._extract_llm_source_clause(high_fee_payload)
 1240|        procurement_clause = self._extract_llm_source_clause(procurement_payload)
 1241|        if not high_fee_clause or not procurement_clause:
 1242|            return None
 1243|        if high_fee_clause not in compact or procurement_clause not in compact:
 1244|            # 每个 LLM 子句都必须可回溯到用户原文，防止幻觉子句补齐关键槽位。
 1245|            return None
 1246|        if not self._llm_source_clauses_cover_original_question(compact, [high_fee_clause, procurement_clause]):
 1247|            # LLM 漏报第三个顶层诉求时不能静默漏答；只能覆盖寒暄、标点和连接词。
 1248|            return None
 1249|        if not self._is_high_fee_address_clause(high_fee_clause):
 1250|            return None
 1251|        if self._high_fee_clause_contains_procurement_ask(high_fee_clause):
 1252|            # 高运费地址子句不能同时吞入采购方式发运量诉求，否则说明 LLM source_clause 过宽。
 1253|            return None
 1254|        if self._high_fee_clause_has_unsupported_qualifier(high_fee_clause):
 1255|            # 当前历史高运费地址子查询不支持区域、月份、承运商等额外限定，不能静默忽略。
 1256|            return None
 1257|        if not self._is_procurement_mw_clause(procurement_clause):
 1258|            return None
 1259|        high_fee_filters = high_fee_payload.get("filters") if isinstance(high_fee_payload.get("filters"), dict) else {}
 1260|        procurement_filters = procurement_payload.get("filters") if isinstance(procurement_payload.get("filters"), dict) else {}
 1261|        if self._filters_have_nonempty_unsupported_keys(
 1262|            high_fee_filters,
 1263|            allowed_filter_keys={"year", "customer_name", "threshold_fee"},
 1264|        ):
 1265|            # 高运费地址子查询只支持年、客户、金额阈值；LLM 额外 filters 不能静默丢弃。
 1266|            return None
 1267|        if self._procurement_clause_has_unsupported_filter(procurement_clause, procurement_filters):
 1268|            # 当前 sys_mw_by_procurement_type 仅支持全局采购方式 MW，不支持客户/区域/承运商等下推限定。
 1269|            return None
 1270|        if self._is_historical_procurement_split_request(compact, high_fee_clause, procurement_clause):
 1271|            return None
 1272|
 1273|        source_high_fee_year = self._extract_year(high_fee_clause)
 1274|        llm_high_fee_year = self._coerce_int(high_fee_filters.get("year"))
 1275|        if source_high_fee_year not in {2023, 2024, 2025}:
 1276|            return None
 1277|        if llm_high_fee_year is not None and llm_high_fee_year != source_high_fee_year:
 1278|            return None
 1279|        high_fee_year = source_high_fee_year
 1280|
 1281|        source_customer_name = self._extract_high_fee_customer_name(high_fee_clause) or self._extract_customer_name(high_fee_clause)
 1282|        llm_customer_name = str(high_fee_filters.get("customer_name") or "").strip()
 1283|        if not source_customer_name or len(source_customer_name) <= 1:
 1284|            return None
 1285|        if llm_customer_name and llm_customer_name != source_customer_name:
 1286|            return None
 1287|        customer_name = source_customer_name
 1288|        if self._procurement_clause_has_unsupported_filter(
 1289|            procurement_clause,
 1290|            procurement_filters,
 1291|            known_customer_name=customer_name,
 1292|        ):
 1293|            # 采购方式子句若隐式复用历史客户名，也属于当前全局 query_key 不支持的限定。
 1294|            return None
 1295|
 1296|        source_threshold_fee = self._extract_fee_threshold_yuan(high_fee_clause)
 1297|        llm_threshold_fee = self._coerce_int(high_fee_filters.get("threshold_fee"))
 1298|        if not source_threshold_fee:
 1299|            return None
 1300|        if llm_threshold_fee is not None and llm_threshold_fee != source_threshold_fee:
 1301|            return None
 1302|        threshold_fee = source_threshold_fee
 1303|
 1304|        source_procurement_year = self._extract_year(procurement_clause)
 1305|        llm_procurement_year = self._coerce_int(procurement_filters.get("year"))
 1306|        if source_procurement_year in {2023, 2024, 2025}:
 1307|            return None
 1308|        if llm_procurement_year is not None and llm_procurement_year != 2026:
 1309|            return None
 1310|        if source_procurement_year is not None and source_procurement_year != 2026:
 1311|            return None
 1312|        procurement_year = 2026
 1313|
 1314|        high_fee_plan = LogisticsDataQaPlan(
 1315|            intent="detail_list",
 1316|            query_key="hist_high_fee_addresses_by_customer",
 1317|            metrics=["total_fee", "shipment_mw"],
 1318|            dimensions=["address"],
 1319|            filters={"year": high_fee_year, "customer_name": customer_name, "threshold_fee": threshold_fee},
 1320|            group_by=["address"],
 1321|            sort=[{"field": "total_fee", "direction": "desc"}],
 1322|        )
 1323|        procurement_plan = LogisticsDataQaPlan(
 1324|            intent="aggregate",
 1325|            query_key="sys_mw_by_procurement_type",
 1326|            metrics=["shipment_mw"],
 1327|            dimensions=["procurement_type"],
 1328|            filters={"year": procurement_year, "default_system_year": procurement_year == 2026 and self._extract_year(procurement_clause) is None},
 1329|            group_by=["procurement_type"],
 1330|            sort=[{"field": "shipment_mw", "direction": "desc"}],
 1331|        )
 1332|        return LogisticsDataQaPlan(
 1333|            intent="composite",
 1334|            query_key="composite_decomposed",
 1335|            metrics=["total_fee", "shipment_mw"],
 1336|            dimensions=["section"],
 1337|            filters={
 1338|                "decomposition_strategy": "top_level_conjunction",
```

## data_qa_planner.py: source_clause span/字段能力边界校验辅助
```python
 1357|            匹配到的子计划字典；未匹配时返回 None。
 1358|        """
 1359|
 1360|        for payload in sub_plan_payloads:
 1361|            if isinstance(payload, dict) and payload.get("query_key") == query_key:
 1362|                return payload
 1363|        return None
 1364|
 1365|    @staticmethod
 1366|    def _extract_llm_source_clause(payload: dict[str, Any]) -> str:
 1367|        """提取 LLM 子计划对应的原始子句。
 1368|
 1369|        参数：
 1370|            payload: 单个 LLM 子计划候选。
 1371|        返回值：
 1372|            去空白后的原始子句；如果没有可审计子句则返回空字符串。
 1373|        """
 1374|
 1375|        source_clause = payload.get("source_clause") or payload.get("clause") or payload.get("question")
 1376|        return re.sub(r"\s+", "", str(source_clause or "").strip())
 1377|
 1378|    @staticmethod
 1379|    def _llm_source_clauses_cover_original_question(compact: str, source_clauses: list[str]) -> bool:
 1380|        """校验 LLM 子句是否以互不重叠的原文片段覆盖全部实质诉求。
 1381|
 1382|        参数：
 1383|            compact: 去空白后的原始问题。
 1384|            source_clauses: LLM 返回且已确认出现在原文中的子句。
 1385|        返回值：
 1386|            若所有 source_clause 都能定位为非重叠 span，且移除后只剩寒暄、标点、连接词，返回 True。
 1387|        业务逻辑：LLM 可以主导拆分，但不能用整句/重叠片段掩盖漏报子问。
 1388|        """
 1389|
 1390|        if not compact or len(set(source_clauses)) != len(source_clauses):
 1391|            return False
 1392|        for clause in source_clauses:
 1393|            if not clause or clause == compact:
 1394|                return False
 1395|        for index, clause in enumerate(source_clauses):
 1396|            for other_index, other_clause in enumerate(source_clauses):
 1397|                if index != other_index and other_clause in clause:
 1398|                    return False
 1399|
 1400|        spans = LogisticsDataQaPlanner._locate_non_overlapping_source_spans(compact, source_clauses)
 1401|        if spans is None:
 1402|            return False
 1403|        covered = [False] * len(compact)
 1404|        for start, end in spans:
 1405|            for position in range(start, end):
 1406|                if covered[position]:
 1407|                    return False
 1408|                covered[position] = True
 1409|        residue = "".join(char for position, char in enumerate(compact) if not covered[position])
 1410|        residue = re.sub(r"[\s，,；;。.!！?？：:、]", "", residue)
 1411|        residue = re.sub(
 1412|            r"(?:请|帮我|帮忙|麻烦|统计一下|统计|查询|查一下|看一下|列出|并且|并|同时|另外|再|以及|和|把|将|分别|一下|的)",
 1413|            "",
 1414|            residue,
 1415|        )
 1416|        return residue == ""
 1417|
 1418|    @staticmethod
 1419|    def _locate_non_overlapping_source_spans(compact: str, source_clauses: list[str]) -> list[tuple[int, int]] | None:
 1420|        """为 LLM source_clause 寻找互不重叠的原文区间。
 1421|
 1422|        参数：
 1423|            compact: 去空白后的原始问题。
 1424|            source_clauses: LLM 子句列表。
 1425|        返回值：
 1426|            成功时返回 `(start, end)` 区间列表；无法找到非重叠定位时返回 None。
 1427|        """
 1428|
 1429|        occurrences: list[list[tuple[int, int]]] = []
 1430|        for clause in source_clauses:
 1431|            clause_occurrences = [(match.start(), match.end()) for match in re.finditer(re.escape(clause), compact)]
 1432|            if not clause_occurrences:
 1433|                return None
 1434|            occurrences.append(clause_occurrences)
 1435|
 1436|        def backtrack(index: int, selected: list[tuple[int, int]]) -> list[tuple[int, int]] | None:
 1437|            """递归选择互不重叠的 source_clause 区间。"""
 1438|
 1439|            if index >= len(occurrences):
 1440|                return selected
 1441|            for span in occurrences[index]:
 1442|                if all(span[1] <= chosen[0] or span[0] >= chosen[1] for chosen in selected):
 1443|                    resolved = backtrack(index + 1, [*selected, span])
 1444|                    if resolved is not None:
 1445|                        return resolved
 1446|            return None
 1447|
 1448|        return backtrack(0, [])
 1449|
 1450|    @staticmethod
 1451|    def _high_fee_clause_contains_procurement_ask(clause: str) -> bool:
 1452|        """判断高运费地址子句是否误吞了采购方式发运量诉求。"""
 1453|
 1454|        return any(keyword in clause for keyword in ("询比价", "招标", "采购方式")) and any(
 1455|            keyword in clause for keyword in ("发运量", "运量", "发货量")
 1456|        )
 1457|
 1458|    @staticmethod
 1459|    def _high_fee_clause_has_unsupported_qualifier(clause: str) -> bool:
 1460|        """判断历史高运费地址子句是否包含当前查询无法下推的限定。"""
 1461|
 1462|        if re.search(r"(?:\d{1,2}|[一二三四五六七八九十]{1,3})月", clause):
 1463|            return True
 1464|        unsupported_keywords = (
 1465|            "区域",
 1466|            "地区",
 1467|            "华东",
 1468|            "华南",
 1469|            "华北",
 1470|            "华中",
 1471|            "西南",
 1472|            "西北",
 1473|            "东北",
 1474|            "基地",
 1475|            "园区",
 1476|            "工厂",
 1477|            "起运",
 1478|            "承运商",
 1479|            "物流公司",
 1480|            "物流供应商",
 1481|        )
 1482|        return any(keyword in clause for keyword in unsupported_keywords)
 1483|
 1484|    @staticmethod
 1485|    def _filters_have_nonempty_unsupported_keys(filters: dict[str, Any], *, allowed_filter_keys: set[str]) -> bool:
 1486|        """判断 LLM filters 是否包含当前子查询无法执行的非空键。
 1487|
 1488|        参数：
 1489|            filters: LLM 子计划 filters。
 1490|            allowed_filter_keys: 当前确定性子查询真正支持的 filter key。
 1491|        返回值：
 1492|            发现非空且不在白名单内的 key 时返回 True。
 1493|        """
 1494|
 1495|        for key, value in filters.items():
 1496|            if key in allowed_filter_keys:
 1497|                continue
 1498|            if value is None or value == "" or value == [] or value == {}:
 1499|                continue
 1500|            return True
 1501|        return False
 1502|
 1503|    @staticmethod
 1504|    def _procurement_clause_has_unsupported_filter(
 1505|        clause: str,
 1506|        filters: dict[str, Any],
 1507|        *,
 1508|        known_customer_name: str | None = None,
 1509|    ) -> bool:
 1510|        """判断采购方式全局统计子句是否携带当前无法下推的额外限定。
 1511|
 1512|        参数：
 1513|            clause: LLM 识别出的采购方式发运量原文子句。
 1514|            filters: LLM 给出的采购方式子计划 filters。
 1515|            known_customer_name: 已从同一原问题其它子句确定的客户名，用于识别无“客户”后缀的隐式限定。
 1516|        返回值：
 1517|            若出现客户、区域、承运商、地址、月份等全局统计不支持的限定，返回 True。
 1518|        """
 1519|
 1520|        if LogisticsDataQaPlanner._filters_have_nonempty_unsupported_keys(
 1521|            filters,
 1522|            allowed_filter_keys={"year", "default_system_year"},
 1523|        ):
 1524|            return True
 1525|        if known_customer_name and known_customer_name in clause:
 1526|            return True
 1527|        if LogisticsDataQaPlanner._procurement_clause_has_unsupported_business_residue(clause):
 1528|            return True
 1529|        if LogisticsDataQaPlanner._procurement_clause_has_leading_unsupported_qualifier(clause):
 1530|            return True
 1531|        if re.search(r"(?:\d{1,2}|[一二三四五六七八九十]{1,3})月", clause):
 1532|            return True
 1533|        unsupported_keywords = (
 1534|            "客户",
 1535|            "区域",
 1536|            "地区",
 1537|            "华东",
 1538|            "华南",
 1539|            "华北",
 1540|            "华中",
 1541|            "西南",
 1542|            "西北",
 1543|            "东北",
 1544|            "省",
 1545|            "市",
 1546|            "基地",
 1547|            "园区",
 1548|            "工厂",
 1549|            "起运",
 1550|            "承运商",
 1551|            "物流公司",
 1552|            "物流供应商",
 1553|            "收货地址",
 1554|            "地址",
 1555|            "项目地",
 1556|            "这些",
 1557|            "上述",
 1558|            "上面",
 1559|            "前述",
 1560|            "该批",
 1561|        )
 1562|        return any(keyword in clause for keyword in unsupported_keywords)
 1563|
 1564|    @staticmethod
 1565|    def _procurement_clause_has_unsupported_business_residue(clause: str) -> bool:
 1566|        """剥离采购方式子句中的受支持词后，检查是否残留业务限定。
 1567|
 1568|        参数：
 1569|            clause: 采购方式发运量原文子句。
 1570|        返回值：
 1571|            若剥离动作词、年份、采购方式词、发运量/MW 口径词后仍有实体残留，返回 True。
 1572|        业务逻辑：覆盖 `询比价和海尔招标` 这类限定出现在第二个采购方式词附近的表达。
 1573|        """
 1574|
 1575|        residue = clause
 1576|        residue = re.sub(r"(?:20\d{2}|\d{2})年", "", residue)
 1577|        residue = re.sub(r"询比价|招标|采购方式", "", residue)
 1578|        residue = re.sub(
 1579|            r"(?:请|帮我|帮忙|麻烦|统计一下|统计|查询|查一下|看一下|列出|并且|并|同时|另外|再|以及|和|把|将|分别|一下|的|按|以|根据|对应|发运量|运量|发货量|MW|兆瓦)",
 1580|            "",
 1581|            residue,
 1582|        )
 1583|        residue = re.sub(r"[\s，,；;。.!！?？：:、]", "", residue)
 1584|        return residue != ""
 1585|
 1586|    @staticmethod
 1587|    def _procurement_clause_has_leading_unsupported_qualifier(clause: str) -> bool:
 1588|        """识别采购方式关键词前方无法下推的隐式限定。
 1589|
 1590|        参数：
 1591|            clause: 采购方式发运量原文子句。
 1592|        返回值：
 1593|            若 `询比价/招标/采购方式` 前仍残留客户、地点、基地等限定文本，返回 True。
 1594|        业务逻辑：`创维询比价发运量`、`常熟基地询比价发运量` 这类表达即使 LLM 未给 filters，也不能查全局。
 1595|        """
 1596|
 1597|        match = re.search(r"询比价|招标|采购方式", clause)
 1598|        if match is None:
 1599|            return False
 1600|        leading = clause[: match.start()]
 1601|        leading = re.sub(r"(?:20\d{2}|\d{2})年", "", leading)
 1602|        leading = re.sub(r"(?:\d{1,2}|[一二三四五六七八九十]{1,3})月", "月份", leading)
 1603|        leading = re.sub(
 1604|            r"(?:请|帮我|帮忙|麻烦|统计一下|统计|查询|查一下|看一下|列出|并且|并|同时|另外|再|以及|和|把|将|分别|一下|的|按|以|根据|发运量|运量|发货量|MW|兆瓦)",
 1605|            "",
```

## data_qa_planner.py: 回指/历史子集拆分保护完整片段
```python
 1605|            "",
 1606|            leading,
 1607|        )
 1608|        leading = re.sub(r"[\s，,；;。.!！?？：:、]", "", leading)
 1609|        return leading != ""
 1610|
 1611|    @staticmethod
 1612|    def _coerce_int(value: Any) -> int | None:
 1613|        """把 LLM 输出中的整数槽位安全转成 int。
 1614|
 1615|        参数：
 1616|            value: LLM 输出的候选值。
 1617|        返回值：
 1618|            可用整数；转换失败或值为空时返回 None。
 1619|        """
 1620|
 1621|        if value in {None, ""}:
 1622|            return None
 1623|        try:
 1624|            return int(float(value))
 1625|        except (TypeError, ValueError):
 1626|            return None
 1627|
 1628|    @staticmethod
 1629|    def _split_composite_clauses(compact: str) -> list[str]:
 1630|        """按顶层并列连接词拆分复合问题子句。"""
 1631|
 1632|        clauses = re.split(r"(?:，|,|；|;|。)?(?:并且|并|同时|另外|再|以及)", compact)
 1633|        return [clause for clause in clauses if clause]
 1634|
 1635|    @staticmethod
 1636|    def _is_high_fee_address_clause(clause: str) -> bool:
 1637|        """判断子句是否是历史高运费收货地址清单。"""
 1638|
 1639|        return (
 1640|            any(keyword in clause for keyword in ("收货地址", "项目地"))
 1641|            and any(keyword in clause for keyword in ("运费", "运输费用"))
 1642|            and "超过" in clause
 1643|            and "万" in clause
 1644|        )
 1645|
 1646|    def _is_procurement_mw_clause(self, clause: str) -> bool:
 1647|        """判断子句是否是采购方式发运量统计。"""
 1648|
```

## llm_understanding_guardrail_service.py: allowlist
```python
   35|        "hist_total_fee_by_origin_and_carrier": "aggregate",
   36|        "sys_mw_and_trip_count": "aggregate",
   37|        "hist_trip_count_by_region": "aggregate",
   38|        "hist_quantity_by_region": "aggregate",
   39|        "hist_customer_mw": "aggregate",
   40|        "hist_vehicle_type_trip_count": "aggregate",
   41|        "sys_signedfor_rate_by_carrier": "ranking",
   42|        "hist_multi_origin_customers": "detail_list",
   43|        "sys_companies_without_tasks": "detail_list",
   44|        "hist_plan_actual_deviation": "compare",
   45|        "sys_special_total_fee": "aggregate",
   46|        "composite_decomposed": "composite",
   47|    }
   48|    COMPOSITE_POLICY_ASSIST_CATEGORIES = {"high_fee_address_procurement_split"}
   49|    GENERIC_CLARIFICATION_QUESTIONS = (
   50|        "当前 MVP 只支持时间聚合、区域筛选、承运商排名、费用/运量统计等结构化数据问题。",
   51|        "请补充明确的时间、指标和维度，例如“2025年华东区域总运费”或“2026年1月总发运量”。",
   52|    )
   53|    ASSIST_ALLOWED_INTENTS = {"aggregate", "ranking", "comparison", "detail", "composite", "unknown"}
   54|
   55|    def __init__(
   56|        self,
   57|        *,
   58|        llm_service: LogisticsLlmUnderstandingService | None = None,
   59|        response_policy: LogisticsQuestionBankResponsePolicy | None = None,
   60|        enabled: bool | None = None,
   61|        mode: str | None = None,
   62|        sample_rate: float | None = None,
   63|        min_confidence: float | None = None,
   64|        audit_enabled: bool | None = None,
   65|        audit_path: Path | None = None,
   66|    ) -> None:
   67|        """初始化 Guardrail 服务。
   68|
   69|        参数：
   70|            llm_service: 可注入的 LLM 理解层服务，便于测试和 PoC 脚本复用。
   71|            response_policy: 可注入的题库响应策略，保证 B/C 边界始终一致。
   72|            enabled: Guardrail 是否启用，默认读取 settings。
   73|            mode: Guardrail 当前运行模式，默认读取 settings。
   74|            sample_rate: 未来小流量 candidate assist 的抽样比例。
   75|            min_confidence: 允许 LLM 候选进入 A 类增强的最低置信度。
   76|            audit_enabled: 是否写 Guardrail 审计日志。
   77|            audit_path: Guardrail 审计日志文件路径。
   78|        """
   79|
   80|        self.llm_service = llm_service or LogisticsLlmUnderstandingService()
   81|        self.response_policy = response_policy or LogisticsQuestionBankResponsePolicy()
   82|        self.enabled = settings.llm_guardrail_enabled if enabled is None else enabled
   83|        self.mode = settings.llm_guardrail_mode if mode is None else mode
   84|        self.sample_rate = settings.llm_guardrail_sample_rate if sample_rate is None else sample_rate
   85|        self.min_confidence = settings.llm_guardrail_min_confidence if min_confidence is None else min_confidence
   86|        self.audit_enabled = settings.llm_guardrail_audit_enabled if audit_enabled is None else audit_enabled
   87|        self.audit_path = audit_path or (settings.log_root / "logistics_llm_guardrail_audit.jsonl")
   88|        self.allowed_query_key_whitelist = self._resolve_allowed_query_key_whitelist()
   89|
   90|    def evaluate(
   91|        self,
   92|        *,
```

## llm_understanding_service.py: query key / prompt / intent
```python
   70|        client: Any | None = None,
   71|        timeout_seconds: float = 15.0,
   72|    ) -> None:
   73|        """初始化 LLM 理解层。
   74|
   75|        参数：
   76|            base_url: 可选的 LLM 服务地址，默认读取 settings。
   77|            api_key: 可选的 LLM 密钥，默认读取 settings。
   78|            model: 可选的模型名，默认读取 settings。
   79|            client: 测试时可注入假的 OpenAI 客户端，避免真实外部调用。
   80|        """
   81|
   82|        self.base_url = base_url if base_url is not None else settings.llm_base_url
   83|        self.api_key = api_key if api_key is not None else settings.llm_api_key
   84|        self.model = model if model is not None else settings.llm_model
   85|        self._client = client
   86|        self.timeout_seconds = timeout_seconds
   87|
   88|    def is_enabled(self) -> bool:
   89|        """判断当前环境是否具备真实 LLM 调用配置。"""
   90|        return bool(self.base_url and self.api_key and self.model)
   91|
   92|    def understand(
   93|        self,
   94|        question: str,
   95|        *,
   96|        allowed_query_keys: list[str] | None = None,
   97|    ) -> LogisticsLlmUnderstandingResult:
   98|        """执行一次 LLM 理解。
   99|
  100|        说明：
  101|            1. 这里只输出候选理解结果，不直接进入 SQL；
  102|            2. allowed_query_keys 用于限制候选 query_key 白名单；
  103|            3. 若调用失败，返回 error 模式，便于 PoC 报告识别误判和可用性。
  104|        """
  105|
  106|        normalized_question = question.strip()
  107|        whitelist = allowed_query_keys or list(self.QUERY_KEY_WHITELIST.keys())
  108|        if not self.is_enabled():
  109|            return LogisticsLlmUnderstandingResult(
  110|                normalized_question=normalized_question,
  111|                intent="unknown",
  112|                provider_mode="disabled",
  113|                provider_error="当前环境未配置可用的 LLM_BASE_URL / LLM_API_KEY / LLM_MODEL。",
  114|            )
  115|
  116|        last_error: Exception | None = None
  117|        for _ in range(2):
  118|            try:
  119|                client = self._client or OpenAI(
  120|                    base_url=self.base_url,
  121|                    api_key=self.api_key,
  122|                    timeout=self.timeout_seconds,
  123|                    max_retries=0,
  124|                )
  125|                completion = client.chat.completions.create(

  220|        question: str,
  221|        payload: dict[str, Any],
  222|        whitelist: list[str],
  223|    ) -> LogisticsLlmUnderstandingResult:
  224|        """对模型输出做白名单清洗和字段兜底。"""
  225|        candidate_query_keys = [
  226|            item
  227|            for item in payload.get("candidate_query_keys", [])
  228|            if isinstance(item, str) and item in whitelist
  229|        ]
  230|        confidence = payload.get("confidence", 0.0)
  231|        try:
  232|            confidence = max(0.0, min(1.0, float(confidence)))
  233|        except Exception:  # noqa: BLE001
  234|            confidence = 0.0
  235|
  236|        intent = payload.get("intent", "unknown")
  237|        if intent not in {"aggregate", "ranking", "comparison", "detail", "composite", "clarification", "unsupported", "unknown"}:
  238|            intent = "unknown"
  239|
  240|        source_scope = payload.get("source_scope", "unknown")
  241|        if source_scope not in {"historical", "system_2026", "mixed", "unknown"}:
  242|            source_scope = "unknown"
  243|
  244|        normalized_terms = payload.get("normalized_terms", {})
  245|        if not isinstance(normalized_terms, dict):
  246|            normalized_terms = {}
  247|
  248|        clarification_questions = payload.get("clarification_questions", [])
  249|        if not isinstance(clarification_questions, list):
  250|            clarification_questions = []
  251|        clarification_questions = [item for item in clarification_questions if isinstance(item, str)]
  252|        unsupported_reason = payload.get("unsupported_reason")
  253|        needs_clarification = bool(payload.get("needs_clarification", False))
  254|
  255|        # 如果模型已经明确给出不支持原因，则统一收敛为 unsupported，避免一条结果同时落到澄清和不支持。
  256|        if unsupported_reason:
  257|            intent = "unsupported"
  258|            needs_clarification = False
  259|            clarification_questions = []
  260|
  261|        normalized_question = str(payload.get("normalized_question") or question).strip()
  262|        # 对高频 B 类模糊问法做理解层后处理：
  263|        # 如果模型把明显的“缺口径”问题误判成 unsupported，则统一拉回 clarification。
  264|        if self._should_convert_unsupported_to_clarification(
  265|            question=normalized_question,
  266|            unsupported_reason=unsupported_reason,
  267|            candidate_query_keys=candidate_query_keys,
  268|        ):
  269|            intent = "clarification"
  270|            needs_clarification = True
  271|            unsupported_reason = None
  272|            clarification_questions = self._build_business_clarification_questions(normalized_question)
  273|
  274|        # 对稳定 A 类 query_key，如果模型同时给出高置信单候选又保留澄清标记，
  275|        # 统一收敛成“候选增强可用”，避免因为模型过度保守而丢掉明显可识别的同构变体。
  276|        if (
  277|            len(candidate_query_keys) == 1
  278|            and candidate_query_keys[0] in self.QUERY_KEY_WHITELIST
  279|            and confidence >= 0.9
  280|            and not unsupported_reason
  281|            and needs_clarification
  282|        ):
  283|            needs_clarification = False
  284|            clarification_questions = []
  285|
  286|        return LogisticsLlmUnderstandingResult(
  287|            normalized_question=normalized_question,
  288|            intent=intent,
  289|            metrics=[item for item in payload.get("metrics", []) if isinstance(item, str)],
  290|            dimensions=[item for item in payload.get("dimensions", []) if isinstance(item, str)],
```

## llm_understanding schema: composite intent
```python
    1|from __future__ import annotations
    2|
    3|from typing import Any, Literal
    4|
    5|from pydantic import BaseModel, Field
    6|
    7|
    8|class LogisticsLlmUnderstandingResult(BaseModel):
    9|    """物流域 LLM 理解层输出结构。
   10|
   11|    说明：
   12|        1. 当前结构只用于影子模式 / PoC，不直接暴露给前端；
   13|        2. LLM 只能输出语言理解层候选，不允许直接生成 SQL 或最终业务答案；
   14|        3. candidate_query_keys 必须仍受现有白名单约束，最终裁决仍由规则层执行。
   15|    """
   16|
   17|    normalized_question: str = ""
   18|    intent: Literal[
   19|        "aggregate",
   20|        "ranking",
   21|        "comparison",
   22|        "detail",
   23|        "composite",
   24|        "clarification",
   25|        "unsupported",
   26|        "unknown",
   27|    ] = "unknown"
   28|    metrics: list[str] = Field(default_factory=list)
   29|    dimensions: list[str] = Field(default_factory=list)
   30|    filters: dict[str, Any] = Field(default_factory=dict)
   31|    time_range: dict[str, Any] = Field(default_factory=dict)
   32|    source_scope: Literal["historical", "system_2026", "mixed", "unknown"] = "unknown"
   33|    candidate_query_keys: list[str] = Field(default_factory=list)
   34|    normalized_terms: dict[str, str] = Field(default_factory=dict)
   35|    needs_clarification: bool = False
   36|    clarification_questions: list[str] = Field(default_factory=list)
   37|    unsupported_reason: str | None = None
   38|    confidence: float = 0.0
   39|    provider_mode: Literal["live", "disabled", "error"] = "disabled"
   40|    provider_error: str | None = None
   41|    llm_model_name: str | None = None
   42|
   43|
   44|class LogisticsLlmClarificationAssistResult(BaseModel):
   45|    """物流域澄清辅助输出结构。
   46|
   47|    说明：
   48|        1. 当前结构只服务于“规则层已明确判定必须澄清”的问题；
   49|        2. LLM 只能补充缺口径识别和业务化追问候选，不能把问题改判成 success / unsupported；
   50|        3. 最终是否采用这些追问，仍由规则层和受控服务层决定。
   51|    """
   52|
   53|    normalized_question: str = ""
   54|    clarification_category: str | None = None
   55|    missing_slots: list[str] = Field(default_factory=list)
   56|    slot_reasons: dict[str, str] = Field(default_factory=dict)
   57|    suggested_questions: list[str] = Field(default_factory=list)
   58|    business_summary: str | None = None
   59|    confidence: float = 0.0
   60|    provider_mode: Literal["live", "disabled", "error"] = "disabled"
   61|    provider_error: str | None = None
   62|    llm_model_name: str | None = None
   63|
   64|
   65|class LogisticsLlmClarificationAssistAuditRecord(BaseModel):
   66|    """物流域澄清辅助审计日志结构。
   67|
   68|    说明：
   69|        1. 用于记录规则澄清类别、LLM 识别出的缺口径以及最终采用情况；
   70|        2. 当前按 JSONL 记审计，不引入新的数据库表；
   71|        3. 便于后续复盘“业务问题为什么这样追问”。
   72|    """
   73|
   74|    created_at: str
   75|    trace_id: str | None = None
   76|    question: str
   77|    clarification_category: str | None = None
   78|    clarification_reason: str | None = None
   79|    rule_missing_slots: list[str] = Field(default_factory=list)
   80|    rule_questions: list[str] = Field(default_factory=list)
   81|    assist_enabled: bool = False
   82|    assist_mode: Literal["off", "shadow", "assist"] = "off"
   83|    sampled_in: bool = False
   84|    llm_invoked: bool = False
   85|    llm_provider_mode: Literal["live", "disabled", "error"] = "disabled"
   86|    llm_missing_slots: list[str] = Field(default_factory=list)
   87|    llm_confidence: float = 0.0
   88|    applied: bool = False
   89|    final_missing_slots: list[str] = Field(default_factory=list)
   90|    final_questions: list[str] = Field(default_factory=list)
```

## data_qa_service.py: composite 执行说明片段
```python
 1110|
 1111|        if plan.query_key == "hist_mw_summary":
 1112|            data = self.repository.hist_mw_summary(
 1113|                year=filters["year"],
 1114|                months=filters.get("months"),
 1115|                customer_name=filters.get("customer_name"),
 1116|                region_name=filters.get("region_name"),
 1117|                origin_place=filters.get("origin_place"),
 1118|                carrier_name=filters.get("carrier_name"),
 1119|                transport_mode=filters.get("transport_mode"),
 1120|            )
 1121|            month_text = ""
 1122|            if filters.get("months"):
 1123|                month_text = "".join(f"{month}月" for month in filters["months"])
 1124|            scope_parts = [f"{filters['year']}年"]
 1125|            if month_text:
 1126|                scope_parts.append(month_text)
 1127|            if filters.get("region_name"):
 1128|                scope_parts.append(f"{filters['region_name']}区域")
 1129|            if filters.get("customer_name"):
 1130|                scope_parts.append(filters["customer_name"])
 1131|            if filters.get("origin_place"):
 1132|                scope_parts.append(f"{filters['origin_place']}基地")
 1133|            if filters.get("carrier_name"):
 1134|                scope_parts.append(filters["carrier_name"])
 1135|            if filters.get("transport_mode"):
 1136|                scope_parts.append(f"{filters['transport_mode']}运输")
 1137|            scope_text = "".join(scope_parts)
 1138|            summary = f"{scope_text}总发运量为{data['shipment_mw'] or 0}MW。"
 1139|            return self._build_result(
 1140|                answer_summary=summary,
 1141|                plan=plan,
 1142|                table_columns=["shipment_mw"],
 1143|                table_rows=[data],
 1144|                calculation_logic=["历史发运量 MW 使用 actual_watt 汇总后除以 1,000,000。"],
 1145|                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
 1146|                warnings=warnings,
 1147|            )
 1148|
 1149|        if plan.query_key == "hist_mw_by_origin_and_carrier":
 1150|            data = self.repository.hist_mw_by_origin_and_carrier(
 1151|                year=filters["year"],
 1152|                origin_place=filters["origin_place"],
 1153|                carrier_name=filters["carrier_name"],
 1154|            )
 1155|            summary = (
 1156|                f"{filters['year']}年{filters['origin_place']}基地、承运商{filters['carrier_name']}的总发运量为"
 1157|                f"{data['shipment_mw'] or 0}MW。"
 1158|            )
 1159|            return self._build_result(
 1160|                answer_summary=summary,
 1161|                plan=plan,
 1162|                table_columns=["shipment_mw"],
 1163|                table_rows=[data],
 1164|                calculation_logic=["历史发运量 MW 使用 actual_watt 汇总后除以 1,000,000。"],
 1165|                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
 1166|                warnings=warnings,
 1167|            )
 1168|
 1169|        if plan.query_key == "hist_mw_by_region_province":
 1170|            data = self.repository.hist_mw_by_region_province(
 1171|                year=filters["year"],
 1172|                region_name=filters["region_name"],
 1173|                provinces=filters.get("provinces"),
 1174|            )
 1175|            summary = f"{filters['year']}年{filters['region_name']}区域各省发运量已拆分返回。"
 1176|            return self._build_result(
 1177|                answer_summary=summary,
 1178|                plan=plan,
 1179|                table_columns=["province", "shipment_mw"],
 1180|                table_rows=data,
 1181|                calculation_logic=["历史发运量 MW 使用 actual_watt 汇总后除以 1,000,000，并按省份分组。"],
 1182|                data_scope={"table": "dwd_logistics_hist_shipment_detail", **filters},
 1183|                warnings=warnings,
 1184|            )
 1185|
 1186|        if plan.query_key == "hist_mw_by_all_regions":
 1187|            data = self.repository.hist_mw_by_all_regions(
 1188|                year=filters["year"],
 1189|                carrier_name=filters.get("carrier_name"),
 1190|                regions=filters.get("regions"),
 1191|            )
 1192|            scope_parts = [f"{filters['year']}年"]
 1193|            if filters.get("carrier_name"):
 1194|                scope_parts.append(str(filters["carrier_name"]))
 1195|            if filters.get("regions"):
```

## test_logistics_llm_led_composite_decomposition.py: 全部回归测试
```python
    1|"""物流综合型问题必须由 LLM 主导拆分的回归测试。
    2|
    3|本文件覆盖用户反馈：综合型问题可以回答，但拆分应建立在 LLM 语义理解之上，
    4|规则层只能做安全校验、白名单回构和边界保护，不能纯靠规则直接拆分。
    5|"""
    6|
    7|from __future__ import annotations
    8|
    9|from copy import deepcopy
   10|from typing import Any
   11|
   12|from backend.app.domains.logistics.schemas.data_qa import LogisticsDataQaQueryRequest
   13|from backend.app.domains.logistics.schemas.llm_understanding import LogisticsLlmGuardrailDecision, LogisticsLlmUnderstandingResult
   14|from backend.app.domains.logistics.services.data_qa_planner import LogisticsDataQaPlanner
   15|from backend.app.domains.logistics.services.data_qa_service import LogisticsDataQaService
   16|from backend.app.domains.logistics.services.llm_answer_presentation_service import LogisticsLlmAnswerPresentationService
   17|from backend.app.domains.logistics.services.llm_understanding_guardrail_service import LogisticsLlmUnderstandingGuardrailService
   18|
   19|COMPOSITE_QUESTION = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和招标的发运量"
   20|
   21|
   22|def _llm_composite_sub_plans() -> list[dict[str, Any]]:
   23|    """构造测试用的 LLM 结构化拆分结果。
   24|
   25|    参数：无。
   26|    返回值：LLM 候选拆分出的两个受控子计划；后续仍由 planner 校验 query_key、年份、客户和阈值。
   27|    业务逻辑：第一个子问题查 2024 年创维历史高运费收货地址，第二个子问题查 2026 系统侧采购方式发运量。
   28|    """
   29|
   30|    return [
   31|        {
   32|            "section_label": "历史高运费收货地址",
   33|            "source_clause": "24年创维客户发货的项目地运费金额超过20万的收货地址",
   34|            "intent": "detail_list",
   35|            "query_key": "hist_high_fee_addresses_by_customer",
   36|            "metrics": ["total_fee", "shipment_mw"],
   37|            "dimensions": ["address"],
   38|            "filters": {"year": 2024, "customer_name": "创维", "threshold_fee": 200000},
   39|            "group_by": ["address"],
   40|            "sort": [{"field": "total_fee", "direction": "desc"}],
   41|        },
   42|        {
   43|            "section_label": "2026采购方式发运量",
   44|            "source_clause": "分别列出询比价和招标的发运量",
   45|            "intent": "aggregate",
   46|            "query_key": "sys_mw_by_procurement_type",
   47|            "metrics": ["shipment_mw"],
   48|            "dimensions": ["procurement_type"],
   49|            "filters": {"year": 2026, "default_system_year": True},
   50|            "group_by": ["procurement_type"],
   51|            "sort": [{"field": "shipment_mw", "direction": "desc"}],
   52|        },
   53|    ]
   54|
   55|
   56|class _FakeDb:
   57|    """测试用空数据库会话，只承接历史快照提交/回滚。"""
   58|
   59|    def commit(self) -> None:
   60|        """提交测试事务；无需真实落库。"""
   61|
   62|    def rollback(self) -> None:
   63|        """回滚测试事务；无需真实落库。"""
   64|
   65|
   66|class _FakeQueryLogRepository:
   67|    """测试用查询日志仓库，避免依赖真实 sys_query_log。"""
   68|
   69|    def write_query_log(self, db: Any, payload: dict[str, Any]) -> int:  # noqa: ARG002
   70|        """返回固定日志 ID，证明主链路已走完。"""
   71|        return 1
   72|
   73|
   74|class _NoopGuardrailService:
   75|    """测试用 Guardrail：不提供 LLM 拆分候选。"""
   76|
   77|    def evaluate(self, *, question: str, rule_plan: Any, trace_id: str | None = None, write_audit: bool = False) -> LogisticsLlmGuardrailDecision:  # noqa: ARG002
   78|        """保持规则计划，不触发 LLM 候选增强。"""
   79|        return LogisticsLlmGuardrailDecision(
   80|            question=question,
   81|            rule_intent=rule_plan.intent,
   82|            rule_query_key=rule_plan.query_key,
   83|            rule_needs_clarification=rule_plan.needs_clarification,
   84|            rule_supported=rule_plan.intent not in {"clarification", "unsupported"},
   85|            final_intent=rule_plan.intent,
   86|            final_query_key=rule_plan.query_key,
   87|            final_needs_clarification=rule_plan.needs_clarification,
   88|            final_supported=rule_plan.intent not in {"clarification", "unsupported"},
   89|        )
   90|
   91|    def write_audit_log(self, *, trace_id: str | None, decision: LogisticsLlmGuardrailDecision) -> None:  # noqa: ARG002
   92|        """测试场景不写审计日志。"""
   93|
   94|
   95|class _LlmCompositeGuardrailService:
   96|    """测试用 Guardrail：模拟 LLM 高置信识别出可拆分综合问题。"""
   97|
   98|    def __init__(self, *, sub_plans: list[dict[str, Any]] | None = None) -> None:
   99|        """保存本次测试注入的 LLM 子计划。"""
  100|        self.sub_plans = sub_plans or _llm_composite_sub_plans()
  101|
  102|    def evaluate(self, *, question: str, rule_plan: Any, trace_id: str | None = None, write_audit: bool = False) -> LogisticsLlmGuardrailDecision:  # noqa: ARG002
  103|        """返回 LLM 主导的 composite_decomposed 候选，供 planner 做受控回构。"""
  104|        return LogisticsLlmGuardrailDecision(
  105|            question=question,
  106|            guardrail_enabled=True,
  107|            guardrail_mode="assist",
  108|            sampled_in=True,
  109|            entered_guardrail=True,
  110|            llm_invoked=True,
  111|            eligible_for_assist=True,
  112|            assist_recommended=True,
  113|            assist_applied=True,
  114|            final_source="llm_assist",
  115|            rule_intent=rule_plan.intent,
  116|            rule_query_key=rule_plan.query_key,
  117|            rule_needs_clarification=rule_plan.needs_clarification,
  118|            rule_supported=rule_plan.intent not in {"clarification", "unsupported"},
  119|            final_intent="composite",
  120|            final_query_key="composite_decomposed",
  121|            final_needs_clarification=False,
  122|            final_supported=True,
  123|            allowed_query_key_whitelist=["composite_decomposed"],
  124|            llm_intent="comparison",
  125|            llm_top_query_key="composite_decomposed",
  126|            llm_candidate_query_keys=["composite_decomposed"],
  127|            llm_filters={
  128|                "decomposition_strategy": "top_level_conjunction",
  129|                "sub_plans": self.sub_plans,
  130|            },
  131|            llm_confidence=0.97,
  132|            llm_provider_mode="live",
  133|        )
  134|
  135|    def write_audit_log(self, *, trace_id: str | None, decision: LogisticsLlmGuardrailDecision) -> None:  # noqa: ARG002
  136|        """测试场景不写审计日志。"""
  137|
  138|
  139|class _FakeLlmUnderstandingService:
  140|    """测试用 LLM 理解服务：返回可审计的复合拆分候选。"""
  141|
  142|    def __init__(self, *, sub_plans: list[dict[str, Any]] | None = None) -> None:
  143|        """保存测试用子计划并记录调用次数。"""
  144|        self.sub_plans = sub_plans or _llm_composite_sub_plans()
  145|        self.calls = 0
  146|        self.allowed_query_keys: list[str] | None = None
  147|
  148|    def understand(
  149|        self,
  150|        question: str,
  151|        *,
  152|        allowed_query_keys: list[str] | None = None,
  153|    ) -> LogisticsLlmUnderstandingResult:
  154|        """模拟真实 LLM 输出 composite_decomposed 顶层候选。
  155|
  156|        参数：
  157|            question: 原始业务问题。
  158|            allowed_query_keys: Guardrail 下发给 LLM 的白名单。
  159|        返回值：LLM 结构化理解结果，包含顶层拆分策略和子计划列表。
  160|        """
  161|        self.calls += 1
  162|        self.allowed_query_keys = allowed_query_keys
  163|        return LogisticsLlmUnderstandingResult(
  164|            normalized_question=question,
  165|            intent="comparison",
  166|            filters={
  167|                "decomposition_strategy": "top_level_conjunction",
  168|                "sub_plans": self.sub_plans,
  169|            },
  170|            source_scope="mixed",
  171|            candidate_query_keys=["composite_decomposed"],
  172|            confidence=0.97,
  173|            provider_mode="live",
  174|        )
  175|
  176|
  177|class _FakeNonCompositeLlmUnderstandingService(_FakeLlmUnderstandingService):
  178|    """测试用 LLM 理解服务：在复合策略例外场景中返回非 composite 候选。"""
  179|
  180|    def understand(
  181|        self,
  182|        question: str,
  183|        *,
  184|        allowed_query_keys: list[str] | None = None,
  185|    ) -> LogisticsLlmUnderstandingResult:
  186|        """模拟 LLM 错误地把复合策略例外改写成普通 A 类 query_key。"""
  187|        self.calls += 1
  188|        self.allowed_query_keys = allowed_query_keys
  189|        return LogisticsLlmUnderstandingResult(
  190|            normalized_question=question,
  191|            intent="ranking",
  192|            filters={"year": 2024},
  193|            source_scope="historical",
  194|            candidate_query_keys=["hist_total_fee_city_rank"],
  195|            confidence=0.97,
  196|            provider_mode="live",
  197|        )
  198|
  199|
  200|class _FakeLogisticsRepository:
  201|    """测试用物流仓库，只实现复合拆分涉及的两个子查询。"""
  202|
  203|    def hist_high_fee_addresses_by_customer(self, *, year: int, customer_name: str, threshold_fee: int) -> list[dict[str, Any]]:
  204|        """返回历史高运费收货地址测试数据。"""
  205|        assert year == 2024
  206|        assert customer_name == "创维"
  207|        assert threshold_fee == 200000
  208|        return [
  209|            {
  210|                "address": "安徽省合肥市测试项目地",
  211|                "province": "安徽",
  212|                "city": "合肥",
  213|                "total_fee": 260000,
  214|                "shipment_mw": 18.5,
  215|                "row_count": 3,
  216|            }
  217|        ]
  218|
  219|    def sys_mw_by_procurement_type(self, *, year: int) -> list[dict[str, Any]]:
  220|        """返回 2026 系统侧采购方式发运量测试数据。"""
  221|        assert year == 2026
  222|        return [
  223|            {"procurement_type": "询比价", "shipment_mw": 12.3, "task_count": 2},
  224|            {"procurement_type": "招标", "shipment_mw": 45.6, "task_count": 4},
  225|        ]
  226|
  227|
  228|def _build_service(*, guardrail_service: Any) -> LogisticsDataQaService:
  229|    """构造隔离外部依赖的物流问答服务。
  230|
  231|    参数：
  232|        guardrail_service: 测试注入的 Guardrail 服务。
  233|    返回值：可直接执行 query 的服务实例。
  234|    """
  235|
  236|    return LogisticsDataQaService(
  237|        db=_FakeDb(),
  238|        repository=_FakeLogisticsRepository(),
  239|        planner=LogisticsDataQaPlanner(),
  240|        query_log_repository=_FakeQueryLogRepository(),
  241|        guardrail_service=guardrail_service,
  242|        answer_presentation_service=LogisticsLlmAnswerPresentationService(enabled=False),
  243|    )
  244|
  245|
  246|def test_rule_planner_must_not_decompose_composite_without_llm() -> None:
  247|    """规则 planner 不能纯靠关键词直接拆分综合型问题。
  248|
  249|    参数：无。
  250|    返回值：无；通过断言确认没有 LLM 候选时不会产生 composite_decomposed 计划。
  251|    业务逻辑：复合问题是否可拆、如何拆，应由 LLM 语义理解主导；规则层最多保守拒答/追问。
  252|    """
  253|
  254|    plan = LogisticsDataQaPlanner().build_plan(COMPOSITE_QUESTION)
  255|
  256|    assert plan.query_key != "composite_decomposed"
  257|    assert plan.intent in {"clarification", "unsupported"}
  258|
  259|
  260|def test_service_does_not_answer_composite_when_llm_decomposition_missing() -> None:
  261|    """没有 LLM 拆分候选时，服务不能用规则兜底强行回答综合型问题。
  262|
  263|    参数：无。
  264|    返回值：无；通过断言确认 no-op Guardrail 下不会执行复合拆分。
  265|    业务逻辑：如果 LLM 不可用或未给出可信拆分，系统应保持保守边界，而不是用规则猜测拆分。
  266|    """
  267|
  268|    service = _build_service(guardrail_service=_NoopGuardrailService())
  269|    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="no-llm-composite")
  270|
  271|    assert result.query_plan.query_key != "composite_decomposed"
  272|    assert not result.supported
  273|
  274|
  275|def test_guardrail_allows_llm_composite_candidate_for_policy_locked_question() -> None:
  276|    """规则层命中旧拒答策略时，仍允许 LLM 给出顶层复合拆分候选。
  277|
  278|    参数：无。
  279|    返回值：无；断言真实 Guardrail 会调用 LLM，并只放行 composite_decomposed 白名单候选。
  280|    业务逻辑：旧规则只能说明“历史高运费地址内部采购方式拆分”不可靠，不能阻止 LLM 将整句理解成两个独立子问题。
  281|    """
  282|
  283|    rule_plan = LogisticsDataQaPlanner().build_plan(COMPOSITE_QUESTION)
  284|    fake_llm = _FakeLlmUnderstandingService()
  285|    guardrail = LogisticsLlmUnderstandingGuardrailService(
  286|        llm_service=fake_llm,  # type: ignore[arg-type]
  287|        enabled=True,
  288|        mode="assist",
  289|        sample_rate=1.0,
  290|        min_confidence=0.8,
  291|        audit_enabled=False,
  292|    )
  293|
  294|    decision = guardrail.evaluate(question=COMPOSITE_QUESTION, rule_plan=rule_plan, write_audit=False)
  295|
  296|    assert fake_llm.calls == 1
  297|    assert fake_llm.allowed_query_keys is not None
  298|    assert "composite_decomposed" in fake_llm.allowed_query_keys
  299|    assert decision.assist_applied
  300|    assert decision.final_query_key == "composite_decomposed"
  301|    assert decision.final_source == "llm_assist"
  302|
  303|
  304|def test_guardrail_rejects_non_composite_candidate_for_policy_locked_question() -> None:
  305|    """旧拒答策略例外只允许 LLM 输出 composite_decomposed，不允许改写成其它 A 类 query_key。
  306|
  307|    参数：无。
  308|    返回值：无；断言 Guardrail 不会借复合例外放行普通候选。
  309|    业务逻辑：复合例外只解决“是否是两个独立子问”的判断，不是通用 unsupported 绕行通道。
  310|    """
  311|
  312|    rule_plan = LogisticsDataQaPlanner().build_plan(COMPOSITE_QUESTION)
  313|    fake_llm = _FakeNonCompositeLlmUnderstandingService()
  314|    guardrail = LogisticsLlmUnderstandingGuardrailService(
  315|        llm_service=fake_llm,  # type: ignore[arg-type]
  316|        enabled=True,
  317|        mode="assist",
  318|        sample_rate=1.0,
  319|        min_confidence=0.8,
  320|        audit_enabled=False,
  321|    )
  322|
  323|    decision = guardrail.evaluate(question=COMPOSITE_QUESTION, rule_plan=rule_plan, write_audit=False)
  324|
  325|    assert fake_llm.calls == 1
  326|    assert not decision.assist_applied
  327|    assert decision.final_query_key != "hist_total_fee_city_rank"
  328|    assert decision.blocked_reason == "composite_policy_requires_composite_candidate"
  329|
  330|
  331|def test_service_uses_llm_led_decomposition_then_rules_validate_and_execute() -> None:
  332|    """LLM 给出可信拆分后，规则层校验并执行白名单子查询。
  333|
  334|    参数：无。
  335|    返回值：无；通过断言验证最终计划带有 LLM 来源标记，并合并两个子查询结果。
  336|    业务逻辑：LLM 负责识别顶层并列子问题；后端规则负责校验 query_key、字段能力和过滤条件，再执行确定性仓储查询。
  337|    """
  338|
  339|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService())
  340|    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="llm-led-composite")
  341|
  342|    assert result.supported
  343|    assert result.query_plan.query_key == "composite_decomposed"
  344|    assert result.query_plan.filters["decomposition_source"] == "llm_guardrail"
  345|    assert result.query_plan.filters["sub_query_keys"] == [
  346|        "hist_high_fee_addresses_by_customer",
  347|        "sys_mw_by_procurement_type",
  348|    ]
  349|    assert len(result.result_table.rows) == 3
  350|    assert any(row.get("section") == "历史高运费收货地址" for row in result.result_table.rows)
  351|    assert any(row.get("procurement_type") == "询比价" for row in result.result_table.rows)
  352|    assert "LLM" in "\n".join(result.calculation_logic + result.warnings)
  353|
  354|
  355|def test_llm_led_decomposition_keeps_ton_unit_guard() -> None:
  356|    """即使 LLM 给出拆分，用户明确要吨口径时也不能替换成 MW 子查询。
  357|
  358|    参数：无。
  359|    返回值：无；断言规则安全校验会拒绝不支持的吨口径。
  360|    业务逻辑：LLM 负责语义拆分，但单位能力边界仍由后端规则 fail-closed 保护。
  361|    """
  362|
  363|    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和招标的发运量吨"
  364|    sub_plans = _llm_composite_sub_plans()
  365|    sub_plans[1] = {**sub_plans[1], "source_clause": "分别列出询比价和招标的发运量吨"}
  366|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  367|
  368|    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-ton-guard")
  369|
  370|    assert result.query_plan.query_key != "composite_decomposed"
  371|    assert not result.supported
  372|    assert result.needs_clarification
  373|    assert "吨重" in "\n".join(result.clarification_questions + result.warnings + result.calculation_logic)
  374|
  375|
  376|def test_llm_led_decomposition_rejects_back_reference_subset_split() -> None:
  377|    """LLM 拆分结果如果把“这些地址”回指误当全局采购方式，也必须拒绝执行。
  378|
  379|    参数：无。
  380|    返回值：无；断言后端规则不会把历史子集采购方式拆分替换成 2026 全局统计。
  381|    业务逻辑：LLM 主导不等于盲信；规则层必须拦截回指前一个子结果的二次拆分。
  382|    """
  383|
  384|    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并把这些地址分别列出询比价和招标的发运量"
  385|    sub_plans = _llm_composite_sub_plans()
  386|    sub_plans[1] = {**sub_plans[1], "source_clause": "把这些地址分别列出询比价和招标的发运量"}
  387|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  388|
  389|    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-backref-guard")
  390|
  391|    assert result.query_plan.query_key != "composite_decomposed"
  392|    assert not result.supported
  393|
  394|
  395|def test_llm_led_decomposition_rejects_back_reference_even_when_llm_omits_it() -> None:
  396|    """原问题含“这些地址”回指时，LLM source_clause 省略回指也必须拒绝。
  397|
  398|    参数：无。
  399|    返回值：无；断言回指保护基于原始问题定位，而不是盲信 LLM 子句。
  400|    业务逻辑：避免 LLM 把历史子集采购方式拆分改写成 2026 全局采购方式统计。
  401|    """
  402|
  403|    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并把这些地址分别列出询比价和招标的发运量"
  404|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService())
  405|
  406|    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-backref-omitted")
  407|
  408|    assert result.query_plan.query_key != "composite_decomposed"
  409|    assert not result.supported
  410|
  411|
  412|def test_llm_led_decomposition_rejects_extra_or_unknown_sub_plan() -> None:
  413|    """LLM 返回额外子计划时必须 fail-closed，不能静默丢弃漏答。
  414|
  415|    参数：无。
  416|    返回值：无；断言含第三个子问的拆分不会被回构成复合计划。
  417|    业务逻辑：综合问题必须完整回答，未知/额外子计划不能被忽略。
  418|    """
  419|
  420|    sub_plans = _llm_composite_sub_plans() + [
  421|        {
  422|            "source_clause": "再按承运商列出费用排名",
  423|            "intent": "ranking",
  424|            "query_key": "carrier_metric_ranking",
  425|            "filters": {"year": 2024},
  426|        }
  427|    ]
  428|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  429|
  430|    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="llm-extra-subplan")
  431|
  432|    assert result.query_plan.query_key != "composite_decomposed"
  433|    assert not result.supported
  434|
  435|
  436|def test_llm_led_decomposition_rejects_ungrounded_source_clause() -> None:
  437|    """LLM 子句必须来自原始问题，幻觉出来的子句不能回构受控计划。
  438|
  439|    参数：无。
  440|    返回值：无；断言 source_clause 无法在原问题中定位时拒绝执行。
  441|    业务逻辑：LLM 负责语义拆分，但每个子句必须可追溯到用户原文。
  442|    """
  443|
  444|    sub_plans = _llm_composite_sub_plans()
  445|    sub_plans[0] = {**sub_plans[0], "source_clause": "2025年某客户高运费地址超过50万"}
  446|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  447|
  448|    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="llm-ungrounded-clause")
  449|
  450|    assert result.query_plan.query_key != "composite_decomposed"
  451|    assert not result.supported
  452|
  453|
  454|def test_llm_led_decomposition_rejects_slot_conflict_with_original_question() -> None:
  455|    """LLM 槽位与原问题确定性抽取冲突时必须拒绝，不能采信错误槽位。
  456|
  457|    参数：无。
  458|    返回值：无；断言 24 年问题被 LLM 写成 2023 年时不会执行。
  459|    业务逻辑：规则层只做校验和回构，关键槽位必须与原文一致。
  460|    """
  461|
  462|    sub_plans = deepcopy(_llm_composite_sub_plans())
  463|    sub_plans[0]["filters"]["year"] = 2023
  464|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  465|
  466|    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="llm-slot-conflict")
  467|
  468|    assert result.query_plan.query_key != "composite_decomposed"
  469|    assert not result.supported
  470|
  471|
  472|def test_llm_led_decomposition_rejects_uncovered_original_subquestion() -> None:
  473|    """原问题还有未被 LLM source_clause 覆盖的第三诉求时必须拒绝。
  474|
  475|    参数：无。
  476|    返回值：无；断言 LLM 漏报第三子问时不会静默漏答后仍返回 composite。
  477|    业务逻辑：LLM 主导拆分必须完整覆盖用户综合问题，规则层负责校验覆盖性。
  478|    """
  479|
  480|    question = f"{COMPOSITE_QUESTION}，并统计2026年华东总运费"
  481|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService())
  482|
  483|    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-uncovered-subquestion")
  484|
  485|    assert result.query_plan.query_key != "composite_decomposed"
  486|    assert not result.supported
  487|
  488|
  489|def test_llm_led_decomposition_rejects_overbroad_overlapping_source_clause() -> None:
  490|    """LLM source_clause 覆盖整句或与另一子句重叠时必须拒绝。
  491|
  492|    参数：无。
  493|    返回值：无；断言过宽 source_clause 不能通过覆盖性校验。
  494|    业务逻辑：避免 LLM 用整句作为某个子计划 source_clause，从而掩盖漏报第三诉求。
  495|    """
  496|
  497|    question = f"{COMPOSITE_QUESTION}，并统计2026年华东总运费"
  498|    sub_plans = deepcopy(_llm_composite_sub_plans())
  499|    sub_plans[0]["source_clause"] = question
  500|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  501|
  502|    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-overbroad-clause")
  503|
  504|    assert result.query_plan.query_key != "composite_decomposed"
  505|    assert not result.supported
  506|
  507|
  508|def test_llm_led_decomposition_rejects_procurement_clause_with_unsupported_customer_filter() -> None:
  509|    """采购方式全局统计子句带客户限定时必须拒绝，不能静默丢弃限定。
  510|
  511|    参数：无。
  512|    返回值：无；断言当前全局采购方式 query_key 不会忽略客户过滤条件后执行。
  513|    业务逻辑：LLM 可以提出子计划，但规则层必须校验目标子查询是否支持原文限定。
  514|    """
  515|
  516|    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出创维客户询比价和招标的发运量"
  517|    sub_plans = deepcopy(_llm_composite_sub_plans())
  518|    sub_plans[1]["source_clause"] = "分别列出创维客户询比价和招标的发运量"
  519|    sub_plans[1]["filters"]["customer_name"] = "创维"
  520|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  521|
  522|    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-procurement-extra-filter")
  523|
  524|    assert result.query_plan.query_key != "composite_decomposed"
  525|    assert not result.supported
  526|
  527|
  528|def test_llm_led_decomposition_rejects_procurement_clause_with_implicit_customer_qualifier() -> None:
  529|    """采购方式子句出现无“客户”后缀的客户名时也必须拒绝。
  530|
  531|    参数：无。
  532|    返回值：无；断言 `创维询比价发运量` 不会被降级为全局采购方式发运量。
  533|    业务逻辑：采购方式子查询当前不支持客户限定，规则层必须用高运费子句中的客户槽位反查子句文本。
  534|    """
  535|
  536|    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出创维询比价和招标的发运量"
  537|    sub_plans = deepcopy(_llm_composite_sub_plans())
  538|    sub_plans[1]["source_clause"] = "分别列出创维询比价和招标的发运量"
  539|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  540|
  541|    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-procurement-implicit-customer")
  542|
  543|    assert result.query_plan.query_key != "composite_decomposed"
  544|    assert not result.supported
  545|
  546|
  547|def test_llm_led_decomposition_rejects_procurement_clause_with_region_or_month_qualifier() -> None:
  548|    """采购方式子句出现区域或月份限定时必须拒绝，不能静默查全局。
  549|
  550|    参数：无。
  551|    返回值：无；断言 `华东1月询比价发运量` 不会被降级为 2026 全局采购方式发运量。
  552|    业务逻辑：当前 sys_mw_by_procurement_type 不支持区域/月度限定，LLM 省略 filters 也要基于子句 fail-closed。
  553|    """
  554|
  555|    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出华东1月询比价和招标的发运量"
  556|    sub_plans = deepcopy(_llm_composite_sub_plans())
  557|    sub_plans[1]["source_clause"] = "分别列出华东1月询比价和招标的发运量"
  558|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  559|
  560|    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-procurement-region-month")
  561|
  562|    assert result.query_plan.query_key != "composite_decomposed"
  563|    assert not result.supported
  564|
  565|
  566|def test_llm_led_decomposition_rejects_procurement_clause_with_nonfirst_implicit_qualifier() -> None:
  567|    """采购方式子句在第二个采购方式词附近出现隐式实体限定时也必须拒绝。
  568|
  569|    参数：无。
  570|    返回值：无；断言 `询比价和海尔招标` 不会被当作全局采购方式发运量。
  571|    业务逻辑：字段能力校验要覆盖整句残留实体，而不是只检查第一个采购方式词前缀。
  572|    """
  573|
  574|    question = "统计一下24年创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和海尔招标的发运量"
  575|    sub_plans = deepcopy(_llm_composite_sub_plans())
  576|    sub_plans[1]["source_clause"] = "分别列出询比价和海尔招标的发运量"
  577|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  578|
  579|    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-procurement-nonfirst-qualifier")
  580|
  581|    assert result.query_plan.query_key != "composite_decomposed"
  582|    assert not result.supported
  583|
  584|
  585|def test_llm_led_decomposition_rejects_high_fee_subplan_with_unsupported_extra_filter() -> None:
  586|    """高运费地址子计划携带未支持 filters 时必须拒绝，不能静默忽略。
  587|
  588|    参数：无。
  589|    返回值：无；断言 LLM 给 high_fee 子计划加入 region_name 时不会执行。
  590|    业务逻辑：规则回构只能接受实际执行子查询支持的槽位，额外过滤条件必须 fail-closed。
  591|    """
  592|
  593|    sub_plans = deepcopy(_llm_composite_sub_plans())
  594|    sub_plans[0]["filters"]["region_name"] = "华东"
  595|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  596|
  597|    result = service.query(LogisticsDataQaQueryRequest(question=COMPOSITE_QUESTION), trace_id="llm-high-fee-extra-filter")
  598|
  599|    assert result.query_plan.query_key != "composite_decomposed"
  600|    assert not result.supported
  601|
  602|
  603|def test_llm_led_decomposition_rejects_high_fee_source_clause_with_unsupported_region_qualifier() -> None:
  604|    """高运费地址 source_clause 自身包含区域限定时也必须拒绝。
  605|
  606|    参数：无。
  607|    返回值：无；断言 LLM 未写 filters 但 source_clause 含华东时不会静默忽略区域。
  608|    业务逻辑：字段能力边界不能只依赖 LLM filters，原文子句中的 unsupported qualifier 也必须 fail-closed。
  609|    """
  610|
  611|    question = "统计一下24年华东创维客户发货的项目地运费金额超过20万的收货地址，并分别列出询比价和招标的发运量"
  612|    sub_plans = deepcopy(_llm_composite_sub_plans())
  613|    sub_plans[0]["source_clause"] = "24年华东创维客户发货的项目地运费金额超过20万的收货地址"
  614|    service = _build_service(guardrail_service=_LlmCompositeGuardrailService(sub_plans=sub_plans))
  615|
  616|    result = service.query(LogisticsDataQaQueryRequest(question=question), trace_id="llm-high-fee-source-region")
  617|
  618|    assert result.query_plan.query_key != "composite_decomposed"
  619|    assert not result.supported
```

## Reviewer 必查点
- policy exception 是否只允许 `composite_decomposed`，而不是通用 unsupported 绕行。
- 采购方式子查询是否会静默丢弃客户/区域/承运商/地址/月度/基地限定，包括限定出现在第二个采购方式词附近。
- 高运费子查询是否会静默丢弃未支持 filters/source_clause 限定。
- 过宽/重叠 source_clause、回指、吨口径、历史高运费地址内部采购方式拆分是否 fail-closed。
- 是否有 hardcoded secret / shell injection / eval / pickle / SQL string-formatting 风险。
