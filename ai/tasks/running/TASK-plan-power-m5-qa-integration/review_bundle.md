# M5 reviewer bundle (concise)


Static scan: static_findings=0

Latest verification: M5 focused 8 passed; M4 regression 9 passed; M3 regression 9 passed, 2 warnings; M2 regression 9 passed; full tests 57 passed, 2 warnings; compileall/diff-check/frontend build passed.

Changed files: deps.py, nlu_center_service.py, qa_service.py, answer_presentation_service.py, frontend planBom.ts, BusinessChatPage.vue, test_plan_power_m5_qa_integration.py, plan.md. Review M5 only.


## NLU rule extraction and guarded LLM merge

```python
 128|
 129|    def _rule_understand(self, question: str) -> PlanBomNluCandidate:
 130|        """用规则层抽取意图和槽位。
 131|
 132|        参数：
 133|            question: 用户问题。
 134|
 135|        返回：
 136|            规则层 NLU 候选。
 137|        """
 138|
 139|        normalized = question.strip()
 140|        slots: dict[str, Any] = {}
 141|        slots["order_tail_no"] = self._extract_order_tails(normalized)
 142|        slots["compare_orders"] = slots["order_tail_no"][:]
 143|        slots["material_category"] = self._extract_material_categories(normalized)
 144|        slots["non_core_material_category"] = self._extract_non_core_material_categories(normalized)
 145|        slots["material_alias"] = self._extract_material_aliases(normalized)
 146|        slots["bom_version"] = self._extract_versions(normalized)
 147|        slots["model"] = self._extract_model(normalized)
 148|        slots["year"] = self._extract_year(normalized)
 149|        slots["country"] = self._extract_country(normalized)
 150|        slots["target_power_ratio"] = self._extract_target_power_ratio(normalized)
 151|        slots["supplier_name"] = self._extract_supplier_name(normalized)
 152|        slots["benchmark"] = self._extract_benchmark(normalized)
 153|        slots["need_table"] = any(word in normalized for word in ("表格", "清单", "列表", "统计出来", "列出来"))
 154|        slots["need_excel"] = any(word.lower() in normalized.lower() for word in ("excel", "导表", "导出"))
 155|        slots["output_format"] = "excel" if slots["need_excel"] else ("table" if slots["need_table"] else "narrative")
 156|
 157|        intent = self._detect_intent(normalized, slots)
 158|        missing_slots = self._detect_missing_slots(intent, slots)
 159|        confidence = 0.78 if not missing_slots else 0.58
 160|        return PlanBomNluCandidate(
 161|            question=question,
 162|            intent=intent,
 163|            slots=slots,
 164|            missing_slots=missing_slots,
 165|            confidence=confidence,
 166|            provider_mode="rule",
 167|            guardrail_notes=["规则层完成初始意图和槽位抽取。"],
 168|        )
 169|
 170|    def _detect_intent(self, question: str, slots: dict[str, Any]) -> str:
 171|        """判断受控意图。
 172|
 173|        参数：
 174|            question: 用户问题；
 175|            slots: 规则层已抽取槽位。
 176|
 177|        返回：
 178|            受控 intent 编码。
 179|        """
 180|
 181|        if self._is_power_question(question):
 182|            if slots.get("target_power_ratio") or any(
 183|                word in question
 184|                for word in ("推荐供应商", "供应商推荐", "推荐电池", "匹配度", "目标功率", "目标比例", "目标", "占比")
 185|            ):
 186|                return "plan_power_supplier_recommendation"
 187|            return "plan_power_prediction"
 188|        if "到" in question and len(slots.get("bom_version") or []) >= 2:
 189|            return "bom_version_compare"
 190|        if any(word in question for word in ("版本", "A0", "A1", "A2", "A3", "变更")) and len(slots.get("bom_version") or []) >= 2:
 191|            return "bom_version_compare"
 192|        if any(word in question for word in ("不一样", "差异", "对比", "比较")):
 193|            return "cross_order_material_compare" if len(slots.get("order_tail_no") or []) >= 2 else "material_consistency_check"
 194|        if any(word in question for word in ("哪些订单没有", "没有接线盒", "是否有", "有没有")):
 195|            return "material_presence_check"
 196|        if any(word in question for word in ("所有", "全部", "多个订单", "清单", "Excel", "excel", "导出")):
 197|            return "scope_material_list" if slots.get("model") or slots.get("year") else "multi_order_material_table"
 198|        if len(slots.get("order_tail_no") or []) >= 2:
 199|            return "multi_order_material_table"
 200|        if slots.get("material_category") and slots.get("order_tail_no"):
 201|            return "single_order_material_specs"
 202|        if slots.get("material_category"):
 203|            return "specific_material_query"
 204|        return "clarification"
 205|
 206|    def _detect_missing_slots(self, intent: str, slots: dict[str, Any]) -> list[str]:
 207|        """识别缺失槽位。
 208|
 209|        参数：
 210|            intent: 受控意图；
 211|            slots: 当前槽位。
 212|
 213|        返回：
 214|            缺失槽位名称列表。
 215|        """
 216|
 217|        missing: list[str] = []
 218|        if intent in {"plan_power_prediction", "plan_power_supplier_recommendation"} and not slots.get("order_tail_no"):
 219|            missing.append("order_id")
 220|        if intent == "plan_power_supplier_recommendation" and not slots.get("target_power_ratio"):
 221|            missing.append("target_power_ratio")
 222|        if intent in {"single_order_material_specs", "specific_material_query", "bom_version_compare"} and not slots.get("order_tail_no"):
 223|            missing.append("order_id")
 224|        if intent in {"multi_order_material_table", "cross_order_material_compare"} and len(slots.get("order_tail_no") or []) < 2:
 225|            missing.append("compare_orders")
 226|        if intent in {"single_order_material_specs", "multi_order_material_table", "cross_order_material_compare"} and not slots.get("material_category"):
 227|            missing.append("material_category")
 228|        if intent == "scope_material_list" and not (slots.get("year") or slots.get("model") or slots.get("country")):
 229|            missing.append("scope")
 230|        return missing
 231|
 232|    def _request_llm_candidate(self, question: str) -> tuple[dict[str, Any] | None, str | None]:
 233|        """请求 LLM 候选理解。
 234|
 235|        参数：
 236|            question: 用户问题。
 237|
 238|        返回：
 239|            二元组：(候选 JSON, 错误信息)。错误为空表示可进入校验。
 240|        """
 241|
 242|        try:
 243|            client = self._client or OpenAI(base_url=self.base_url, api_key=self.api_key, timeout=15, max_retries=0)
 244|            completion = client.chat.completions.create(
 245|                model=self.model,
 246|                temperature=0,
 247|                messages=[
 248|                    {"role": "system", "content": self._build_llm_system_prompt()},
 249|                    {"role": "user", "content": question},
 250|                ],
 251|            )
 252|            content = completion.choices[0].message.content or "{}"
 253|            return self._extract_json(content), None
 254|        except Exception as exc:  # noqa: BLE001
 255|            return None, str(exc)
 256|
 257|    def _merge_llm_candidate(self, rule_candidate: PlanBomNluCandidate, payload: dict[str, Any] | None) -> PlanBomNluCandidate:
 258|        """合并 LLM 候选并执行 Guardrail。
 259|
 260|        参数：
 261|            rule_candidate: 规则层候选；
 262|            payload: LLM 输出 JSON。
 263|
 264|        返回：
 265|            最终 NLU 候选；校验失败时保持规则层。
 266|        """
 267|
 268|        if not isinstance(payload, dict):
 269|            rule_candidate.guardrail_notes.append("LLM 未返回 JSON 对象，保持规则层。")
 270|            return rule_candidate
 271|        raw_intent = str(payload.get("intent_candidate") or payload.get("intent") or "").strip()
 272|        intent = self._normalize_intent(raw_intent)
 273|        if intent not in self.INTENTS:
 274|            rule_candidate.guardrail_notes.append(f"LLM intent 不在 BOM 白名单，保持规则层：{raw_intent}")
 275|            return rule_candidate
 276|        slot_candidate = payload.get("slot_candidate") or payload.get("slots") or {}
 277|        if not isinstance(slot_candidate, dict):
 278|            rule_candidate.guardrail_notes.append("LLM slots 非对象，保持规则层。")
 279|            return rule_candidate
 280|
 281|        validated_slots = dict(rule_candidate.slots)
 282|        is_power_intent = intent in self.POWER_INTENTS or rule_candidate.intent in self.POWER_INTENTS
 283|        rejected_reasons: list[str] = []
 284|        if "material_category" in slot_candidate:
 285|            llm_core_materials, llm_non_core_materials = self._normalize_material_candidates(
 286|                slot_candidate.get("material_category") or []
 287|            )
 288|            if llm_core_materials:
 289|                validated_slots["material_category"] = llm_core_materials
 290|            if llm_non_core_materials:
 291|                validated_slots["non_core_material_category"] = llm_non_core_materials
 292|                rule_candidate.guardrail_notes.append(
 293|                    "LLM 非核心材料候选已识别，但当前 detail/compare 主链路仅支持核心五类，未写入 material_category。"
 294|                )
 295|            if not llm_core_materials and not llm_non_core_materials:
 296|                rule_candidate.guardrail_notes.append("LLM 材料候选未通过 BOM 材料别名白名单校验，未采纳材料槽位。")
 297|        if "order_tail_no" in slot_candidate:
 298|            tails = [self._normalize_order_tail(str(item)) for item in slot_candidate.get("order_tail_no") or []]
 299|            tails = [item for item in tails if item]
 300|            rule_tails = rule_candidate.slots.get("order_tail_no") or []
 301|            if is_power_intent and tails != rule_tails:
 302|                rejected_reasons.append("功率预测类问题的 LLM 订单候选未与规则层原文抽取完全一致，未采纳订单槽位。")
 303|            elif tails and self._all_order_tails_exist(tails):
 304|                validated_slots["order_tail_no"] = tails
 305|                validated_slots["compare_orders"] = tails
 306|            else:
 307|                rejected_reasons.append("LLM 订单候选未通过 BOM 索引校验，未采纳订单槽位。")
 308|        if "bom_version" in slot_candidate:
 309|            versions = [str(item).upper().strip() for item in slot_candidate.get("bom_version") or [] if str(item).strip()]
 310|            if versions and self._versions_are_allowed(versions, rule_candidate=rule_candidate, validated_slots=validated_slots):
 311|                validated_slots["bom_version"] = versions
 312|            elif versions:
 313|                rule_candidate.guardrail_notes.append("LLM BOM 版本候选未通过问题原文或 BOM 版本索引校验，未采纳版本槽位。")
 314|        if "target_power_ratio" in slot_candidate:
 315|            target = self._normalize_target_power_ratio(slot_candidate.get("target_power_ratio"))
 316|            rule_target = rule_candidate.slots.get("target_power_ratio") or {}
 317|            if target and self._target_ratio_matches_rule(target, rule_target):
 318|                validated_slots["target_power_ratio"] = target
 319|            elif target:
 320|                rule_candidate.guardrail_notes.append(
 321|                    "LLM 目标功率比例候选未完全出现在规则层抽取结果中，未采纳目标比例槽位。"
 322|                )
 323|            else:
 324|                rule_candidate.guardrail_notes.append("LLM 目标功率比例候选未通过数字校验，未采纳目标比例槽位。")
 325|        if "supplier_name" in slot_candidate:
 326|            supplier = self._normalize_supplier_candidate(slot_candidate.get("supplier_name"))
 327|            rule_supplier = rule_candidate.slots.get("supplier_name")
 328|            if is_power_intent and supplier != rule_supplier:
 329|                rule_candidate.guardrail_notes.append("功率预测类问题的 LLM 供应商候选未与规则层原文抽取一致，未采纳供应商槽位。")
 330|            elif supplier:
 331|                validated_slots["supplier_name"] = supplier
 332|            else:
 333|                rule_candidate.guardrail_notes.append("LLM 供应商候选未命中 active 功率模型供应商，未采纳供应商槽位。")
 334|        if "benchmark" in slot_candidate:
 335|            benchmark = self._canonical_benchmark(str(slot_candidate.get("benchmark") or ""))
 336|            rule_benchmark = rule_candidate.slots.get("benchmark")
 337|            if is_power_intent and benchmark != rule_benchmark:
 338|                rule_candidate.guardrail_notes.append("功率预测类问题的 LLM 标板候选未与规则层原文抽取一致，未采纳标板槽位。")
 339|            elif benchmark:
 340|                validated_slots["benchmark"] = benchmark
 341|        if rejected_reasons:
 342|            rule_candidate.guardrail_notes.extend(rejected_reasons)
 343|            rule_candidate.guardrail_notes.append("LLM 候选被拒绝，已保持规则层边界。")
 344|            return rule_candidate
 345|
 346|        final_intent = intent
 347|        final_missing = self._detect_missing_slots(intent, validated_slots)
 348|        if intent != rule_candidate.intent and final_missing and not rule_candidate.missing_slots:
 349|            # LLM 候选不能把规则层已闭合的问题改成缺槽问题；这种冲突保持规则 intent，避免安全可答问题被降级。
 350|            final_intent = rule_candidate.intent
 351|            final_missing = self._detect_missing_slots(final_intent, validated_slots)
 352|            rule_candidate.guardrail_notes.append(f"LLM intent 会引入缺失槽位，保持规则层 intent：{rule_candidate.intent}。")
 353|        if intent != rule_candidate.intent:
```


