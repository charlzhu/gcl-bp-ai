import { computed, onMounted, reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { fetchQueryHistory, fetchQueryHistoryDetail, } from '@/api/logistics';
import { saveLastQueryContext, saveQueryPageDraft } from '@/utils/queryStorage';
const router = useRouter();
const payload = ref(null);
const detailVisible = ref(false);
const detailLoading = ref(false);
const detailData = ref(null);
const loading = ref(false);
const loadError = ref('');
const detailError = ref('');
const filters = reactive({
    query_type: '',
    keyword: '',
    trace_id: '',
});
const pager = reactive({
    page: 1,
    page_size: 20,
});
/**
 * 当前表格数据。
 */
const list = computed(() => payload.value?.items ?? []);
/**
 * 页面级提示文案。
 */
const warningText = computed(() => payload.value?.load_warning || loadError.value);
/**
 * 加载查询历史列表。
 * 说明：
 * 这里仍沿用列表接口，只在查看详情时再按需拉单条详情，避免页面初始请求过重。
 */
async function load() {
    loading.value = true;
    loadError.value = '';
    try {
        const resp = await fetchQueryHistory({
            page: pager.page,
            page_size: pager.page_size,
            query_type: filters.query_type || undefined,
            keyword: filters.keyword.trim() || undefined,
            trace_id: filters.trace_id || undefined,
        });
        payload.value = (resp.data ?? resp ?? null);
        pager.page = payload.value?.page || pager.page;
        pager.page_size = payload.value?.page_size || pager.page_size;
    }
    catch (_error) {
        loadError.value = '当前后端未开放查询历史接口，或接口路径与前端默认配置不一致。';
        payload.value = {
            total: 0,
            page: pager.page,
            page_size: pager.page_size,
            items: [],
            load_warning: null,
        };
    }
    finally {
        loading.value = false;
    }
}
/**
 * 以当前筛选条件重新查询历史列表。
 * 说明：
 * 关键词、类型和 Trace ID 变更后，统一回到第一页，避免仍停留在旧页码导致“查不到数据”的错觉。
 */
function handleSearch() {
    pager.page = 1;
    load();
}
/**
 * 重置筛选条件并回到第一页。
 */
function resetFilters() {
    filters.query_type = '';
    filters.keyword = '';
    filters.trace_id = '';
    pager.page = 1;
    pager.page_size = 20;
    load();
}
/**
 * 切换页码。
 */
function handlePageChange(page) {
    pager.page = page;
    load();
}
/**
 * 切换每页条数。
 * 说明：
 * 调整分页大小后也回到第一页，避免请求越界页码。
 */
function handlePageSizeChange(pageSize) {
    pager.page_size = pageSize;
    pager.page = 1;
    load();
}
/**
 * 查看单条历史详情。
 * 说明：
 * 详情统一走后端单条接口，避免列表页反复拼装结构化快照。
 */
async function view(row) {
    detailVisible.value = true;
    detailLoading.value = true;
    detailError.value = '';
    detailData.value = null;
    try {
        const resp = await fetchQueryHistoryDetail(row.id);
        detailData.value = (resp.data ?? resp ?? null);
    }
    catch (_error) {
        detailError.value = '查询历史详情加载失败，请稍后重试。';
    }
    finally {
        detailLoading.value = false;
    }
}
/**
 * 重新发起查询。
 * 说明：
 * 1. 这里只负责把历史问题或结构化条件带回对应查询页；
 * 2. 不在历史页自动重跑，避免用户离开历史页后立即触发新请求；
 * 3. 优先复用已有的 queryStorage，减少新增全局状态。
 */
function requery(row) {
    if (row.query_type === 'AGGREGATE') {
        const aggregatePayload = extractAggregatePayload(row.request_payload_json);
        if (!aggregatePayload) {
            ElMessage.warning('当前结构化历史记录缺少可回填的请求参数。');
            return;
        }
        saveQueryPageDraft({
            sourcePage: 'structured-query',
            formData: aggregatePayload,
        });
        saveLastQueryContext({
            sourcePage: 'structured-query',
            requestPayload: aggregatePayload,
            rawResponse: null,
            queryResult: null,
            selectedRow: null,
        });
        router.push('/structured-query');
        return;
    }
    if (!row.question || row.question === '-') {
        ElMessage.warning('当前历史记录缺少可回填的问题文本。');
        return;
    }
    saveQueryPageDraft({
        sourcePage: 'nl-query',
        formData: {
            question: row.question,
        },
    });
    saveLastQueryContext({
        sourcePage: 'nl-query',
        question: row.question,
        requestPayload: { question: row.question },
        rawResponse: null,
        parsed: null,
        queryResult: null,
        selectedRow: null,
    });
    router.push('/nl-query');
}
/**
 * 提取结构化查询的原始请求参数。
 * 说明：
 * 历史日志的 request_payload_json 在不同来源下可能层级略有差异，
 * 这里只提取前端条件查询页已经支持的最小字段集合。
 */
function extractAggregatePayload(payloadJson) {
    if (!payloadJson || typeof payloadJson !== 'object')
        return null;
    let candidate = null;
    if (payloadJson.metric_type || payloadJson.source_scope || payloadJson.year_month_list) {
        candidate = payloadJson;
    }
    else {
        const nestedPayload = payloadJson.request_payload;
        if (isAggregatePayload(nestedPayload)) {
            candidate = nestedPayload;
        }
    }
    if (!candidate)
        return null;
    return {
        metric_type: candidate.metric_type,
        source_scope: candidate.source_scope,
        year_month_list: Array.isArray(candidate.year_month_list) ? candidate.year_month_list : [],
        customer_name: candidate.customer_name ?? null,
        logistics_company_name: candidate.logistics_company_name ?? null,
        region_name: candidate.region_name ?? null,
        origin_place: candidate.origin_place ?? null,
        transport_mode: candidate.transport_mode ?? null,
        group_by: Array.isArray(candidate.group_by) ? candidate.group_by : [],
        order_direction: candidate.order_direction ?? 'desc',
        limit: candidate.limit ?? 100,
    };
}
/**
 * 判断对象是否可视为结构化查询请求。
 */
function isAggregatePayload(value) {
    if (!value || typeof value !== 'object')
        return false;
    const payload = value;
    return Boolean(payload.metric_type || payload.source_scope || payload.year_month_list);
}
/**
 * 格式化查询类型名称。
 */
function formatQueryType(value) {
    if (value === 'NL_QUERY_PLAN')
        return '自然语言';
    if (value === 'AGGREGATE')
        return '结构化统计';
    if (value === 'DETAIL')
        return '明细查询';
    if (value === 'COMPARE')
        return '对比查询';
    return value || '-';
}
/**
 * 格式化执行模式名称。
 */
function formatExecutionMode(value) {
    if (value === 'database')
        return '数据库';
    if (value === 'fallback')
        return '兼容模式';
    if (value === 'error_fallback')
        return '错误兜底';
    return value || '-';
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
 * 统一映射状态标签颜色。
 */
function resolveStatusTagType(value) {
    if (value === 'OK')
        return 'success';
    if (value === 'EMPTY_RESULT' || value === 'FALLBACK_MODE' || value === 'DETAIL_NOT_FOUND')
        return 'warning';
    if (value === 'EXECUTION_ERROR')
        return 'danger';
    return 'info';
}
/**
 * 格式化时间。
 */
function formatDateTime(value) {
    if (!value)
        return '-';
    const date = new Date(value);
    if (Number.isNaN(date.getTime()))
        return value;
    return date.toLocaleString('zh-CN', { hour12: false });
}
/**
 * JSON 格式化。
 */
function formatJson(value) {
    if (!value)
        return '-';
    return JSON.stringify(value, null, 2);
}
onMounted(() => {
    load();
});
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
    ...{ class: "page-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "page-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "page-subtitle" },
});
const __VLS_0 = {}.ElSpace;
/** @type {[typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    wrap: true,
}));
const __VLS_2 = __VLS_1({
    wrap: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ElSelect;
/** @type {[typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, typeof __VLS_components.ElSelect, typeof __VLS_components.elSelect, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    modelValue: (__VLS_ctx.filters.query_type),
    clearable: true,
    placeholder: "查询类型",
    ...{ style: {} },
}));
const __VLS_6 = __VLS_5({
    modelValue: (__VLS_ctx.filters.query_type),
    clearable: true,
    placeholder: "查询类型",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
__VLS_7.slots.default;
const __VLS_8 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    label: "NL_QUERY_PLAN",
    value: "NL_QUERY_PLAN",
}));
const __VLS_10 = __VLS_9({
    label: "NL_QUERY_PLAN",
    value: "NL_QUERY_PLAN",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
const __VLS_12 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    label: "AGGREGATE",
    value: "AGGREGATE",
}));
const __VLS_14 = __VLS_13({
    label: "AGGREGATE",
    value: "AGGREGATE",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
const __VLS_16 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
    label: "DETAIL",
    value: "DETAIL",
}));
const __VLS_18 = __VLS_17({
    label: "DETAIL",
    value: "DETAIL",
}, ...__VLS_functionalComponentArgsRest(__VLS_17));
const __VLS_20 = {}.ElOption;
/** @type {[typeof __VLS_components.ElOption, typeof __VLS_components.elOption, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    label: "COMPARE",
    value: "COMPARE",
}));
const __VLS_22 = __VLS_21({
    label: "COMPARE",
    value: "COMPARE",
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
var __VLS_7;
const __VLS_24 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.filters.keyword),
    clearable: true,
    placeholder: "按问题关键词检索",
    ...{ style: {} },
}));
const __VLS_26 = __VLS_25({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.filters.keyword),
    clearable: true,
    placeholder: "按问题关键词检索",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onKeyup: (__VLS_ctx.handleSearch)
};
var __VLS_27;
const __VLS_32 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.filters.trace_id),
    clearable: true,
    placeholder: "按 Trace ID 过滤",
    ...{ style: {} },
}));
const __VLS_34 = __VLS_33({
    ...{ 'onKeyup': {} },
    modelValue: (__VLS_ctx.filters.trace_id),
    clearable: true,
    placeholder: "按 Trace ID 过滤",
    ...{ style: {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
let __VLS_36;
let __VLS_37;
let __VLS_38;
const __VLS_39 = {
    onKeyup: (__VLS_ctx.handleSearch)
};
var __VLS_35;
const __VLS_40 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
}));
const __VLS_42 = __VLS_41({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_41));
let __VLS_44;
let __VLS_45;
let __VLS_46;
const __VLS_47 = {
    onClick: (__VLS_ctx.handleSearch)
};
__VLS_43.slots.default;
var __VLS_43;
const __VLS_48 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.loading),
}));
const __VLS_50 = __VLS_49({
    ...{ 'onClick': {} },
    disabled: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_49));
let __VLS_52;
let __VLS_53;
let __VLS_54;
const __VLS_55 = {
    onClick: (__VLS_ctx.resetFilters)
};
__VLS_51.slots.default;
var __VLS_51;
var __VLS_3;
if (__VLS_ctx.warningText) {
    const __VLS_56 = {}.ElAlert;
    /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        title: (__VLS_ctx.warningText),
        type: "warning",
        closable: (false),
        showIcon: true,
        ...{ style: {} },
    }));
    const __VLS_58 = __VLS_57({
        title: (__VLS_ctx.warningText),
        type: "warning",
        closable: (false),
        showIcon: true,
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
}
const __VLS_60 = {}.ElTable;
/** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
// @ts-ignore
const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
    data: (__VLS_ctx.list),
    border: true,
    stripe: true,
    rowKey: "id",
}));
const __VLS_62 = __VLS_61({
    data: (__VLS_ctx.list),
    border: true,
    stripe: true,
    rowKey: "id",
}, ...__VLS_functionalComponentArgsRest(__VLS_61));
__VLS_63.slots.default;
const __VLS_64 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
    prop: "question",
    label: "历史问题",
    minWidth: "320",
    showOverflowTooltip: true,
}));
const __VLS_66 = __VLS_65({
    prop: "question",
    label: "历史问题",
    minWidth: "320",
    showOverflowTooltip: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_65));
const __VLS_68 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
    label: "类型",
    width: "140",
}));
const __VLS_70 = __VLS_69({
    label: "类型",
    width: "140",
}, ...__VLS_functionalComponentArgsRest(__VLS_69));
__VLS_71.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_71.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_72 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        size: "small",
        effect: "plain",
    }));
    const __VLS_74 = __VLS_73({
        size: "small",
        effect: "plain",
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
    __VLS_75.slots.default;
    (__VLS_ctx.formatQueryType(row.query_type));
    var __VLS_75;
}
var __VLS_71;
const __VLS_76 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
    label: "执行模式",
    width: "130",
}));
const __VLS_78 = __VLS_77({
    label: "执行模式",
    width: "130",
}, ...__VLS_functionalComponentArgsRest(__VLS_77));
__VLS_79.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_79.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_80 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
        size: "small",
        type: (__VLS_ctx.resolveExecutionModeTagType(row.execution_mode)),
    }));
    const __VLS_82 = __VLS_81({
        size: "small",
        type: (__VLS_ctx.resolveExecutionModeTagType(row.execution_mode)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_81));
    __VLS_83.slots.default;
    (__VLS_ctx.formatExecutionMode(row.execution_mode));
    var __VLS_83;
}
var __VLS_79;
const __VLS_84 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
    label: "模板命中",
    width: "180",
}));
const __VLS_86 = __VLS_85({
    label: "模板命中",
    width: "180",
}, ...__VLS_functionalComponentArgsRest(__VLS_85));
__VLS_87.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_87.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tag-cell" },
    });
    const __VLS_88 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
        size: "small",
        type: (row.template_hit ? 'success' : 'info'),
    }));
    const __VLS_90 = __VLS_89({
        size: "small",
        type: (row.template_hit ? 'success' : 'info'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_89));
    __VLS_91.slots.default;
    (row.template_hit ? '已命中' : '未命中');
    var __VLS_91;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "minor-text" },
    });
    (row.template_id || '-');
}
var __VLS_87;
const __VLS_92 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
    label: "状态",
    width: "220",
}));
const __VLS_94 = __VLS_93({
    label: "状态",
    width: "220",
}, ...__VLS_functionalComponentArgsRest(__VLS_93));
__VLS_95.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_95.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "tag-cell" },
    });
    const __VLS_96 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
        size: "small",
        type: (__VLS_ctx.resolveStatusTagType(row.status_code || row.status)),
    }));
    const __VLS_98 = __VLS_97({
        size: "small",
        type: (__VLS_ctx.resolveStatusTagType(row.status_code || row.status)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_97));
    __VLS_99.slots.default;
    (row.status_code || row.status || '-');
    var __VLS_99;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "minor-text" },
    });
    (row.status_message || row.message || '-');
}
var __VLS_95;
const __VLS_100 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    prop: "result_count",
    label: "结果数",
    width: "90",
}));
const __VLS_102 = __VLS_101({
    prop: "result_count",
    label: "结果数",
    width: "90",
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
const __VLS_104 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
    prop: "created_at",
    label: "时间",
    minWidth: "180",
}));
const __VLS_106 = __VLS_105({
    prop: "created_at",
    label: "时间",
    minWidth: "180",
}, ...__VLS_functionalComponentArgsRest(__VLS_105));
__VLS_107.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_107.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    (__VLS_ctx.formatDateTime(row.created_at));
}
var __VLS_107;
const __VLS_108 = {}.ElTableColumn;
/** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
// @ts-ignore
const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
    label: "操作",
    width: "190",
    fixed: "right",
}));
const __VLS_110 = __VLS_109({
    label: "操作",
    width: "190",
    fixed: "right",
}, ...__VLS_functionalComponentArgsRest(__VLS_109));
__VLS_111.slots.default;
{
    const { default: __VLS_thisSlot } = __VLS_111.slots;
    const [{ row }] = __VLS_getSlotParams(__VLS_thisSlot);
    const __VLS_112 = {}.ElSpace;
    /** @type {[typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, ]} */ ;
    // @ts-ignore
    const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({}));
    const __VLS_114 = __VLS_113({}, ...__VLS_functionalComponentArgsRest(__VLS_113));
    __VLS_115.slots.default;
    const __VLS_116 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
        ...{ 'onClick': {} },
        size: "small",
    }));
    const __VLS_118 = __VLS_117({
        ...{ 'onClick': {} },
        size: "small",
    }, ...__VLS_functionalComponentArgsRest(__VLS_117));
    let __VLS_120;
    let __VLS_121;
    let __VLS_122;
    const __VLS_123 = {
        onClick: (...[$event]) => {
            __VLS_ctx.view(row);
        }
    };
    __VLS_119.slots.default;
    var __VLS_119;
    const __VLS_124 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
        ...{ 'onClick': {} },
        size: "small",
        type: "primary",
        plain: true,
    }));
    const __VLS_126 = __VLS_125({
        ...{ 'onClick': {} },
        size: "small",
        type: "primary",
        plain: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_125));
    let __VLS_128;
    let __VLS_129;
    let __VLS_130;
    const __VLS_131 = {
        onClick: (...[$event]) => {
            __VLS_ctx.requery(row);
        }
    };
    __VLS_127.slots.default;
    var __VLS_127;
    var __VLS_115;
}
var __VLS_111;
var __VLS_63;
if (!__VLS_ctx.loading && __VLS_ctx.list.length === 0) {
    const __VLS_132 = {}.ElEmpty;
    /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
        description: "暂无查询历史记录",
        ...{ style: {} },
    }));
    const __VLS_134 = __VLS_133({
        description: "暂无查询历史记录",
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_133));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "pager-wrap" },
});
const __VLS_136 = {}.ElPagination;
/** @type {[typeof __VLS_components.ElPagination, typeof __VLS_components.elPagination, ]} */ ;
// @ts-ignore
const __VLS_137 = __VLS_asFunctionalComponent(__VLS_136, new __VLS_136({
    ...{ 'onCurrentChange': {} },
    ...{ 'onSizeChange': {} },
    background: true,
    layout: "total, sizes, prev, pager, next",
    total: (__VLS_ctx.payload?.total ?? 0),
    currentPage: (__VLS_ctx.pager.page),
    pageSize: (__VLS_ctx.pager.page_size),
    pageSizes: ([10, 20, 50, 100]),
}));
const __VLS_138 = __VLS_137({
    ...{ 'onCurrentChange': {} },
    ...{ 'onSizeChange': {} },
    background: true,
    layout: "total, sizes, prev, pager, next",
    total: (__VLS_ctx.payload?.total ?? 0),
    currentPage: (__VLS_ctx.pager.page),
    pageSize: (__VLS_ctx.pager.page_size),
    pageSizes: ([10, 20, 50, 100]),
}, ...__VLS_functionalComponentArgsRest(__VLS_137));
let __VLS_140;
let __VLS_141;
let __VLS_142;
const __VLS_143 = {
    onCurrentChange: (__VLS_ctx.handlePageChange)
};
const __VLS_144 = {
    onSizeChange: (__VLS_ctx.handlePageSizeChange)
};
var __VLS_139;
const __VLS_145 = {}.ElDrawer;
/** @type {[typeof __VLS_components.ElDrawer, typeof __VLS_components.elDrawer, typeof __VLS_components.ElDrawer, typeof __VLS_components.elDrawer, ]} */ ;
// @ts-ignore
const __VLS_146 = __VLS_asFunctionalComponent(__VLS_145, new __VLS_145({
    modelValue: (__VLS_ctx.detailVisible),
    title: "查询历史详情",
    size: "48%",
    destroyOnClose: true,
}));
const __VLS_147 = __VLS_146({
    modelValue: (__VLS_ctx.detailVisible),
    title: "查询历史详情",
    size: "48%",
    destroyOnClose: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_146));
