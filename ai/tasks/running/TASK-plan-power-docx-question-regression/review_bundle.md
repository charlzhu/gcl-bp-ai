# TASK-plan-power-docx-question-regression Review Bundle

## Scope
- 从附件 `ai/inbox/attachments/BOM配置搭配问询：.docx` 的 12 道功率题抽象验收模板。
- 订单类问题使用当前库真实可解析 BOM 订单，不 hardcode docx 假订单/评审号/项目名。
- 显式配置类问题走 NLU 槽位抽取 -> M4 确定性配置解析 -> M3 确定性推荐/预测。
- 修复目标比例表达：`620:625 1:1`、`715和720 2:8`、`各占一半`、百分比写法。

## Changed files in this review
- backend/app/domains/plan_bom/services/nlu_center_service.py
- backend/app/domains/plan_bom/services/qa_service.py
- backend/app/domains/plan_bom/services/power_config_resolver_service.py
- tests/business_acceptance/test_plan_power_docx_question_regression.py

## Verification already run
- RED: 新增 docx regression 初跑失败，暴露原链路 B/CLARIFICATION_REQUIRED、显式配置未接入、目标比例/供应商识别不足。
- `PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_docx_question_regression.py -q` -> `33 passed in 10.12s`
- `PYTHONPATH=. pytest tests/business_acceptance/test_plan_power_docx_question_regression.py tests/business_acceptance/test_plan_power_m3_prediction_engine.py tests/business_acceptance/test_plan_power_m4_config_resolver.py tests/business_acceptance/test_plan_power_m5_qa_integration.py -q` -> `59 passed, 2 warnings in 25.94s`
- `PYTHONPATH=. pytest -q` -> `107 passed, 2 warnings in 32.96s`
- `python -m compileall -q backend/app tests` -> exit 0
- `npm run build` -> exit 0 (only Vite chunk-size warning)
- `git diff --check` -> exit 0

## Static scan
### Added-line secret/shell/eval/pickle/SQL-format scan
exit=0
```
(no findings)
```

### Old plan power admin token exact scan
exit=0
```
(no findings)
```

## Critical excerpts
### backend/app/domains/plan_bom/services/nlu_center_service.py:147-195
```python
 147|        slots["model"] = self._extract_model(normalized)
 148|        slots["year"] = self._extract_year(normalized)
 149|        slots["country"] = self._extract_country(normalized)
 150|        slots["target_power_ratio"] = self._extract_target_power_ratio(normalized)
 151|        slots["supplier_name"] = self._extract_supplier_name(normalized)
 152|        slots["benchmark"] = self._extract_benchmark(normalized)
 153|        slots["explicit_power_configuration"] = self._extract_explicit_power_configuration(normalized)
 154|        slots["need_table"] = any(word in normalized for word in ("表格", "清单", "列表", "统计出来", "列出来"))
 155|        slots["need_excel"] = any(word.lower() in normalized.lower() for word in ("excel", "导表", "导出"))
 156|        slots["output_format"] = "excel" if slots["need_excel"] else ("table" if slots["need_table"] else "narrative")
 157|
 158|        intent = self._detect_intent(normalized, slots)
 159|        missing_slots = self._detect_missing_slots(intent, slots)
 160|        confidence = 0.78 if not missing_slots else 0.58
 161|        return PlanBomNluCandidate(
 162|            question=question,
 163|            intent=intent,
 164|            slots=slots,
 165|            missing_slots=missing_slots,
 166|            confidence=confidence,
 167|            provider_mode="rule",
 168|            guardrail_notes=["规则层完成初始意图和槽位抽取。"],
 169|        )
 170|
 171|    def _detect_intent(self, question: str, slots: dict[str, Any]) -> str:
 172|        """判断受控意图。
 173|
 174|        参数：
 175|            question: 用户问题；
 176|            slots: 规则层已抽取槽位。
 177|
 178|        返回：
 179|            受控 intent 编码。
 180|        """
 181|
 182|        if self._is_power_question(question) or (
 183|            slots.get("target_power_ratio")
 184|            and (slots.get("model") or slots.get("supplier_name") or slots.get("explicit_power_configuration") or slots.get("order_tail_no"))
 185|        ):
 186|            if slots.get("target_power_ratio") or any(
 187|                word in question
 188|                for word in ("推荐供应商", "供应商推荐", "推荐电池", "匹配度", "目标功率", "目标比例", "目标", "占比")
 189|            ):
 190|                return "plan_power_supplier_recommendation"
 191|            return "plan_power_prediction"
 192|        if "到" in question and len(slots.get("bom_version") or []) >= 2:
 193|            return "bom_version_compare"
 194|        if any(word in question for word in ("版本", "A0", "A1", "A2", "A3", "变更")) and len(slots.get("bom_version") or []) >= 2:
 195|            return "bom_version_compare"
```

