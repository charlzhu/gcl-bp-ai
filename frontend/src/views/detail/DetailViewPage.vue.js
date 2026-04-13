import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import ResultTable from '@/components/ResultTable.vue';
import { clearLastQueryContext, getLastQueryContext } from '@/utils/queryStorage';
const router = useRouter();
const context = ref(getLastQueryContext());
const selectedRow = ref(null);
const visible = ref(false);
/**
 * 来源类型中文映射。
 * 说明：
 * 明细页优先展示业务能理解的来源标签，而不是直接暴露底层枚举值。
 */
const SOURCE_TYPE_LABEL_MAP = {
    HIST: '历史 Excel',
    SYS: '正式系统',
    history: '历史 Excel',
    system_formal: '正式系统',
    mixed: '混合来源',
};
/**
 * 当前激活记录。
 * 说明：
 * 1. 优先使用上一个页面点击的那一行；
 * 2. 如果没有选中行，则默认取当前结果的第一条，避免明细页空白。
 */
const activeRow = computed(() => {
    if (selectedRow.value)
        return selectedRow.value;
    if (context.value?.selectedRow)
        return context.value.selectedRow;
    const items = context.value?.queryResult?.items;
    if (Array.isArray(items) && items.length > 0)
        return items[0];
    return null;
});
/**
 * 返回上一页。
 */
function goBack() {
    if (context.value?.sourcePage === 'structured-query') {
        router.push('/structured-query');
        return;
    }
    router.push('/nl-query');
}
/**
 * 清理上下文后刷新当前视图。
 */
function clearContext() {
    clearLastQueryContext();
    context.value = null;
}
/**
 * 展示单行详情。
 */
function showRowDetail(row) {
    selectedRow.value = row;
    visible.value = true;
}
/**
 * 返回来源页面中文名。
 */
function resolveSourcePageLabel(value) {
    if (value === 'structured-query')
        return '条件查询';
    if (value === 'nl-query')
        return '自然语言查询';
    return value || '-';
}
/**
 * 返回来源类型中文名。
 */
function resolveSourceTypeLabel(value) {
    const key = typeof value === 'string' ? value : '';
    return SOURCE_TYPE_LABEL_MAP[key] || key || '-';
}
/**
 * 计算当前结果条数。
 */
function resolveResultCount() {
    const queryResult = context.value?.queryResult;
    if (!queryResult)
        return '-';
    if (queryResult.total !== undefined && queryResult.total !== null) {
        return formatValue(queryResult.total);
    }
    const items = queryResult.items;
    if (Array.isArray(items))
        return formatValue(items.length);
    return '-';
}
/**
 * 界面值格式化。
 * 说明：
 * 和结果表保持一致，空值统一显示为短横线。
 */
function formatValue(value) {
    if (value === null || value === undefined || value === '')
        return '-';
    if (typeof value === 'number') {
        return value.toLocaleString('zh-CN', {
            maximumFractionDigits: 2,
        });
    }
    return String(value);
}
/**
 * JSON 格式化。
 */
