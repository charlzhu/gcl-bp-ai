import { computed } from 'vue';
import { ElMessage } from 'element-plus';
import ResultTable from '@/components/ResultTable.vue';
import { buildQueryResultPresentation, formatExecutionModeLabel, formatMetricTypeLabel, formatQueryTypeLabel, formatSourceScopeLabel, } from '@/utils/queryResultPresentation';
const props = defineProps();
const emit = defineEmits();
/**
 * 表格数据兜底为数组，避免模板层重复做空值判断。
 */
const tableItems = computed(() => {
    const items = props.queryResult?.items;
    return Array.isArray(items) ? items : [];
});
/**
 * 构建统一的页面展示视图。
 */
const presentation = computed(() => buildQueryResultPresentation({
    queryResult: props.queryResult,
    parsed: props.parsed,
    question: props.question,
    requestPayload: props.requestPayload,
    responseMeta: props.responseMeta,
}));
/**
 * 当前是否已有可展示的查询载荷。
 * 说明：
 * 未执行查询前只展示空态，避免把“尚未查询”误渲染成“空结果”。
 */
const hasDisplayPayload = computed(() => {
    return Boolean(props.queryResult || props.responseMeta || props.parsed);
});
/**
 * 导出当前结果。
 * 说明：
 * 第二版先做 JSON 导出，确保联调阶段可用；
 * 如果后续要导出 Excel，可在后续版本增强。
 */