## NLU helpers for power slots

```python
 440|            tails: 订单短号或完整订单号。
 441|
 442|        返回：
 443|            所有尾号均可命中时返回 True。
 444|        """
 445|
 446|        for tail in tails:
 447|            if not self.repository.list_active_headers(order_no_like=tail, order_name_like=tail):
 448|                return False
 449|        return True
 450|
 451|    @staticmethod
 452|    def _is_power_question(question: str) -> bool:
 453|        """判断问题是否属于计划 BOM 功率预测子能力。
 454|
 455|        参数：
 456|            question: 用户问题。
 457|
 458|        返回：
 459|            命中功率预测、目标功率、供应商推荐等关键词时返回 True。
 460|        """
 461|        power_words = (
 462|            "功率预测",
 463|            "功率档",
 464|            "功率分布",
 465|            "目标功率",
 466|            "目标比例",
 467|            "电池效率",
 468|            "供应商推荐",
 469|            "推荐供应商",
 470|            "需要什么样的电池",
 471|            "功率倒推",
 472|            "满足订单需求功率",
 473|        )
 474|        return any(word in question for word in power_words)
 475|
 476|    @staticmethod
 477|    def _extract_target_power_ratio(question: str) -> dict[str, float]:
 478|        """从自然语言中抽取目标功率档比例。
 479|
 480|        参数：
 481|            question: 用户问题，例如“目标620W 50%，625W 50%”。
 482|
 483|        返回：
 484|            `{功率档: 比例}` 字典。比例保留用户原始百分数数值，后续推荐服务会归一化。
 485|        """
 486|        target: dict[str, float] = {}
 487|        patterns = [
 488|            r"(?P<power>\d{3,4}(?:\.\d+)?)\s*(?:W|w|瓦|档)?[^\d%]{0,12}(?P<ratio>\d+(?:\.\d+)?)\s*%",
 489|            r"(?P<power>\d{3,4}(?:\.\d+)?)\s*[:：]\s*(?P<ratio>\d+(?:\.\d+)?)\s*%?",
 490|        ]
 491|        for pattern in patterns:
 492|            for match in re.finditer(pattern, question):
 493|                try:
 494|                    power = float(match.group("power"))
 495|                    ratio = float(match.group("ratio"))
 496|                except (TypeError, ValueError):
 497|                    continue
 498|                if ratio <= 0:
 499|                    continue
 500|                key = str(int(power)) if power.is_integer() else str(power)
 501|                target[key] = ratio
 502|        return target
 503|
 504|    def _extract_supplier_name(self, question: str) -> str | None:
 505|        """从问题中抽取已存在于 active 功率模型的供应商。
 506|
 507|        参数：
 508|            question: 用户问题。
 509|
 510|        返回：
 511|            命中的供应商名称；未命中时返回 None。
 512|        """
 513|        suppliers = self._active_power_suppliers()
 514|        normalized = question.replace(" ", "")
 515|        for supplier in sorted(suppliers, key=len, reverse=True):
 516|            if supplier and supplier.replace(" ", "") in normalized:
 517|                return supplier
 518|        return None
 519|
 520|    @staticmethod
 521|    def _extract_benchmark(question: str) -> str | None:
 522|        """抽取并归一化标板基准表达。
 523|
 524|        参数：
 525|            question: 用户问题。
 526|
 527|        返回：
 528|            当前业务确认的标板基准归一值；未命中时返回 None。
 529|        """
 530|        return PlanBomNluCenterService._canonical_benchmark(question)
 531|
 532|    @staticmethod
 533|    def _canonical_benchmark(value: str) -> str | None:
 534|        """归一化标板基准别名。"""
 535|        text = value.strip()
 536|        if not text:
 537|            return None
 538|        if any(alias in text for alias in ("TÜV北德", "TUV北德", "新北德", "北德")):
 539|            return "新北德"
 540|        if "计量院" in text:
 541|            return "中国计量院"
 542|        if "莱茵" in text:
 543|            return "莱茵基准"
 544|        return None
 545|
 546|    def _normalize_supplier_candidate(self, value: Any) -> str | None:
 547|        """校验 LLM 或规则抽取出的供应商是否存在于 active 功率模型。"""
 548|        raw_values = value if isinstance(value, list) else [value]
 549|        suppliers = self._active_power_suppliers()
 550|        for raw in raw_values:
 551|            text = str(raw or "").replace(" ", "")
 552|            for supplier in sorted(suppliers, key=len, reverse=True):
 553|                if supplier and supplier.replace(" ", "") == text:
 554|                    return supplier
 555|        return None
 556|
 557|    @staticmethod
 558|    def _normalize_target_power_ratio(value: Any) -> dict[str, float]:
 559|        """校验并归一 LLM 候选目标功率比例。"""
 560|        if not isinstance(value, dict):
 561|            return {}
 562|        result: dict[str, float] = {}
 563|        for key, raw_ratio in value.items():
 564|            try:
 565|                power = float(key)
 566|                ratio = float(raw_ratio)
 567|            except (TypeError, ValueError):
 568|                continue
 569|            if ratio <= 0:
 570|                continue
 571|            normalized_key = str(int(power)) if power.is_integer() else str(power)
 572|            result[normalized_key] = ratio
 573|        return result
 574|
 575|    @staticmethod
 576|    def _target_ratio_matches_rule(candidate: dict[str, float], rule_target: dict[str, float]) -> bool:
 577|        """校验 LLM 目标功率比例是否完全来自规则层抽取。
 578|
 579|        参数：
 580|            candidate: LLM 候选目标比例；
```


