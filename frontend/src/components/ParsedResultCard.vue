<template>
  <div class="page-card">
    <div class="header-row">
      <h3 style="margin: 0">解析结果</h3>
      <el-space v-if="parsed" wrap>
        <el-tag size="small" effect="plain">{{ parsed.mode || '-' }}</el-tag>
        <el-tag size="small" effect="plain">{{ parsed.source_scope || '-' }}</el-tag>
        <el-tag size="small" :type="parsed.template_hit ? 'success' : 'info'">
          {{ parsed.template_hit ? '模板已命中' : '模板未命中' }}
        </el-tag>
      </el-space>
    </div>

    <div v-if="parsed" class="kv-grid">
      <el-descriptions :column="1" border>
        <el-descriptions-item label="查询模式">{{ parsed.mode || '-' }}</el-descriptions-item>
        <el-descriptions-item label="指标">{{ parsed.metric_type || '-' }}</el-descriptions-item>
        <el-descriptions-item label="来源范围">{{ parsed.source_scope || '-' }}</el-descriptions-item>
        <el-descriptions-item label="模板 ID">{{ parsed.template_id || '-' }}</el-descriptions-item>
        <el-descriptions-item label="模板名称">{{ parsed.template_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="模板分数">{{ parsed.template_score ?? '-' }}</el-descriptions-item>
      </el-descriptions>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="年份月份">{{ formatValue(parsed.year_month_list) }}</el-descriptions-item>
        <el-descriptions-item label="合同编号">{{ parsed.contract_no || '-' }}</el-descriptions-item>
        <el-descriptions-item label="物流公司">{{ parsed.logistics_company_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="区域">{{ parsed.region_name || '-' }}</el-descriptions-item>
        <el-descriptions-item label="运输方式">{{ parsed.transport_mode || '-' }}</el-descriptions-item>
        <el-descriptions-item label="配置版本">{{ parsed.config_version || '-' }}</el-descriptions-item>
      </el-descriptions>
    </div>

    <el-empty v-else description="当前暂无解析结果" />

    <el-collapse v-if="parsed" style="margin-top: 16px">
      <el-collapse-item title="模板匹配说明" name="template-reasons">
        <ul v-if="templateReasons.length" class="reason-list">
          <li v-for="item in templateReasons" :key="item">{{ item }}</li>
        </ul>
        <div v-else class="minor-text">当前没有可展示的模板匹配说明。</div>
      </el-collapse-item>
      <el-collapse-item title="查看完整 parsed JSON" name="parsed-json">
        <div class="mono-block">{{ formatJson(parsed) }}</div>
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  parsed: Record<string, any> | null
}

const props = defineProps<Props>()

/**
 * 模板匹配原因列表。
 */
const templateReasons = computed(() => {
  const reasons = props.parsed?.template_match_reasons
  return Array.isArray(reasons) ? reasons.filter(Boolean) : []
})

/**
 * 将任意值格式化为便于界面展示的文本。
 */
function formatValue(value: unknown) {
  if (Array.isArray(value)) return value.join(', ')
  if (value === null || value === undefined || value === '') return '-'
  return String(value)
}

/**
 * 将对象格式化为 JSON 字符串，便于调试自然语言解析结果。
 */
function formatJson(value: unknown) {
  if (!value) return '-'
  return JSON.stringify(value, null, 2)
}
</script>

<style scoped>
.header-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.minor-text {
  color: var(--el-text-color-secondary);
  line-height: 1.7;
}

.reason-list {
  margin: 0;
  padding-left: 18px;
  color: var(--el-text-color-regular);
  line-height: 1.8;
}
</style>
