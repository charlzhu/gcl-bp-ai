from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

CATALOG_VERSION = "business_analysis_inventory_sales_production_catalog.v1"
M6_GATE_VERSION = "business_analysis_inventory_sales_production_m6_live_provider_gate.v1"


def _m6_module():
    """加载产销存 M6 live provider gate 模块；RED 阶段应因模块尚未实现而失败。"""

    return importlib.import_module(
        "backend.app.domains.business_analysis.services.inventory_sales_production.m6_live_provider_gate"
    )


def _safe_text(payload: object) -> str:
    """把对象转成小写 JSON 文本，便于统一检查脱敏结果。"""

    return json.dumps(payload, ensure_ascii=False, default=str).lower()


def test_m6_catalog_reindex_documents_cover_canonical_dependencies_without_external_sources() -> None:
    """M6 catalog reindex 必须从产销存本地语义目录生成可召回文档，并排除外部/ODS/日志来源。"""

    m6 = _m6_module()

    builder = m6.InventorySalesProductionM6CatalogRecallDocumentBuilder()
    documents = builder.build_documents()
    by_id = {document.catalog_id: document for document in documents}

    assert m6.M6_ISP_LIVE_PROVIDER_GATE_VERSION == M6_GATE_VERSION
    assert "table:dwd_ba_isp_monthly_fact" in by_id
    assert "metric:shipment_volume" in by_id
    assert "metric:ending_inventory_volume" in by_id
    assert "dimension:base_name" in by_id
    assert "rule:policy_current_year_use_published_months_only" in by_id

    shipment_doc = by_id["metric:shipment_volume"]
    assert shipment_doc.catalog_version == CATALOG_VERSION
    assert shipment_doc.domain == "business_analysis"
    assert shipment_doc.sub_domain == "inventory_sales_production"
    assert set(shipment_doc.required_catalog_refs) >= {
        "table:dwd_ba_isp_monthly_fact",
        "dimension:business_year",
        "rule:sales_defaults_to_shipment_volume",
    }
    assert "销量" in shipment_doc.retrieval_text
    assert "发货量" in shipment_doc.retrieval_text

    serialized = _safe_text([document.model_dump(mode="json") for document in documents])
    for forbidden in ("ods_ba_isp", "sap_oracle", "oracle", "v_sap_", "sys_query_log", "raw_sql", "password"):
        assert forbidden not in serialized


def test_m6_provider_smoke_reports_embedding_vector_rerank_llm_separately_and_redacts_details() -> None:
    """M6 provider smoke 必须拆分四类 provider 检查，并对 provider/密钥/连接细节做公开脱敏。"""

    m6 = _m6_module()

    runner = m6.InventorySalesProductionM6ProviderSmokeRunner(
        embedding_probe=lambda: {"status": "PASS"},
        vector_store_probe=lambda: {"collection": "isp_catalog_secret_collection", "status": "ok"},
        rerank_probe=lambda: {"status": "PASS"},
        llm_probe=lambda: {"status": "PASS", "provider": "bailian", "model": "deepseek", "api_key": "***"},
    )
    result = runner.run()

    assert [gate.name for gate in result.gates] == ["embedding", "vector_store", "rerank", "llm"]
    assert all(gate.status == "PASS" for gate in result.gates)
    assert result.ok is True

    safe_json = m6.render_safe_m6_provider_smoke_summary_json(result)
    lower = safe_json.lower()
    assert "embedding" in lower
    assert "vector_store" in lower
    assert "rerank" in lower
    assert "llm" in lower
    for leaked in ("sk-live-secret", "api_key", "password", "bailian", "deepseek", "isp_catalog_secret_collection"):
        assert leaked not in lower


def test_m6_provider_smoke_preserves_blocked_status_and_redacts_blocked_reason() -> None:
    """provider smoke 遇到缺配置/外部阻塞时必须保持 BLOCKED，不得降级成 FAIL 或伪 PASS。"""

    m6 = _m6_module()

    runner = m6.InventorySalesProductionM6ProviderSmokeRunner(
        embedding_probe=lambda: {"status": "BLOCKED", "reason": "api_key=sk-test-secret bailian https://secret.example.com"},
        vector_store_probe=lambda: {"status": "PASS"},
        rerank_probe=lambda: {"status": "BLOCKED", "reason": "Authorization: Bearer very-secret-token"},
        llm_probe=lambda: {"status": "FAIL", "reason": "empty_response"},
    )
    result = runner.run()

    statuses = {gate.name: gate.status for gate in result.gates}
    assert statuses == {"embedding": "BLOCKED", "vector_store": "PASS", "rerank": "BLOCKED", "llm": "FAIL"}
    assert result.ok is False
    safe_json = m6.render_safe_m6_provider_smoke_summary_json(result).lower()
    for leaked in ("api_key", "sk-test-secret", "bailian", "secret.example.com", "bearer", "very-secret-token"):
        assert leaked not in safe_json
    assert "shadow_error_redacted" in safe_json