### backend/app/domains/plan_bom/services/nlu_center_service.py:467-515
```python
 467|            "功率预测",
 468|            "功率档",
 469|            "功率分布",
 470|            "目标功率",
 471|            "目标比例",
 472|            "需求占比",
 473|            "占比",
 474|            "电池效率",
 475|            "效率段",
 476|            "供应商推荐",
 477|            "推荐供应商",
 478|            "各家供应商",
 479|            "哪些家电池",
 480|            "哪几家电池",
 481|            "哪个效率",
 482|            "用供应商",
 483|            "需要什么样的电池",
 484|            "电池可以满足",
 485|            "功率倒推",
 486|            "满足订单需求功率",
 487|        )
 488|        return any(word in question for word in power_words)
 489|
 490|    @staticmethod
 491|    def _extract_target_power_ratio(question: str) -> dict[str, float]:
 492|        """从自然语言中抽取目标功率档比例。
 493|
 494|        参数：
 495|            question: 用户问题，例如“目标620W 50%，625W 50%”“620:625 1:1”“715和720 2:8”。
 496|
 497|        返回：
 498|            `{功率档: 比例}` 字典。比例保留用户原始占比数值，后续推荐服务会归一化。
 499|        """
 500|        target: dict[str, float] = {}
 501|
 502|        def put(power_value: str | float, ratio_value: str | float) -> None:
 503|            """写入一个功率档比例；非法数字或非正比例直接忽略。"""
 504|            try:
 505|                power = float(power_value)
 506|                ratio = float(ratio_value)
 507|            except (TypeError, ValueError):
 508|                return
 509|            if ratio <= 0:
 510|                return
 511|            key = str(int(power)) if power.is_integer() else str(power)
 512|            target[key] = ratio
 513|
 514|        pair_patterns = [
 515|            # 业务常用写法：715:720=2:8、620:625 1:1、715和720 2:8。
```

### backend/app/domains/plan_bom/services/nlu_center_service.py:542-590
```python
 542|        参数：
 543|            question: 用户问题，支持“焊带：0.24+玻璃：双镀+汇流条：...+接线盒：300/200”等 docx 问法。
 544|
 545|        返回：
 546|            可交给 M4 显式配置解析的配置字典；这里只做文本槽位抽取，不做数值计算。
 547|        """
 548|        config: dict[str, str] = {}
 549|        extractors = {
 550|            "ribbon": r"焊带\s*[:：]?\s*(?P<value>.+?)(?=\+?玻璃|[，,；;。]|$)",
 551|            "glass": r"玻璃\s*[:：]?\s*(?P<value>.+?)(?=\+?汇流条|\+?接线盒|[，,；;。]|$)",
 552|            "busbar": r"汇流条\s*[:：]?\s*(?P<value>.+?)(?=\+?接线盒|[，,；;。]|$)",
 553|            "cable": r"接线盒\s*[:：]?\s*(?P<value>.+?)(?=\s*[，,；;。]|\s*标板|$)",
 554|        }
 555|        for key, pattern in extractors.items():
 556|            match = re.search(pattern, question, flags=re.IGNORECASE)
 557|            if match:
 558|                value = match.group("value").strip().strip("+").strip()
 559|                if value:
 560|                    config[key] = value
 561|        benchmark = PlanBomNluCenterService._extract_benchmark(question)
 562|        if benchmark:
 563|            config["benchmark"] = benchmark
 564|        return config
 565|
 566|    def _extract_supplier_name(self, question: str) -> str | None:
 567|        """从问题中抽取已存在于 active 功率模型的供应商。
 568|
 569|        参数：
 570|            question: 用户问题。
 571|
 572|        返回：
 573|            命中的供应商名称；未命中时返回 None。
 574|        """
 575|        suppliers = self._active_power_suppliers()
 576|        normalized = question.replace(" ", "")
 577|        all_supplier_markers = ("各家", "所有供应商", "全部供应商", "哪些家", "哪几家", "各个供应商")
 578|        asks_all_suppliers = any(marker in normalized for marker in all_supplier_markers)
 579|        for supplier in sorted(suppliers, key=len, reverse=True):
 580|            supplier_key = supplier.replace(" ", "")
 581|            if supplier and supplier_key in normalized:
 582|                if asks_all_suppliers:
 583|                    # “通威、爱旭、时创等各家电池”这类 docx 派生问法是在举例要求全供应商，
 584|                    # 不能把第一个命中的供应商误当作筛选条件；真正指定单供应商的问法通常不会带“各家/哪些家”。
 585|                    return None
 586|                return supplier
 587|        return None
 588|
 589|    @staticmethod
 590|    def _extract_benchmark(question: str) -> str | None:
```

