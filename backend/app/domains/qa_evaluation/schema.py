"""统一业务问法评测集（NQE-Eval）Schema 定义。

业务逻辑：
    本模块定义跨业务域（物流、计划BOM、功率预测、经营分析）的统一评测集核心 Schema。
    包括评测用例（EvaluationCase）、评测套件（EvaluationSuite）、
    评测结果（EvaluationResult）和评测报告（EvaluationReport）。

    设计原则：
    1. 评测用例独立可序列化，不依赖运行时环境。
    2. 套件可包含多条用例，按业务域组织。
    3. 评测结果保留实际回答快照，支持人工复核。
    4. 报告汇总套件级统计，支持 pass_rate 计算。
"""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# 一致性评测分级枚举
# ---------------------------------------------------------------------------
"""一致性评测分级：
    - pass：全部核心指标匹配。
    - fail：存在硬性不合格项（状态不匹配、行数不匹配、技术泄露）。
    - warning：存在软性风险项（文本相似度低、数值误差超标）。
"""
ConsistencyGrade = Literal["pass", "fail", "warning"]
_CONSISTENCY_GRADES = frozenset({"pass", "fail", "warning"})


# ---------------------------------------------------------------------------
# 业务问法评测集支持的业务域
# ---------------------------------------------------------------------------
"""支持的业务域列表：
    - logistics：物流问答。
    - plan_bom：计划 BOM 问答。
    - power_prediction：功率预测问答。
    - business_analysis：经营分析（产销存）问答。
"""
_SUPPORTED_DOMAINS = frozenset({
    "logistics",
    "plan_bom",
    "power_prediction",
    "business_analysis",
})

# ---------------------------------------------------------------------------
# 业务问法评测预期状态枚举
# ---------------------------------------------------------------------------
"""预期回答状态列表：
    - success：成功回答，包含关键业务数据。
    - clarification：需要澄清，缺少关键槽位。
    - unsupported：暂不支持的问题类型。
    - empty_result：数据范围内无匹配记录。
    - error：后端执行异常。
"""
_EXPECTED_STATUSES = frozenset({
    "success",
    "clarification",
    "unsupported",
    "empty_result",
    "error",
})


# ---------------------------------------------------------------------------
# EvaluationCase —— 单条评测用例
# ---------------------------------------------------------------------------