def test_m6_provider_smoke_fail_closes_unknown_provider_exception_reason() -> None:
    """provider 异常公开 reason 必须默认脱敏，不能回显模型、provider、debug 或内部主机文本。"""

    m6 = _m6_module()
    unsafe_reason = (
        "OpenAI qwen-max dashscope model error from internal-gateway.local "
        "debug raw_sql provider trace id=abc123"
    )
    runner = m6.InventorySalesProductionM6ProviderSmokeRunner(
        embedding_probe=lambda: (_ for _ in ()).throw(RuntimeError(unsafe_reason)),
        vector_store_probe=lambda: {"status": "PASS"},
        rerank_probe=lambda: {"status": "PASS"},
        llm_probe=lambda: {"status": "PASS"},
    )

    result = runner.run()
    safe_json = m6.render_safe_m6_provider_smoke_summary_json(result).lower()

    assert result.gates[0].status == "BLOCKED"
    assert "shadow_error_redacted" in safe_json
    for leaked in ("openai", "qwen", "dashscope", "model", "internal-gateway", "debug", "raw_sql", "trace id"):
        assert leaked not in safe_json


def test_m6_provider_smoke_redacts_plain_unknown_exception_text_by_default() -> None:
    """未命中已知敏感词的外部异常也不能公开回显，必须默认脱敏。"""

    m6 = _m6_module()
    plain_external_reason = "upstream gateway rejected request id abc123 tenant route unavailable retry later"
    runner = m6.InventorySalesProductionM6ProviderSmokeRunner(
        embedding_probe=lambda: (_ for _ in ()).throw(RuntimeError(plain_external_reason)),
        vector_store_probe=lambda: {"status": "PASS"},
        rerank_probe=lambda: {"status": "PASS"},
        llm_probe=lambda: {"status": "PASS"},
    )

    result = runner.run()
    safe_json = m6.render_safe_m6_provider_smoke_summary_json(result).lower()

    assert result.gates[0].status == "BLOCKED"
    assert "shadow_error_redacted" in safe_json
    for leaked in ("upstream gateway", "abc123", "tenant route", "retry later"):
        assert leaked not in safe_json



def test_m6_provider_smoke_fail_closes_dict_probe_without_explicit_status() -> None:
    """dict probe 缺少显式 PASS/FAIL/BLOCKED 时必须 fail-closed，不能因非空字典误判通过。"""

    m6 = _m6_module()
    runner = m6.InventorySalesProductionM6ProviderSmokeRunner(
        embedding_probe=lambda: {"collection": "internal_isp_catalog", "count": 1},
        vector_store_probe=lambda: {"status": "PASS"},
        rerank_probe=lambda: {"status": "PASS"},
        llm_probe=lambda: {"status": "PASS"},
    )

    result = runner.run()
    safe_json = m6.render_safe_m6_provider_smoke_summary_json(result).lower()

    assert result.gates[0].status == "FAIL"
    assert result.ok is False
    assert "probe_status_missing" in safe_json
    assert "internal_isp_catalog" not in safe_json



