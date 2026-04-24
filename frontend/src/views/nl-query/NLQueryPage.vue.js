import { computed, nextTick, onMounted, ref, watch } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ElMessage } from 'element-plus';
import { fetchNLQuery } from '@/api/logistics';
import QueryResultCard from '@/components/QueryResultCard.vue';
import { buildQueryResultPresentation } from '@/utils/queryResultPresentation';
import { buildNLQuerySessionId, buildNLQuerySessionTitle, getNLQuerySession, saveNLQuerySession, } from '@/utils/nlQuerySessions';
import { clearQueryPageDraft, getQueryPageDraft, saveLastQueryContext, saveQueryPageDraft, } from '@/utils/queryStorage';
const router = useRouter();
const route = useRoute();
const question = ref('');
const loading = ref(false);
const chatItems = ref([]);
const conversationRef = ref(null);
/** 当前路由下激活的自然语言会话 ID。 */
const activeSessionId = computed(() => {
    return typeof route.query.session === 'string' ? route.query.session : '';
});
/** 当前是否已经拿到可展示的自然语言查询结果。 */
const hasResult = computed(() => chatItems.value.length > 0);
/** 填充示例问题，便于快速联调。 */
function fillExample(value) {
    question.value = value;
}
/**
 * 恢复空白页输入草稿。
 * 说明：
 * 1. 只在“新聊天”空白页中恢复未发送的问题；
 * 2. 已进入会话页签后，不再用草稿覆盖真实会话内容。
 */
function restoreDraftQuestion() {
    const draft = getQueryPageDraft('nl-query');
    if (draft?.formData?.question) {
        question.value = String(draft.formData.question);
    }
}
/**
 * 根据当前路由中的会话 ID，同步自然语言页的数据来源。
 * 说明：
 * 1. 没有 session 参数时，视为“新聊天”空白页；
 * 2. 有 session 参数时，只从对应会话里恢复历史问答；
 * 3. 如果会话不存在，自动退回空白页，避免页面卡死在失效链接。
 */
async function syncSessionFromRoute() {
    if (!activeSessionId.value) {
        chatItems.value = [];
        restoreDraftQuestion();
        await nextTick();
        return;
    }
    const session = getNLQuerySession(activeSessionId.value);
    if (!session) {
        ElMessage.warning('当前会话不存在，已返回新聊天页面');
        await router.replace({ path: '/nl-query' });
        return;
    }
    chatItems.value = session.items.map((item) => ({ ...item }));
    question.value = '';
    await nextTick();
    scrollConversationToBottom();
}
/**
 * 将当前会话滚动到底部。
 * 说明：
 * 一旦进入多轮会话模式，只滚动聊天区，不滚动整个页面。
 */
function scrollConversationToBottom() {
    if (!conversationRef.value)
        return;
    conversationRef.value.scrollTop = conversationRef.value.scrollHeight;
}
/**
 * 保存指定问答的最近一次查询上下文，便于从详情页返回时仍能回到自然语言页。
 */
function persistContext(item, selectedRow = null) {
    saveLastQueryContext({
        sourcePage: 'nl-query',
        question: item.question,
        requestPayload: { question: item.question },
        rawResponse: item.response,
        parsed: item.response.parsed ?? null,
        queryResult: item.response.query_result ?? null,
        selectedRow,
    });
}
/**
 * 以当前会话为单位持久化自然语言页签数据。
 * 说明：
 * 1. 只有已经形成真实会话 ID 的页面才会写入会话存储；
 * 2. 标题固定取首问，避免每轮提问导致左侧页签不断跳变。
 */
function persistCurrentSession(sessionId, items) {
    if (!items.length)
        return;
    saveNLQuerySession({
        id: sessionId,
        title: buildNLQuerySessionTitle(items[0].question),
        items,
        updatedAt: items[items.length - 1].answeredAt,
    });
}
/**
 * 打开完整明细页。
 */
function openDetail(item) {
    persistContext(item);
    router.push('/detail-view');
}
/**
 * 打开带有选中行的明细页。
 */