## QA power response fail-closed + M3 calls

```python
 358|    def _power_response(self, *, question: str, nlu: PlanBomNluCandidate) -> PlanBomQaResponse:
 359|        """处理计划 BOM 功率预测 / 供应商推荐问答。
 360|
 361|        参数：
 362|            question: 原始问题；
 363|            nlu: 已完成规则和可选 LLM guardrail 的 NLU 候选。
 364|
 365|        返回：
 366|            QA 响应。所有配置解析来自 M4，所有数值计算来自 M3，LLM 不参与计算。
 367|        """
 368|
 369|        tail = (nlu.slots.get("order_tail_no") or [None])[0]
 370|        benchmark = nlu.slots.get("benchmark")
 371|        resolution = self.power_config_resolver.resolve(order_no=tail, benchmark=benchmark)
 372|        resolution_payload = resolution.to_dict()
 373|        if resolution.status in {CANDIDATE_REQUIRED_STATUS, PARTIAL_STATUS}:
 374|            slot_name = "candidate" if resolution.status == CANDIDATE_REQUIRED_STATUS else "power_configuration"
 375|            nlu.missing_slots = sorted(set([*(nlu.missing_slots or []), slot_name]))
 376|            return self._with_presentation(
 377|                PlanBomQaResponse(
 378|                    question=question,
 379|                    classification="B",
 380|                    status=PlanBomQaStatus(
 381|                        code="CLARIFICATION_REQUIRED",
 382|                        message="功率预测配置仍需确认",
 383|                        severity="warning",
 384|                    ),
 385|                    nlu=nlu,
 386|                    answer_summary=self._power_resolution_clarification_summary(resolution_payload),
 387|                    raw_result={"bom_config_resolution": resolution_payload},
 388|                    warnings=["M4 配置解析未完全 resolved，已停止调用 M3 计算，避免编造功率预测。"],
 389|                )
 390|            )
 391|        if resolution.status in {NOT_FOUND_STATUS, NO_ACTIVE_MODEL_STATUS} or resolution.model_code is None:
 392|            return self._empty_response(
 393|                question=question,
 394|                nlu=nlu,
 395|                reason=resolution.message,
 396|                raw={"bom_config_resolution": resolution_payload},
 397|            )
 398|        if resolution.status != RESOLVED_STATUS:
 399|            return self._empty_response(
 400|                question=question,
 401|                nlu=nlu,
 402|                reason=f"BOM 配置映射状态不可用于功率预测：{resolution.status}",
 403|                raw={"bom_config_resolution": resolution_payload},
 404|            )
 405|
 406|        configuration = resolution.to_prediction_configuration()
 407|        supplier_name = nlu.slots.get("supplier_name")
 408|        if supplier_name:
 409|            configuration["supplier"] = supplier_name
 410|        try:
 411|            if nlu.intent == "plan_power_supplier_recommendation":
 412|                recommendation = self.power_recommendation_service.recommend(
 413|                    model_code=resolution.model_code,
 414|                    configuration=configuration,
 415|                    target_power_ratio=nlu.slots.get("target_power_ratio"),
 416|                    supplier_names=[supplier_name] if supplier_name else None,
 417|                )
 418|                return self._power_recommendation_response(
 419|                    question=question,
 420|                    nlu=nlu,
 421|                    resolution_payload=resolution_payload,
 422|                    recommendation=recommendation,
 423|                )
 424|            prediction = self.power_prediction_engine.predict(
 425|                model_code=resolution.model_code,
 426|                configuration=configuration,
 427|                supplier_name=supplier_name,
 428|            )
 429|            return self._power_prediction_response(
 430|                question=question,
 431|                nlu=nlu,
 432|                resolution_payload=resolution_payload,
 433|                prediction=prediction,
 434|            )
 435|        except PowerPredictionError as exc:
 436|            return self._empty_response(
 437|                question=question,
 438|                nlu=nlu,
 439|                reason=str(exc),
 440|                raw={"bom_config_resolution": resolution_payload, "power_error": str(exc)},
 441|            )
 442|
 443|    def _power_prediction_response(
 444|        self,
 445|        *,
 446|        question: str,
 447|        nlu: PlanBomNluCandidate,
 448|        resolution_payload: dict[str, Any],
 449|        prediction: PowerPredictionResult,
 450|    ) -> PlanBomQaResponse:
 451|        """构造单供应商功率预测 QA 响应。
 452|
 453|        参数：
 454|            question: 原始问题；
 455|            nlu: NLU 候选；
 456|            resolution_payload: M4 配置映射追溯；
 457|            prediction: M3 确定性预测结果。
 458|
 459|        返回：
 460|            A 类预测响应。
 461|        """
 462|
 463|        rows = self._power_distribution_rows(prediction)
 464|        configuration_text = self._power_configuration_text(resolution_payload)
 465|        answer = (
 466|            f"已完成订单 {resolution_payload.get('order_no')} 的功率预测：版型 {prediction.model_code}，"
 467|            f"供应商 {prediction.supplier_name}，中心功率 {round(prediction.center_power, 4)}W。"
 468|            f"配置来源：{configuration_text}。"
 469|        )
 470|        warnings = list(resolution_payload.get("warnings") or []) + list(prediction.warnings)
 471|        return self._with_presentation(
 472|            PlanBomQaResponse(
 473|                question=question,
 474|                classification="A",
 475|                status=PlanBomQaStatus(code="OK", message="功率预测成功"),
 476|                nlu=nlu,
 477|                answer_summary=answer,
 478|                result_table=PlanBomTableSpec(columns=["功率档", "预测比例", "累计比例", "中心功率", "供应商"], rows=rows),
 479|                raw_result={
 480|                    "bom_config_resolution": resolution_payload,
 481|                    "power_prediction": prediction.to_dict(),
 482|                },
 483|                warnings=warnings,
 484|            )
 485|        )
 486|
 487|    def _power_recommendation_response(
 488|        self,
 489|        *,
 490|        question: str,
 491|        nlu: PlanBomNluCandidate,
 492|        resolution_payload: dict[str, Any],
 493|        recommendation: PowerRecommendationResult,
 494|    ) -> PlanBomQaResponse:
 495|        """构造目标功率比例下的供应商推荐 QA 响应。
 496|
 497|        参数：
 498|            question: 原始问题；
 499|            nlu: NLU 候选；
 500|            resolution_payload: M4 配置映射追溯；
 501|            recommendation: M3 推荐服务输出。
 502|
 503|        返回：
 504|            A 类推荐响应。
 505|        """
 506|
 507|        rows = self._power_recommendation_rows(recommendation)
 508|        top_supplier = recommendation.recommendations[0].supplier_name if recommendation.recommendations else "无"
 509|        answer = (
 510|            f"已按订单 {resolution_payload.get('order_no')} 的 BOM 配置和目标功率比例完成供应商推荐，"
 511|            f"当前最高匹配供应商为 {top_supplier}。"
 512|        )
 513|        warnings = list(resolution_payload.get("warnings") or []) + list(recommendation.warnings)
 514|        return self._with_presentation(
 515|            PlanBomQaResponse(
 516|                question=question,
 517|                classification="A",
 518|                status=PlanBomQaStatus(code="OK", message="供应商功率推荐成功"),
 519|                nlu=nlu,
 520|                answer_summary=answer,
```