class EvaluationCase(BaseModel):
    """单条业务问法评测用例。

    描述一条用户自然语言问题及其预期回答，供评测引擎自动化对比。

    参数：
        question: 用户自然语言问题，必填。
        domain: 所属业务域，必填，见 _SUPPORTED_DOMAINS。
        expected_status: 预期回答状态，必填，见 _EXPECTED_STATUSES。
        expected_text: 预期回答核心文本，可选。
            —— 用于验证 LLM 生成回答是否包含关键业务数据。
        expected_row_count: 预期结果行数，可选。
            —— 用于验证查询返回的数据量是否匹配。
        caliber: 业务口径说明，可选。
            —— 说明本问题的数据范围、计算公式、筛选条件等，供评测员参考。
        tags: 分类标签列表，可选，默认空列表。
            —— 如 ["smoke", "logistics_route_price"]。
        allow_empty_substitute: 是否允许空结果回填预期，默认 True。
            —— 当数据源无匹配记录时，是否接受 row_count=0 的结果。
        schema_version: Schema 版本号，默认 "1.0"。
        case_id: 用例唯一标识，可选，未传入时自动生成 UUID。

    业务注意：
        本 Schema 仅用于构建评测数据集，不执行实际查询。
        评测引擎需基于 case_id 关联实际回答和 EvaluationResult。
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="用例唯一标识，未传入时自动生成 UUID",
    )
    question: str = Field(..., min_length=1, description="用户自然语言问题")
    domain: str = Field(..., description="所属业务域")
    expected_status: str = Field(..., description="预期回答状态")
    expected_text: str | None = Field(
        default=None,
        description="预期回答核心文本，用于验证关键业务数据是否存在",
    )
    expected_row_count: int | None = Field(
        default=None,
        ge=0,
        description="预期结果行数，用于验证查询返回的数据量",
    )
    caliber: str | None = Field(
        default=None,
        description="业务口径说明：数据范围、计算公式、筛选条件等",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="分类标签列表，如 ['smoke', 'logistics_route_price']",
    )
    allow_empty_substitute: bool = Field(
        default=True,
        description="是否允许空结果回填预期（row_count=0 可接受）",
    )
    schema_version: str = Field(
        default="1.0",
        description="Schema 版本号",
    )

    @model_validator(mode="after")
    def _validate_domain(self) -> "EvaluationCase":
        """校验 domain 是否在支持的业务域白名单内。"""
        if self.domain not in _SUPPORTED_DOMAINS:
            raise ValueError(
                f"domain 必须是以下之一：{sorted(_SUPPORTED_DOMAINS)}，"
                f"当前值：{self.domain}",
            )
        return self

    @model_validator(mode="after")
    def _validate_expected_status(self) -> "EvaluationCase":
        """校验 expected_status 是否在允许的状态值内。"""
        if self.expected_status not in _EXPECTED_STATUSES:
            raise ValueError(
                f"expected_status 必须是以下之一：{sorted(_EXPECTED_STATUSES)}，"
                f"当前值：{self.expected_status}",
            )
        return self


# ---------------------------------------------------------------------------
# EvaluationSuite —— 评测套件
# ---------------------------------------------------------------------------

class EvaluationSuite(BaseModel):
    """评测套件：包含一个业务域内的多条评测用例。

    参数：
        name: 套件名称，必填，如"物流核心问答回归"。
        domain: 所属业务域，必填。
        cases: 评测用例列表，默认空列表。
        description: 套件描述，可选。

    业务注意：
        套件内的用例应属于同一业务域；评测引擎可按套件批量执行。
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="套件名称")
    domain: str = Field(..., description="所属业务域")
    cases: list[EvaluationCase] = Field(
        default_factory=list,
        description="评测用例列表",
    )
    description: str | None = Field(
        default=None,
        description="套件描述",
    )

    @model_validator(mode="after")
    def _validate_domain(self) -> "EvaluationSuite":
        """校验 domain 是否在支持的业务域白名单内。"""
        if self.domain not in _SUPPORTED_DOMAINS:
            raise ValueError(
                f"domain 必须是以下之一：{sorted(_SUPPORTED_DOMAINS)}，"
                f"当前值：{self.domain}",
            )
        return self

    @model_validator(mode="after")
    def _validate_cases_domain(self) -> "EvaluationSuite":
        """校验所有 case 的 domain 与套件 domain 一致。"""
        for i, case in enumerate(self.cases):
            if case.domain != self.domain:
                raise ValueError(
                    f"cases[{i}] 的 domain ({case.domain}) 与套件 domain"
                    f" ({self.domain}) 不一致",
                )
        return self


# ---------------------------------------------------------------------------
# EvaluationResult —— 单条用例评测结果
# ---------------------------------------------------------------------------