function exportCurrentItems() {
    try {
        const payload = JSON.stringify(props.queryResult?.items ?? [], null, 2);
        const blob = new Blob([payload], { type: 'application/json;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'query-result.json';
        a.click();
        URL.revokeObjectURL(url);
        ElMessage.success('已导出当前结果 JSON');
    }
    catch (_error) {
        ElMessage.error('导出失败');
    }
}
/**
 * 打开完整明细页。
 */
function emitOpenDetail() {
    emit('open-detail');
}
/**
 * 查看单行明细。
 */
function emitRowDetail(row) {
    emit('row-detail', row);
}
/**
 * 统一映射状态标签颜色。
 */
function resolveStatusTagType(severity) {
    if (severity === 'error')
        return 'danger';
    if (severity === 'warning')
        return 'warning';
    return 'success';
}
/**
 * 统一映射执行模式标签颜色。
 */
function resolveExecutionModeTagType(value) {
    if (value === 'database')
        return 'success';
    if (value === 'fallback')
        return 'warning';
    if (value === 'error_fallback')
        return 'danger';
    return 'info';
}
/**
 * 将状态严重级别映射为展示面板色调。
 */
function resolvePanelTone(severity) {
    if (severity === 'error')
        return 'danger';
    if (severity === 'warning')
        return 'warning';
    return 'success';
}
/**
 * 汇总数值格式化。
 * 说明：
 * 1. 百分比字段单独转百分数；
 * 2. 可解析的数字统一千分位；
 * 3. 其它值原样兜底。
 */
function formatSummaryValue(key, value) {
    if (key === 'diff_rate') {
        return formatRate(value);
    }
    if (value === null || value === undefined || value === '')
        return '-';
    if (typeof value === 'number') {
        return value.toLocaleString();
    }
    if (typeof value === 'string') {
        const parsedNumber = Number(value);
        if (!Number.isNaN(parsedNumber)) {
            return parsedNumber.toLocaleString();
        }
        return value;
    }
    return String(value);
}
/**
 * 比例格式化为百分比。
 */
function formatRate(value) {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return `${(value * 100).toFixed(2)}%`;
    }
    if (typeof value === 'string' && value.trim()) {
        const parsedNumber = Number(value);
        if (!Number.isNaN(parsedNumber)) {
            return `${(parsedNumber * 100).toFixed(2)}%`;
        }
    }
    return '-';
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-row" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
    ...{ style: {} },
});
const __VLS_0 = {}.ElSpace;
/** @type {[typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
if (__VLS_ctx.presentation.hasItems) {
    const __VLS_4 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
        ...{ 'onClick': {} },
        size: "small",
    }));
    const __VLS_6 = __VLS_5({
        ...{ 'onClick': {} },
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_5));
    let __VLS_8;
    let __VLS_9;
    let __VLS_10;
    const __VLS_11 = {
        onClick: (__VLS_ctx.emitOpenDetail)
    };
    __VLS_7.slots.default;
    var __VLS_7;
}
if (__VLS_ctx.presentation.hasItems) {
    const __VLS_12 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
        ...{ 'onClick': {} },
        size: "small",
    }));
    const __VLS_14 = __VLS_13({
        ...{ 'onClick': {} },
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_13));
    let __VLS_16;
    let __VLS_17;
    let __VLS_18;
    const __VLS_19 = {
        onClick: (__VLS_ctx.exportCurrentItems)
    };
    __VLS_15.slots.default;
    var __VLS_15;
}
var __VLS_3;
if (__VLS_ctx.hasDisplayPayload) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "status-panel" },
        ...{ class: (`status-panel--${__VLS_ctx.resolvePanelTone(__VLS_ctx.presentation.status.severity)}`) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "status-panel__top" },
    });
    const __VLS_20 = {}.ElSpace;
    /** @type {[typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        wrap: true,
    }));
    const __VLS_22 = __VLS_21({
        wrap: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
    __VLS_23.slots.default;
    const __VLS_24 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        effect: "dark",
        type: (__VLS_ctx.resolveStatusTagType(__VLS_ctx.presentation.status.severity)),
    }));
    const __VLS_26 = __VLS_25({
        effect: "dark",
        type: (__VLS_ctx.resolveStatusTagType(__VLS_ctx.presentation.status.severity)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    __VLS_27.slots.default;
    (__VLS_ctx.presentation.status.code);
    var __VLS_27;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "status-message" },
    });
    (__VLS_ctx.presentation.status.message);
    var __VLS_23;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "status-panel__meta" },
    });
    const __VLS_28 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        size: "small",
        type: (__VLS_ctx.resolveExecutionModeTagType(__VLS_ctx.presentation.executionMode)),
    }));
    const __VLS_30 = __VLS_29({
        size: "small",
        type: (__VLS_ctx.resolveExecutionModeTagType(__VLS_ctx.presentation.executionMode)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    __VLS_31.slots.default;
    (__VLS_ctx.formatExecutionModeLabel(__VLS_ctx.presentation.executionMode));
    var __VLS_31;
    const __VLS_32 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        size: "small",
        effect: "plain",
    }));
    const __VLS_34 = __VLS_33({
        size: "small",
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    __VLS_35.slots.default;
    (__VLS_ctx.formatQueryTypeLabel(__VLS_ctx.presentation.queryType));
    var __VLS_35;
    const __VLS_36 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        size: "small",
        effect: "plain",
    }));
    const __VLS_38 = __VLS_37({
        size: "small",
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    __VLS_39.slots.default;
    (__VLS_ctx.formatMetricTypeLabel(__VLS_ctx.presentation.metricType));
    var __VLS_39;
    const __VLS_40 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        size: "small",
        effect: "plain",
    }));
    const __VLS_42 = __VLS_41({
        size: "small",
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
    (__VLS_ctx.formatSourceScopeLabel(__VLS_ctx.presentation.sourceScope));
    var __VLS_43;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-grid" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card__label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card__value" },
    });
    (__VLS_ctx.presentation.resultCount.toLocaleString());
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card__label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card__value" },
    });
    (__VLS_ctx.formatExecutionModeLabel(__VLS_ctx.presentation.executionMode));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card__label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card__value" },
    });
    (__VLS_ctx.formatMetricTypeLabel(__VLS_ctx.presentation.metricType));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card__label" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "overview-card__value" },
    });
    (__VLS_ctx.formatSourceScopeLabel(__VLS_ctx.presentation.sourceScope));
    if (__VLS_ctx.presentation.resultExplanation) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "explanation-panel" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-text" },
        });
        (__VLS_ctx.presentation.resultExplanation.summary);
        if (__VLS_ctx.presentation.resultExplanation.highlights.length) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "tag-group" },
            });
            for (const [item] of __VLS_getVForSourceType((__VLS_ctx.presentation.resultExplanation.highlights))) {
                const __VLS_44 = {}.ElTag;
                /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
                // @ts-ignore
                const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
                    key: (item),
                    size: "small",
                    effect: "plain",
                }));
                const __VLS_46 = __VLS_45({
                    key: (item),
                    size: "small",
                    effect: "plain",
                }, ...__VLS_functionalComponentArgsRest(__VLS_45));
                __VLS_47.slots.default;
                (item);
                var __VLS_47;
            }
        }
        if (__VLS_ctx.presentation.resultExplanation.notes.length) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({
                ...{ class: "note-list" },
            });
            for (const [item] of __VLS_getVForSourceType((__VLS_ctx.presentation.resultExplanation.notes))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
                    key: (item),
                });
                (item);
            }
        }
    }
    if (__VLS_ctx.presentation.compatibilityNotice.length > 0) {
        const __VLS_48 = {}.ElAlert;
        /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
        // @ts-ignore
        const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
            type: "info",
            showIcon: true,
            closable: (false),
            ...{ style: {} },
        }));
        const __VLS_50 = __VLS_49({
            type: "info",
            showIcon: true,
            closable: (false),
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_49));
        __VLS_51.slots.default;
        {
            const { title: __VLS_thisSlot } = __VLS_51.slots;
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "alert-list" },
        });
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.presentation.compatibilityNotice))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (item),
            });
            (item);
        }
        var __VLS_51;
    }
    if (__VLS_ctx.presentation.noResultAnalysis) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "analysis-panel" },
            ...{ class: (`analysis-panel--${__VLS_ctx.resolvePanelTone(__VLS_ctx.presentation.status.severity)}`) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "analysis-panel__question" },
        });
        (__VLS_ctx.presentation.noResultAnalysis.question);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "analysis-columns" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "analysis-subtitle" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({
            ...{ class: "note-list" },
        });
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.presentation.noResultAnalysis.possible_reasons))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
                key: (item),
            });
            (item);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "analysis-subtitle" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({
            ...{ class: "note-list" },
        });
        for (const [item] of __VLS_getVForSourceType((__VLS_ctx.presentation.noResultAnalysis.suggestions))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
                key: (item),
            });
            (item);
        }
    }
    if (__VLS_ctx.presentation.summaryEntries.length > 0) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-panel" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-grid" },
        });
        for (const [entry] of __VLS_getVForSourceType((__VLS_ctx.presentation.summaryEntries))) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                key: (entry.key),
                ...{ class: "summary-card" },
            });
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "summary-card__label" },
            });
            (entry.label);
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "summary-card__value" },
            });
            (__VLS_ctx.formatSummaryValue(entry.key, entry.value));
        }
    }
    if (__VLS_ctx.presentation.showCompareSummary) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-panel" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-title" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-grid" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card__label" },
        });
        (props.queryResult?.left_label || '左值');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card__value" },
        });
        (__VLS_ctx.formatSummaryValue('left_value', props.queryResult?.left_value));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card__label" },
        });
        (props.queryResult?.right_label || '右值');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card__value" },
        });
        (__VLS_ctx.formatSummaryValue('right_value', props.queryResult?.right_value));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card__label" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card__value" },
        });
        (__VLS_ctx.formatSummaryValue('diff_value', props.queryResult?.diff_value));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card__label" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "summary-card__value" },
        });
        (__VLS_ctx.formatRate(props.queryResult?.diff_rate));
    }
    if (__VLS_ctx.presentation.templateInfo) {
        const __VLS_52 = {}.ElCollapse;
        /** @type {[typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, ]} */ ;
        // @ts-ignore
        const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
            ...{ style: {} },
        }));
        const __VLS_54 = __VLS_53({
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_53));
        __VLS_55.slots.default;
        const __VLS_56 = {}.ElCollapseItem;
        /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
        // @ts-ignore
        const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
            title: "模板命中信息",
            name: "template-info",
        }));
        const __VLS_58 = __VLS_57({
            title: "模板命中信息",
            name: "template-info",
        }, ...__VLS_functionalComponentArgsRest(__VLS_57));
        __VLS_59.slots.default;
        const __VLS_60 = {}.ElDescriptions;
        /** @type {[typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, ]} */ ;
        // @ts-ignore
        const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
            column: (1),
            border: true,
        }));
        const __VLS_62 = __VLS_61({
            column: (1),
            border: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_61));
        __VLS_63.slots.default;
        const __VLS_64 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
            label: "模板状态",
        }));
        const __VLS_66 = __VLS_65({
            label: "模板状态",
        }, ...__VLS_functionalComponentArgsRest(__VLS_65));
        __VLS_67.slots.default;
        (__VLS_ctx.presentation.templateInfo.template_hit ? '已命中' : '未命中');
        var __VLS_67;
        const __VLS_68 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
            label: "模板 ID",
        }));
        const __VLS_70 = __VLS_69({
            label: "模板 ID",
        }, ...__VLS_functionalComponentArgsRest(__VLS_69));
        __VLS_71.slots.default;
        (__VLS_ctx.presentation.templateInfo.template_id || '-');
        var __VLS_71;
        const __VLS_72 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
            label: "模板名称",
        }));
        const __VLS_74 = __VLS_73({
            label: "模板名称",
        }, ...__VLS_functionalComponentArgsRest(__VLS_73));
        __VLS_75.slots.default;
        (__VLS_ctx.presentation.templateInfo.template_name || '-');
        var __VLS_75;
        const __VLS_76 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
            label: "模板分数",
        }));
        const __VLS_78 = __VLS_77({
            label: "模板分数",
        }, ...__VLS_functionalComponentArgsRest(__VLS_77));
        __VLS_79.slots.default;
        (__VLS_ctx.presentation.templateInfo.template_score ?? '-');
        var __VLS_79;
        var __VLS_63;
        if (__VLS_ctx.presentation.templateInfo.template_match_reasons.length) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.ul, __VLS_intrinsicElements.ul)({
                ...{ class: "note-list" },
                ...{ style: {} },
            });
            for (const [item] of __VLS_getVForSourceType((__VLS_ctx.presentation.templateInfo.template_match_reasons))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.li, __VLS_intrinsicElements.li)({
                    key: (item),
                });
                (item);
            }
        }
        var __VLS_59;
        var __VLS_55;
    }
    if (__VLS_ctx.presentation.hasItems) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
        /** @type {[typeof ResultTable, ]} */ ;
        // @ts-ignore
        const __VLS_80 = __VLS_asFunctionalComponent(ResultTable, new ResultTable({
            ...{ 'onRowDetail': {} },
            items: (__VLS_ctx.tableItems),
            title: "明细/统计列表",
        }));
        const __VLS_81 = __VLS_80({
            ...{ 'onRowDetail': {} },
            items: (__VLS_ctx.tableItems),
            title: "明细/统计列表",
        }, ...__VLS_functionalComponentArgsRest(__VLS_80));
        let __VLS_83;
        let __VLS_84;
        let __VLS_85;
        const __VLS_86 = {
            onRowDetail: (__VLS_ctx.emitRowDetail)
        };
        var __VLS_82;
    }
}
else {
    const __VLS_87 = {}.ElEmpty;
    /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_88 = __VLS_asFunctionalComponent(__VLS_87, new __VLS_87({
        description: "当前暂无查询结果",
    }));
    const __VLS_89 = __VLS_88({
        description: "当前暂无查询结果",
    }, ...__VLS_functionalComponentArgsRest(__VLS_88));
}
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['header-row']} */ ;
/** @type {__VLS_StyleScopedClasses['status-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['status-panel__top']} */ ;
/** @type {__VLS_StyleScopedClasses['status-message']} */ ;
/** @type {__VLS_StyleScopedClasses['status-panel__meta']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card__label']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card__value']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card__label']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card__value']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card__label']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card__value']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card__label']} */ ;
/** @type {__VLS_StyleScopedClasses['overview-card__value']} */ ;
/** @type {__VLS_StyleScopedClasses['explanation-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-text']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-group']} */ ;
/** @type {__VLS_StyleScopedClasses['note-list']} */ ;
/** @type {__VLS_StyleScopedClasses['alert-list']} */ ;
/** @type {__VLS_StyleScopedClasses['analysis-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['analysis-panel__question']} */ ;
/** @type {__VLS_StyleScopedClasses['analysis-columns']} */ ;
/** @type {__VLS_StyleScopedClasses['analysis-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['note-list']} */ ;
/** @type {__VLS_StyleScopedClasses['analysis-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['note-list']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card__label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card__value']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['section-title']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-grid']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card__label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card__value']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card__label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card__value']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card__label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card__value']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card__label']} */ ;
/** @type {__VLS_StyleScopedClasses['summary-card__value']} */ ;
/** @type {__VLS_StyleScopedClasses['note-list']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            ResultTable: ResultTable,
            formatExecutionModeLabel: formatExecutionModeLabel,
            formatMetricTypeLabel: formatMetricTypeLabel,
            formatQueryTypeLabel: formatQueryTypeLabel,
            formatSourceScopeLabel: formatSourceScopeLabel,
            tableItems: tableItems,
            presentation: presentation,
            hasDisplayPayload: hasDisplayPayload,
            exportCurrentItems: exportCurrentItems,
            emitOpenDetail: emitOpenDetail,
            emitRowDetail: emitRowDetail,
            resolveStatusTagType: resolveStatusTagType,
            resolveExecutionModeTagType: resolveExecutionModeTagType,
            resolvePanelTone: resolvePanelTone,
            formatSummaryValue: formatSummaryValue,
            formatRate: formatRate,
        };
    },
    __typeEmits: {},
    __typeProps: {},
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
});
; /* PartiallyEnd: #4569/main.vue */