## QA power result serialization

```python
 520|                answer_summary=answer,
 521|                result_table=PlanBomTableSpec(
 522|                    columns=["供应商", "匹配度", "目标功率档", "目标比例", "预测比例", "差异", "中心功率"],
 523|                    rows=rows,
 524|                ),
 525|                raw_result={
 526|                    "bom_config_resolution": resolution_payload,
 527|                    "power_recommendation": recommendation.to_dict(),
 528|                },
 529|                warnings=warnings,
 530|            )
 531|        )
 532|
 533|    @staticmethod
 534|    def _power_distribution_rows(prediction: PowerPredictionResult) -> list[dict[str, Any]]:
 535|        """转换 M3 功率档分布为 QA 表格行。"""
 536|        rows: list[dict[str, Any]] = []
 537|        cumulative = 0.0
 538|        for power_bin, ratio in prediction.weighted_distribution.items():
 539|            cumulative += float(ratio)
 540|            rows.append(
 541|                {
 542|                    "功率档": f"{power_bin}W",
 543|                    "预测比例": round(float(ratio) * 100.0, 4),
 544|                    "累计比例": round(cumulative * 100.0, 4),
 545|                    "中心功率": round(prediction.center_power, 4),
 546|                    "供应商": prediction.supplier_name,
 547|                }
 548|            )
 549|        return rows
 550|
 551|    @staticmethod
 552|    def _power_recommendation_rows(recommendation: PowerRecommendationResult) -> list[dict[str, Any]]:
 553|        """转换 M3 推荐结果为 QA 表格行。"""
 554|        rows: list[dict[str, Any]] = []
 555|        for item in recommendation.recommendations:
 556|            for power_bin, target_ratio in recommendation.target_power_ratio.items():
 557|                rows.append(
 558|                    {
 559|                        "供应商": item.supplier_name,
 560|                        "匹配度": round(item.score, 4),
 561|                        "目标功率档": f"{power_bin}W",
 562|                        "目标比例": round(float(target_ratio) * 100.0, 4),
 563|                        "预测比例": round(float(item.predicted_target_ratio.get(power_bin, 0.0)) * 100.0, 4),
 564|                        "差异": round(float(item.target_diff.get(power_bin, 0.0)) * 100.0, 4),
 565|                        "中心功率": round(item.prediction.center_power, 4),
 566|                    }
 567|                )
 568|        return rows
 569|
 570|    @staticmethod
 571|    def _power_configuration_text(resolution_payload: dict[str, Any]) -> str:
 572|        """汇总 M4 已解析配置，供 answer_summary 使用。"""
 573|        resolved_config = resolution_payload.get("resolved_config") or {}
 574|        pairs = []
 575|        for key in ["glass", "ribbon", "busbar", "cable", "cell_size", "benchmark"]:
 576|            item = resolved_config.get(key) or {}
 577|            if item.get("value"):
 578|                pairs.append(f"{key}={item['value']}")
 579|        return "；".join(pairs) if pairs else "无可展示配置"
 580|
 581|    @staticmethod
 582|    def _power_resolution_clarification_summary(resolution_payload: dict[str, Any]) -> str:
 583|        """为 M4 candidate / partial 状态生成追问摘要。"""
 584|        if resolution_payload.get("status") == CANDIDATE_REQUIRED_STATUS:
 585|            count = resolution_payload.get("candidate_total_count") or len(resolution_payload.get("candidates") or [])
 586|            return f"当前订单条件命中 {count} 个 BOM 候选，请先确认订单或文件实例后再做功率预测。"
 587|        unresolved = resolution_payload.get("unresolved_items") or []
 588|        labels = [str(item.get("factor_key")) for item in unresolved if item.get("factor_key")]
 589|        return f"当前 BOM 配置仍有未确认项：{', '.join(labels) if labels else '未知配置'}。请确认后再执行功率预测。"
 590|
 591|    def _resolve_core_material_categories(
 592|        self,
 593|        *,
 594|        question: str,
 595|        nlu: PlanBomNluCandidate,
 596|        default_categories: list[str] | None = None,
 597|    ) -> tuple[list[str], PlanBomQaResponse | None]:
 598|        """解析可进入当前 detail/compare 主链路的核心材料类别。
 599|
 600|        参数：
 601|            question: 原始问题；
 602|            nlu: NLU 候选；
 603|            default_categories: 未显式指定材料时的默认核心材料范围。
 604|
 605|        返回：
 606|            二元组：(可安全传入 Pydantic 查询 schema 的核心材料列表, 非核心材料受控响应)。
 607|        """
 608|
 609|        requested = list(nlu.slots.get("material_category") or [])
 610|        core_categories = [category for category in requested if category in CORE_MATERIAL_CATEGORIES]
 611|        invalid_or_non_core = [category for category in requested if category not in CORE_MATERIAL_CATEGORIES]
 612|        llm_non_core = list(nlu.slots.get("non_core_material_category") or [])
 613|        non_core_categories: list[str] = []
 614|        for category in [*invalid_or_non_core, *llm_non_core]:
 615|            if category and category not in non_core_categories:
 616|                non_core_categories.append(category)
 617|        if non_core_categories and not self._question_mentions_core_material(question):
 618|            return [], self._non_core_material_response(question=question, nlu=nlu, categories=non_core_categories)
 619|        if non_core_categories and not core_categories:
 620|            return [], self._non_core_material_response(question=question, nlu=nlu, categories=non_core_categories)
 621|        if non_core_categories:
 622|            nlu.guardrail_notes.append(
 623|                f"已过滤当前核心五类查询不支持的非核心材料：{', '.join(non_core_categories)}。"
 624|            )
 625|        return core_categories or list(default_categories or CORE_MATERIAL_CATEGORIES), None
 626|
 627|    @staticmethod
 628|    def _question_mentions_core_material(question: str) -> bool:
 629|        """判断问题原文是否显式包含核心五类材料表达。
 630|
 631|        参数：
 632|            question: 原始问题。
 633|
 634|        返回：
 635|            包含核心五类或五类集合表达时返回 True。
 636|        """
 637|
 638|        core_words = ("玻璃", "间隙贴膜", "间隙膜", "焊带", "互联条", "汇流条", "接线盒", "线盒", "五类", "关键材料", "核心材料", "核心辅材", "关键辅材")
 639|        return any(word in question for word in core_words)
 640|
```