function openRowDetail(item, row) {
    persistContext(item, row);
    router.push('/detail-view');
}
/** 主答案区点击“查看详细结果”时，直接展开补充信息区。 */
function expandDetail(item) {
    item.showAdvancedInfo = true;
    if (activeSessionId.value) {
        persistCurrentSession(activeSessionId.value, chatItems.value);
    }
}
/** 切换单条问答的补充信息展示状态。 */
function toggleAdvancedInfo(item) {
    item.showAdvancedInfo = !item.showAdvancedInfo;
    if (activeSessionId.value) {
        persistCurrentSession(activeSessionId.value, chatItems.value);
    }
}
/**
 * 调用后端自然语言查询接口，并把本轮问答追加到当前会话。
 * 说明：
 * 1. 如果当前还没有会话 ID，首轮成功后再创建会话页签；
 * 2. 后续提问只追加，不覆盖前面的问答；
 * 3. 提问模块始终保留在页面底部，只有聊天区域滚动。
 */
async function handleQuery() {
    const questionText = question.value.trim();
    if (!questionText) {
        ElMessage.warning('请输入查询问题');
        return;
    }
    const askedAt = new Date().toISOString();
    loading.value = true;
    try {
        const resp = await fetchNLQuery({ question: questionText });
        const response = (resp.data ?? resp);
        const answeredAt = new Date().toISOString();
        const item = buildConversationItem(questionText, response, askedAt, answeredAt);
        const nextItems = [...chatItems.value, item];
        const nextSessionId = activeSessionId.value || buildNLQuerySessionId();
        chatItems.value = nextItems;
        persistCurrentSession(nextSessionId, nextItems);
        persistContext(item);
        question.value = '';
        clearQueryPageDraft('nl-query');
        if (!activeSessionId.value) {
            await router.replace({ path: '/nl-query', query: { session: nextSessionId } });
        }
        await nextTick();
        scrollConversationToBottom();
        ElMessage.success('查询成功');
    }
    catch (error) {
        ElMessage.error('查询失败，请稍后重试；如持续失败请联系技术支持');
        throw error;
    }
    finally {
        loading.value = false;
    }
}
/**
 * 持续缓存空白页输入草稿。
 * 说明：
 * 只有在“新聊天”空白页里才缓存草稿，避免覆盖已存在会话。
 */
watch(question, (value) => {
    if (activeSessionId.value)
        return;
    saveQueryPageDraft({
        sourcePage: 'nl-query',
        formData: {
            question: value,
        },
    });
}, { immediate: true });
watch(() => route.query.session, async () => {
    await syncSessionFromRoute();
}, { immediate: true });
onMounted(() => {
    restoreDraftQuestion();
});
/**
 * 将直接回答里出现的数值做最小格式化，避免主答案区直接展示太长原始数字串。
 */