### backend/app/domains/plan_bom/services/nlu_center_service.py:773-821
```python
 773|
 774|        aliases: list[str] = []
 775|        normalized = question.lower().replace(" ", "")
 776|        for values in self.material_aliases.values():
 777|            for alias in values:
 778|                if alias.lower().replace(" ", "") in normalized and alias not in aliases:
 779|                    aliases.append(alias)
 780|        return aliases
 781|
 782|    @staticmethod
 783|    def _extract_versions(question: str) -> list[str]:
 784|        """抽取 BOM 版本号。
 785|
 786|        参数：
 787|            question: 用户问题。
 788|
 789|        返回：
 790|            版本号列表，例如 A0、A1。
 791|        """
 792|
 793|        versions = re.findall(r"\b[A-Ea-e]\d{0,2}\b", question)
 794|        return [item.upper() if len(item) > 1 else f"{item.upper()}0" for item in versions]
 795|
 796|    @staticmethod
 797|    def _extract_model(question: str) -> str | None:
 798|        """抽取产品型号。
 799|
 800|        参数：
 801|            question: 用户问题。
 802|
 803|        返回：
 804|            型号字符串；未命中时返回 None。
 805|        """
 806|
 807|        match = re.search(r"NT[0-9A-Z]+[-/][0-9A-Z]+GDF|NT[0-9A-Z]+GDF", question, flags=re.I)
 808|        return match.group(0).upper().replace("/", "-") if match else None
 809|
 810|    @staticmethod
 811|    def _extract_year(question: str) -> int | None:
 812|        """抽取年份。
 813|
 814|        参数：
 815|            question: 用户问题。
 816|
 817|        返回：
 818|            四位年份；未命中时返回 None。
 819|        """
 820|
 821|        match = re.search(r"20\d{2}", question)
```
### backend/app/domains/plan_bom/services/qa_service.py:334-382
```python
 334|                {
 335|                    "order_no": header.order_no,
 336|                    "order_name": header.order_name,
 337|                    "version_no": header.version_no,
 338|                    "material_category": ",".join(categories),
 339|                    "status": "缺失" if not lines else "存在",
 340|                    "source_file": header.raw_file_name,
 341|                }
 342|            )
 343|        return self._with_presentation(
 344|            PlanBomQaResponse(
 345|                question=question,
 346|                classification="A",
 347|                status=PlanBomQaStatus(code="OK", message="物料存在性检查完成"),
 348|                nlu=nlu,
 349|                answer_summary=f"已完成 {len(headers)} 个当前 BOM 版本的物料存在性检查，返回 {len(rows)} 条匹配记录。",
 350|                result_table=PlanBomTableSpec(
 351|                    columns=["order_no", "order_name", "version_no", "material_category", "status", "source_file"],
 352|                    rows=rows,
 353|                ),
 354|                raw_result={"checked_orders": len(headers), "matched_rows": len(rows)},
 355|            )
 356|        )
 357|
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
 371|        explicit_configuration = dict(nlu.slots.get("explicit_power_configuration") or {})
 372|        if benchmark and "benchmark" not in explicit_configuration:
 373|            explicit_configuration["benchmark"] = benchmark
 374|        if nlu.slots.get("supplier_name") and "supplier" not in explicit_configuration:
 375|            explicit_configuration["supplier"] = nlu.slots.get("supplier_name")
 376|        if tail:
 377|            resolution = self.power_config_resolver.resolve(order_no=tail, benchmark=benchmark)
 378|        else:
 379|            resolution = self.power_config_resolver.resolve_explicit_configuration(
 380|                model_code=nlu.slots.get("model"),
 381|                configuration=explicit_configuration,
 382|            )
```

