<template>
  <div class="page-card">
    <h3 style="margin-top: 0">解析结果</h3>
    <div class="kv-grid" v-if="parsed">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="查询模式">{{ parsed.mode || '-' }}</el-descriptions-item>
        <el-descriptions-item label="指标">{{ parsed.metric_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源范围">{{ parsed.source_scope || '-' }}</el-descriptions-item>
        <el-descriptions-item label="模板ID">{{ parsed.template_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="SQL模板ID">{{ parsed.sql_template_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="配置版本">{{ parsed.config_version || '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="年份月份">{{ formatValue(parsed.year_month_list) }}</el-descriptions-item>
        <el-descriptions-item label="合同编号">{{ parsed.contract_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="物流公司">{{ parsed.logistics_company_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="区域">{{ parsed.region_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="运输方式">{{ parsed.transport_mode || '-' }}</el-descriptions-item>
        <el-descriptions-item label="指标展示名">{{ parsed.metric_display_name || '-' }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <el-collapse style="margin-top: 16px">
      <el-collapse-item title="查看完整 parsed JSON" name="1">
        <div class="mono-block">{{ formatJson(parsed) }}</div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
interface Props {
  parsed: Record<string, any> | null
}

defineProps<Props>()

/** 将任意值格式化为便于界面展示的文本。 */
function formatValue(value: unknown) {
  if (Array.isArray(value)) return value.join(', ')
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}

/** 将对象格式化为 JSON 字符串，便于调试自然语言解析结果。 */
function formatJson(value: unknown) {
  if (!value) return '-'
  return JSON.stringify(value, null, 2)
}
</script>
