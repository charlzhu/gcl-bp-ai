import { computed } from 'vue';
const props = withDefaults(defineProps(), {
    title: '结果表格',
    showToolbar: true,
});
const emit = defineEmits();
/**
 * 常用业务字段中文表头映射。
 * 说明：
 * 结果表格第二版优先面向业务查看，因此不再直接暴露所有后端原始字段名。
 */
const COLUMN_LABEL_MAP = {
    id: 'ID',
    biz_date: '业务日期',
    biz_year: '业务年份',
    biz_month: '业务月份',
    customer_name: '客户',
    contract_no: '合同编号',
    inquiry_no: '询比价编号',
    ship_instruction_no: '发货指令',
    sap_order_no: 'SAP 单号',
    task_id: '任务编号',
    logistics_company_name: '物流公司',
    fallback_base_name: '基地',
    warehouse_name: '仓库',
    region_name: '区域',
    origin_place: '始发地',
    destination: '目的地',
    transport_mode: '运输方式',
    plate_number: '车牌号',
    product_spec: '产品规格',
    product_power: '产品功率',
    source_type: '来源类型',
    source_ref: '来源引用',
    shipment_count: '发货次数',
    shipment_watt: '运量',
    shipment_trip_count: '车次',
    total_fee: '总费用',
    extra_fee: '附加费',
    row_count: '记录数',
    left_value: '左侧值',
    right_value: '右侧值',
    diff_value: '差值',
    diff_rate: '差异率',
};
/**
 * 业务字段优先级。
 * 说明：
 * 先把业务最关心的列稳定排在前面，其余未知字段再按字典序补在后面。
 */
const COLUMN_PRIORITY = [
    'biz_date',
    'biz_month',
    'biz_year',
    'customer_name',
    'contract_no',
    'inquiry_no',
    'ship_instruction_no',
    'sap_order_no',
    'task_id',
    'logistics_company_name',
    'fallback_base_name',
    'warehouse_name',
    'region_name',
    'origin_place',
    'destination',
    'transport_mode',
    'plate_number',
    'product_spec',
    'product_power',
    'source_type',
    'source_ref',
    'shipment_count',
    'shipment_watt',
    'shipment_trip_count',
    'total_fee',
    'extra_fee',
    'row_count',
    'left_value',
    'right_value',
    'diff_value',
    'diff_rate',
    'id',
];
/**
 * 整数类字段。
 * 说明：
 * 这类字段默认不保留小数，避免业务看到无意义的 `.00`。
 */
const INTEGER_FIELDS = new Set([
    'id',
    'page',
    'page_size',
    'total',
    'record_count',
    'row_count',
    'shipment_count',
    'shipment_trip_count',
    'item_count',
]);
/**
 * 金额、运量和对比值等字段统一保留两位以内小数。
 */
const DECIMAL_FIELDS = new Set([
    'shipment_watt',
    'total_fee',
    'extra_fee',
    'left_value',
    'right_value',
    'diff_value',
]);
/**
 * 比例字段统一转成百分比。
 */
const RATE_FIELDS = new Set(['diff_rate']);
/**
 * 明显偏文本的字段扩大列宽，减少无意义换行。
 */
const WIDE_TEXT_FIELDS = new Set([
    'contract_no',
    'inquiry_no',
    'ship_instruction_no',
    'sap_order_no',
    'source_ref',
    'destination',
    'product_spec',
]);
/**
 * 预先构建优先级索引，避免每次排序重复查找数组。
 */
const COLUMN_PRIORITY_INDEX = new Map(COLUMN_PRIORITY.map((column, index) => [column, index]));
/**
 * 推断表格列。
 * 说明：
 * 第二版不再只取第一行字段，而是把所有行的字段做并集，
 * 并按“业务优先级 + 字典序”稳定排序，保证不同查询结果下表头顺序一致。
 */
const columns = computed(() => {
    const set = new Set();
    for (const item of props.items || []) {
        Object.keys(item || {}).forEach((key) => set.add(key));
    }
    return Array.from(set).sort((left, right) => {
        const leftPriority = COLUMN_PRIORITY_INDEX.get(left) ?? Number.MAX_SAFE_INTEGER;
        const rightPriority = COLUMN_PRIORITY_INDEX.get(right) ?? Number.MAX_SAFE_INTEGER;
        if (leftPriority !== rightPriority) {
            return leftPriority - rightPriority;
        }
        return left.localeCompare(right, 'zh-CN');
    });
});
/**
 * 格式化单元格内容。
 * 说明：
 * 1. 空值统一显示为短横线；
 * 2. 根据字段类型做千分位、百分比和小数位处理；
 * 3. 对象与数组统一转可读文本，避免前端直接显示 `[object Object]`。
 */