## Presentation deterministic-only for power intents

```python
  23|    DISPLAY_TYPES = {
  24|        "narrative",
  25|        "table",
  26|        "comparison_table",
  27|        "summary_cards",
  28|        "clarification",
  29|        "unsupported",
  30|        "empty_result",
  31|        "mixed",
  32|        "error",
  33|    }
  34|    POWER_INTENTS = {"plan_power_prediction", "plan_power_supplier_recommendation"}
  35|
  36|    def __init__(
  37|        self,
  38|        *,
  39|        enabled: bool | None = None,
  40|        base_url: str | None = None,
  41|        api_key: str | None = None,
  42|        model: str | None = None,
  43|        client: Any | None = None,
  44|    ) -> None:
  45|        """初始化计划 BOM 表达层。
  46|
  47|        参数：
  48|            enabled: 是否启用表达层，默认跟随全局答案表达层开关；
  49|            base_url: LLM 服务地址；
  50|            api_key: LLM 密钥；
  51|            model: 表达层模型名，优先使用专用模型，未配置时兜底通用模型；
  52|            client: 测试注入客户端。
  53|
  54|        返回：
  55|            无返回值。
  56|        """
  57|
  58|        self.enabled = settings.llm_answer_presentation_enabled if enabled is None else enabled
  59|        self.base_url = base_url if base_url is not None else settings.llm_base_url
  60|        self.api_key = api_key if api_key is not None else settings.llm_api_key
  61|        self.model = model if model is not None else (settings.llm_answer_presentation_model or settings.llm_model)
  62|        self._client = client
  63|
  64|    def build_presentation(self, response: PlanBomQaResponse) -> PlanBomPresentation:
  65|        """生成计划 BOM presentation。
  66|
  67|        参数：
  68|            response: 确定性 BOM QA 响应。
  69|
  70|        返回：
  71|            安全可用的 presentation，LLM 不可用或校验失败时返回确定性版本。
  72|        """
  73|
  74|        fallback = self._build_deterministic_presentation(response)
  75|        if response.nlu.intent in self.POWER_INTENTS:
  76|            # 功率预测类答案包含中心功率、档位比例、供应商匹配度等数值结果。
  77|            # 这些结果只能来自 M3 确定性服务，表达层不再调用 LLM，避免改写或新增数值事实。
  78|            fallback.debug["fallback_reason"] = "plan_power_deterministic_only"
  79|            return fallback
  80|        if not self.enabled:
  81|            fallback.debug["fallback_reason"] = "presentation_disabled"
  82|            return fallback
  83|        if not self._is_llm_available():
  84|            fallback.debug["fallback_reason"] = "llm_not_configured"
  85|            return fallback
  86|        payload, error = self._request_llm(response, fallback)
  87|        if error:
  88|            fallback.debug["fallback_reason"] = error
  89|            return fallback
  90|        normalized, validation_error = self._normalize_and_validate(response, fallback, payload)
  91|        if validation_error:
  92|            fallback.debug["fallback_reason"] = validation_error
  93|            return fallback
  94|        normalized.debug.update({"presentation_source": "llm", "llm_model_name": self.model})
  95|        return normalized
  96|
  97|    def _build_deterministic_presentation(self, response: PlanBomQaResponse) -> PlanBomPresentation:
  98|        """构造确定性展示。
  99|
 100|        参数：
 101|            response: 确定性 BOM QA 响应。
 102|
 103|        返回：
 104|            不依赖 LLM 的 presentation。
 105|        """
 106|
 107|        display_type = self._resolve_display_type(response)
 108|        caveats = [
 109|            "所有订单、物料、版本和规格均来自已导入的计划 BOM 结构化数据。",
 110|            "LLM 只允许优化表达，不作为查数或改写结果来源。",
 111|        ]
 112|        if response.nlu.intent in {"plan_power_prediction", "plan_power_supplier_recommendation"}:
 113|            caveats.append("功率预测数值来自后端确定性功率模型；LLM、前端和 Excel 宏均不参与计算。")
 114|        presentation = PlanBomPresentation(
 115|            display_type=display_type,
 116|            title=self._build_title(response),
 117|            answer=response.answer_summary,
 118|            highlights=self._build_highlights(response),
 119|            table_spec=response.result_table if response.result_table.rows else None,
 120|            caveats=caveats,
 121|            debug={"presentation_source": "deterministic", "status_code": response.status.code},
 122|        )
 123|        if response.classification == "B":
 124|            presentation.follow_up = {
 125|                "questions": response.nlu.missing_slots,
 126|                "examples": self._build_follow_up_examples(response),
 127|            }
```


