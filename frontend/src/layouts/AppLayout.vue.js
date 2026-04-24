import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import { ElMessage, ElMessageBox } from 'element-plus';
import { ChatDotRound, DataBoard, Files, MoreFilled, Plus, Search, Tickets, Timer } from '@element-plus/icons-vue';
import { useRoute, useRouter } from 'vue-router';
import brandLogoUrl from '@/assets/gcl-logo.svg';
import { buildLogisticsDataQaSessionId, getLogisticsDataQaSessionEventName, listLogisticsDataQaSessions, removeLogisticsDataQaSession, renameLogisticsDataQaSession, saveLogisticsDataQaSession, } from '@/utils/logisticsDataQaSessions';
const route = useRoute();
const router = useRouter();
const isAsideCollapsed = ref(false);
const qaSessionSummaries = ref([]);
const APP_SHELL_SIDEBAR_TOGGLE_EVENT = 'app-shell:toggle-sidebar';
/** 侧边栏品牌标题固定为业务系统口径，避免继续透出“智能助手”等技术化旧名称。 */
const appTitle = '协鑫集成';
/**
 * 当前左侧主菜单宽度。
 * 说明：
 * 折叠后只保留图标入口，避免正文区被压缩得太碎。
 */
const asideWidth = computed(() => (isAsideCollapsed.value ? '84px' : '236px'));
/** 当前激活菜单。 */
const activePath = computed(() => {
    if (route.path.startsWith('/logistics/data-qa/history'))
        return '/logistics/data-qa/history';
    if (route.path.startsWith('/logistics/data-qa'))
        return '/logistics/data-qa';
    return route.path;
});
/** 条件查询父菜单和物流数据问答父菜单在对应场景下默认展开。 */
const openedMenus = computed(() => {
    if (isAsideCollapsed.value) {
        return [];
    }
    const menus = [];
    if (route.path.startsWith('/logistics/data-qa')) {
        menus.push('logistics-data-qa-group');
    }
    if (route.path === '/structured-query' || route.path.startsWith('/plan-bom/')) {
        menus.push('query-group');
    }
    return menus;
});
/**
 * 物流数据问答相关页面使用页内自己的头部与工具栏。
 * 说明：
 * 为了避免出现“系统页头 + 页面页头”重复堆叠，这里对 data-qa 路由隐藏外层页头。
 */
const hideHeader = computed(() => route.path.startsWith('/logistics/data-qa'));
/**
 * 顶部标题按当前路由切换。
 * 说明：
 * 物流页继续保留原有描述，BOM 页面单独给出当前 MVP 边界，避免页头误导。
 */
const headerMeta = computed(() => {
    if (route.path.startsWith('/logistics/data-qa/history')) {
        return {
            title: '查询历史记录',
            description: '查看过去问过的问题和保存下来的结果快照，适合回看、核对与继续导出。',
        };
    }
    if (route.path.startsWith('/logistics/data-qa')) {
        return {
            title: '自然语言问答',
            description: '像持续对话一样提问、查看结果、回看历史并导出内容。当前已正式接入物流数据问答能力。',
        };
    }
    if (route.path.startsWith('/nl-query')) {
        return {
            title: '自然语言查询',
            description: '像对话一样输入业务问题，系统会自动解析条件并返回查询结果。当前已开通物流问答能力，BOM 自然语言问答后续接入。',
        };
    }
    if (route.path.startsWith('/structured-query')) {
        return {
            title: '物流条件查询',
            description: '按时间、客户、物流公司等条件筛选物流结果，适合日常统计核对和条件筛查。',
        };
    }
    if (route.path.startsWith('/plan-bom')) {
        return {
            title: '计划 BOM 明细查询',
            description: '按订单号、评审号或订单名称查看命中版本和核心材料明细，适合业务查询、结果核对和汇报展示。',
        };
    }
    return {
        title: '经营计划查询系统',
        description: '用于查看经营计划相关查询结果，强调查询清晰、结果易读、便于业务使用。',
    };
});
/**
 * 刷新自然语言问答会话摘要。
 * 说明：
 * 左侧主菜单直接复用当前页已有的本地会话能力，不额外新造会话系统。
 */
function refreshQaSessions() {
    qaSessionSummaries.value = listLogisticsDataQaSessions();
}
/**
 * 判断某条会话是否为当前激活会话。
 */