### backend/app/domains/plan_bom/services/qa_service.py:474-522
```python
 474|        rows = self._power_distribution_rows(prediction)
 475|        configuration_text = self._power_configuration_text(resolution_payload)
 476|        answer = (
 477|            f"已完成订单 {resolution_payload.get('order_no')} 的功率预测：版型 {prediction.model_code}，"
 478|            f"供应商 {prediction.supplier_name}，中心功率 {round(prediction.center_power, 4)}W。"
 479|            f"配置来源：{configuration_text}。"
 480|        )
 481|        warnings = list(resolution_payload.get("warnings") or []) + list(prediction.warnings)
 482|        return self._with_presentation(
 483|            PlanBomQaResponse(
 484|                question=question,
 485|                classification="A",
 486|                status=PlanBomQaStatus(code="OK", message="功率预测成功"),
 487|                nlu=nlu,
 488|                answer_summary=answer,
 489|                result_table=PlanBomTableSpec(columns=["功率档", "预测比例", "累计比例", "中心功率", "供应商"], rows=rows),
 490|                raw_result={
 491|                    "bom_config_resolution": resolution_payload,
 492|                    "power_prediction": prediction.to_dict(),
 493|                },
 494|                warnings=warnings,
 495|            )
 496|        )
 497|
 498|    def _power_recommendation_response(
 499|        self,
 500|        *,
 501|        question: str,
 502|        nlu: PlanBomNluCandidate,
 503|        resolution_payload: dict[str, Any],
 504|        recommendation: PowerRecommendationResult,
 505|    ) -> PlanBomQaResponse:
 506|        """构造目标功率比例下的供应商推荐 QA 响应。
 507|
 508|        参数：
 509|            question: 原始问题；
 510|            nlu: NLU 候选；
 511|            resolution_payload: M4 配置映射追溯；
 512|            recommendation: M3 推荐服务输出。
 513|
 514|        返回：
 515|            A 类推荐响应。
 516|        """
 517|
 518|        rows = self._power_recommendation_rows(recommendation)
 519|        top_supplier = recommendation.recommendations[0].supplier_name if recommendation.recommendations else "无"
 520|        source_label = f"订单 {resolution_payload.get('order_no')} 的 BOM 配置" if resolution_payload.get("order_no") else "显式输入配置"
 521|        answer = (
 522|            f"已按{source_label}和目标功率比例完成供应商推荐，"
```

