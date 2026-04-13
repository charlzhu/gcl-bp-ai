import { computed } from 'vue';
import { ElMessage } from 'element-plus';
import ResultTable from '@/components/ResultTable.vue';
const props = defineProps();
const emit = defineEmits();
/**
 * 当前结果是否存在 items。
 */
const hasItems = computed(() => {
    const items = props.queryResult?.items;
    return Array.isArray(items) && items.length > 0;
});
/**
 * 表格数据兜底为数组，避免模板层重复做空值判断。
 */
const tableItems = computed(() => {
    const items = props.queryResult?.items;
    return Array.isArray(items) ? items : [];
});
/**
 * compare 总量对比场景在没有 items 时，仍然需要把 left/right/diff 展示出来。
 */
const showCompareSummary = computed(() => {
    if (hasItems.value)
        return false;
    return Boolean(props.queryResult &&
        (props.queryResult.left_value !== undefined ||
            props.queryResult.right_value !== undefined ||
            props.queryResult.diff_value !== undefined));
});
/**
 * fallback / 兼容模式提示合并展示。
 */
const compatibilityNotice = computed(() => {
    const notices = props.queryResult?.compatibility_notice;
    if (!Array.isArray(notices) || notices.length === 0)
        return '';
    return notices.join('；');
});
/**
 * 导出当前结果。
 * 说明：
 * 第二版先做 JSON 导出，确保联调阶段可用；
 * 如果后续要导出 Excel，可在第三版增强。
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
 * 将对象格式化为 JSON 字符串。
 */
function formatJson(value) {
    if (!value)
        return '-';
    return JSON.stringify(value, null, 2);
}
/**
 * 统一把状态严重级别映射为 Element Plus 的提示类型。
 */
function resolveAlertType(severity) {
    if (severity === 'error')
        return 'error';
    if (severity === 'warning')
        return 'warning';
    return 'success';
}
/**
 * 对比数值格式化。
 */
function formatCell(value) {
    if (value === null || value === undefined || value === '')
        return '-';
    if (typeof value === 'number')
        return value.toLocaleString();
    return String(value);
}
/**
 * 对比比例格式化为百分比。
 */