function formatAnswerValue(value) {
    if (typeof value === 'number' && Number.isFinite(value)) {
        return value.toLocaleString();
    }
    if (typeof value === 'string' && value.trim()) {
        const numeric = Number(value);
        if (Number.isFinite(numeric)) {
            return numeric.toLocaleString();
        }
        return value;
    }
    if (value === null || value === undefined || value === '')
        return '-';
    return String(value);
}
/** 将 ISO 时间格式化成 hh:mm:ss，便于自然语言问答区按真实时间展示。 */
function formatDisplayTime(value) {
    const date = new Date(value);
    if (Number.isNaN(date.getTime()))
        return '--:--:--';
    return date.toLocaleTimeString('zh-CN', {
        hour12: false,
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
    });
}
/** 构建单条会话项，确保后续多轮提问不会覆盖前面的结果。 */
function buildConversationItem(questionText, response, askedAt, answeredAt) {
    return {
        id: `nl-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        question: questionText,
        response,
        askedAt,
        answeredAt,
        showAdvancedInfo: false,
    };
}
/** 为指定问答构建统一展示视图，避免多轮问答共享同一份计算结果。 */
function buildPresentation(item) {
    return buildQueryResultPresentation({
        queryResult: item.response.query_result ?? null,
        parsed: item.response.parsed ?? null,
        question: item.question,
        requestPayload: { question: item.question },
        responseMeta: item.response.response_meta ?? null,
    });
}
/** 判断某条问答是否已有可展示的完整查询载荷。 */
function hasDisplayPayload(item) {
    return Boolean(item.response.query_result || item.response.response_meta || item.response.parsed);
}
/** 为指定问答提炼自然语言页主视觉里的直接回答，避免多轮问答互相覆盖。 */
function buildAnswerView(item) {
    const view = buildPresentation(item);
    const summaryEntries = view.summaryEntries;
    if (view.noResultAnalysis) {
        return {
            tone: 'warning',
            statusLabel: '未找到结果',
            title: '当前没有查到符合条件的结果',
            body: view.noResultAnalysis.possible_reasons[0] || '当前条件下没有命中数据。',
            tip: view.noResultAnalysis.suggestions[0] || '建议换一个问题表达或放宽筛选条件后重试。',
        };
    }
    if (view.showCompareSummary) {
        const leftLabel = item.response.query_result?.left_label || '左侧结果';
        const rightLabel = item.response.query_result?.right_label || '右侧结果';
        const leftValue = formatAnswerValue(item.response.query_result?.left_value);
        const rightValue = formatAnswerValue(item.response.query_result?.right_value);
        const diffValue = formatAnswerValue(item.response.query_result?.diff_value);
        return {
            tone: 'success',
            statusLabel: '已完成对比',
            title: `${leftLabel} 与 ${rightLabel} 已完成对比`,
            body: `左侧为 ${leftValue}，右侧为 ${rightValue}，差值为 ${diffValue}。`,
            tip: null,
        };
    }
    if (summaryEntries.length > 0) {
        const primaryEntry = summaryEntries[0];
        const secondaryEntry = summaryEntries[1];
        return {
            tone: 'success',
            statusLabel: '已找到结果',
            title: `${primaryEntry.label}：${formatAnswerValue(primaryEntry.value)}`,
            body: secondaryEntry
                ? `${secondaryEntry.label}：${formatAnswerValue(secondaryEntry.value)}`
                : view.resultExplanation?.summary || '查询已完成。',
            tip: null,
        };
    }
    return {
        tone: view.status.severity === 'warning' ? 'warning' : 'success',
        statusLabel: view.status.success ? '查询完成' : '查询失败',
        title: view.resultExplanation?.summary || view.status.message || '查询已完成',
        body: view.resultExplanation?.highlights[0] || '如需进一步核对，可展开查看详细结果。',
        tip: view.status.success ? null : '请稍后重试；如持续失败，请联系管理员或技术支持。',
    };
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['nl-page']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-page--conversation']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-landing__tips']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-conversation']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-conversation']} */ ;
/** @type {__VLS_StyleScopedClasses['el-textarea__inner']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-query-input']} */ ;
/** @type {__VLS_StyleScopedClasses['el-textarea__inner']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-query-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-example-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-page--conversation']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-conversation']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-query-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-query-actions__submit']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card--question']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card--answer']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card--analysis']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-composer']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "nl-page" },
    ...{ class: ({ 'nl-page--conversation': __VLS_ctx.hasResult }) },
});
if (!__VLS_ctx.hasResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "nl-landing" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "nl-landing__badge" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h2, __VLS_intrinsicElements.h2)({
        ...{ class: "nl-landing__title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "nl-landing__desc" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "nl-landing__note" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "nl-landing__tips" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
}
if (__VLS_ctx.hasResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
        ...{ class: "nl-chat-shell" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ref: "conversationRef",
        ...{ class: "nl-conversation" },
    });
    /** @type {typeof __VLS_ctx.conversationRef} */ ;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "nl-thread" },
    });
    for (const [item] of __VLS_getVForSourceType((__VLS_ctx.chatItems))) {
        (item.id);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-thread__question" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-thread-card nl-thread-card--question" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-thread-card__label" },
        });
        (__VLS_ctx.formatDisplayTime(item.askedAt));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-thread-card__content" },
        });
        (item.question);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-thread__answer" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-thread-card nl-thread-card--answer" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-thread-card__label" },
        });
        (__VLS_ctx.formatDisplayTime(item.answeredAt));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-direct-answer" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-direct-answer__status" },
            ...{ class: (`nl-direct-answer__status--${__VLS_ctx.buildAnswerView(item).tone}`) },
        });
        (__VLS_ctx.buildAnswerView(item).statusLabel);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-direct-answer__title" },
        });
        (__VLS_ctx.buildAnswerView(item).title);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-direct-answer__body" },
        });
        (__VLS_ctx.buildAnswerView(item).body);
        if (__VLS_ctx.buildAnswerView(item).tip) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "nl-direct-answer__tip" },
            });
            (__VLS_ctx.buildAnswerView(item).tip);
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "nl-direct-answer__actions" },
        });
        if (__VLS_ctx.buildPresentation(item).hasItems) {
            const __VLS_0 = {}.ElButton;
            /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
            // @ts-ignore
            const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
                ...{ 'onClick': {} },
                text: true,
                type: "primary",
            }));
            const __VLS_2 = __VLS_1({
                ...{ 'onClick': {} },
                text: true,
                type: "primary",
            }, ...__VLS_functionalComponentArgsRest(__VLS_1));
            let __VLS_4;
            let __VLS_5;
            let __VLS_6;
            const __VLS_7 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.hasResult))
                        return;
                    if (!(__VLS_ctx.buildPresentation(item).hasItems))
                        return;
                    __VLS_ctx.expandDetail(item);
                }
            };
            __VLS_3.slots.default;
            var __VLS_3;
        }
        if (__VLS_ctx.buildPresentation(item).noResultAnalysis || __VLS_ctx.hasDisplayPayload(item)) {
            const __VLS_8 = {}.ElButton;
            /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
            // @ts-ignore
            const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({
                ...{ 'onClick': {} },
                text: true,
            }));
            const __VLS_10 = __VLS_9({
                ...{ 'onClick': {} },
                text: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_9));
            let __VLS_12;
            let __VLS_13;
            let __VLS_14;
            const __VLS_15 = {
                onClick: (...[$event]) => {
                    if (!(__VLS_ctx.hasResult))
                        return;
                    if (!(__VLS_ctx.buildPresentation(item).noResultAnalysis || __VLS_ctx.hasDisplayPayload(item)))
                        return;
                    __VLS_ctx.toggleAdvancedInfo(item);
                }
            };
            __VLS_11.slots.default;
            (item.showAdvancedInfo ? '收起补充信息' : '查看补充信息');
            var __VLS_11;
        }
        if (item.showAdvancedInfo) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "page-card nl-thread-card nl-thread-card--analysis" },
            });
            if (__VLS_ctx.hasDisplayPayload(item)) {
                /** @type {[typeof QueryResultCard, ]} */ ;
                // @ts-ignore
                const __VLS_16 = __VLS_asFunctionalComponent(QueryResultCard, new QueryResultCard({
                    ...{ 'onOpenDetail': {} },
                    ...{ 'onRowDetail': {} },
                    queryResult: (item.response.query_result ?? null),
                    parsed: (item.response.parsed ?? null),
                    question: (item.question),
                    requestPayload: ({ question: item.question }),
                    responseMeta: (item.response.response_meta ?? null),
                    showTemplateInfo: (false),
                }));
                const __VLS_17 = __VLS_16({
                    ...{ 'onOpenDetail': {} },
                    ...{ 'onRowDetail': {} },
                    queryResult: (item.response.query_result ?? null),
                    parsed: (item.response.parsed ?? null),
                    question: (item.question),
                    requestPayload: ({ question: item.question }),
                    responseMeta: (item.response.response_meta ?? null),
                    showTemplateInfo: (false),
                }, ...__VLS_functionalComponentArgsRest(__VLS_16));
                let __VLS_19;
                let __VLS_20;
                let __VLS_21;
                const __VLS_22 = {
                    onOpenDetail: (...[$event]) => {
                        if (!(__VLS_ctx.hasResult))
                            return;
                        if (!(item.showAdvancedInfo))
                            return;
                        if (!(__VLS_ctx.hasDisplayPayload(item)))
                            return;
                        __VLS_ctx.openDetail(item);
                    }
                };
                const __VLS_23 = {
                    onRowDetail: (...[$event]) => {
                        if (!(__VLS_ctx.hasResult))
                            return;
                        if (!(item.showAdvancedInfo))
                            return;
                        if (!(__VLS_ctx.hasDisplayPayload(item)))
                            return;
                        __VLS_ctx.openRowDetail(item, $event);
                    }
                };
                var __VLS_18;
            }
        }
    }
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
    ...{ class: "page-card nl-composer" },
    ...{ class: ({ 'nl-composer--conversation': __VLS_ctx.hasResult }) },
});
const __VLS_24 = {}.ElForm;
/** @type {[typeof __VLS_components.ElForm, typeof __VLS_components.elForm, typeof __VLS_components.ElForm, typeof __VLS_components.elForm, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    ...{ 'onSubmit': {} },
    ...{ class: "nl-query-form" },
}));
const __VLS_26 = __VLS_25({
    ...{ 'onSubmit': {} },
    ...{ class: "nl-query-form" },
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
let __VLS_28;
let __VLS_29;
let __VLS_30;
const __VLS_31 = {
    onSubmit: () => { }
};
__VLS_27.slots.default;
const __VLS_32 = {}.ElFormItem;
/** @type {[typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, typeof __VLS_components.ElFormItem, typeof __VLS_components.elFormItem, ]} */ ;
// @ts-ignore
const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
    label: "",
}));
const __VLS_34 = __VLS_33({
    label: "",
}, ...__VLS_functionalComponentArgsRest(__VLS_33));
__VLS_35.slots.default;
const __VLS_36 = {}.ElInput;
/** @type {[typeof __VLS_components.ElInput, typeof __VLS_components.elInput, ]} */ ;
// @ts-ignore
const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
    ...{ 'onKeydown': {} },
    modelValue: (__VLS_ctx.question),
    ...{ class: "nl-query-input" },
    ...{ class: ({ 'nl-query-input--conversation': __VLS_ctx.hasResult }) },
    type: "textarea",
    rows: (__VLS_ctx.hasResult ? 1 : 3),
    resize: "none",
    placeholder: "有问题，尽管问。例如：2025年3月运量是多少；25年3月和26年3月发货量对比；合同编号 GCL5010ZJ202503015 的明细",
}));
const __VLS_38 = __VLS_37({
    ...{ 'onKeydown': {} },
    modelValue: (__VLS_ctx.question),
    ...{ class: "nl-query-input" },
    ...{ class: ({ 'nl-query-input--conversation': __VLS_ctx.hasResult }) },
    type: "textarea",
    rows: (__VLS_ctx.hasResult ? 1 : 3),
    resize: "none",
    placeholder: "有问题，尽管问。例如：2025年3月运量是多少；25年3月和26年3月发货量对比；合同编号 GCL5010ZJ202503015 的明细",
}, ...__VLS_functionalComponentArgsRest(__VLS_37));
let __VLS_40;
let __VLS_41;
let __VLS_42;
const __VLS_43 = {
    onKeydown: (__VLS_ctx.handleQuery)
};
var __VLS_39;
var __VLS_35;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "nl-query-actions" },
    ...{ class: ({ 'nl-query-actions--conversation': __VLS_ctx.hasResult }) },
});
if (!__VLS_ctx.hasResult) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "nl-example-list" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(!__VLS_ctx.hasResult))
                    return;
                __VLS_ctx.fillExample('2025年3月运量是多少');
            } },
        type: "button",
        ...{ class: "nl-example-chip" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(!__VLS_ctx.hasResult))
                    return;
                __VLS_ctx.fillExample('25年3月和26年3月发货量对比');
            } },
        type: "button",
        ...{ class: "nl-example-chip" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(!__VLS_ctx.hasResult))
                    return;
                __VLS_ctx.fillExample('合同编号GCL5010ZJ202503015的明细');
            } },
        type: "button",
        ...{ class: "nl-example-chip" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "nl-query-actions__submit" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "nl-query-actions__hint" },
});
(__VLS_ctx.hasResult ? '修改问题后可继续提问。' : '如不确定输入方式，可直接点击示例问题。');
const __VLS_44 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
    ...{ 'onClick': {} },
    type: "primary",
    size: "large",
    loading: (__VLS_ctx.loading),
}));
const __VLS_46 = __VLS_45({
    ...{ 'onClick': {} },
    type: "primary",
    size: "large",
    loading: (__VLS_ctx.loading),
}, ...__VLS_functionalComponentArgsRest(__VLS_45));
let __VLS_48;
let __VLS_49;
let __VLS_50;
const __VLS_51 = {
    onClick: (__VLS_ctx.handleQuery)
};
__VLS_47.slots.default;
var __VLS_47;
var __VLS_27;
/** @type {__VLS_StyleScopedClasses['nl-page']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-landing']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-landing__badge']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-landing__title']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-landing__desc']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-landing__note']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-landing__tips']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-chat-shell']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-conversation']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread__question']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card--question']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card__label']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card__content']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread__answer']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card--answer']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card__label']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-direct-answer']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-direct-answer__status']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-direct-answer__title']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-direct-answer__body']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-direct-answer__tip']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-direct-answer__actions']} */ ;
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-thread-card--analysis']} */ ;
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-composer']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-query-form']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-query-input']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-query-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-example-list']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-example-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-example-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-example-chip']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-query-actions__submit']} */ ;
/** @type {__VLS_StyleScopedClasses['nl-query-actions__hint']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            QueryResultCard: QueryResultCard,
            question: question,
            loading: loading,
            chatItems: chatItems,
            conversationRef: conversationRef,
            hasResult: hasResult,
            fillExample: fillExample,
            openDetail: openDetail,
            openRowDetail: openRowDetail,
            expandDetail: expandDetail,
            toggleAdvancedInfo: toggleAdvancedInfo,
            handleQuery: handleQuery,
            formatDisplayTime: formatDisplayTime,
            buildPresentation: buildPresentation,
            hasDisplayPayload: hasDisplayPayload,
            buildAnswerView: buildAnswerView,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