def test_m6_sqlplan_generator_uses_recalled_catalog_context_and_never_returns_executable_sql() -> None:
    """M6 LLM SQLPlan generator 只能基于召回目录生成可校验 SQLPlan 候选，不能返回可执行 SQL。"""

    m6 = _m6_module()

    recall_service = m6.InventorySalesProductionM6CatalogRecallService.from_documents(
        m6.InventorySalesProductionM6CatalogRecallDocumentBuilder().build_documents()
    )
    fake_llm = m6.InventorySalesProductionM6FakeSqlPlanProvider(
        candidate_payload={
            "catalog_version": CATALOG_VERSION,
            "catalog_refs": [
                {"catalog_id": "table:dwd_ba_isp_monthly_fact", "catalog_version": CATALOG_VERSION},
                {"catalog_id": "metric:shipment_volume", "catalog_version": CATALOG_VERSION},
                {"catalog_id": "dimension:business_year", "catalog_version": CATALOG_VERSION},
            ],
            "plan": {
                "query_key": "ba_isp_metric_summary",
                "tables": ["dwd_ba_isp_monthly_fact"],
                "metrics": ["shipment_volume"],
                "dimensions": [],
                "filters": [{"field": "business_year", "op": "=", "values": [2025]}],
                "period_type": "year",
                "year": 2025,
                "calculation_policy": "flow_sum",
                "safety": {"read_only": True, "row_limit": 200},
            },
        }
    )
    generator = m6.InventorySalesProductionM6SqlPlanGenerator(recall_service=recall_service, llm_provider=fake_llm)

    result = generator.generate("2025年销量是多少？")

    assert result.provider_live_called is True
    assert result.validation.ok is True, result.validation.error_codes
    assert result.normalized_plan is not None
    assert result.normalized_plan.metrics == ["shipment_volume"]
    serialized = result.normalized_plan.model_dump_json().lower()
    for forbidden in ("select ", " from ", " where ", "raw_sql", "free_sql"):
        assert forbidden not in serialized


def test_m6_sqlplan_normalizer_does_not_backfill_catalog_refs_from_provider_plan() -> None:
    """LLM 只在 plan 中发明的指标/维度不得被 normalizer 反向补成合法 catalog_ref。"""

    m6 = _m6_module()
    recall_service = m6.InventorySalesProductionM6CatalogRecallService.from_documents(
        m6.InventorySalesProductionM6CatalogRecallDocumentBuilder().build_documents()
    )
    fake_llm = m6.InventorySalesProductionM6FakeSqlPlanProvider(
        candidate_payload={
            "catalog_version": CATALOG_VERSION,
            "catalog_refs": [
                {"catalog_id": "table:dwd_ba_isp_monthly_fact", "catalog_version": CATALOG_VERSION},
                {"catalog_id": "metric:shipment_volume", "catalog_version": CATALOG_VERSION},
                {"catalog_id": "dimension:business_year", "catalog_version": CATALOG_VERSION},
            ],
            "plan": {
                "query_key": "ba_isp_metric_summary",
                "tables": ["dwd_ba_isp_monthly_fact"],
                "metrics": ["ending_inventory_volume"],
                "dimensions": [],
                "filters": [{"field": "business_year", "op": "=", "values": [2025]}],
                "period_type": "year",
                "year": 2025,
                "calculation_policy": "period_end",
            },
        }
    )
    generator = m6.InventorySalesProductionM6SqlPlanGenerator(recall_service=recall_service, llm_provider=fake_llm)

    result = generator.generate("2025年销量是多少？")

    assert result.provider_live_called is True
    assert result.validation.ok is False
    assert "metric:ending_inventory_volume" not in _safe_text(result.candidate_payload)
    assert any("catalog_ref" in code for code in result.error_codes)


def test_m6_live_shadow_gate_runs_provider_candidate_validator_and_readonly_middle_db_shadow(tmp_path: Path) -> None:
    """M6 live shadow gate 必须串起真实 provider 候选、SQLPlan 校验和只读中间库 shadow，不接管正式 QA。"""

    m6 = _m6_module()

    runner = m6.InventorySalesProductionM6LiveShadowGateRunner(
        sqlplan_generator=m6.InventorySalesProductionM6FakeSqlPlanGenerator.success_for_metric("shipment_volume"),
        readonly_shadow_executor=m6.InventorySalesProductionM6FakeReadonlyShadowExecutor(rows=[{"metric": "shipment_volume"}]),
    )
    run = runner.run(
        samples=[
            m6.InventorySalesProductionM6LiveShadowSample(
                sample_id="m6_live_sales_year_summary",
                question="2025年销量是多少？",
                expected_status="matched",
            )
        ],
        artifact_dir=tmp_path,
    )

    assert run.report["version"] == M6_GATE_VERSION
    assert run.report["total"] == 1
    assert run.report["provider_live_called"] is True
    assert run.report["sqlplan_validation_pass_count"] == 1
    assert run.report["readonly_middle_db_shadow_executed"] is True
    assert run.report["formal_qa_executed"] is False
    assert run.report["expected_status_mismatch_count"] == 0
    assert run.records_path.exists()
    assert run.report_path.exists()