function isQaSessionActive(sessionId) {
    return route.path.startsWith('/logistics/data-qa') && route.query.session === sessionId;
}
/**
 * 进入自然语言问答正式页。
 */
function goDataQaPage() {
    const activeSessionId = typeof route.query.session === 'string' ? route.query.session : '';
    router.push({
        path: '/logistics/data-qa',
        query: activeSessionId ? { session: activeSessionId } : undefined,
    });
}
/**
 * 从主菜单创建新会话。
 * 说明：
 * 新建按钮放在“发起查询”右侧，满足业务上“查新问题”的直接入口习惯。
 */
function createQaSession() {
    const sessionId = buildLogisticsDataQaSessionId();
    saveLogisticsDataQaSession({
        id: sessionId,
        title: '新建对话',
        preview: '等待开始新的业务问题',
        updatedAt: new Date().toISOString(),
        items: [],
    });
    refreshQaSessions();
    router.push({
        path: '/logistics/data-qa',
        query: { session: sessionId },
    });
}
/**
 * 打开指定会话。
 */
function openQaSession(sessionId) {
    router.push({
        path: '/logistics/data-qa',
        query: { session: sessionId },
    });
}
/**
 * 处理会话操作命令。
 */
function handleQaSessionCommand(session, command) {
    if (command === 'rename') {
        renameQaSession(session);
        return;
    }
    if (command === 'delete') {
        deleteQaSession(session);
    }
}
/**
 * 重命名菜单中的会话。
 */
async function renameQaSession(session) {
    try {
        const { value } = await ElMessageBox.prompt('请输入新的会话标题', '重命名会话', {
            inputValue: session.title,
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            inputPlaceholder: '例如：2026年1月发运量',
        });
        const title = String(value || '').trim();
        if (!title) {
            ElMessage.warning('请输入有效的会话标题。');
            return;
        }
        renameLogisticsDataQaSession(session.id, title);
        refreshQaSessions();
        ElMessage.success('会话标题已更新。');
    }
    catch (_error) {
        // 用户主动取消时不提示。
    }
}
/**
 * 删除菜单中的会话。
 */
async function deleteQaSession(session) {
    try {
        await ElMessageBox.confirm('删除后，这个会话在当前浏览器会话中将无法继续查看。是否继续？', '删除会话', {
            confirmButtonText: '删除',
            cancelButtonText: '取消',
            type: 'warning',
        });
    }
    catch (_error) {
        return;
    }
    removeLogisticsDataQaSession(session.id);
    refreshQaSessions();
    const nextSessionId = qaSessionSummaries.value[0]?.id;
    if (isQaSessionActive(session.id)) {
        if (nextSessionId) {
            router.replace({
                path: '/logistics/data-qa',
                query: { session: nextSessionId },
            });
        }
        else {
            router.replace('/logistics/data-qa');
        }
    }
    ElMessage.success('会话已删除。');
}
/**
 * 响应正文区的主菜单缩进按钮。
 * 说明：
 * 当前页内的折叠按钮只负责左侧主菜单，不再作用于页内独立模块。
 */