### backend/app/domains/plan_bom/services/qa_service.py:540-588
```python
 540|                },
 541|                warnings=warnings,
 542|            )
 543|        )
 544|
 545|    @staticmethod
 546|    def _power_distribution_rows(prediction: PowerPredictionResult) -> list[dict[str, Any]]:
 547|        """转换 M3 功率档分布为 QA 表格行。"""
 548|        rows: list[dict[str, Any]] = []
 549|        cumulative = 0.0
 550|        for power_bin, ratio in prediction.weighted_distribution.items():
 551|            cumulative += float(ratio)
 552|            rows.append(
 553|                {
 554|                    "功率档": f"{power_bin}W",
 555|                    "预测比例": round(float(ratio) * 100.0, 4),
 556|                    "累计比例": round(cumulative * 100.0, 4),
 557|                    "中心功率": round(prediction.center_power, 4),
 558|                    "供应商": prediction.supplier_name,
 559|                }
 560|            )
 561|        return rows
 562|
 563|    @staticmethod
 564|    def _power_recommendation_rows(recommendation: PowerRecommendationResult) -> list[dict[str, Any]]:
 565|        """转换 M3 推荐结果为 QA 表格行。"""
 566|        rows: list[dict[str, Any]] = []
 567|        target_bins = list(recommendation.target_power_ratio.keys())
 568|        for item in recommendation.recommendations:
 569|            efficiency_label = PlanBomQaService._suggest_efficiency_segment(item.prediction, target_bins)
 570|            for power_bin, target_ratio in recommendation.target_power_ratio.items():
 571|                rows.append(
 572|                    {
 573|                        "供应商": item.supplier_name,
 574|                        "匹配度": round(item.score, 4),
 575|                        "目标功率档": f"{power_bin}W",
 576|                        "目标比例": round(float(target_ratio) * 100.0, 4),
 577|                        "预测比例": round(float(item.predicted_target_ratio.get(power_bin, 0.0)) * 100.0, 4),
 578|                        "差异": round(float(item.target_diff.get(power_bin, 0.0)) * 100.0, 4),
 579|                        "中心功率": round(item.prediction.center_power, 4),
 580|                        "建议效率段": efficiency_label,
 581|                    }
 582|                )
 583|        return rows
 584|
 585|    @staticmethod
 586|    def _suggest_efficiency_segment(prediction: PowerPredictionResult, target_bins: list[str]) -> str:
 587|        """按目标功率档贡献度给出建议电池效率段。
 588|
```
### backend/app/domains/plan_bom/services/power_config_resolver_service.py:290-358
```python
 290|                option = self._coerce_to_valid_option(sheet.id, factor_key, benchmark_value)
 291|                if option is None:
 292|                    unresolved.append(
 293|                        PowerBomUnresolvedItem(
 294|                            factor_key="benchmark",
 295|                            reason="显式输入的标板基准未命中当前功率模型有效选项，不能回退默认值。",
 296|                            candidate_options=self._option_labels(sheet.id, "benchmark"),
 297|                            strategy="ask_confirmation",
 298|                        )
 299|                    )
 300|                    continue
 301|                default_item = PowerBomResolvedItem(
 302|                    factor_key="benchmark",
 303|                    value=option.option_label,
 304|                    source="explicit_input",
 305|                    confidence=0.95,
 306|                    source_description=benchmark,
 307|                    rule_id="explicit.benchmark",
 308|                )
 309|            else:
 310|                default_item = self._resolve_default_option(
 311|                    sheet,
 312|                    factor_key,
 313|                    input_value=None,
 314|                    source=str(default_rule.get("source") or "model_default"),
 315|                    confidence=float(default_rule.get("confidence") or 0.85),
 316|                )
 317|            if default_item is not None:
 318|                resolved[factor_key] = default_item
 319|            elif factor_key in {"cell_size", "supplier", "benchmark"}:
 320|                warnings.append(f"功率模型缺少默认 {factor_key} 选项，M3 调用时可能需要显式补充。")
 321|
 322|        return self._build_result(header, model_code_item.value, resolved, unresolved, source_lines, warnings)
 323|
 324|    def resolve_explicit_configuration(
 325|        self,
 326|        *,
 327|        model_code: str | None,
 328|        configuration: Mapping[str, Any] | None = None,
 329|    ) -> PowerBomConfigResolution:
 330|        """解析用户显式输入的功率预测配置。
 331|
 332|        参数：
 333|            model_code: 用户自然语言中给出的版型编码，例如 `NT12R-66GDF` 或 `NT12R/66GDF`。
 334|            configuration: 用户显式给出的配置项，支持 ribbon/glass/busbar/cable/benchmark/supplier/cell_size。
 335|
 336|        返回：
 337|            `PowerBomConfigResolution`。该结果不绑定 BOM 订单，order_no 为空，但仍复用 M4 的 option 校验、别名归一和追溯结构。
 338|        """
 339|        active_version = self._active_power_version()
 340|        if active_version is None:
 341|            return PowerBomConfigResolution(status=NO_ACTIVE_MODEL_STATUS, message="当前没有 active 功率模型版本，无法执行显式配置映射。")
 342|        if not model_code or not self._stringify(model_code):
 343|            return PowerBomConfigResolution(
 344|                status=PARTIAL_STATUS,
 345|                message="显式配置功率问答缺少版型编码。",
 346|                unresolved_items=[
 347|                    PowerBomUnresolvedItem(
 348|                        factor_key="model_code",
 349|                        reason="用户问题中未识别到当前功率模型支持的版型。",
 350|                        candidate_options=self._active_model_codes(active_version.id),
 351|                    )
 352|                ],
 353|            )
 354|
 355|        normalized_model_code = self._normalize_model_code(model_code)
 356|        sheet = self._get_sheet(active_version.id, normalized_model_code)
 357|        if sheet is None:
 358|            return PowerBomConfigResolution(
```