__VLS_148.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalDirective(__VLS_directives.vLoading)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.detailLoading) }, null, null);
if (__VLS_ctx.detailError) {
    const __VLS_149 = {}.ElAlert;
    /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
    // @ts-ignore
    const __VLS_150 = __VLS_asFunctionalComponent(__VLS_149, new __VLS_149({
        title: (__VLS_ctx.detailError),
        type: "error",
        closable: (false),
        showIcon: true,
        ...{ style: {} },
    }));
    const __VLS_151 = __VLS_150({
        title: (__VLS_ctx.detailError),
        type: "error",
        closable: (false),
        showIcon: true,
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_150));
}
if (__VLS_ctx.detailData) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "detail-toolbar" },
    });
    const __VLS_153 = {}.ElSpace;
    /** @type {[typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, ]} */ ;
    // @ts-ignore
    const __VLS_154 = __VLS_asFunctionalComponent(__VLS_153, new __VLS_153({
        wrap: true,
    }));
    const __VLS_155 = __VLS_154({
        wrap: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_154));
    __VLS_156.slots.default;
    const __VLS_157 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_158 = __VLS_asFunctionalComponent(__VLS_157, new __VLS_157({
        effect: "dark",
        type: (__VLS_ctx.resolveStatusTagType(__VLS_ctx.detailData.status_code || __VLS_ctx.detailData.status)),
    }));
    const __VLS_159 = __VLS_158({
        effect: "dark",
        type: (__VLS_ctx.resolveStatusTagType(__VLS_ctx.detailData.status_code || __VLS_ctx.detailData.status)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_158));
    __VLS_160.slots.default;
    (__VLS_ctx.detailData.status_code || __VLS_ctx.detailData.status || '-');
    var __VLS_160;
    const __VLS_161 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_162 = __VLS_asFunctionalComponent(__VLS_161, new __VLS_161({
        type: (__VLS_ctx.resolveExecutionModeTagType(__VLS_ctx.detailData.execution_mode)),
    }));
    const __VLS_163 = __VLS_162({
        type: (__VLS_ctx.resolveExecutionModeTagType(__VLS_ctx.detailData.execution_mode)),
    }, ...__VLS_functionalComponentArgsRest(__VLS_162));
    __VLS_164.slots.default;
    (__VLS_ctx.formatExecutionMode(__VLS_ctx.detailData.execution_mode));
    var __VLS_164;
    const __VLS_165 = {}.ElTag;
    /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
    // @ts-ignore
    const __VLS_166 = __VLS_asFunctionalComponent(__VLS_165, new __VLS_165({
        type: (__VLS_ctx.detailData.template_hit ? 'success' : 'info'),
    }));
    const __VLS_167 = __VLS_166({
        type: (__VLS_ctx.detailData.template_hit ? 'success' : 'info'),
    }, ...__VLS_functionalComponentArgsRest(__VLS_166));
    __VLS_168.slots.default;
    (__VLS_ctx.detailData.template_hit ? '模板已命中' : '模板未命中');
    var __VLS_168;
    var __VLS_156;
    const __VLS_169 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_170 = __VLS_asFunctionalComponent(__VLS_169, new __VLS_169({
        ...{ 'onClick': {} },
        size: "small",
        type: "primary",
        plain: true,
    }));
    const __VLS_171 = __VLS_170({
        ...{ 'onClick': {} },
        size: "small",
        type: "primary",
        plain: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_170));
    let __VLS_173;
    let __VLS_174;
    let __VLS_175;
    const __VLS_176 = {
        onClick: (...[$event]) => {
            if (!(__VLS_ctx.detailData))
                return;
            __VLS_ctx.requery(__VLS_ctx.detailData);
        }
    };
    __VLS_172.slots.default;
    var __VLS_172;
    const __VLS_177 = {}.ElDescriptions;
    /** @type {[typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_178 = __VLS_asFunctionalComponent(__VLS_177, new __VLS_177({
        column: (1),
        border: true,
        ...{ style: {} },
    }));
    const __VLS_179 = __VLS_178({
        column: (1),
        border: true,
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_178));
    __VLS_180.slots.default;
    const __VLS_181 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_182 = __VLS_asFunctionalComponent(__VLS_181, new __VLS_181({
        label: "历史问题",
    }));
    const __VLS_183 = __VLS_182({
        label: "历史问题",
    }, ...__VLS_functionalComponentArgsRest(__VLS_182));
    __VLS_184.slots.default;
    (__VLS_ctx.detailData.question || '-');
    var __VLS_184;
    const __VLS_185 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_186 = __VLS_asFunctionalComponent(__VLS_185, new __VLS_185({
        label: "查询类型",
    }));
    const __VLS_187 = __VLS_186({
        label: "查询类型",
    }, ...__VLS_functionalComponentArgsRest(__VLS_186));
    __VLS_188.slots.default;
    (__VLS_ctx.formatQueryType(__VLS_ctx.detailData.query_type));
    var __VLS_188;
    const __VLS_189 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_190 = __VLS_asFunctionalComponent(__VLS_189, new __VLS_189({
        label: "执行模式",
    }));
    const __VLS_191 = __VLS_190({
        label: "执行模式",
    }, ...__VLS_functionalComponentArgsRest(__VLS_190));
    __VLS_192.slots.default;
    (__VLS_ctx.formatExecutionMode(__VLS_ctx.detailData.execution_mode));
    var __VLS_192;
    const __VLS_193 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_194 = __VLS_asFunctionalComponent(__VLS_193, new __VLS_193({
        label: "模板 ID",
    }));
    const __VLS_195 = __VLS_194({
        label: "模板 ID",
    }, ...__VLS_functionalComponentArgsRest(__VLS_194));
    __VLS_196.slots.default;
    (__VLS_ctx.detailData.template_id || '-');
    var __VLS_196;
    const __VLS_197 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_198 = __VLS_asFunctionalComponent(__VLS_197, new __VLS_197({
        label: "状态说明",
    }));
    const __VLS_199 = __VLS_198({
        label: "状态说明",
    }, ...__VLS_functionalComponentArgsRest(__VLS_198));
    __VLS_200.slots.default;
    (__VLS_ctx.detailData.status_message || __VLS_ctx.detailData.message || '-');
    var __VLS_200;
    const __VLS_201 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_202 = __VLS_asFunctionalComponent(__VLS_201, new __VLS_201({
        label: "Trace ID",
    }));
    const __VLS_203 = __VLS_202({
        label: "Trace ID",
    }, ...__VLS_functionalComponentArgsRest(__VLS_202));
    __VLS_204.slots.default;
    (__VLS_ctx.detailData.trace_id || '-');
    var __VLS_204;
    const __VLS_205 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_206 = __VLS_asFunctionalComponent(__VLS_205, new __VLS_205({
        label: "时间",
    }));
    const __VLS_207 = __VLS_206({
        label: "时间",
    }, ...__VLS_functionalComponentArgsRest(__VLS_206));
    __VLS_208.slots.default;
    (__VLS_ctx.formatDateTime(__VLS_ctx.detailData.created_at));
    var __VLS_208;
    var __VLS_180;
    const __VLS_209 = {}.ElCollapse;
    /** @type {[typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, ]} */ ;
    // @ts-ignore
    const __VLS_210 = __VLS_asFunctionalComponent(__VLS_209, new __VLS_209({}));
    const __VLS_211 = __VLS_210({}, ...__VLS_functionalComponentArgsRest(__VLS_210));
    __VLS_212.slots.default;
    const __VLS_213 = {}.ElCollapseItem;
    /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
    // @ts-ignore
    const __VLS_214 = __VLS_asFunctionalComponent(__VLS_213, new __VLS_213({
        name: "parsed",
        title: "问题解析（parsed）",
    }));
    const __VLS_215 = __VLS_214({
        name: "parsed",
        title: "问题解析（parsed）",
    }, ...__VLS_functionalComponentArgsRest(__VLS_214));
    __VLS_216.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (__VLS_ctx.formatJson(__VLS_ctx.detailData.parsed));
    var __VLS_216;
    const __VLS_217 = {}.ElCollapseItem;
    /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
    // @ts-ignore
    const __VLS_218 = __VLS_asFunctionalComponent(__VLS_217, new __VLS_217({
        name: "query-result",
        title: "查询结果快照（query_result）",
    }));
    const __VLS_219 = __VLS_218({
        name: "query-result",
        title: "查询结果快照（query_result）",
    }, ...__VLS_functionalComponentArgsRest(__VLS_218));
    __VLS_220.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (__VLS_ctx.formatJson(__VLS_ctx.detailData.query_result));
    var __VLS_220;
    const __VLS_221 = {}.ElCollapseItem;
    /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
    // @ts-ignore
    const __VLS_222 = __VLS_asFunctionalComponent(__VLS_221, new __VLS_221({
        name: "response-meta",
        title: "响应元信息（response_meta）",
    }));
    const __VLS_223 = __VLS_222({
        name: "response-meta",
        title: "响应元信息（response_meta）",
    }, ...__VLS_functionalComponentArgsRest(__VLS_222));
    __VLS_224.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (__VLS_ctx.formatJson(__VLS_ctx.detailData.response_meta));
    var __VLS_224;
    const __VLS_225 = {}.ElCollapseItem;
    /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
    // @ts-ignore
    const __VLS_226 = __VLS_asFunctionalComponent(__VLS_225, new __VLS_225({
        name: "execution-binding",
        title: "执行绑定（execution_binding）",
    }));
    const __VLS_227 = __VLS_226({
        name: "execution-binding",
        title: "执行绑定（execution_binding）",
    }, ...__VLS_functionalComponentArgsRest(__VLS_226));
    __VLS_228.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (__VLS_ctx.formatJson(__VLS_ctx.detailData.execution_binding));
    var __VLS_228;
    const __VLS_229 = {}.ElCollapseItem;
    /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
    // @ts-ignore
    const __VLS_230 = __VLS_asFunctionalComponent(__VLS_229, new __VLS_229({
        name: "execution-summary",
        title: "执行摘要（execution_summary）",
    }));
    const __VLS_231 = __VLS_230({
        name: "execution-summary",
        title: "执行摘要（execution_summary）",
    }, ...__VLS_functionalComponentArgsRest(__VLS_230));
    __VLS_232.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (__VLS_ctx.formatJson(__VLS_ctx.detailData.execution_summary));
    var __VLS_232;
    const __VLS_233 = {}.ElCollapseItem;
    /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
    // @ts-ignore
    const __VLS_234 = __VLS_asFunctionalComponent(__VLS_233, new __VLS_233({
        name: "request-payload",
        title: "原始请求载荷（request_payload_json）",
    }));
    const __VLS_235 = __VLS_234({
        name: "request-payload",
        title: "原始请求载荷（request_payload_json）",
    }, ...__VLS_functionalComponentArgsRest(__VLS_234));
    __VLS_236.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (__VLS_ctx.formatJson(__VLS_ctx.detailData.request_payload_json));
    var __VLS_236;
    var __VLS_212;
}
else if (!__VLS_ctx.detailLoading && !__VLS_ctx.detailError) {
    const __VLS_237 = {}.ElEmpty;
    /** @type {[typeof __VLS_components.ElEmpty, typeof __VLS_components.elEmpty, ]} */ ;
    // @ts-ignore
    const __VLS_238 = __VLS_asFunctionalComponent(__VLS_237, new __VLS_237({
        description: "请选择一条历史记录查看详情",
    }));
    const __VLS_239 = __VLS_238({
        description: "请选择一条历史记录查看详情",
    }, ...__VLS_functionalComponentArgsRest(__VLS_238));
}
var __VLS_148;
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['minor-text']} */ ;
/** @type {__VLS_StyleScopedClasses['tag-cell']} */ ;
/** @type {__VLS_StyleScopedClasses['minor-text']} */ ;
/** @type {__VLS_StyleScopedClasses['pager-wrap']} */ ;
/** @type {__VLS_StyleScopedClasses['detail-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            payload: payload,
            detailVisible: detailVisible,
            detailLoading: detailLoading,
            detailData: detailData,
            loading: loading,
            detailError: detailError,
            filters: filters,
            pager: pager,
            list: list,
            warningText: warningText,
            handleSearch: handleSearch,
            resetFilters: resetFilters,
            handlePageChange: handlePageChange,
            handlePageSizeChange: handlePageSizeChange,
            view: view,
            requery: requery,
            formatQueryType: formatQueryType,
            formatExecutionMode: formatExecutionMode,
            resolveExecutionModeTagType: resolveExecutionModeTagType,
            resolveStatusTagType: resolveStatusTagType,
            formatDateTime: formatDateTime,
            formatJson: formatJson,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