def test_m6_live_shadow_gate_preserves_provider_called_when_readonly_shadow_raises(tmp_path: Path) -> None:
    """只读 shadow 执行异常时仍必须保留 provider 已调用状态，并输出脱敏失败记录。"""

    m6 = _m6_module()

    class RaisingReadonlyShadowExecutor:
        """测试用 executor：模拟只读中间库执行阶段异常。"""

        def execute(self, plan: object) -> list[dict[str, object]]:
            """抛出带连接/SQL 片段的异常，验证 M6 记录不会泄漏细节。"""

            raise RuntimeError("mysql://user:secret@127.0.0.1/db select * from dwd_ba_isp_monthly_fact")

    runner = m6.InventorySalesProductionM6LiveShadowGateRunner(
        sqlplan_generator=m6.InventorySalesProductionM6FakeSqlPlanGenerator.success_for_metric("shipment_volume"),
        readonly_shadow_executor=RaisingReadonlyShadowExecutor(),
    )
    run = runner.run(
        samples=[
            m6.InventorySalesProductionM6LiveShadowSample(
                sample_id="m6_live_sales_year_summary_error",
                question="2025年销量是多少？",
                expected_status="shadow_error",
            )
        ],
        artifact_dir=tmp_path,
    )
    record = json.loads(run.records_path.read_text(encoding="utf-8").splitlines()[0])
    serialized = _safe_text(record)

    assert run.report["provider_live_called"] is True
    assert run.report["expected_status_mismatch_count"] == 0
    assert record["provider_live_called"] is True
    assert record["actual_status"] == "shadow_error"
    assert "shadow_error_redacted" in serialized
    for leaked in ("mysql://", "127.0.0.1", "select *", "dwd_ba_isp_monthly_fact", "secret"):
        assert leaked not in serialized


def test_m6_readonly_shadow_executor_declares_shadow_only_and_no_query_log_contract() -> None:
    """M6 真实只读 executor 必须显式声明 shadow-only 且不写正式问答/query log。"""

    m6 = _m6_module()
    executor = m6.InventorySalesProductionM6ReadonlyMiddleDbShadowExecutor(session_factory=lambda: None)

    assert executor.shadow_only is True
    assert executor.formal_qa_executed is False
    assert executor.write_query_log is False


def test_m6_public_shadow_summary_redacts_internal_sqlplan_provider_and_secret_fragments() -> None:
    """M6 写入 outbox/历史/公开摘要前必须去除 SQLPlan 内部、表字段、provider、密钥和连接串细节。"""

    m6 = _m6_module()

    unsafe_summary = {
        "error_codes": [
            "sqlplan_missing_catalog_ref::table:dwd_ba_isp_monthly_fact",
            "provider_error::bailian::Bearer sk-secret-token",
            "sqlplan_table_column_not_allowed::dwd_ba_isp_monthly_fact.raw_payload",
        ],
        "error_message": "mysql://user:password@127.0.0.1:3306/db select * from sys_query_log api_key=sk-secret-token",
        "candidate_sql_gate_reason": "raw_sql::SELECT * FROM dwd_ba_isp_monthly_fact",
    }

    safe_summary = m6.render_safe_m6_live_shadow_summary(unsafe_summary)
    serialized = _safe_text(safe_summary)

    assert "shadow_error_redacted" in serialized or "redacted" in serialized
    for leaked in (
        "dwd_ba_isp_monthly_fact",
        "raw_payload",
        "sys_query_log",
        "select *",
        "mysql://",
        "127.0.0.1",
        "password",
        "api_key",
        "sk-secret-token",
        "bearer",
        "bailian",
    ):
        assert leaked not in serialized


def test_m6_openai_provider_prompt_contains_strict_sqlplan_schema_contract() -> None:
    """真实 provider prompt 必须包含严格 SQLPlan candidate 合同，避免返回自定义对象结构。"""

    m6 = _m6_module()
    documents = m6.InventorySalesProductionM6CatalogRecallDocumentBuilder().build_documents()
    recall_service = m6.InventorySalesProductionM6CatalogRecallService.from_documents(documents)
    recall_result = recall_service.recall("2025年销量是多少？")
    provider = m6.InventorySalesProductionM6OpenAiSqlPlanProvider(
        base_url="https://example.invalid/v1",
        api_key="fake-key",
        model="fake-model",
    )

    messages = provider._build_messages(question="2025年销量是多少？", recall_result=recall_result)  # noqa: SLF001
    user_payload = json.loads(messages[1]["content"])
    serialized = json.dumps(user_payload, ensure_ascii=False)

    assert user_payload["required_schema"] == "business_analysis_inventory_sales_production_sqlplan_candidate.v1"
    assert user_payload["strict_output_contract"]["strategy"] == "sql_direct"
    assert user_payload["strict_output_contract"]["plan"]["query_key"] == "ba_isp_metric_summary"
    assert user_payload["strict_output_contract"]["plan"]["metrics"] == ["shipment_volume"]
    assert "不能是对象数组" in serialized
    assert "不能返回 markdown、解释、reasoning 或 SQL" in serialized