### backend/app/domains/plan_bom/services/power_config_resolver_service.py:728-796
```python
 728|            model_code=model_code,
 729|            resolved_config=resolved,
 730|            unresolved_items=unresolved,
 731|            source_lines=source_lines,
 732|            warnings=warnings,
 733|        )
 734|
 735|    def _candidate_required(self, message: str, headers: list[PlanBomHeader]) -> PowerBomConfigResolution:
 736|        """返回受控候选列表，避免宽泛查询一次性暴露过多候选。"""
 737|        total_count = len(headers)
 738|        limited_headers = headers[:CANDIDATE_LIMIT]
 739|        has_more = total_count > CANDIDATE_LIMIT
 740|        warnings = [f"候选数量 {total_count} 超过上限 {CANDIDATE_LIMIT}，仅返回前 {CANDIDATE_LIMIT} 条，请补充订单/文件条件。"] if has_more else []
 741|        return PowerBomConfigResolution(
 742|            status=CANDIDATE_REQUIRED_STATUS,
 743|            message=message,
 744|            candidates=[self._candidate(header) for header in limited_headers],
 745|            candidate_total_count=total_count,
 746|            candidate_has_more=has_more,
 747|            warnings=warnings,
 748|        )
 749|
 750|    def _coerce_to_valid_option(self, sheet_id: int, factor_key: str, value: str | None) -> PlanPowerFactorOption | None:
 751|        """把候选值校验并转换成当前模型真实 option。"""
 752|        if value is None or self._stringify(value) == "":
 753|            return None
 754|        canonical_value = self._canonical_option(factor_key, value)
 755|        for option in self._options(sheet_id, factor_key):
 756|            option_labels = [option.option_label, option.normalized_option_label]
 757|            for label in option_labels:
 758|                if self._normalize_label(self._canonical_option(factor_key, label)) == self._normalize_label(canonical_value):
 759|                    return option
 760|        return None
 761|
 762|    def _coerce_explicit_option(
 763|        self,
 764|        sheet: PlanPowerModelSheet,
 765|        factor_key: str,
 766|        value: str,
 767|        warnings: list[str],
 768|    ) -> PlanPowerFactorOption | None:
 769|        """把显式自然语言配置归一到当前模型真实 option。
 770|
 771|        参数：
 772|            sheet: 当前功率模型页。
 773|            factor_key: 配置项 key。
 774|            value: 用户原文中的配置值。
 775|            warnings: 输出警告列表；当使用确定性降级规则时记录原因。
 776|
 777|        返回：
 778|            命中的真实 `PlanPowerFactorOption`；无法安全命中时返回 None。
 779|        """
 780|        option = self._coerce_to_valid_option(sheet.id, factor_key, value)
 781|        if option is not None:
 782|            return option
 783|        normalized = self._normalize_label(value)
 784|        if factor_key == "benchmark":
 785|            return self._coerce_to_valid_option(sheet.id, factor_key, self._canonical_benchmark(value))
 786|        if factor_key == "ribbon":
 787|            # docx 中“0.24+0.26”表示混用焊带；M4 显式配置按较大直径作为模型选择项，
 788|            # 与 BOM 映射中按主用量/较大规格收敛到单一 Excel option 的原则一致。
 789|            values = re.findall(r"\d+(?:\.\d+)?", value)
 790|            if values:
 791|                selected = max(values, key=lambda item: Decimal(item))
 792|                option = self._coerce_to_valid_option(sheet.id, factor_key, self._format_number(selected))
 793|                if option is not None:
 794|                    if len(set(values)) > 1:
 795|                        warnings.append(f"显式焊带包含多个规格 {value}，已按较大直径 {option.option_label} 映射到功率模型单选项。")
 796|                    return option
```
### tests/business_acceptance/test_plan_power_docx_question_regression.py:3-39
```python
   3|from pathlib import Path
   4|from typing import Any
   5|
   6|import pytest
   7|from docx import Document
   8|
   9|from backend.app.db.session import SessionLocal
  10|from backend.app.domains.plan_bom.models import PlanBomHeader, PlanPowerModelVersion
  11|from backend.app.domains.plan_bom.repositories.query_repository import PlanBomQueryRepository
  12|from backend.app.domains.plan_bom.services.answer_presentation_service import PlanBomAnswerPresentationService
  13|from backend.app.domains.plan_bom.services.nlu_center_service import PlanBomNluCenterService
  14|from backend.app.domains.plan_bom.services.power_config_resolver_service import RESOLVED_STATUS, PlanBomPowerConfigResolverService
  15|from backend.app.domains.plan_bom.services.power_prediction_engine import PowerPredictionEngine
  16|from backend.app.domains.plan_bom.services.power_recommendation_service import PowerRecommendationService
  17|from backend.app.domains.plan_bom.services.qa_service import PlanBomQaService
  18|from backend.app.domains.plan_bom.services.query_service import PlanBomQueryService
  19|
  20|DOCX_PATH = Path("ai/inbox/attachments/BOM配置搭配问询：.docx")
  21|POWER_DOCX_EXAMPLE_COUNT = 12
  22|
  23|
  24|@pytest.fixture()
  25|def live_db_session():
  26|    """连接当前项目真实数据库，供 docx 问法回归从真实 BOM 与 active 功率模型动态抽题。"""
  27|    session = SessionLocal()
  28|    try:
  29|        try:
  30|            session.query(PlanBomHeader).limit(1).all()
  31|        except Exception as exc:  # pragma: no cover - 仅用于缺少本地验收库时跳过。
  32|            pytest.skip(f"当前环境无法连接真实 BOM 数据库，跳过 docx 问法回归：{exc}")
  33|        if session.query(PlanPowerModelVersion).filter_by(is_active=1).first() is None:
  34|            pytest.skip("当前数据库没有 active 功率模型版本，无法执行 docx 问法回归。")
  35|        yield session
  36|    finally:
  37|        session.close()
  38|
  39|
```