function formatCell(column, value) {
    if (value === null || value === undefined || value === '')
        return '-';
    if (RATE_FIELDS.has(column)) {
        const rateValue = normalizeNumber(value);
        if (rateValue === null)
            return String(value);
        return `${(rateValue * 100).toFixed(2)}%`;
    }
    if (typeof value === 'number' || isNumericString(value)) {
        const numberValue = normalizeNumber(value);
        if (numberValue === null)
            return String(value);
        if (INTEGER_FIELDS.has(column)) {
            return numberValue.toLocaleString('zh-CN', {
                maximumFractionDigits: 0,
            });
        }
        if (DECIMAL_FIELDS.has(column)) {
            return numberValue.toLocaleString('zh-CN', {
                minimumFractionDigits: Number.isInteger(numberValue) ? 0 : 2,
                maximumFractionDigits: 2,
            });
        }
        return numberValue.toLocaleString('zh-CN', {
            maximumFractionDigits: 2,
        });
    }
    if (Array.isArray(value)) {
        if (!value.length)
            return '-';
        if (value.every((item) => ['string', 'number', 'boolean'].includes(typeof item))) {
            return value.join('，');
        }
        return JSON.stringify(value, null, 2);
    }
    if (typeof value === 'object') {
        if (!Object.keys(value).length)
            return '-';
        return JSON.stringify(value, null, 2);
    }
    return String(value);
}
/**
 * 返回中文列名。
 * 说明：
 * 未配置映射的字段继续保留原名，避免误改后端新增字段语义。
 */
function resolveColumnLabel(column) {
    return COLUMN_LABEL_MAP[column] || column;
}
/**
 * 根据字段类型设置基础列宽。
 * 说明：
 * 结果表第二版优先保证“可看清”，因此对编号、文本和数值列做不同宽度策略。
 */
function resolveColumnMinWidth(column) {
    if (WIDE_TEXT_FIELDS.has(column))
        return 220;
    if (INTEGER_FIELDS.has(column) || DECIMAL_FIELDS.has(column) || RATE_FIELDS.has(column))
        return 140;
    return 160;
}
/**
 * 数值字段右对齐，其余字段左对齐，方便快速扫描。
 */
function resolveColumnAlign(column) {
    if (INTEGER_FIELDS.has(column) || DECIMAL_FIELDS.has(column) || RATE_FIELDS.has(column)) {
        return 'right';
    }
    return 'left';
}
/**
 * 为整行补可点击样式。
 */
function resolveRowClassName() {
    return 'clickable-row';
}
/**
 * 触发行明细查看。
 */
function emitRowDetail(row) {
    emit('row-detail', row);
}
/**
 * 判断字符串是否为数值文本。
 */
function isNumericString(value) {
    return typeof value === 'string' && /^-?\d+(\.\d+)?$/.test(value.trim());
}
/**
 * 将数字或数字字符串统一转成 number。
 */