class EvaluationResult(BaseModel):
    """单条评测用例的执行结果。

    对比实际回答与预期用例，记录是否匹配及差异详情。

    参数：
        case_id: 关联的用例标识，必填。
        matched_status: 实际状态是否匹配预期，默认 False。
        key_numbers_match: 关键数字是否匹配，可选。
            —— 例如预期 row_count=5，实际 row_count=5 则为 True。
        text_similarity: 文本相似度（0.0~1.0），可选。
            —— 基于 expected_text 与实际 answer 的语义/字符匹配计算。
        leak_found: 是否发现技术泄露（SQL/表名/字段名等），默认 False。
        actual_status: 实际回答状态，可选。
        actual_answer_summary: 实际回答摘要，可选。
        actual_row_count: 实际返回行数，可选。
        mismatch_detail: 差异说明，可选。
            —— 用人类可读方式描述不匹配的具体项目。

    业务注意：
        matched_status=False 时可通过 mismatch_detail 了解具体差异。
        leak_found=True 是严重问题，即使其他指标全匹配也应标记不通过。
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(..., min_length=1, description="关联的用例标识")
    matched_status: bool = Field(
        default=False,
        description="实际状态是否匹配预期",
    )
    key_numbers_match: bool | None = Field(
        default=None,
        description="关键数字（如 row_count）是否匹配",
    )
    text_similarity: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="文本相似度，范围 0.0~1.0",
    )
    leak_found: bool = Field(
        default=False,
        description="是否发现技术泄露（SQL/表名/字段名等）",
    )
    actual_status: str | None = Field(
        default=None,
        description="实际回答状态",
    )
    actual_answer_summary: str | None = Field(
        default=None,
        description="实际回答摘要",
    )
    actual_row_count: int | None = Field(
        default=None,
        ge=0,
        description="实际返回行数",
    )
    mismatch_detail: str | None = Field(
        default=None,
        description="差异说明，用人类可读方式描述不匹配的具体项目",
    )
    consistency_grade: ConsistencyGrade = Field(
        default="pass",
        description="一致性评测分级：pass=全部匹配、fail=硬性不合格、warning=软性风险",
    )
    numeric_error_pct: float | None = Field(
        default=None,
        ge=0.0,
        description="关键数值误差百分比（0.0~），None 表示未计算",
    )


# ---------------------------------------------------------------------------
# EvaluationReport —— 评测报告
# ---------------------------------------------------------------------------

class EvaluationReport(BaseModel):
    """套件级评测汇总报告。

    汇总一个评测套件的整体通过/失败情况，附每条用例的详细结果。

    参数：
        suite_name: 套件名称，必填。
        domain: 所属业务域，可选。
        total_cases: 总用例数，必填。
        passed_cases: 通过用例数，必填。
        failed_cases: 失败用例数，必填。
        results: 详细评测结果列表，默认空列表。
        notes: 备注信息，可选。

    业务逻辑：
        passed_cases + failed_cases 必须等于 total_cases，否则抛 ValidationError。
        pass_rate 为计算属性（passed_cases / total_cases），
        当 total_cases=0 时返回 1.0（空套件视为全部通过）。
        evaluate_consistency() 方法按 fail/pass/warning 对每条结果一致性分级。
    """

    model_config = ConfigDict(extra="forbid")

    suite_name: str = Field(..., min_length=1, description="套件名称")
    domain: str | None = Field(
        default=None,
        description="所属业务域",
    )
    total_cases: int = Field(..., ge=0, description="总用例数")
    passed_cases: int = Field(..., ge=0, description="通过用例数")
    failed_cases: int = Field(..., ge=0, description="失败用例数")
    results: list[EvaluationResult] = Field(
        default_factory=list,
        description="详细评测结果列表",
    )
    notes: str | None = Field(
        default=None,
        description="备注信息",
    )

    @model_validator(mode="after")
    def _validate_consistency(self) -> "EvaluationReport":
        """校验 passed_cases + failed_cases 与 total_cases 一致。"""
        if self.passed_cases + self.failed_cases != self.total_cases:
            raise ValueError(
                f"passed_cases + failed_cases 必须等于 total_cases，"
                f"当前 passed={self.passed_cases} + failed={self.failed_cases}"
                f" != total={self.total_cases}",
            )
        return self

    @model_validator(mode="after")
    def _validate_results_count(self) -> "EvaluationReport":
        """校验 results 列表长度与 total_cases 一致（非空时）。"""
        if self.results and len(self.results) != self.total_cases:
            raise ValueError(
                f"results 长度 ({len(self.results)}) 与 total_cases"
                f" ({self.total_cases}) 不一致",
            )
        return self

    @property
    def pass_rate(self) -> float:
        """计算通过率（0.0~1.0）。"""
        if self.total_cases == 0:
            return 1.0
        return self.passed_cases / self.total_cases

    # -----------------------------------------------------------------------
    # 一致性评测方法
    # -----------------------------------------------------------------------

    def evaluate_consistency(self) -> "EvaluationReport":
        """对每条评测结果进行一致性分级（fail/pass/warning）。

        参数：无。
        返回：self，支持链式调用。

        业务逻辑：
            遍历 self.results，根据以下规则逐条赋值 consistency_grade：
            - fail：满足任一硬性不合格条件
                * leak_found 为 True（技术泄露）。
                * matched_status 为 False（状态不匹配）。
                * key_numbers_match 为 False（行数不匹配）。
            - warning：不满足 fail 条件时，满足任一软性风险条件
                * text_similarity 已计算且 < 0.5（文本相似度低）。
                * numeric_error_pct 已计算且 > 0.10（数值误差超标）。
            - pass：不满足以上任一条件。

        边界说明：
            - text_similarity=None 时不触发 warning。
            - numeric_error_pct=None 时不触发 warning。
            - 阈值边界值（0.5 / 0.10）属于 pass，不触发 warning。
            - fail 优先级高于 warning（同时满足时判定为 fail）。
        """
        for result in self.results:
            result.consistency_grade = self._grade_one(result)
        return self

    @staticmethod
    def _grade_one(result: EvaluationResult) -> ConsistencyGrade:
        """对单条结果做一致性分级。

        参数：
            result: 单条评测结果。
        返回：
            "pass" / "fail" / "warning"。
        """
        # 一、硬性不合格检查（优先级最高）
        if result.leak_found:
            return "fail"
        if not result.matched_status:
            return "fail"
        if result.key_numbers_match is False:
            return "fail"

        # 二、软性风险检查
        if result.text_similarity is not None and result.text_similarity < 0.5:
            return "warning"
        if result.numeric_error_pct is not None and result.numeric_error_pct > 0.10:
            return "warning"

        # 三、全部通过
        return "pass"