def test_m6_cli_llm_smoke_prompt_is_compatible_with_json_object_response_format() -> None:
    """LLM smoke 使用 json_object 响应格式时，提示词必须显式包含 JSON 关键词。"""

    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "dev" / "run_inventory_sales_production_m6_live_provider_gate.py"
    source = script_path.read_text(encoding="utf-8")

    assert 'response_format={"type": "json_object"}' in source
    assert "请只返回 JSON 对象" in source


def test_m6_cli_exposes_separate_provider_reindex_and_live_shadow_gate_switches() -> None:
    """M6 固定脚本必须把 provider smoke、catalog reindex 和 live shadow gate 作为独立显式门禁。"""

    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "dev" / "run_inventory_sales_production_m6_live_provider_gate.py"

    assert script_path.exists(), "missing M6 live provider gate CLI script"

    completed = subprocess.run(
        [sys.executable, str(script_path), "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    help_text = completed.stdout

    assert "--provider-smoke" in help_text
    assert "--reindex-catalog" in help_text
    assert "--reindex-dry-run" in help_text
    assert "--live-provider-shadow-gate" in help_text
    assert "--max-live-samples" in help_text

    blocked_env = os.environ.copy()
    blocked_env.update(
        {
            "LLM_BASE_URL": "",
            "LLM_API_KEY": "",
            "LLM_MODEL": "",
            "EMBEDDING_MODEL": "",
            "RERANK_MODEL": "",
        }
    )
    blocked = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--provider-smoke",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=blocked_env,
    )
    assert blocked.returncode == 2
    blocked_output = (blocked.stdout + blocked.stderr).lower()
    assert "blocked" in blocked_output
    assert "fake" not in blocked_output


# ===== M6.1 加固测试 =====


def test_m6_1_provider_gate_fail_closes_list_and_float_probe_without_explicit_status() -> None:
    """非 dict 返回值若缺少显式 PASS/FAIL/BLOCKED，默认 fail-closed 为 FAIL 而非 PASS。

    业务逻辑：review 建议 dict probe 默认 fail-closed。同理 list/float 等 truthy 值
    也不应因 bool(value)=True 而误判通过。
    """
    m6 = _m6_module()
    for probe_val in ([0.1, 0.2, 0.3], ["ok"], 0.99, "ok", (0.1,)):
        result = m6._provider_gate_from_probe_result("embedding", probe_val)  # noqa: SLF001
        assert result.status == "FAIL", f"expected FAIL for {type(probe_val).__name__}={probe_val!r}, got {result.status}"


def test_m6_1_provider_gate_fail_closes_empty_list_and_zero_probe() -> None:
    """空列表/零等 falsy 值继续按 FAIL 处理；该行为已覆盖，此处加固回归。"""
    m6 = _m6_module()
    for probe_val in ([], 0, 0.0, False, None, ""):
        result = m6._provider_gate_from_probe_result("embedding", probe_val)  # noqa: SLF001
        assert result.status == "FAIL", f"expected FAIL for {type(probe_val).__name__}={probe_val!r}, got {result.status}"


def test_m6_1_dict_probe_with_non_standard_status_is_fail_closed() -> None:
    """dict probe 即使包含 status 字段，如果值不是 PASS/FAIL/BLOCKED/OK，也应按 FAIL 处理。"""
    m6 = _m6_module()
    cases = [
        {"status": "UP"},
        {"status": "DOWN"},
        {"status": "UNKNOWN"},
        {"status": "in_progress"},
        {"status": "timeout"},
        {"status": ""},
        {"status": None},
    ]
    for case in cases:
        result = m6._provider_gate_from_probe_result("embedding", case)  # noqa: SLF001
        assert result.status == "FAIL", f"expected FAIL for {case!r}, got {result.status}"


def test_m6_1_live_shadow_gate_preserves_provider_called_when_generator_raises() -> None:
    """generator.generate() 抛出异常时，如果 provider 已调用，_run_one 仍应保留此状态。

    业务逻辑：review 建议异常分支尽量保留已发生的 provider_live_called 状态。
    这里用已调用过的 fake generator 模拟异常，验证异常分支返回 provider_live_called=True。
    """
    m6 = _m6_module()
    tmp_path = Path(__file__).resolve().parent / "_m6_1_generator_raises_tmp"

    class GeneratorThatAlreadyCalledProvider:
        """模拟 generate() 已调用 provider 但在后续抛异常的 generator。"""

        def __init__(self) -> None:
            self.live_called = True

        def generate(self, question: str) -> object:
            raise RuntimeError("shadow_readonly_connection_timeout")

    runner = m6.InventorySalesProductionM6LiveShadowGateRunner(
        sqlplan_generator=GeneratorThatAlreadyCalledProvider(),
        readonly_shadow_executor=m6.InventorySalesProductionM6FakeReadonlyShadowExecutor(rows=[]),
    )
    samples = [
        m6.InventorySalesProductionM6LiveShadowSample(
            sample_id="m6_1_generator_raises",
            question="2025年销量是多少？",
            expected_status="shadow_error",
        )
    ]
    run = runner.run(samples=samples, artifact_dir=tmp_path)
    record = json.loads(run.records_path.read_text(encoding="utf-8").splitlines()[0])
    assert record.get("provider_live_called") is True, (
        f"generator 抛出异常时仍应保留 provider_live_called=True，实际为 {record.get('provider_live_called')}"
    )
    assert record.get("actual_status") == "shadow_error"
    if tmp_path.exists():
        import shutil
        shutil.rmtree(tmp_path)


# ===== M6.2 扩样测试 =====


def test_m6_2_default_shadow_samples_cover_all_categories() -> None:
    """M6.2 默认 live shadow 样本必须覆盖 A/B/C 三类问法，且总样本数 >= 18。"""
    from backend.app.domains.business_analysis.services.inventory_sales_production.m6_live_provider_gate import (
        InventorySalesProductionM6LiveShadowSample,
    )

    import importlib
    module = importlib.import_module("scripts.dev.run_inventory_sales_production_m6_live_provider_gate")

    samples = module._default_live_shadow_samples(99)  # noqa: SLF001
    assert len(samples) >= 18, f"expected >= 18 samples, got {len(samples)}"
    by_id = {s.sample_id: s for s in samples}

    # A 类成功样本必须覆盖
    a_ids = [sid for sid, s in by_id.items() if s.expected_status == "matched"]
    assert len(a_ids) >= 10, f"expected >= 10 A-class samples, got {len(a_ids)}"
    assert any("sales" in sid for sid in a_ids)
    assert any("inventory" in sid or "consigned" in sid for sid in a_ids)
    assert any("budget" in sid or "production" in sid for sid in a_ids)
    assert any("quarter" in sid or "ytd" in sid for sid in a_ids)
    assert any("model_type" in sid or "base_" in sid for sid in a_ids)
    assert any("invoice" in sid for sid in a_ids)

    # B/C 类 fail-closed 样本必须覆盖
    bc_ids = [sid for sid, s in by_id.items() if s.expected_status == "validation_failed"]
    assert len(bc_ids) >= 5, f"expected >= 5 BC-class samples, got {len(bc_ids)}"
    assert any("yoy" in sid or "mom" in sid for sid in bc_ids)
    assert any("month_range" in sid for sid in bc_ids)
    assert any("unknown_year" in sid or "turnover" in sid for sid in bc_ids)
    assert any("sql" in sid for sid in bc_ids)

    # 所有样本的 question 不包含真正的技术泄露内容（安全负例 SQL 片段本身是预期的）
    forbidden = ("raw_sql", "dwd_ba_isp", "sys_query", "shadow_error_redacted", "api_key")
    serialized = json.dumps([s.model_dump(mode="json") for s in samples]).lower()
    for term in forbidden:
        assert term not in serialized, f"leak detected: {term} in samples"


def test_m6_2_default_shadow_samples_max_live_samples_caps_correctly() -> None:
    """max-live-samples 参数必须正确限制样本数目；默认值与显式值应行为一致。"""
    import importlib
    module = importlib.import_module("scripts.dev.run_inventory_sales_production_m6_live_provider_gate")

    full = module._default_live_shadow_samples(99)  # noqa: SLF001
    capped_1 = module._default_live_shadow_samples(1)  # noqa: SLF001
    capped_5 = module._default_live_shadow_samples(5)  # noqa: SLF001
    capped_19 = module._default_live_shadow_samples(19)  # noqa: SLF001

    assert len(capped_1) == 1
    assert len(capped_5) == 5
    assert len(capped_19) == 19
    assert len(full) >= 18