function normalizeNumber(value) {
    const nextValue = typeof value === 'string' ? Number(value.trim()) : value;
    return typeof nextValue === 'number' && !Number.isNaN(nextValue) ? nextValue : null;
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_withDefaultsArg = (function (t) { return t; })({
    title: '结果表格',
    showToolbar: true,
});
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({});
if (__VLS_ctx.showToolbar) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "table-toolbar" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "table-title" },
    });
    (__VLS_ctx.title);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "table-actions" },
    });
    var __VLS_0 = {};
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "table-scroll-shell" },
});
const __VLS_2 = {}.ElTable;
/** @type {[typeof __VLS_components.ElTable, typeof __VLS_components.elTable, typeof __VLS_components.ElTable, typeof __VLS_components.elTable, ]} */ ;
// @ts-ignore
const __VLS_3 = __VLS_asFunctionalComponent(__VLS_2, new __VLS_2({
    ...{ 'onRowClick': {} },
    data: (__VLS_ctx.items),
    border: true,
    stripe: true,
    fit: (false),
    ...{ style: {} },
    maxHeight: "520",
    rowClassName: (__VLS_ctx.resolveRowClassName),
}));
const __VLS_4 = __VLS_3({
    ...{ 'onRowClick': {} },
    data: (__VLS_ctx.items),
    border: true,
    stripe: true,
    fit: (false),
    ...{ style: {} },
    maxHeight: "520",
    rowClassName: (__VLS_ctx.resolveRowClassName),
}, ...__VLS_functionalComponentArgsRest(__VLS_3));
let __VLS_6;
let __VLS_7;
let __VLS_8;
const __VLS_9 = {
    onRowClick: (__VLS_ctx.emitRowDetail)
};
__VLS_5.slots.default;
for (const [column] of __VLS_getVForSourceType((__VLS_ctx.columns))) {
    const __VLS_10 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_11 = __VLS_asFunctionalComponent(__VLS_10, new __VLS_10({
        key: (column),
        prop: (column),
        label: (__VLS_ctx.resolveColumnLabel(column)),
        minWidth: (__VLS_ctx.resolveColumnMinWidth(column)),
        align: (__VLS_ctx.resolveColumnAlign(column)),
        showOverflowTooltip: true,
    }));
    const __VLS_12 = __VLS_11({
        key: (column),
        prop: (column),
        label: (__VLS_ctx.resolveColumnLabel(column)),
        minWidth: (__VLS_ctx.resolveColumnMinWidth(column)),
        align: (__VLS_ctx.resolveColumnAlign(column)),
        showOverflowTooltip: true,
    }, ...__VLS_functionalComponentArgsRest(__VLS_11));
    __VLS_13.slots.default;
    {
        const { default: __VLS_thisSlot } = __VLS_13.slots;
        const [scope] = __VLS_getSlotParams(__VLS_thisSlot);
        (__VLS_ctx.formatCell(column, scope.row[column]));
    }
    var __VLS_13;
}
if (__VLS_ctx.items.length) {
    const __VLS_14 = {}.ElTableColumn;
    /** @type {[typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, typeof __VLS_components.ElTableColumn, typeof __VLS_components.elTableColumn, ]} */ ;
    // @ts-ignore
    const __VLS_15 = __VLS_asFunctionalComponent(__VLS_14, new __VLS_14({
        label: "操作",
        width: "100",
        fixed: "right",
        align: "center",
    }));
    const __VLS_16 = __VLS_15({
        label: "操作",
        width: "100",
        fixed: "right",
        align: "center",
    }, ...__VLS_functionalComponentArgsRest(__VLS_15));
    __VLS_17.slots.default;
    {
        const { default: __VLS_thisSlot } = __VLS_17.slots;
        const [scope] = __VLS_getSlotParams(__VLS_thisSlot);
        const __VLS_18 = {}.ElButton;
        /** @type {[typeof __VLS_components.ElButton, typeof __VLS_components.elButton, typeof __VLS_components.ElButton, typeof __VLS_components.elButton, ]} */ ;
        // @ts-ignore
        const __VLS_19 = __VLS_asFunctionalComponent(__VLS_18, new __VLS_18({
            ...{ 'onClick': {} },
            link: true,
            type: "primary",
        }));
        const __VLS_20 = __VLS_19({
            ...{ 'onClick': {} },
            link: true,
            type: "primary",
        }, ...__VLS_functionalComponentArgsRest(__VLS_19));
        let __VLS_22;
        let __VLS_23;
        let __VLS_24;
        const __VLS_25 = {
            onClick: (...[$event]) => {
                if (!(__VLS_ctx.items.length))
                    return;
                __VLS_ctx.emitRowDetail(scope.row);
            }
        };
        __VLS_21.slots.default;
        var __VLS_21;
    }
    var __VLS_17;
}
var __VLS_5;
/** @type {__VLS_StyleScopedClasses['table-toolbar']} */ ;
/** @type {__VLS_StyleScopedClasses['table-title']} */ ;
/** @type {__VLS_StyleScopedClasses['table-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['table-scroll-shell']} */ ;
// @ts-ignore
var __VLS_1 = __VLS_0;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            columns: columns,
            formatCell: formatCell,
            resolveColumnLabel: resolveColumnLabel,
            resolveColumnMinWidth: resolveColumnMinWidth,
            resolveColumnAlign: resolveColumnAlign,
            resolveRowClassName: resolveRowClassName,
            emitRowDetail: emitRowDetail,
        };
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
const __VLS_component = (await import('vue')).defineComponent({
    setup() {
        return {};
    },
    __typeEmits: {},
    __typeProps: {},
    props: {},
});
export default {};
; /* PartiallyEnd: #4569/main.vue */