function formatRate(value) {
    if (typeof value !== 'number' || Number.isNaN(value))
        return '-';
    return `${(value * 100).toFixed(2)}%`;
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
if (__VLS_ctx.hasItems) {
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
if (__VLS_ctx.hasItems) {
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
if (props.queryResult?.status) {
    const __VLS_20 = {}.ElAlert;
    /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        title: (`${props.queryResult.status.code} - ${props.queryResult.status.message}`),
        type: (__VLS_ctx.resolveAlertType(props.queryResult.status.severity)),
        showIcon: true,
        closable: (false),
        ...{ style: {} },
    }));
    const __VLS_22 = __VLS_21({
        title: (`${props.queryResult.status.code} - ${props.queryResult.status.message}`),
        type: (__VLS_ctx.resolveAlertType(props.queryResult.status.severity)),
        showIcon: true,
        closable: (false),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
if (props.queryResult?.result_explanation) {
    const __VLS_24 = {}.ElDescriptions;
    /** @type {[typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        column: (1),
        border: true,
        ...{ style: {} },
    }));
    const __VLS_26 = __VLS_25({
        column: (1),
        border: true,
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    __VLS_27.slots.default;
    const __VLS_28 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        label: "结果说明",
    }));
    const __VLS_30 = __VLS_29({
        label: "结果说明",
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    __VLS_31.slots.default;
    (props.queryResult.result_explanation.summary || '-');
    var __VLS_31;
    const __VLS_32 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        label: "执行模式",
    }));
    const __VLS_34 = __VLS_33({
        label: "执行模式",
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    __VLS_35.slots.default;
    (props.queryResult.execution_mode || '-');
    var __VLS_35;
    const __VLS_36 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        label: "返回条数",
    }));
    const __VLS_38 = __VLS_37({
        label: "返回条数",
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    __VLS_39.slots.default;
    (props.queryResult.result_explanation.result_count ?? '-');
    var __VLS_39;
    var __VLS_27;
}
if (__VLS_ctx.compatibilityNotice) {
    const __VLS_40 = {}.ElAlert;
    /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        type: "info",
        showIcon: true,
        closable: (false),
        ...{ style: {} },
    }));
    const __VLS_42 = __VLS_41({
        type: "info",
        showIcon: true,
        closable: (false),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
    {
        const { title: __VLS_thisSlot } = __VLS_43.slots;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ style: {} },
    });
    (__VLS_ctx.compatibilityNotice);
    var __VLS_43;
}
if (props.queryResult?.no_result_analysis) {
    const __VLS_44 = {}.ElAlert;
    /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        type: "warning",
        showIcon: true,
        closable: (false),
        ...{ style: {} },
    }));
    const __VLS_46 = __VLS_45({
        type: "warning",
        showIcon: true,
        closable: (false),
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    __VLS_47.slots.default;
    {
        const { title: __VLS_thisSlot } = __VLS_47.slots;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    ((props.queryResult.no_result_analysis.possible_reasons || []).join('；') || '-');
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.strong, __VLS_intrinsicElements.strong)({});
    ((props.queryResult.no_result_analysis.suggestions || []).join('；') || '-');
    var __VLS_47;
}
if (props.queryResult?.summary) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h4, __VLS_intrinsicElements.h4)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (__VLS_ctx.formatJson(props.queryResult.summary));
}
if (__VLS_ctx.showCompareSummary) {
    const __VLS_48 = {}.ElDescriptions;
    /** @type {[typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        column: (2),
        border: true,
        ...{ style: {} },
    }));
    const __VLS_50 = __VLS_49({
        column: (2),
        border: true,
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_51.slots.default;
    const __VLS_52 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        label: (props.queryResult?.left_label || '左值'),
    }));
    const __VLS_54 = __VLS_53({
        label: (props.queryResult?.left_label || '左值'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    __VLS_55.slots.default;
    (__VLS_ctx.formatCell(props.queryResult?.left_value));
    var __VLS_55;
    const __VLS_56 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        label: (props.queryResult?.right_label || '右值'),
    }));
    const __VLS_58 = __VLS_57({
        label: (props.queryResult?.right_label || '右值'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    __VLS_59.slots.default;
    (__VLS_ctx.formatCell(props.queryResult?.right_value));
    var __VLS_59;
    const __VLS_60 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
        label: "差值",
    }));
    const __VLS_62 = __VLS_61({
        label: "差值",
    }, ...__VLS_functionalComponentArgsRest(__VLS_61));
    __VLS_63.slots.default;
    (__VLS_ctx.formatCell(props.queryResult?.diff_value));
    var __VLS_63;
    const __VLS_64 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        label: "差异率",
    }));
    const __VLS_66 = __VLS_65({
        label: "差异率",
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    __VLS_67.slots.default;
    (__VLS_ctx.formatRate(props.queryResult?.diff_rate));
    var __VLS_67;
    var __VLS_51;
}
if (__VLS_ctx.hasItems) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
    /** @type {[typeof ResultTable, ]} */ ;
    // @ts-ignore
    const __VLS_68 = __VLS_asFunctionalComponent(ResultTable, new ResultTable({
        ...{ 'onRowDetail': {} },
        items: (__VLS_ctx.tableItems),
        title: "明细/统计列表",
    }));
    const __VLS_69 = __VLS_68({
        ...{ 'onRowDetail': {} },
        items: (__VLS_ctx.tableItems),
        title: "明细/统计列表",
    }, ...__VLS_functionalComponentArgsRest(__VLS_68));
    let __VLS_71;
    let __VLS_72;
    let __VLS_73;
    const __VLS_74 = {
        onRowDetail: (__VLS_ctx.emitRowDetail)
    };
    var __VLS_70;
}
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['header-row']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            ResultTable: ResultTable,
            hasItems: hasItems,
            tableItems: tableItems,
            showCompareSummary: showCompareSummary,
            compatibilityNotice: compatibilityNotice,
            exportCurrentItems: exportCurrentItems,
            emitOpenDetail: emitOpenDetail,
            emitRowDetail: emitRowDetail,
            formatJson: formatJson,
            resolveAlertType: resolveAlertType,
            formatCell: formatCell,
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