### tests/business_acceptance/test_plan_power_docx_question_regression.py:170-206
```python
 170|
 171|
 172|@pytest.mark.parametrize("variant", [0, 1])
 173|def test_docx_part1_multi_order_table_example_has_multiple_real_questions(live_db_session, qa_service, variant: int) -> None:
 174|    """docx 第一部分例题 3：多个真实订单五类核心材料规格生成表格。"""
 175|    tails = _five_active_order_tails(live_db_session)
 176|    joined = "/".join(tails)
 177|    questions = [
 178|        f"查找订单{joined}这几个订单的玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述并生成表格？",
 179|        f"把{','.join(tails)}五个评审号的关键BOM配置列成清单，字段要有玻璃、间隙膜、焊带、汇流条和接线盒。",
 180|    ]
 181|
 182|    response = qa_service.ask(questions[variant], use_llm=False)
 183|
 184|    _assert_ok_table_response(response, expected_intent="multi_order_material_table")
 185|
 186|
 187|@pytest.mark.parametrize("variant", [0, 1, 2])
 188|def test_docx_power_example_1_nt12_order_recommends_multiple_suppliers(live_db_session, qa_service, variant: int) -> None:
 189|    """docx 第二部分例题 1：NT12/66GDF 真实订单按 715/720=2/8 推荐可满足的电池供应商。"""
 190|    tail, _ = _resolved_order_by_model(live_db_session, "NT12-66GDF")
 191|    questions = [
 192|        f"NT12/66GDF（真实订单-{tail}）用哪些家电池可以满足715和720 2:8的需求占比？",
 193|        f"评审号{tail}目标功率715:720=2:8，请推荐通威、爱旭、时创等各家电池使用方案。",
 194|        f"订单{tail}要满足715W占20%、720W占80%，哪些供应商更合适？请表格展示。",
 195|    ]
 196|
 197|    response = qa_service.ask(questions[variant], use_llm=False)
 198|
 199|    _assert_power_recommendation_response(response, expected_bins={"715", "720"})
 200|    assert len({row["供应商"] for row in response.result_table.rows}) >= 3
 201|
 202|
 203|@pytest.mark.parametrize("variant", [0, 1, 2])
 204|def test_docx_power_example_2_nt12r_order_wuhu_efficiency_segment(live_db_session, qa_service, variant: int) -> None:
 205|    """docx 第二部分例题 2：NT12R/66GDF 真实订单指定芜湖供应商，回答满足 615/620=1/1 的效率段。"""
 206|    tail, _ = _resolved_order_by_model(live_db_session, "NT12R-66GDF")
```

## Reviewer questions
Return JSON only. Fail closed on security/logic issues. Focus on:
1. NLU only extracts intent/slots; M3/M4 own numeric/config calculation.
2. LLM candidates cannot silently alter order/supplier/benchmark/ratio.
3. Explicit config without order is resolved by deterministic active model options, not docx hardcode.
4. Target ratio parsing supports business forms and avoids treating `620:625` as ratio pair by itself.
5. All-supplier vs single-supplier wording does not over-filter.
6. Candidate/partial resolver status stops before calculation.
7. Tests cover docx 12 power examples with multiple business variants.