## M5 focused tests

```python
  72|
  73|
  74|class _FakeLlmClient:
  75|    """测试用 OpenAI 兼容客户端，记录是否真的发生 LLM 调用。"""
  76|
  77|    def __init__(self, payload: dict[str, object]) -> None:
  78|        self.payload = payload
  79|        self.calls = 0
  80|        self.chat = self
  81|        self.completions = self
  82|
  83|    def create(self, **_: object):
  84|        """返回最小 completion 对象，模拟 LLM JSON 输出。"""
  85|        self.calls += 1
  86|        message = type("Message", (), {"content": json.dumps(self.payload, ensure_ascii=False)})()
  87|        choice = type("Choice", (), {"message": message})()
  88|        return type("Completion", (), {"choices": [choice]})()
  89|
  90|
  91|def test_plan_bom_qa_answers_power_prediction_for_real_order(live_db_session, qa_service) -> None:
  92|    """计划 BOM QA 应能把功率预测问题串联到 M4 配置解析和 M3 确定性预测。"""
  93|    tail, _, _ = _resolved_order_tail(live_db_session)
  94|
  95|    response = qa_service.ask(f"订单{tail}做功率预测，给出功率档分布", use_llm=False)
  96|
  97|    assert response.classification == "A"
  98|    assert response.status.code == "OK"
  99|    assert response.nlu.intent == "plan_power_prediction"
 100|    assert response.raw_result["bom_config_resolution"]["status"] == RESOLVED_STATUS
 101|    assert response.raw_result["power_prediction"]["center_power"] > 0
 102|    assert response.raw_result["power_prediction"]["weighted_distribution"]
 103|    assert response.result_table.rows
 104|    assert {"功率档", "预测比例"}.issubset(set(response.result_table.columns))
 105|    assert response.presentation is not None
 106|    assert response.presentation.table_spec is not None
 107|
 108|
 109|def test_plan_bom_qa_recommends_suppliers_by_target_ratio(live_db_session, qa_service) -> None:
 110|    """用户给出目标功率比例时，QA 应调用 M3 推荐服务并返回供应商匹配度。"""
 111|    tail, _, resolved = _resolved_order_tail(live_db_session)
 112|    prediction = PowerPredictionEngine(live_db_session).predict(
 113|        model_code=resolved.model_code,
 114|        configuration=resolved.to_prediction_configuration(),
 115|    )
 116|    target = _target_ratio_from_prediction(prediction)
 117|    bins = list(target)
 118|
 119|    response = qa_service.ask(f"订单{tail}目标{bins[0]}W 50%，{bins[1]}W 50%，推荐供应商", use_llm=False)
 120|
 121|    assert response.classification == "A"
 122|    assert response.status.code == "OK"
 123|    assert response.nlu.intent == "plan_power_supplier_recommendation"
 124|    assert response.nlu.slots["target_power_ratio"]
 125|    recommendation = response.raw_result["power_recommendation"]
 126|    assert recommendation["recommendations"]
 127|    assert response.result_table.rows
 128|    assert {"供应商", "匹配度"}.issubset(set(response.result_table.columns))
 129|
 130|
 131|def test_plan_bom_qa_accepts_explicit_supplier_for_power_prediction(live_db_session, qa_service) -> None:
 132|    """显式供应商只作为确定性预测输入，不由 LLM 或前端补算。"""
 133|    tail, _, resolved = _resolved_order_tail(live_db_session)
 134|    baseline = PowerPredictionEngine(live_db_session).predict(
 135|        model_code=resolved.model_code,
 136|        configuration=resolved.to_prediction_configuration(),
 137|    )
 138|
 139|    response = qa_service.ask(f"订单{tail}按{baseline.supplier_name}供应商预测功率分布", use_llm=False)
 140|
 141|    assert response.classification == "A"
 142|    assert response.nlu.slots["supplier_name"] == baseline.supplier_name
 143|    assert response.raw_result["power_prediction"]["supplier_name"] == baseline.supplier_name
 144|
 145|
 146|def test_power_question_without_order_requires_clarification(qa_service) -> None:
 147|    """缺少订单的功率问题只能追问，不能绕过 BOM 配置映射直接计算。"""
 148|    response = qa_service.ask("帮我做功率预测并推荐供应商", use_llm=False)
 149|
 150|    assert response.classification == "B"
 151|    assert response.status.code == "CLARIFICATION_REQUIRED"
 152|    assert "order_id" in response.nlu.missing_slots
 153|    assert response.raw_result == {}
 154|
 155|
 156|def test_llm_target_ratio_without_question_grounding_is_rejected(live_db_session) -> None:
 157|    """LLM 不能凭空补目标功率比例并绕过缺槽保护。"""
 158|    tail, _, _ = _resolved_order_tail(live_db_session)
 159|    repository = PlanBomQueryRepository(live_db_session)
 160|    fake_client = _FakeLlmClient(
 161|        {
 162|            "intent_candidate": "plan_power_supplier_recommendation",
 163|            "slot_candidate": {
 164|                "order_tail_no": [tail],
 165|                "target_power_ratio": {"620": 50, "625": 50},
 166|            },
 167|            "confidence": 0.95,
 168|        }
 169|    )
 170|    nlu = PlanBomNluCenterService(
 171|        repository=repository,
 172|        base_url="http://llm.invalid",
 173|        api_key="k",
 174|        model="test-model",
 175|        client=fake_client,
 176|    )
 177|
 178|    candidate = nlu.understand(f"订单{tail}推荐供应商", use_llm=True)
 179|
 180|    assert fake_client.calls == 1
 181|    assert candidate.intent == "plan_power_supplier_recommendation"
 182|    assert candidate.slots.get("target_power_ratio") == {}
 183|    assert "target_power_ratio" in candidate.missing_slots
 184|
 185|
 186|def test_llm_order_without_question_grounding_cannot_trigger_power_calculation(live_db_session) -> None:
 187|    """LLM 不能凭空补订单号并触发 M4/M3 功率计算。"""
 188|    tail, _, _ = _resolved_order_tail(live_db_session)
 189|    repository = PlanBomQueryRepository(live_db_session)
 190|    fake_client = _FakeLlmClient(
 191|        {
 192|            "intent_candidate": "plan_power_prediction",
 193|            "slot_candidate": {"order_tail_no": [tail]},
 194|            "confidence": 0.95,
 195|        }
 196|    )
 197|    engine = PowerPredictionEngine(live_db_session)
 198|    service = PlanBomQaService(
 199|        repository=repository,
 200|        query_service=PlanBomQueryService(repository=repository),
 201|        nlu_service=PlanBomNluCenterService(
 202|            repository=repository,
 203|            base_url="http://llm.invalid",
 204|            api_key="k",
 205|            model="test-model",
 206|            client=fake_client,
 207|        ),
 208|        presentation_service=PlanBomAnswerPresentationService(enabled=False, base_url="", api_key="", model=""),
 209|        power_config_resolver=PlanBomPowerConfigResolverService(live_db_session, repository=repository),
 210|        power_prediction_engine=engine,
 211|        power_recommendation_service=PowerRecommendationService(live_db_session, engine=engine),
 212|    )
 213|
 214|    response = service.ask("帮我做功率预测", use_llm=True)
 215|
 216|    assert fake_client.calls == 1
 217|    assert response.classification == "B"
 218|    assert "order_id" in response.nlu.missing_slots
 219|    assert response.raw_result == {}
 220|
 221|
 222|def test_llm_supplier_and_benchmark_without_question_grounding_are_rejected(live_db_session) -> None:
 223|    """LLM 不能凭空补供应商或标板来改变 M3 预测输入。"""
 224|    tail, _, resolved = _resolved_order_tail(live_db_session)
 225|    repository = PlanBomQueryRepository(live_db_session)
 226|    fake_client = _FakeLlmClient(
 227|        {
 228|            "intent_candidate": "plan_power_prediction",
 229|            "slot_candidate": {
 230|                "order_tail_no": [tail],
 231|                "supplier_name": resolved.resolved_config.get("supplier"),
 232|                "benchmark": "新北德",
 233|            },
 234|            "confidence": 0.95,
 235|        }
 236|    )
 237|    nlu = PlanBomNluCenterService(
 238|        repository=repository,
 239|        base_url="http://llm.invalid",
 240|        api_key="k",
 241|        model="test-model",
 242|        client=fake_client,
 243|    )
 244|
 245|    candidate = nlu.understand(f"订单{tail}做功率预测", use_llm=True)
 246|
 247|    assert fake_client.calls == 1
 248|    assert candidate.intent == "plan_power_prediction"
 249|    assert candidate.slots.get("supplier_name") is None
 250|    assert candidate.slots.get("benchmark") is None
 251|
 252|
 253|def test_power_presentation_bypasses_llm_even_when_enabled(live_db_session) -> None:
 254|    """功率预测展示层必须保持确定性，不能让 LLM 改写数值答案。"""
 255|    tail, _, _ = _resolved_order_tail(live_db_session)
 256|    repository = PlanBomQueryRepository(live_db_session)
 257|    engine = PowerPredictionEngine(live_db_session)
 258|    fake_client = _FakeLlmClient(
 259|        {
 260|            "display_type": "narrative",
 261|            "title": "LLM 改写标题",
 262|            "answer": "LLM 伪造中心功率 999W",
 263|            "highlights": ["LLM 伪造供应商"],
 264|        }
 265|    )
 266|    service = PlanBomQaService(
 267|        repository=repository,
 268|        query_service=PlanBomQueryService(repository=repository),
 269|        nlu_service=PlanBomNluCenterService(repository=repository, base_url="", api_key="", model=""),
 270|        presentation_service=PlanBomAnswerPresentationService(
 271|            enabled=True,
 272|            base_url="http://llm.invalid",
 273|            api_key="k",
 274|            model="test-model",
 275|            client=fake_client,
 276|        ),
 277|        power_config_resolver=PlanBomPowerConfigResolverService(live_db_session, repository=repository),
 278|        power_prediction_engine=engine,
 279|        power_recommendation_service=PowerRecommendationService(live_db_session, engine=engine),
 280|    )
 281|
 282|    response = service.ask(f"订单{tail}做功率预测，给出功率档分布", use_llm=False)
 283|
 284|    assert response.classification == "A"
 285|    assert fake_client.calls == 0
 286|    assert response.presentation is not None
 287|    assert response.presentation.debug["presentation_source"] == "deterministic"
 288|    assert response.presentation.debug["fallback_reason"] == "plan_power_deterministic_only"
 289|    assert "999W" not in response.presentation.answer
```


