<template>
  <div>
    <div class="table-toolbar" v-if="showToolbar">
      <div class="table-title">{{ title }}</div>
      <div class="table-actions">
        <slot name="toolbar" />
      </div>
    </div>

    <div class="table-scroll-shell">
      <el-table
        :data="items"
        border
        stripe
        :fit="false"
        style="width: 100%"
        max-height="520"
        @row-click="emitRowDetail"
        :row-class-name="resolveRowClassName"
      >
        <el-table-column
          v-for="column in columns"
          :key="column"
          :prop="column"
          :label="resolveColumnLabel(column)"
          :min-width="resolveColumnMinWidth(column)"
          :align="resolveColumnAlign(column)"
          show-overflow-tooltip
        >
          <template #default="scope">
            {{ formatCell(column, scope.row[column]) }}
          </template>
        </el-table-column>git init

        <el-table-column v-if="items.length" label="操作" width="100" fixed="right" align="center">
          <template #default="scope">
            <el-button link type="primary" @click.stop="emitRowDetail(scope.row)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  items: Record<string, any>[]
  title?: string
  showToolbar?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  title: '结果表格',
  showToolbar: true,
})

const emit = defineEmits<{
  (e: 'row-detail', row: Record<string, any>): void
}>()

/**
 * 常用业务字段中文表头映射。
 * 说明：
 * 结果表格第二版优先面向业务查看，因此不再直接暴露所有后端原始字段名。
 */
const COLUMN_LABEL_MAP: Record<string, string> = {
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
}

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
]

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
])

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
])

/**
 * 比例字段统一转成百分比。
 */
const RATE_FIELDS = new Set(['diff_rate'])

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
])

/**
 * 预先构建优先级索引，避免每次排序重复查找数组。
 */
const COLUMN_PRIORITY_INDEX = new Map(
  COLUMN_PRIORITY.map((column, index) => [column, index]),
)

/**
 * 推断表格列。
 * 说明：
 * 第二版不再只取第一行字段，而是把所有行的字段做并集，
 * 并按“业务优先级 + 字典序”稳定排序，保证不同查询结果下表头顺序一致。
 */
const columns = computed(() => {
  const set = new Set<string>()
  for (const item of props.items || []) {
    Object.keys(item || {}).forEach((key) => set.add(key))
  }
  return Array.from(set).sort((left, right) => {
    const leftPriority = COLUMN_PRIORITY_INDEX.get(left) ?? Number.MAX_SAFE_INTEGER
    const rightPriority = COLUMN_PRIORITY_INDEX.get(right) ?? Number.MAX_SAFE_INTEGER
    if (leftPriority !== rightPriority) {
      return leftPriority - rightPriority
    }
    return left.localeCompare(right, 'zh-CN')
  })
})

/**
 * 格式化单元格内容。
 * 说明：
 * 1. 空值统一显示为短横线；
 * 2. 根据字段类型做千分位、百分比和小数位处理；
 * 3. 对象与数组统一转可读文本，避免前端直接显示 `[object Object]`。
 */
function formatCell(column: string, value: unknown) {
  if (value === null || value === undefined || value === '') return '-'

  if (RATE_FIELDS.has(column)) {
    const rateValue = normalizeNumber(value)
    if (rateValue === null) return String(value)
    return `${(rateValue * 100).toFixed(2)}%`
  }

  if (typeof value === 'number' || isNumericString(value)) {
    const numberValue = normalizeNumber(value)
    if (numberValue === null) return String(value)
    if (INTEGER_FIELDS.has(column)) {
      return numberValue.toLocaleString('zh-CN', {
        maximumFractionDigits: 0,
      })
    }
    if (DECIMAL_FIELDS.has(column)) {
      return numberValue.toLocaleString('zh-CN', {
        minimumFractionDigits: Number.isInteger(numberValue) ? 0 : 2,
        maximumFractionDigits: 2,
      })
    }
    return numberValue.toLocaleString('zh-CN', {
      maximumFractionDigits: 2,
    })
  }

  if (Array.isArray(value)) {
    if (!value.length) return '-'
    if (value.every((item) => ['string', 'number', 'boolean'].includes(typeof item))) {
      return value.join('，')
    }
    return JSON.stringify(value, null, 2)
  }

  if (typeof value === 'object') {
    if (!Object.keys(value).length) return '-'
    return JSON.stringify(value, null, 2)
  }

  return String(value)
}

/**
 * 返回中文列名。
 * 说明：
 * 未配置映射的字段继续保留原名，避免误改后端新增字段语义。
 */
function resolveColumnLabel(column: string) {
  return COLUMN_LABEL_MAP[column] || column
}

/**
 * 根据字段类型设置基础列宽。
 * 说明：
 * 结果表第二版优先保证“可看清”，因此对编号、文本和数值列做不同宽度策略。
 */
function resolveColumnMinWidth(column: string) {
  if (WIDE_TEXT_FIELDS.has(column)) return 220
  if (INTEGER_FIELDS.has(column) || DECIMAL_FIELDS.has(column) || RATE_FIELDS.has(column)) return 140
  return 160
}

/**
 * 数值字段右对齐，其余字段左对齐，方便快速扫描。
 */
function resolveColumnAlign(column: string) {
  if (INTEGER_FIELDS.has(column) || DECIMAL_FIELDS.has(column) || RATE_FIELDS.has(column)) {
    return 'right'
  }
  return 'left'
}

/**
 * 为整行补可点击样式。
 */
function resolveRowClassName() {
  return 'clickable-row'
}

/**
 * 触发行明细查看。
 */
function emitRowDetail(row: Record<string, any>) {
  emit('row-detail', row)
}

/**
 * 判断字符串是否为数值文本。
 */
function isNumericString(value: unknown) {
  return typeof value === 'string' && /^-?\d+(\.\d+)?$/.test(value.trim())
}

/**
 * 将数字或数字字符串统一转成 number。
 */
function normalizeNumber(value: unknown) {
  const nextValue = typeof value === 'string' ? Number(value.trim()) : value
  return typeof nextValue === 'number' && !Number.isNaN(nextValue) ? nextValue : null
}
</script>

<style scoped>
.table-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
}
.table-title {
  font-weight: 600;
}
.table-actions {
  display: flex;
  gap: 8px;
}

.table-scroll-shell {
  overflow-x: auto;
}

:deep(.clickable-row) {
  cursor: pointer;
}
</style>
