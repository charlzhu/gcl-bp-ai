import { onMounted, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { fetchNLQuery } from '@/api/logistics';
import ParsedResultCard from '@/components/ParsedResultCard.vue';
import QueryResultCard from '@/components/QueryResultCard.vue';
import { getLastQueryContext, getQueryPageDraft, saveLastQueryContext, saveQueryPageDraft, } from '@/utils/queryStorage';
const router = useRouter();
const question = ref('2025年3月运量是多少');
const loading = ref(false);
const resultData = ref(null);
/** 填充示例问题，便于快速联调。 */
function fillExample(value) {
    question.value = value;
}
/**
 * 保存最近一次查询上下文。
 */
function persistContext(selectedRow = null) {
    if (!resultData.value)
        return;
    saveLastQueryContext({
        sourcePage: 'nl-query',
        question: question.value.trim(),
        requestPayload: { question: question.value.trim() },
        rawResponse: resultData.value,
        parsed: resultData.value.parsed ?? null,
        queryResult: resultData.value.query_result ?? null,
        selectedRow,
    });
}
/**
 * 恢复自然语言查询页草稿和最近一次结果。
 * 说明：
 * 1. 先恢复未提交的输入草稿；
 * 2. 再恢复最近一次已执行查询的结果，保证从明细页返回时不丢上下文；
 * 3. 只恢复当前页面自己的缓存，避免误把条件查询页的结果带进来。
 */
function restorePageState() {
    const draft = getQueryPageDraft('nl-query');
    if (draft?.formData?.question) {
        question.value = String(draft.formData.question);
    }
    const context = getLastQueryContext();
    if (context?.sourcePage !== 'nl-query')
        return;
    if (context.question) {
        question.value = context.question;
    }
    if (context.rawResponse && typeof context.rawResponse === 'object') {
        resultData.value = context.rawResponse;
        return;
    }
    if (context.parsed || context.queryResult) {
        resultData.value = {
            question: context.question,
            parsed: context.parsed ?? null,
            query_result: context.queryResult ?? null,
        };
    }
}
/**
 * 打开完整明细页。
 */
function openDetail() {
    persistContext();
    router.push('/detail-view');
}
/**
 * 打开带有选中行的明细页。
 */
function openRowDetail(row) {
    persistContext(row);
    router.push('/detail-view');
}
/** 调用后端自然语言查询接口，并将完整结果挂到页面。 */
async function handleQuery() {
    if (!question.value.trim()) {
        ElMessage.warning('请输入查询问题');
        return;
    }
    loading.value = true;
    try {
        const resp = await fetchNLQuery({ question: question.value.trim() });
        resultData.value = resp.data ?? resp;
        persistContext();
        ElMessage.success('查询成功');
    }
    catch (error) {
        ElMessage.error('查询失败，请检查后端接口或请求参数');
        throw error;
    }
    finally {
        loading.value = false;
    }
}
/**
 * 持续缓存输入草稿。
 * 说明：
 * 即使用户还没有点击查询，也尽量保住当前问题文本。
 */
watch(question, (value) => {
    saveQueryPageDraft({
        sourcePage: 'nl-query',
        formData: {
            question: value,
        },
    });
}, { immediate: true });
onMounted(() => {
    restorePageState();
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-card" },
    ...{ style: {} },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
    ...{ class: "page-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
    ...{ class: "page-subtitle" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.code, __VLS_intrinsicElements.code)({});
const __VLS_0 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ 'onSubmit': {} },
}));
const __VLS_2 = __VLS_1({
    ...{ 'onSubmit': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
let __VLS_4;
let __VLS_5;
let __VLS_6;
const __VLS_7 = {
    onSubmit: () => { }
};
__VLS_3.slots.default;
const __VLS_8 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
    label: "问题",
}));
const __VLS_10 = __VLS_9({
    label: "问题",
}, ...__VLS_functionalComponentArgsRest(__VLS_9));
__VLS_11.slots.default;
const __VLS_12 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    modelValue: (__VLS_ctx.question),
    type: "textarea",
    rows: (4),
    placeholder: "例如：2025年3月运量是多少；合同编号GCL5010ZJ202503015的明细",
}));
const __VLS_14 = __VLS_13({
    modelValue: (__VLS_ctx.question),
    type: "textarea",
    rows: (4),
    placeholder: "例如：2025年3月运量是多少；合同编号GCL5010ZJ202503015的明细",
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
var __VLS_11;
const __VLS_16 = {}.ElSpace;
/** @type {[typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, typeof __VLS_components.ElSpace, typeof __VLS_components.elSpace, ]} */ ;
// @ts-ignore
const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({}));
const __VLS_18 = __VLS_17({}, ...__VLS_functionalComponentArgsRest(__VLS_17));
__VLS_19.slots.default;
const __VLS_20 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
}));
const __VLS_22 = __VLS_21({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_21));
let __VLS_24;
let __VLS_25;
let __VLS_26;
const __VLS_27 = {
    onClick: (__VLS_ctx.handleQuery)
};
__VLS_23.slots.default;
var __VLS_23;
const __VLS_28 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
    ...{ 'onClick': {} },
}));
const __VLS_30 = __VLS_29({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_29));
let __VLS_32;
let __VLS_33;
let __VLS_34;
const __VLS_35 = {
    onClick: (...[$event]) => {
        __VLS_ctx.fillExample('2025年3月运量是多少');
    }
};
__VLS_31.slots.default;
var __VLS_31;
const __VLS_36 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    ...{ 'onClick': {} },
}));
const __VLS_38 = __VLS_37({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
let __VLS_40;
let __VLS_41;
let __VLS_42;
const __VLS_43 = {
    onClick: (...[$event]) => {
        __VLS_ctx.fillExample('25年3月和26年3月发货量对比');
    }
};
__VLS_39.slots.default;
var __VLS_39;
const __VLS_44 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    ...{ 'onClick': {} },
}));
const __VLS_46 = __VLS_45({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
let __VLS_48;
let __VLS_49;
let __VLS_50;
const __VLS_51 = {
    onClick: (...[$event]) => {
        __VLS_ctx.fillExample('合同编号GCL5010ZJ202503015的明细');
    }
};
__VLS_47.slots.default;
var __VLS_47;
var __VLS_19;
var __VLS_3;
const __VLS_52 = {}.ElRow;
/** @type {[typeof __VLS_components.ElRow, typeof __VLS_components.elRow, typeof __VLS_components.ElRow, typeof __VLS_components.elRow, ]} */ ;
// @ts-ignore
const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
    gutter: (20),
}));
const __VLS_54 = __VLS_53({
    gutter: (20),
}, ...__VLS_functionalComponentArgsRest(__VLS_53));
__VLS_55.slots.default;
const __VLS_56 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
    span: (12),
}));
const __VLS_58 = __VLS_57({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_57));
__VLS_59.slots.default;
/** @type {[typeof ParsedResultCard, ]} */ ;
// @ts-ignore
const __VLS_60 = __VLS_asFunctionalComponent(ParsedResultCard, new ParsedResultCard({
    parsed: (__VLS_ctx.resultData?.parsed ?? null),
}));
const __VLS_61 = __VLS_60({
    parsed: (__VLS_ctx.resultData?.parsed ?? null),
}, ...__VLS_functionalComponentArgsRest(__VLS_60));
var __VLS_59;
const __VLS_63 = {}.ElCol;
/** @type {[typeof __VLS_components.ElCol, typeof __VLS_components.elCol, typeof __VLS_components.ElCol, typeof __VLS_components.elCol, ]} */ ;
// @ts-ignore
const __VLS_64 = __VLS_asFunctionalComponent(__VLS_63, new __VLS_63({
    span: (12),
}));
const __VLS_65 = __VLS_64({
    span: (12),
}, ...__VLS_functionalComponentArgsRest(__VLS_64));
__VLS_66.slots.default;
/** @type {[typeof QueryResultCard, ]} */ ;
// @ts-ignore
const __VLS_67 = __VLS_asFunctionalComponent(QueryResultCard, new QueryResultCard({
    ...{ 'onOpenDetail': {} },
    ...{ 'onRowDetail': {} },
    queryResult: (__VLS_ctx.resultData?.query_result ?? null),
    parsed: (__VLS_ctx.resultData?.parsed ?? null),
    question: (__VLS_ctx.resultData?.question ?? __VLS_ctx.question),
    requestPayload: ({ question: __VLS_ctx.question.trim() }),
    responseMeta: (__VLS_ctx.resultData?.response_meta ?? null),
}));
const __VLS_68 = __VLS_67({
    ...{ 'onOpenDetail': {} },
    ...{ 'onRowDetail': {} },
    queryResult: (__VLS_ctx.resultData?.query_result ?? null),
    parsed: (__VLS_ctx.resultData?.parsed ?? null),
    question: (__VLS_ctx.resultData?.question ?? __VLS_ctx.question),
    requestPayload: ({ question: __VLS_ctx.question.trim() }),
    responseMeta: (__VLS_ctx.resultData?.response_meta ?? null),
}, ...__VLS_functionalComponentArgsRest(__VLS_67));
let __VLS_70;
let __VLS_71;
let __VLS_72;
const __VLS_73 = {
    onOpenDetail: (__VLS_ctx.openDetail)
};
const __VLS_74 = {
    onRowDetail: (__VLS_ctx.openRowDetail)
};
var __VLS_69;
var __VLS_66;
var __VLS_55;
if (__VLS_ctx.resultData) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "page-card" },
        ...{ style: {} },
    });
    const __VLS_75 = {}.ElCollapse;
    /** @type {[typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, ]} */ ;
    // @ts-ignore
    const __VLS_76 = __VLS_asFunctionalComponent(__VLS_75, new __VLS_75({}));
    const __VLS_77 = __VLS_76({}, ...__VLS_functionalComponentArgsRest(__VLS_76));
    __VLS_78.slots.default;
    const __VLS_79 = {}.ElCollapseItem;
    /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
    // @ts-ignore
    const __VLS_80 = __VLS_asFunctionalComponent(__VLS_79, new __VLS_79({
        title: "查看完整响应（调试）",
        name: "raw-response",
    }));
    const __VLS_81 = __VLS_80({
        title: "查看完整响应（调试）",
        name: "raw-response",
    }, ...__VLS_functionalComponentArgsRest(__VLS_80));
    __VLS_82.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (JSON.stringify(__VLS_ctx.resultData, null, 2));
    var __VLS_82;
    var __VLS_78;
}
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            ParsedResultCard: ParsedResultCard,
            QueryResultCard: QueryResultCard,
            question: question,
            loading: loading,
            resultData: resultData,
            fillExample: fillExample,
            openDetail: openDetail,
            openRowDetail: openRowDetail,
            handleQuery: handleQuery,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