## Frontend routing/display excerpts

```ts
 318|interface UnifiedTable {
 319|  columns: string[]
 320|  rows: Array<Record<string, any>>
 321|}
 322|
 323|interface UnifiedResult {
 324|  displayType: string
 325|  title: string
 326|  answer: string
 327|  highlights: string[]
 328|  cards: Array<{ label: string; value: any; unit?: string | null; description?: string | null }>
 329|  chart: UnifiedChart | null
 330|  table: UnifiedTable | null
 331|  followUps: string[]
 332|  suggestions: string[]
 333|  caveats: string[]
 334|}
 335|
 336|interface UnifiedChart {
 337|  chart_type: 'line' | 'bar' | 'pie'
 338|  title?: string | null
 339|  x_axis?: string | null
 340|  y_axis?: string[]
 341|  series?: Array<Record<string, any>>
 342|  unit?: string | null
 343|  data?: Array<Record<string, any>>
 344|}
 345|
 346|interface ChartRenderPoint {
 347|  x: number
 348|  y: number
 349|}
 350|
 351|interface ChartRenderLabel {
 352|  x: number
 353|  text: string
 354|}
 355|
 356|interface ChartRenderBar {
 357|  x: number
 358|  y: number
 359|  width: number
 360|  height: number
 361|}
 362|
 363|interface ChartRenderSlice {
 364|  path: string
 365|  color: string
 366|  label: string
 367|  value: number
 368|  percent: number
 369|  tooltip: string
 370|}
 371|
 372|interface ChartLegendItem {
 373|  color: string
 374|  label: string
 375|  valueText: string
 376|}
 377|
 378|interface ChartValue {
 379|  label: unknown
 380|  value: number
 381|}
 382|
 383|interface ResultSummaryItem {
 384|  label: string
 385|  value: string
 386|}
 387|
 388|const pieChartColors = ['#2f7a4a', '#60a5fa', '#f59e0b', '#ef4444', '#8b5cf6', '#14b8a6', '#f97316', '#64748b']
 389|
 390|const question = ref('')
 391|const activeSession = ref<BusinessChatSession | null>(null)
 392|const conversationRef = ref<HTMLElement | null>(null)
 393|
 394|const examples = [
 395|  { domain: '物流', mode: 'logistics' as BusinessChatDomain, text: '2024年江苏省各城市总费用排名前五？' },
 396|  { domain: '物流', mode: 'logistics' as BusinessChatDomain, text: '查询下个月物流费用预测需要哪些条件？' },
 397|  { domain: 'BOM', mode: 'plan_bom' as BusinessChatDomain, text: '订单00104的玻璃、间隙贴膜、焊带、汇流条、接线盒规格描述？' },
 398|  { domain: 'BOM', mode: 'plan_bom' as BusinessChatDomain, text: '订单00104做功率预测，给出功率档分布。' },
 399|  { domain: 'BOM', mode: 'plan_bom' as BusinessChatDomain, text: '订单00104目标620W 50%，625W 50%，推荐供应商。' },
 400|  { domain: 'BOM', mode: 'plan_bom' as BusinessChatDomain, text: '哪些订单的接线盒规格不一样，按订单列出来。' },
 401|]
 402|
 403|const domainLabelMap: Record<BusinessChatDomain, string> = {
 404|  auto: '自动识别',
 405|  logistics: '物流数据',
 406|  plan_bom: '计划 BOM',
 407|}
 408|
 409|/** 当前窗口消息列表，切换窗口时自动隔离。 */
 410|const messages = computed(() => activeSession.value?.messages || [])
```