function formatJson(value) {
    if (!value)
        return '-';
    return JSON.stringify(value, null, 2);
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "page-card" },
    ...{ style: {} },
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
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({}));
const __VLS_2 = __VLS_1({}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
const __VLS_4 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
    ...{ 'onClick': {} },
}));
const __VLS_6 = __VLS_5({
    ...{ 'onClick': {} },
}, ...__VLS_functionalComponentArgsRest(__VLS_5));
let __VLS_8;
let __VLS_9;
let __VLS_10;
const __VLS_11 = {
    onClick: (__VLS_ctx.goBack)
};
__VLS_7.slots.default;
var __VLS_7;
const __VLS_12 = {}.ElButton;
/** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
// @ts-ignore
const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
    ...{ 'onClick': {} },
    type: "danger",
    plain: true,
}));
const __VLS_14 = __VLS_13({
    ...{ 'onClick': {} },
    type: "danger",
    plain: true,
}, ...__VLS_functionalComponentArgsRest(__VLS_13));
let __VLS_16;
let __VLS_17;
let __VLS_18;
const __VLS_19 = {
    onClick: (__VLS_ctx.clearContext)
};
__VLS_15.slots.default;
var __VLS_15;
var __VLS_3;
if (!__VLS_ctx.context) {
    const __VLS_20 = {}.ElAlert;
    /** @type {[typeof __VLS_components.ElAlert, typeof __VLS_components.elAlert, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({
        title: "当前没有可展示的查询上下文，请先在自然语言查询页或条件查询页执行一次查询。",
        type: "warning",
        closable: (false),
        showIcon: true,
        ...{ class: "page-card" },
    }));
    const __VLS_22 = __VLS_21({
        title: "当前没有可展示的查询上下文，请先在自然语言查询页或条件查询页执行一次查询。",
        type: "warning",
        closable: (false),
        showIcon: true,
        ...{ class: "page-card" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
else {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "page-card" },
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ style: {} },
    });
    const __VLS_24 = {}.ElDescriptions;
    /** @type {[typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
        column: (2),
        border: true,
    }));
    const __VLS_26 = __VLS_25({
        column: (2),
        border: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_25));
    __VLS_27.slots.default;
    const __VLS_28 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        label: "来源页面",
    }));
    const __VLS_30 = __VLS_29({
        label: "来源页面",
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    __VLS_31.slots.default;
    (__VLS_ctx.resolveSourcePageLabel(__VLS_ctx.context.sourcePage));
    var __VLS_31;
    const __VLS_32 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
        label: "问题",
    }));
    const __VLS_34 = __VLS_33({
        label: "问题",
    }, ...__VLS_functionalComponentArgsRest(__VLS_33));
    __VLS_35.slots.default;
    (__VLS_ctx.context.question || '-');
    var __VLS_35;
    const __VLS_36 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({
        label: "查询类型",
    }));
    const __VLS_38 = __VLS_37({
        label: "查询类型",
    }, ...__VLS_functionalComponentArgsRest(__VLS_37));
    __VLS_39.slots.default;
    (__VLS_ctx.context.queryResult?.query_type || '-');
    var __VLS_39;
    const __VLS_40 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        label: "来源范围",
    }));
    const __VLS_42 = __VLS_41({
        label: "来源范围",
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
    (__VLS_ctx.context.queryResult?.source_scope || '-');
    var __VLS_43;
    const __VLS_44 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({
        label: "执行模式",
    }));
    const __VLS_46 = __VLS_45({
        label: "执行模式",
    }, ...__VLS_functionalComponentArgsRest(__VLS_45));
    __VLS_47.slots.default;
    (__VLS_ctx.context.queryResult?.execution_mode || '-');
    var __VLS_47;
    const __VLS_48 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        label: "状态码",
    }));
    const __VLS_50 = __VLS_49({
        label: "状态码",
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_51.slots.default;
    (__VLS_ctx.context.rawResponse?.response_meta?.status?.code || __VLS_ctx.context.queryResult?.status?.code || '-');
    var __VLS_51;
    const __VLS_52 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
        label: "模板ID",
    }));
    const __VLS_54 = __VLS_53({
        label: "模板ID",
    }, ...__VLS_functionalComponentArgsRest(__VLS_53));
    __VLS_55.slots.default;
    (__VLS_ctx.context.parsed?.template_id || '-');
    var __VLS_55;
    const __VLS_56 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
        label: "返回条数",
    }));
    const __VLS_58 = __VLS_57({
        label: "返回条数",
    }, ...__VLS_functionalComponentArgsRest(__VLS_57));
    __VLS_59.slots.default;
    (__VLS_ctx.resolveResultCount());
    var __VLS_59;
    var __VLS_27;
    if (__VLS_ctx.activeRow) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "page-card" },
            ...{ style: {} },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "section-header" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
            ...{ style: {} },
        });
        const __VLS_60 = {}.ElTag;
        /** @type {[typeof __VLS_components.ElTag, typeof __VLS_components.elTag, typeof __VLS_components.ElTag, typeof __VLS_components.elTag, ]} */ ;
        // @ts-ignore
        const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({
            size: "small",
            type: "info",
        }));
        const __VLS_62 = __VLS_61({
            size: "small",
            type: "info",
        }, ...__VLS_functionalComponentArgsRest(__VLS_61));
        __VLS_63.slots.default;
        (__VLS_ctx.resolveSourceTypeLabel(__VLS_ctx.activeRow.source_type));
        var __VLS_63;
        const __VLS_64 = {}.ElDescriptions;
        /** @type {[typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, ]} */ ;
        // @ts-ignore
        const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
            column: (2),
            border: true,
        }));
        const __VLS_66 = __VLS_65({
            column: (2),
            border: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_65));
        __VLS_67.slots.default;
        const __VLS_68 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
            label: "业务日期",
        }));
        const __VLS_70 = __VLS_69({
            label: "业务日期",
        }, ...__VLS_functionalComponentArgsRest(__VLS_69));
        __VLS_71.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.biz_date));
        var __VLS_71;
        const __VLS_72 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
            label: "业务月份",
        }));
        const __VLS_74 = __VLS_73({
            label: "业务月份",
        }, ...__VLS_functionalComponentArgsRest(__VLS_73));
        __VLS_75.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.biz_month));
        var __VLS_75;
        const __VLS_76 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
            label: "合同编号",
        }));
        const __VLS_78 = __VLS_77({
            label: "合同编号",
        }, ...__VLS_functionalComponentArgsRest(__VLS_77));
        __VLS_79.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.contract_no));
        var __VLS_79;
        const __VLS_80 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({
            label: "任务编号",
        }));
        const __VLS_82 = __VLS_81({
            label: "任务编号",
        }, ...__VLS_functionalComponentArgsRest(__VLS_81));
        __VLS_83.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.task_id));
        var __VLS_83;
        const __VLS_84 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({
            label: "客户",
        }));
        const __VLS_86 = __VLS_85({
            label: "客户",
        }, ...__VLS_functionalComponentArgsRest(__VLS_85));
        __VLS_87.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.customer_name));
        var __VLS_87;
        const __VLS_88 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
            label: "物流公司",
        }));
        const __VLS_90 = __VLS_89({
            label: "物流公司",
        }, ...__VLS_functionalComponentArgsRest(__VLS_89));
        __VLS_91.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.logistics_company_name));
        var __VLS_91;
        const __VLS_92 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            label: "区域",
        }));
        const __VLS_94 = __VLS_93({
            label: "区域",
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        __VLS_95.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.region_name));
        var __VLS_95;
        const __VLS_96 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
            label: "始发地",
        }));
        const __VLS_98 = __VLS_97({
            label: "始发地",
        }, ...__VLS_functionalComponentArgsRest(__VLS_97));
        __VLS_99.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.origin_place));
        var __VLS_99;
        const __VLS_100 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
            label: "运输方式",
        }));
        const __VLS_102 = __VLS_101({
            label: "运输方式",
        }, ...__VLS_functionalComponentArgsRest(__VLS_101));
        __VLS_103.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.transport_mode));
        var __VLS_103;
        const __VLS_104 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_105 = __VLS_asFunctionalComponent(__VLS_104, new __VLS_104({
            label: "车牌号",
        }));
        const __VLS_106 = __VLS_105({
            label: "车牌号",
        }, ...__VLS_functionalComponentArgsRest(__VLS_105));
        __VLS_107.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.plate_number));
        var __VLS_107;
        const __VLS_108 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
            label: "来源引用",
        }));
        const __VLS_110 = __VLS_109({
            label: "来源引用",
        }, ...__VLS_functionalComponentArgsRest(__VLS_109));
        __VLS_111.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.source_ref));
        var __VLS_111;
        const __VLS_112 = {}.ElDescriptionsItem;
        /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
        // @ts-ignore
        const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({
            label: "运量",
        }));
        const __VLS_114 = __VLS_113({
            label: "运量",
        }, ...__VLS_functionalComponentArgsRest(__VLS_113));
        __VLS_115.slots.default;
        (__VLS_ctx.formatValue(__VLS_ctx.activeRow.shipment_watt));
        var __VLS_115;
        var __VLS_67;
        const __VLS_116 = {}.ElCollapse;
        /** @type {[typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, ]} */ ;
        // @ts-ignore
        const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
            ...{ style: {} },
        }));
        const __VLS_118 = __VLS_117({
            ...{ style: {} },
        }, ...__VLS_functionalComponentArgsRest(__VLS_117));
        __VLS_119.slots.default;
        const __VLS_120 = {}.ElCollapseItem;
        /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
        // @ts-ignore
        const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({
            title: "查看当前记录完整 JSON",
            name: "selected-row-json",
        }));
        const __VLS_122 = __VLS_121({
            title: "查看当前记录完整 JSON",
            name: "selected-row-json",
        }, ...__VLS_functionalComponentArgsRest(__VLS_121));
        __VLS_123.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "mono-block" },
        });
        (__VLS_ctx.formatJson(__VLS_ctx.activeRow));
        var __VLS_123;
        var __VLS_119;
    }
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "page-card" },
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ style: {} },
    });
    /** @type {[typeof ResultTable, ]} */ ;
    // @ts-ignore
    const __VLS_124 = __VLS_asFunctionalComponent(ResultTable, new ResultTable({
        ...{ 'onRowDetail': {} },
        items: (__VLS_ctx.context.queryResult?.items || []),
        title: "明细结果",
    }));
    const __VLS_125 = __VLS_124({
        ...{ 'onRowDetail': {} },
        items: (__VLS_ctx.context.queryResult?.items || []),
        title: "明细结果",
    }, ...__VLS_functionalComponentArgsRest(__VLS_124));
    let __VLS_127;
    let __VLS_128;
    let __VLS_129;
    const __VLS_130 = {
        onRowDetail: (__VLS_ctx.showRowDetail)
    };
    var __VLS_126;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "page-card" },
        ...{ style: {} },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ style: {} },
    });
    const __VLS_131 = {}.ElDescriptions;
    /** @type {[typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, typeof __VLS_components.ElDescriptions, typeof __VLS_components.elDescriptions, ]} */ ;
    // @ts-ignore
    const __VLS_132 = __VLS_asFunctionalComponent(__VLS_131, new __VLS_131({
        column: (2),
        border: true,
    }));
    const __VLS_133 = __VLS_132({
        column: (2),
        border: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_132));
    __VLS_134.slots.default;
    const __VLS_135 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_136 = __VLS_asFunctionalComponent(__VLS_135, new __VLS_135({
        label: "查询模式",
    }));
    const __VLS_137 = __VLS_136({
        label: "查询模式",
    }, ...__VLS_functionalComponentArgsRest(__VLS_136));
    __VLS_138.slots.default;
    (__VLS_ctx.context.parsed?.mode || '-');
    var __VLS_138;
    const __VLS_139 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_140 = __VLS_asFunctionalComponent(__VLS_139, new __VLS_139({
        label: "指标",
    }));
    const __VLS_141 = __VLS_140({
        label: "指标",
    }, ...__VLS_functionalComponentArgsRest(__VLS_140));
    __VLS_142.slots.default;
    (__VLS_ctx.context.parsed?.metric_type || '-');
    var __VLS_142;
    const __VLS_143 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_144 = __VLS_asFunctionalComponent(__VLS_143, new __VLS_143({
        label: "来源范围",
    }));
    const __VLS_145 = __VLS_144({
        label: "来源范围",
    }, ...__VLS_functionalComponentArgsRest(__VLS_144));
    __VLS_146.slots.default;
    (__VLS_ctx.context.parsed?.source_scope || '-');
    var __VLS_146;
    const __VLS_147 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_148 = __VLS_asFunctionalComponent(__VLS_147, new __VLS_147({
        label: "模板命中",
    }));
    const __VLS_149 = __VLS_148({
        label: "模板命中",
    }, ...__VLS_functionalComponentArgsRest(__VLS_148));
    __VLS_150.slots.default;
    (__VLS_ctx.context.parsed?.template_hit ? '是' : '否');
    var __VLS_150;
    const __VLS_151 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_152 = __VLS_asFunctionalComponent(__VLS_151, new __VLS_151({
        label: "执行模式",
    }));
    const __VLS_153 = __VLS_152({
        label: "执行模式",
    }, ...__VLS_functionalComponentArgsRest(__VLS_152));
    __VLS_154.slots.default;
    (__VLS_ctx.context.queryResult?.execution_mode || '-');
    var __VLS_154;
    const __VLS_155 = {}.ElDescriptionsItem;
    /** @type {[typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, typeof __VLS_components.ElDescriptionsItem, typeof __VLS_components.elDescriptionsItem, ]} */ ;
    // @ts-ignore
    const __VLS_156 = __VLS_asFunctionalComponent(__VLS_155, new __VLS_155({
        label: "状态说明",
    }));
    const __VLS_157 = __VLS_156({
        label: "状态说明",
    }, ...__VLS_functionalComponentArgsRest(__VLS_156));
    __VLS_158.slots.default;
    (__VLS_ctx.context.rawResponse?.response_meta?.status?.message || __VLS_ctx.context.queryResult?.status?.message || '-');
    var __VLS_158;
    var __VLS_134;
    const __VLS_159 = {}.ElCollapse;
    /** @type {[typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, ]} */ ;
    // @ts-ignore
    const __VLS_160 = __VLS_asFunctionalComponent(__VLS_159, new __VLS_159({
        ...{ style: {} },
    }));
    const __VLS_161 = __VLS_160({
        ...{ style: {} },
    }, ...__VLS_functionalComponentArgsRest(__VLS_160));
    __VLS_162.slots.default;
    const __VLS_163 = {}.ElCollapseItem;
    /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
    // @ts-ignore
    const __VLS_164 = __VLS_asFunctionalComponent(__VLS_163, new __VLS_163({
        title: "查看 parsed 关键上下文",
        name: "parsed-json",
    }));
    const __VLS_165 = __VLS_164({
        title: "查看 parsed 关键上下文",
        name: "parsed-json",
    }, ...__VLS_functionalComponentArgsRest(__VLS_164));
    __VLS_166.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (__VLS_ctx.formatJson(__VLS_ctx.context.parsed || {}));
    var __VLS_166;
    const __VLS_167 = {}.ElCollapseItem;
    /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
    // @ts-ignore
    const __VLS_168 = __VLS_asFunctionalComponent(__VLS_167, new __VLS_167({
        title: "查看汇总结果",
        name: "summary-json",
    }));
    const __VLS_169 = __VLS_168({
        title: "查看汇总结果",
        name: "summary-json",
    }, ...__VLS_functionalComponentArgsRest(__VLS_168));
    __VLS_170.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (__VLS_ctx.formatJson(__VLS_ctx.context.queryResult?.summary || {}));
    var __VLS_170;
    var __VLS_162;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "page-card" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.h3, __VLS_intrinsicElements.h3)({
        ...{ style: {} },
    });
    const __VLS_171 = {}.ElCollapse;
    /** @type {[typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, typeof __VLS_components.ElCollapse, typeof __VLS_components.elCollapse, ]} */ ;
    // @ts-ignore
    const __VLS_172 = __VLS_asFunctionalComponent(__VLS_171, new __VLS_171({}));
    const __VLS_173 = __VLS_172({}, ...__VLS_functionalComponentArgsRest(__VLS_172));
    __VLS_174.slots.default;
    const __VLS_175 = {}.ElCollapseItem;
    /** @type {[typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, typeof __VLS_components.ElCollapseItem, typeof __VLS_components.elCollapseItem, ]} */ ;
    // @ts-ignore
    const __VLS_176 = __VLS_asFunctionalComponent(__VLS_175, new __VLS_175({
        title: "查看完整原始响应 JSON",
        name: "raw-response-json",
    }));
    const __VLS_177 = __VLS_176({
        title: "查看完整原始响应 JSON",
        name: "raw-response-json",
    }, ...__VLS_functionalComponentArgsRest(__VLS_176));
    __VLS_178.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (__VLS_ctx.formatJson(__VLS_ctx.context.rawResponse || {}));
    var __VLS_178;
    var __VLS_174;
    const __VLS_179 = {}.ElDialog;
    /** @type {[typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, typeof __VLS_components.ElDialog, typeof __VLS_components.elDialog, ]} */ ;
    // @ts-ignore
    const __VLS_180 = __VLS_asFunctionalComponent(__VLS_179, new __VLS_179({
        modelValue: (__VLS_ctx.visible),
        title: "单行详情",
        width: "60%",
    }));
    const __VLS_181 = __VLS_180({
        modelValue: (__VLS_ctx.visible),
        title: "单行详情",
        width: "60%",
    }, ...__VLS_functionalComponentArgsRest(__VLS_180));
    __VLS_182.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "mono-block" },
    });
    (__VLS_ctx.formatJson(__VLS_ctx.selectedRow));
    var __VLS_182;
}
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['page-header']} */ ;
/** @type {__VLS_StyleScopedClasses['page-title']} */ ;
/** @type {__VLS_StyleScopedClasses['page-subtitle']} */ ;
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['section-header']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
/** @type {__VLS_StyleScopedClasses['page-card']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
/** @type {__VLS_StyleScopedClasses['mono-block']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            ResultTable: ResultTable,
            context: context,
            selectedRow: selectedRow,
            visible: visible,
            activeRow: activeRow,
            goBack: goBack,
            clearContext: clearContext,
            showRowDetail: showRowDetail,
            resolveSourcePageLabel: resolveSourcePageLabel,
            resolveSourceTypeLabel: resolveSourceTypeLabel,
            resolveResultCount: resolveResultCount,
            formatValue: formatValue,
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
