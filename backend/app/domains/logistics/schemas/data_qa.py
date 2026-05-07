from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class LogisticsDataQaQueryRequest(BaseModel):
    """物流数据问答请求。

    参数：
        question: 业务人员输入的自然语言问题。
    """

    question: str = Field(..., min_length=1, description="物流数据问答问题")


class LogisticsDataQaStatus(BaseModel):
    """物流数据问答状态。

    说明：
        1. 统一表达成功、澄清、暂不支持、空结果和错误态；
        2. 既给前端正式页使用，也给查询历史快照复用；
        3. 保持字段简单稳定，避免前端重复推断状态。
    """

    code: str
    message: str
    success: bool
    severity: str = "info"


class LogisticsDataQaPlan(BaseModel):
    """受控查询计划。

    说明：
        1. 本结构只描述白名单内的意图、指标、维度和过滤条件；
        2. 不承载任意 SQL；
        3. 支持澄清和不支持问题的可审计输出。
        4. unsupported_* 字段用于 C 类边界治理，给前端展示业务可理解拒答原因和可改问方向。
    """

    domain: Literal["logistics"] = "logistics"
    intent: str
    query_key: str | None = None
    metrics: list[str] = Field(default_factory=list)
    dimensions: list[str] = Field(default_factory=list)
    filters: dict[str, Any] = Field(default_factory=dict)
    group_by: list[str] = Field(default_factory=list)
    sort: list[dict[str, Any]] = Field(default_factory=list)
    limit: int | None = None
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    clarification_category: str | None = None
    clarification_reason: str | None = None
    clarification_missing_slots: list[str] = Field(default_factory=list)
    clarification_template: str | None = None
    clarification_assist_used: bool = False
    clarification_assist_provider_mode: str | None = None
    unsupported_reason: str | None = None
    unsupported_category: str | None = None
    unsupported_template: str | None = None
    unsupported_suggestions: list[str] = Field(default_factory=list)
    unsupported_assist_used: bool = False
    unsupported_assist_provider_mode: str | None = None


class LogisticsDataQaTable(BaseModel):
    """结构化结果表。"""

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class LogisticsDataQaChartSpec(BaseModel):
    """前端图表展示配置。

    说明：
        1. 图表只使用后端已经计算出的结构化 rows；
        2. 不允许 LLM 在 chart_spec 中新增数据点；
        3. 前端可按 chart_type 选择轻量 SVG 折线图、柱状图或饼图渲染。
    """

    chart_type: Literal["line", "bar", "pie"] | None = None
    title: str = ""
    x_axis: str = ""
    y_axis: list[str] = Field(default_factory=list)
    series: list[dict[str, Any]] = Field(default_factory=list)
    unit: str | None = None
    data: list[dict[str, Any]] = Field(default_factory=list)


class LogisticsDataQaTableSpec(BaseModel):
    """前端表格展示配置。"""

    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class LogisticsDataQaPresentationCard(BaseModel):
    """前端指标卡配置。"""

    label: str
    value: Any
    unit: str | None = None
    description: str | None = None


class LogisticsDataQaFollowUp(BaseModel):
    """B 类追问展示配置。"""

    questions: list[str] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)


class LogisticsDataQaUnsupportedExplanation(BaseModel):
    """C 类拒答解释展示配置。"""

    reason: str = ""
    suggestions: list[str] = Field(default_factory=list)


class LogisticsDataQaPresentation(BaseModel):
    """答案表达层 / 展示编排层输出。

    返回：
        display_type: 前端主展示类型；
        title: 面向业务用户的标题；
        answer: 面向业务用户的主回答；
        highlights: 关键结论；
        chart_spec/table_spec/cards: 可选展示组件；
        follow_up: B 类追问配置；
        unsupported_explanation: C 类解释配置；
        caveats: 数据范围和口径提醒；
        debug: 只供折叠或开发排查使用。
    """

    display_type: Literal[
        "narrative",
        "summary_cards",
        "table",
        "line_chart",
        "bar_chart",
        "pie_chart",
        "mixed",
        "clarification",
        "unsupported",
        "empty_result",
        "error",
    ] = "narrative"
    title: str = ""
    answer: str = ""
    highlights: list[str] = Field(default_factory=list)
    chart_spec: LogisticsDataQaChartSpec | None = None
    table_spec: LogisticsDataQaTableSpec | None = None
    cards: list[LogisticsDataQaPresentationCard] = Field(default_factory=list)
    follow_up: LogisticsDataQaFollowUp | None = None
    unsupported_explanation: LogisticsDataQaUnsupportedExplanation | None = None
    caveats: list[str] = Field(default_factory=list)
    debug: dict[str, Any] = Field(default_factory=dict)


class LogisticsDataQaResult(BaseModel):
    """物流数据问答响应。

    返回：
        answer_summary: 业务摘要
        result_table: 结构化结果表
        calculation_logic: 计算口径说明
        data_scope: 数据范围说明
        query_plan: 受控查询计划
        warnings: 口径提醒/缺失提醒
        needs_clarification: 是否需要追问
        clarification_questions: 追问列表
    """

    answer_summary: str
    result_table: LogisticsDataQaTable
    calculation_logic: list[str] = Field(default_factory=list)
    data_scope: dict[str, Any] = Field(default_factory=dict)
    query_plan: LogisticsDataQaPlan
    warnings: list[str] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    supported: bool = True
    status: LogisticsDataQaStatus | None = None
    history_log_id: int | None = None
    history_ready: bool = False
    presentation: LogisticsDataQaPresentation | None = None
    trace_events: list[dict[str, Any]] = Field(default_factory=list)