function handleSidebarToggle() {
    isAsideCollapsed.value = !isAsideCollapsed.value;
}
onMounted(() => {
    refreshQaSessions();
    window.addEventListener(getLogisticsDataQaSessionEventName(), refreshQaSessions);
    window.addEventListener(APP_SHELL_SIDEBAR_TOGGLE_EVENT, handleSidebarToggle);
});
onBeforeUnmount(() => {
    window.removeEventListener(getLogisticsDataQaSessionEventName(), refreshQaSessions);
    window.removeEventListener(APP_SHELL_SIDEBAR_TOGGLE_EVENT, handleSidebarToggle);
});
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-menu-item']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-menu-item']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-menu-item']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-sub-menu__title']} */ ;
/** @type {__VLS_StyleScopedClasses['el-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-sub-menu__title']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-sub-menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-menu-item']} */ ;
/** @type {__VLS_StyleScopedClasses['qa-menu-launch__main']} */ ;
/** @type {__VLS_StyleScopedClasses['qa-session-item']} */ ;
/** @type {__VLS_StyleScopedClasses['app-shell']} */ ;
/** @type {__VLS_StyleScopedClasses['aside']} */ ;
/** @type {__VLS_StyleScopedClasses['aside--collapsed']} */ ;
/** @type {__VLS_StyleScopedClasses['header-title']} */ ;
/** @type {__VLS_StyleScopedClasses['app-shell']} */ ;
/** @type {__VLS_StyleScopedClasses['aside']} */ ;
/** @type {__VLS_StyleScopedClasses['aside--collapsed']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-sub-menu__title']} */ ;
/** @type {__VLS_StyleScopedClasses['aside--collapsed']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-menu-item']} */ ;
/** @type {__VLS_StyleScopedClasses['aside--collapsed']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-sub-menu__title']} */ ;
/** @type {__VLS_StyleScopedClasses['aside--collapsed']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-menu-item']} */ ;
/** @type {__VLS_StyleScopedClasses['aside--collapsed']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-sub-menu__title']} */ ;
/** @type {__VLS_StyleScopedClasses['el-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['aside--collapsed']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['el-menu-item']} */ ;
/** @type {__VLS_StyleScopedClasses['el-icon']} */ ;
// CSS variable injection 
// CSS variable injection end 
const __VLS_0 = {}.ElContainer;
/** @type {[typeof __VLS_components.ElContainer, typeof __VLS_components.elContainer, typeof __VLS_components.ElContainer, typeof __VLS_components.elContainer, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    ...{ class: "app-shell" },
}));
const __VLS_2 = __VLS_1({
    ...{ class: "app-shell" },
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
var __VLS_4 = {};
__VLS_3.slots.default;
const __VLS_5 = {}.ElAside;
/** @type {[typeof __VLS_components.ElAside, typeof __VLS_components.elAside, typeof __VLS_components.ElAside, typeof __VLS_components.elAside, ]} */ ;
// @ts-ignore
const __VLS_6 = __VLS_asFunctionalComponent(__VLS_5, new __VLS_5({
    width: (__VLS_ctx.asideWidth),
    ...{ class: (['aside', { 'aside--collapsed': __VLS_ctx.isAsideCollapsed }]) },
}));
const __VLS_7 = __VLS_6({
    width: (__VLS_ctx.asideWidth),
    ...{ class: (['aside', { 'aside--collapsed': __VLS_ctx.isAsideCollapsed }]) },
}, ...__VLS_functionalComponentArgsRest(__VLS_6));
__VLS_8.slots.default;
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "logo-card" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "logo-mark" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.img)({
    src: (__VLS_ctx.brandLogoUrl),
    alt: "协鑫集成标识",
    ...{ class: "logo-mark__image" },
});
if (!__VLS_ctx.isAsideCollapsed) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "logo-copy" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "logo-title" },
    });
    (__VLS_ctx.appTitle);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "logo-subtitle" },
    });
}
const __VLS_9 = {}.ElMenu;
/** @type {[typeof __VLS_components.ElMenu, typeof __VLS_components.elMenu, typeof __VLS_components.ElMenu, typeof __VLS_components.elMenu, ]} */ ;
// @ts-ignore
const __VLS_10 = __VLS_asFunctionalComponent(__VLS_9, new __VLS_9({
    defaultActive: (__VLS_ctx.activePath),
    defaultOpeneds: (__VLS_ctx.openedMenus),
    router: true,
    ...{ class: "menu" },
}));
const __VLS_11 = __VLS_10({
    defaultActive: (__VLS_ctx.activePath),
    defaultOpeneds: (__VLS_ctx.openedMenus),
    router: true,
    ...{ class: "menu" },
}, ...__VLS_functionalComponentArgsRest(__VLS_10));
__VLS_12.slots.default;
const __VLS_13 = {}.ElSubMenu;
/** @type {[typeof __VLS_components.ElSubMenu, typeof __VLS_components.elSubMenu, typeof __VLS_components.ElSubMenu, typeof __VLS_components.elSubMenu, ]} */ ;
// @ts-ignore
const __VLS_14 = __VLS_asFunctionalComponent(__VLS_13, new __VLS_13({
    index: "logistics-data-qa-group",
}));
const __VLS_15 = __VLS_14({
    index: "logistics-data-qa-group",
}, ...__VLS_functionalComponentArgsRest(__VLS_14));
__VLS_16.slots.default;
{
    const { title: __VLS_thisSlot } = __VLS_16.slots;
    const __VLS_17 = {}.ElIcon;
    /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
    // @ts-ignore
    const __VLS_18 = __VLS_asFunctionalComponent(__VLS_17, new __VLS_17({}));
    const __VLS_19 = __VLS_18({}, ...__VLS_functionalComponentArgsRest(__VLS_18));
    __VLS_20.slots.default;
    const __VLS_21 = {}.ChatDotRound;
    /** @type {[typeof __VLS_components.ChatDotRound, ]} */ ;
    // @ts-ignore
    const __VLS_22 = __VLS_asFunctionalComponent(__VLS_21, new __VLS_21({}));
    const __VLS_23 = __VLS_22({}, ...__VLS_functionalComponentArgsRest(__VLS_22));
    var __VLS_20;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "qa-menu-launch" },
    ...{ class: ({ 'qa-menu-launch--active': __VLS_ctx.route.path.startsWith('/logistics/data-qa') && !__VLS_ctx.route.path.startsWith('/logistics/data-qa/history') }) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
    ...{ onClick: (__VLS_ctx.goDataQaPage) },
    type: "button",
    ...{ class: "qa-menu-launch__main" },
});
const __VLS_25 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_26 = __VLS_asFunctionalComponent(__VLS_25, new __VLS_25({}));
const __VLS_27 = __VLS_26({}, ...__VLS_functionalComponentArgsRest(__VLS_26));
__VLS_28.slots.default;
const __VLS_29 = {}.ChatDotRound;
/** @type {[typeof __VLS_components.ChatDotRound, ]} */ ;
// @ts-ignore
const __VLS_30 = __VLS_asFunctionalComponent(__VLS_29, new __VLS_29({}));
const __VLS_31 = __VLS_30({}, ...__VLS_functionalComponentArgsRest(__VLS_30));
var __VLS_28;
if (!__VLS_ctx.isAsideCollapsed) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
}
if (!__VLS_ctx.isAsideCollapsed) {
    const __VLS_33 = {}.ElButton;
    /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
    // @ts-ignore
    const __VLS_34 = __VLS_asFunctionalComponent(__VLS_33, new __VLS_33({
        ...{ 'onClick': {} },
        text: true,
        circle: true,
        ...{ class: "qa-menu-launch__create" },
        title: "新建会话",
    }));
    const __VLS_35 = __VLS_34({
        ...{ 'onClick': {} },
        text: true,
        circle: true,
        ...{ class: "qa-menu-launch__create" },
        title: "新建会话",
    }, ...__VLS_functionalComponentArgsRest(__VLS_34));
    let __VLS_37;
    let __VLS_38;
    let __VLS_39;
    const __VLS_40 = {
        onClick: (__VLS_ctx.createQaSession)
    };
    __VLS_36.slots.default;
    const __VLS_41 = {}.ElIcon;
    /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
    // @ts-ignore
    const __VLS_42 = __VLS_asFunctionalComponent(__VLS_41, new __VLS_41({}));
    const __VLS_43 = __VLS_42({}, ...__VLS_functionalComponentArgsRest(__VLS_42));
    __VLS_44.slots.default;
    const __VLS_45 = {}.Plus;
    /** @type {[typeof __VLS_components.Plus, ]} */ ;
    // @ts-ignore
    const __VLS_46 = __VLS_asFunctionalComponent(__VLS_45, new __VLS_45({}));
    const __VLS_47 = __VLS_46({}, ...__VLS_functionalComponentArgsRest(__VLS_46));
    var __VLS_44;
    var __VLS_36;
}
if (!__VLS_ctx.isAsideCollapsed && __VLS_ctx.qaSessionSummaries.length) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "qa-session-list" },
    });
    for (const [session] of __VLS_getVForSourceType((__VLS_ctx.qaSessionSummaries))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(!__VLS_ctx.isAsideCollapsed && __VLS_ctx.qaSessionSummaries.length))
                        return;
                    __VLS_ctx.openQaSession(session.id);
                } },
            key: (session.id),
            type: "button",
            ...{ class: "qa-session-item" },
            ...{ class: ({ 'qa-session-item--active': __VLS_ctx.isQaSessionActive(session.id) }) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "qa-session-item__copy" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "qa-session-item__title" },
        });
        (session.title);
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "qa-session-item__preview" },
        });
        (session.preview);
        if (__VLS_ctx.isQaSessionActive(session.id)) {
            const __VLS_49 = {}.ElDropdown;
            /** @type {[typeof __VLS_components.ElDropdown, typeof __VLS_components.elDropdown, typeof __VLS_components.ElDropdown, typeof __VLS_components.elDropdown, ]} */ ;
            // @ts-ignore
            const __VLS_50 = __VLS_asFunctionalComponent(__VLS_49, new __VLS_49({
                ...{ 'onCommand': {} },
                trigger: "click",
            }));
            const __VLS_51 = __VLS_50({
                ...{ 'onCommand': {} },
                trigger: "click",
            }, ...__VLS_functionalComponentArgsRest(__VLS_50));
            let __VLS_53;
            let __VLS_54;
            let __VLS_55;
            const __VLS_56 = {
                onCommand: (...[$event]) => {
                    if (!(!__VLS_ctx.isAsideCollapsed && __VLS_ctx.qaSessionSummaries.length))
                        return;
                    if (!(__VLS_ctx.isQaSessionActive(session.id)))
                        return;
                    __VLS_ctx.handleQaSessionCommand(session, $event);
                }
            };
            __VLS_52.slots.default;
            const __VLS_57 = {}.ElButton;
            /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
            // @ts-ignore
            const __VLS_58 = __VLS_asFunctionalComponent(__VLS_57, new __VLS_57({
                ...{ 'onClick': {} },
                text: true,
                ...{ class: "qa-session-item__menu" },
            }));
            const __VLS_59 = __VLS_58({
                ...{ 'onClick': {} },
                text: true,
                ...{ class: "qa-session-item__menu" },
            }, ...__VLS_functionalComponentArgsRest(__VLS_58));
            let __VLS_61;
            let __VLS_62;
            let __VLS_63;
            const __VLS_64 = {
                onClick: () => { }
            };
            __VLS_60.slots.default;
            const __VLS_65 = {}.ElIcon;
            /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
            // @ts-ignore
            const __VLS_66 = __VLS_asFunctionalComponent(__VLS_65, new __VLS_65({}));
            const __VLS_67 = __VLS_66({}, ...__VLS_functionalComponentArgsRest(__VLS_66));
            __VLS_68.slots.default;
            const __VLS_69 = {}.MoreFilled;
            /** @type {[typeof __VLS_components.MoreFilled, ]} */ ;
            // @ts-ignore
            const __VLS_70 = __VLS_asFunctionalComponent(__VLS_69, new __VLS_69({}));
            const __VLS_71 = __VLS_70({}, ...__VLS_functionalComponentArgsRest(__VLS_70));
            var __VLS_68;
            var __VLS_60;
            {
                const { dropdown: __VLS_thisSlot } = __VLS_52.slots;
                const __VLS_73 = {}.ElDropdownMenu;
                /** @type {[typeof __VLS_components.ElDropdownMenu, typeof __VLS_components.elDropdownMenu, typeof __VLS_components.ElDropdownMenu, typeof __VLS_components.elDropdownMenu, ]} */ ;
                // @ts-ignore
                const __VLS_74 = __VLS_asFunctionalComponent(__VLS_73, new __VLS_73({}));
                const __VLS_75 = __VLS_74({}, ...__VLS_functionalComponentArgsRest(__VLS_74));
                __VLS_76.slots.default;
                const __VLS_77 = {}.ElDropdownItem;
                /** @type {[typeof __VLS_components.ElDropdownItem, typeof __VLS_components.elDropdownItem, typeof __VLS_components.ElDropdownItem, typeof __VLS_components.elDropdownItem, ]} */ ;
                // @ts-ignore
                const __VLS_78 = __VLS_asFunctionalComponent(__VLS_77, new __VLS_77({
                    command: "rename",
                }));
                const __VLS_79 = __VLS_78({
                    command: "rename",
                }, ...__VLS_functionalComponentArgsRest(__VLS_78));
                __VLS_80.slots.default;
                var __VLS_80;
                const __VLS_81 = {}.ElDropdownItem;
                /** @type {[typeof __VLS_components.ElDropdownItem, typeof __VLS_components.elDropdownItem, typeof __VLS_components.ElDropdownItem, typeof __VLS_components.elDropdownItem, ]} */ ;
                // @ts-ignore
                const __VLS_82 = __VLS_asFunctionalComponent(__VLS_81, new __VLS_81({
                    command: "delete",
                }));
                const __VLS_83 = __VLS_82({
                    command: "delete",
                }, ...__VLS_functionalComponentArgsRest(__VLS_82));
                __VLS_84.slots.default;
                var __VLS_84;
                var __VLS_76;
            }
            var __VLS_52;
        }
    }
}
const __VLS_85 = {}.ElMenuItem;
/** @type {[typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, ]} */ ;
// @ts-ignore
const __VLS_86 = __VLS_asFunctionalComponent(__VLS_85, new __VLS_85({
    index: "/logistics/data-qa/history",
}));
const __VLS_87 = __VLS_86({
    index: "/logistics/data-qa/history",
}, ...__VLS_functionalComponentArgsRest(__VLS_86));
__VLS_88.slots.default;
const __VLS_89 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_90 = __VLS_asFunctionalComponent(__VLS_89, new __VLS_89({}));
const __VLS_91 = __VLS_90({}, ...__VLS_functionalComponentArgsRest(__VLS_90));
__VLS_92.slots.default;
const __VLS_93 = {}.Timer;
/** @type {[typeof __VLS_components.Timer, ]} */ ;
// @ts-ignore
const __VLS_94 = __VLS_asFunctionalComponent(__VLS_93, new __VLS_93({}));
const __VLS_95 = __VLS_94({}, ...__VLS_functionalComponentArgsRest(__VLS_94));
var __VLS_92;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
(__VLS_ctx.isAsideCollapsed ? '历史' : '查询历史');
var __VLS_88;
var __VLS_16;
const __VLS_97 = {}.ElSubMenu;
/** @type {[typeof __VLS_components.ElSubMenu, typeof __VLS_components.elSubMenu, typeof __VLS_components.ElSubMenu, typeof __VLS_components.elSubMenu, ]} */ ;
// @ts-ignore
const __VLS_98 = __VLS_asFunctionalComponent(__VLS_97, new __VLS_97({
    index: "query-group",
}));
const __VLS_99 = __VLS_98({
    index: "query-group",
}, ...__VLS_functionalComponentArgsRest(__VLS_98));
__VLS_100.slots.default;
{
    const { title: __VLS_thisSlot } = __VLS_100.slots;
    const __VLS_101 = {}.ElIcon;
    /** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
    // @ts-ignore
    const __VLS_102 = __VLS_asFunctionalComponent(__VLS_101, new __VLS_101({}));
    const __VLS_103 = __VLS_102({}, ...__VLS_functionalComponentArgsRest(__VLS_102));
    __VLS_104.slots.default;
    const __VLS_105 = {}.Search;
    /** @type {[typeof __VLS_components.Search, ]} */ ;
    // @ts-ignore
    const __VLS_106 = __VLS_asFunctionalComponent(__VLS_105, new __VLS_105({}));
    const __VLS_107 = __VLS_106({}, ...__VLS_functionalComponentArgsRest(__VLS_106));
    var __VLS_104;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
}
const __VLS_109 = {}.ElMenuItem;
/** @type {[typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, ]} */ ;
// @ts-ignore
const __VLS_110 = __VLS_asFunctionalComponent(__VLS_109, new __VLS_109({
    index: "/structured-query",
}));
const __VLS_111 = __VLS_110({
    index: "/structured-query",
}, ...__VLS_functionalComponentArgsRest(__VLS_110));
__VLS_112.slots.default;
const __VLS_113 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_114 = __VLS_asFunctionalComponent(__VLS_113, new __VLS_113({}));
const __VLS_115 = __VLS_114({}, ...__VLS_functionalComponentArgsRest(__VLS_114));
__VLS_116.slots.default;
const __VLS_117 = {}.DataBoard;
/** @type {[typeof __VLS_components.DataBoard, ]} */ ;
// @ts-ignore
const __VLS_118 = __VLS_asFunctionalComponent(__VLS_117, new __VLS_117({}));
const __VLS_119 = __VLS_118({}, ...__VLS_functionalComponentArgsRest(__VLS_118));
var __VLS_116;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
var __VLS_112;
const __VLS_121 = {}.ElMenuItem;
/** @type {[typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, ]} */ ;
// @ts-ignore
const __VLS_122 = __VLS_asFunctionalComponent(__VLS_121, new __VLS_121({
    index: "/plan-bom/detail-query",
}));
const __VLS_123 = __VLS_122({
    index: "/plan-bom/detail-query",
}, ...__VLS_functionalComponentArgsRest(__VLS_122));
__VLS_124.slots.default;
const __VLS_125 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_126 = __VLS_asFunctionalComponent(__VLS_125, new __VLS_125({}));
const __VLS_127 = __VLS_126({}, ...__VLS_functionalComponentArgsRest(__VLS_126));
__VLS_128.slots.default;
const __VLS_129 = {}.Files;
/** @type {[typeof __VLS_components.Files, ]} */ ;
// @ts-ignore
const __VLS_130 = __VLS_asFunctionalComponent(__VLS_129, new __VLS_129({}));
const __VLS_131 = __VLS_130({}, ...__VLS_functionalComponentArgsRest(__VLS_130));
var __VLS_128;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
var __VLS_124;
var __VLS_100;
const __VLS_133 = {}.ElMenuItem;
/** @type {[typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, ]} */ ;
// @ts-ignore
const __VLS_134 = __VLS_asFunctionalComponent(__VLS_133, new __VLS_133({
    index: "/tasks",
}));
const __VLS_135 = __VLS_134({
    index: "/tasks",
}, ...__VLS_functionalComponentArgsRest(__VLS_134));
__VLS_136.slots.default;
const __VLS_137 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_138 = __VLS_asFunctionalComponent(__VLS_137, new __VLS_137({}));
const __VLS_139 = __VLS_138({}, ...__VLS_functionalComponentArgsRest(__VLS_138));
__VLS_140.slots.default;
const __VLS_141 = {}.Tickets;
/** @type {[typeof __VLS_components.Tickets, ]} */ ;
// @ts-ignore
const __VLS_142 = __VLS_asFunctionalComponent(__VLS_141, new __VLS_141({}));
const __VLS_143 = __VLS_142({}, ...__VLS_functionalComponentArgsRest(__VLS_142));
var __VLS_140;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
var __VLS_136;
const __VLS_145 = {}.ElMenuItem;
/** @type {[typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, typeof __VLS_components.ElMenuItem, typeof __VLS_components.elMenuItem, ]} */ ;
// @ts-ignore
const __VLS_146 = __VLS_asFunctionalComponent(__VLS_145, new __VLS_145({
    index: "/history",
}));
const __VLS_147 = __VLS_146({
    index: "/history",
}, ...__VLS_functionalComponentArgsRest(__VLS_146));
__VLS_148.slots.default;
const __VLS_149 = {}.ElIcon;
/** @type {[typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, typeof __VLS_components.ElIcon, typeof __VLS_components.elIcon, ]} */ ;
// @ts-ignore
const __VLS_150 = __VLS_asFunctionalComponent(__VLS_149, new __VLS_149({}));
const __VLS_151 = __VLS_150({}, ...__VLS_functionalComponentArgsRest(__VLS_150));
__VLS_152.slots.default;
const __VLS_153 = {}.Timer;
/** @type {[typeof __VLS_components.Timer, ]} */ ;
// @ts-ignore
const __VLS_154 = __VLS_asFunctionalComponent(__VLS_153, new __VLS_153({}));
const __VLS_155 = __VLS_154({}, ...__VLS_functionalComponentArgsRest(__VLS_154));
var __VLS_152;
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({});
var __VLS_148;
var __VLS_12;
if (!__VLS_ctx.isAsideCollapsed) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "aside-footnote" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "aside-footnote__title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "aside-footnote__desc" },
    });
}
var __VLS_8;
const __VLS_157 = {}.ElContainer;
/** @type {[typeof __VLS_components.ElContainer, typeof __VLS_components.elContainer, typeof __VLS_components.ElContainer, typeof __VLS_components.elContainer, ]} */ ;
// @ts-ignore
const __VLS_158 = __VLS_asFunctionalComponent(__VLS_157, new __VLS_157({
    ...{ class: "content-shell" },
}));
const __VLS_159 = __VLS_158({
    ...{ class: "content-shell" },
}, ...__VLS_functionalComponentArgsRest(__VLS_158));
__VLS_160.slots.default;
if (!__VLS_ctx.hideHeader) {
    const __VLS_161 = {}.ElHeader;
    /** @type {[typeof __VLS_components.ElHeader, typeof __VLS_components.elHeader, typeof __VLS_components.ElHeader, typeof __VLS_components.elHeader, ]} */ ;
    // @ts-ignore
    const __VLS_162 = __VLS_asFunctionalComponent(__VLS_161, new __VLS_161({
        ...{ class: "header" },
    }));
    const __VLS_163 = __VLS_162({
        ...{ class: "header" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_162));
    __VLS_164.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "header-left" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "header-title" },
    });
    (__VLS_ctx.headerMeta.title);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "header-desc" },
    });
    (__VLS_ctx.headerMeta.description);
    var __VLS_164;
}
const __VLS_165 = {}.ElMain;
/** @type {[typeof __VLS_components.ElMain, typeof __VLS_components.elMain, typeof __VLS_components.ElMain, typeof __VLS_components.elMain, ]} */ ;
// @ts-ignore
const __VLS_166 = __VLS_asFunctionalComponent(__VLS_165, new __VLS_165({
    ...{ class: (['main', { 'main--immersive': __VLS_ctx.hideHeader }]) },
}));
const __VLS_167 = __VLS_166({
    ...{ class: (['main', { 'main--immersive': __VLS_ctx.hideHeader }]) },
}, ...__VLS_functionalComponentArgsRest(__VLS_166));
__VLS_168.slots.default;
const __VLS_169 = {}.RouterView;
/** @type {[typeof __VLS_components.RouterView, typeof __VLS_components.routerView, ]} */ ;
// @ts-ignore
const __VLS_170 = __VLS_asFunctionalComponent(__VLS_169, new __VLS_169({}));
const __VLS_171 = __VLS_170({}, ...__VLS_functionalComponentArgsRest(__VLS_170));
var __VLS_168;
var __VLS_160;
var __VLS_3;
/** @type {__VLS_StyleScopedClasses['app-shell']} */ ;
/** @type {__VLS_StyleScopedClasses['logo-card']} */ ;
/** @type {__VLS_StyleScopedClasses['logo-mark']} */ ;
/** @type {__VLS_StyleScopedClasses['logo-mark__image']} */ ;
/** @type {__VLS_StyleScopedClasses['logo-copy']} */ ;
/** @type {__VLS_StyleScopedClasses['logo-title']} */ ;
/** @type {__VLS_StyleScopedClasses['logo-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['menu']} */ ;
/** @type {__VLS_StyleScopedClasses['qa-menu-launch']} */ ;
/** @type {__VLS_StyleScopedClasses['qa-menu-launch__main']} */ ;
/** @type {__VLS_StyleScopedClasses['qa-menu-launch__create']} */ ;
/** @type {__VLS_StyleScopedClasses['qa-session-list']} */ ;
/** @type {__VLS_StyleScopedClasses['qa-session-item']} */ ;
/** @type {__VLS_StyleScopedClasses['qa-session-item__copy']} */ ;
/** @type {__VLS_StyleScopedClasses['qa-session-item__title']} */ ;
/** @type {__VLS_StyleScopedClasses['qa-session-item__preview']} */ ;
/** @type {__VLS_StyleScopedClasses['qa-session-item__menu']} */ ;
/** @type {__VLS_StyleScopedClasses['aside-footnote']} */ ;
/** @type {__VLS_StyleScopedClasses['aside-footnote__title']} */ ;
/** @type {__VLS_StyleScopedClasses['aside-footnote__desc']} */ ;
/** @type {__VLS_StyleScopedClasses['content-shell']} */ ;
/** @type {__VLS_StyleScopedClasses['header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
/** @type {__VLS_StyleScopedClasses['header-title']} */ ;
/** @type {__VLS_StyleScopedClasses['header-desc']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            ChatDotRound: ChatDotRound,
            DataBoard: DataBoard,
            Files: Files,
            MoreFilled: MoreFilled,
            Plus: Plus,
            Search: Search,
            Tickets: Tickets,
            Timer: Timer,
            brandLogoUrl: brandLogoUrl,
            route: route,
            isAsideCollapsed: isAsideCollapsed,
            qaSessionSummaries: qaSessionSummaries,
            appTitle: appTitle,
            asideWidth: asideWidth,
            activePath: activePath,
            openedMenus: openedMenus,
            hideHeader: hideHeader,
            headerMeta: headerMeta,
            isQaSessionActive: isQaSessionActive,
            goDataQaPage: goDataQaPage,
            createQaSession: createQaSession,
            openQaSession: openQaSession,
            handleQaSessionCommand: handleQaSessionCommand,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
