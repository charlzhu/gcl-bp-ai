<template>
  <section class="bom-page">
    <header class="page-head enterprise-hero">
      <div class="hero-copy">
        <div class="page-kicker">Data workspace</div>
        <h1>BOM 数据管理</h1>
        <p>上传、追溯、切换，一眼看清</p>
        <div class="hero-tags" aria-label="关键能力">
          <span>文件隔离</span>
          <span>温和校验</span>
          <span>版本追溯</span>
        </div>
      </div>
      <section class="primary-overview" aria-label="核心状态">
        <article v-for="item in primaryOverviewCards" :key="item.label" class="overview-card" :class="`overview-card--${item.tone}`">
          <span>{{ item.label }}</span>
          <strong>{{ item.value }}</strong>
          <em>{{ item.description }}</em>
        </article>
      </section>
    </header>

    <section class="secondary-status-strip" aria-label="轻量状态">
      <span v-for="item in secondaryStatusChips" :key="item.label" :class="`status-chip status-chip--${item.tone}`">
        <b>{{ item.label }}</b>{{ item.value }}
      </span>
    </section>

    <section class="upload-zone-grid" aria-label="上传操作区">
      <article class="upload-zone-card">
        <div class="panel-head">
          <div>
            <span class="section-eyebrow">BOM 数据导入</span>
            <h2>上传 BOM Excel</h2>
            <p>.xls / .xlsx / .xlsm</p>
          </div>
          <span class="upload-type-badge">BOM</span>
        </div>
        <div class="upload-card">
          <div class="upload-main">
            <input ref="fileInputRef" class="native-file-input" type="file" accept=".xls,.xlsx,.xlsm" @change="handleFileChange" />
            <div class="file-info">
              <strong>{{ selectedFile?.name || '请选择 BOM Excel 文件' }}</strong>
              <span>{{ selectedFile ? formatFileSize(selectedFile.size) : '可用于问答' }}</span>
            </div>
          </div>
          <el-button type="primary" :disabled="!selectedFile" :loading="uploading" @click="uploadFile">上传并解析</el-button>
        </div>
        <div v-if="uploading || bomUploadProgress > 0" class="upload-progress">
          <span>BOM 上传进度：{{ bomUploadProgress }}%</span>
          <el-progress :percentage="bomUploadProgress" />
        </div>
      </article>

      <article class="upload-zone-card upload-zone-card--power">
        <div class="panel-head">
          <div>
            <span class="section-eyebrow">功率模型版本</span>
            <h2>上传功率模型</h2>
            <p>GCL 功率测试基准 .xlsm</p>
          </div>
          <span class="upload-type-badge upload-type-badge--power">POWER</span>
        </div>
        <div class="upload-card upload-card--stacked">
          <div class="upload-main">
            <input
              ref="powerModelFileInputRef"
              class="native-file-input"
              type="file"
              accept=".xlsm"
              @change="handlePowerModelFileChange"
            />
            <div class="file-info">
              <strong>{{ powerModelSelectedFile?.name || '请选择功率模型 xlsm 文件' }}</strong>
              <span>{{ powerModelSelectedFile ? formatFileSize(powerModelSelectedFile.size) : '生成模型版本' }}</span>
            </div>
          </div>
          <el-button
            type="success"
            :disabled="!powerModelSelectedFile"
            :loading="powerModelUploading"
            @click="uploadPowerModelFile"
          >上传功率模型</el-button>
        </div>
        <div v-if="powerModelUploading || powerModelUploadProgress > 0" class="upload-progress">
          <span>功率模型上传进度：{{ powerModelUploadProgress }}%</span>
          <el-progress :percentage="powerModelUploadProgress" />
        </div>
      </article>
    </section>

    <section v-if="hasUploadFeedback" class="feedback-stack" aria-label="上传反馈">
      <el-alert
        v-if="uploadSuccessMessage"
        :title="uploadSuccessMessage"
        type="success"
        show-icon
        :closable="false"
      />

      <el-alert
        v-if="uploadError"
        :title="uploadError"
        type="error"
        show-icon
        :closable="false"
      />

      <el-alert
        v-if="powerModelUploadSuccessMessage"
        :title="powerModelUploadSuccessMessage"
        type="success"
        show-icon
        :closable="false"
      />

      <el-alert
        v-if="powerModelUploadError"
        :title="powerModelUploadError"
        type="error"
        show-icon
        :closable="false"
      />

      <div v-if="uploadResult" class="result-card">
        <div class="result-title">{{ uploadResult.message || '上传处理完成' }}</div>
        <div class="summary-grid">
          <div>
            <span>解析订单数</span>
            <strong>{{ uploadResult.parsed_orders_count ?? 0 }}</strong>
          </div>
          <div>
            <span>解析物料数</span>
            <strong>{{ uploadResult.parsed_materials_count ?? 0 }}</strong>
          </div>
          <div>
            <span>Warning</span>
            <strong>{{ uploadResult.warning_count ?? 0 }}</strong>
          </div>
          <div>
            <span>Error</span>
            <strong>{{ uploadResult.error_count ?? 0 }}</strong>
          </div>
        </div>
        <p class="next-action">{{ uploadResult.next_action || '上传完成，可进入智能问答' }}</p>
      </div>

      <div v-if="uploadPowerModelResult" class="result-card power-result-card">
        <div class="result-title">{{ uploadPowerModelResult.message || '功率模型上传处理完成' }}</div>
        <div class="summary-grid">
          <div>
            <span>版本 ID</span>
            <strong>{{ uploadPowerModelResult.version?.id ?? '-' }}</strong>
          </div>
          <div>
            <span>解析状态</span>
            <strong>{{ uploadPowerModelResult.version?.parse_status || '-' }}</strong>
          </div>
          <div>
            <span>是否生效</span>
            <strong>{{ uploadPowerModelResult.version?.is_active ? '当前生效' : '未生效' }}</strong>
          </div>
          <div>
            <span>Issue 数</span>
            <strong>{{ uploadPowerModelResult.detail?.issues?.length ?? uploadPowerModelResult.version?.error_count ?? '-' }}</strong>
          </div>
        </div>
        <p class="next-action">{{ powerModelResultNextAction }}</p>
      </div>
    </section>

    <section class="history-panel">
      <div class="panel-head history-head">
        <div>
          <span class="section-eyebrow">审计与回溯</span>
          <h2>上传历史</h2>
          <p>分页查看，保留审计线索</p>
        </div>
        <el-button :loading="historyLoading" @click="loadUploadHistory">刷新历史</el-button>
      </div>

      <el-alert
        v-if="historyError"
        :title="historyError"
        type="error"
        show-icon
        :closable="false"
      />

      <el-tabs v-model="historyActiveTab" class="history-tabs">
        <el-tab-pane label="BOM 上传历史" name="bom_upload_history">
          <div class="history-toolbar">
            <div>
              <h3>BOM 上传历史</h3>
              <p class="history-tip">共 {{ bomUploadHistory.length }} 批 · 时间倒序</p>
            </div>
          </div>
          <el-table v-loading="historyLoading" :data="pagedBomUploadHistory" border stripe size="small" table-layout="auto">
            <el-table-column prop="file_name" label="文件名" min-width="220" show-overflow-tooltip />
            <el-table-column prop="status" label="状态" width="100">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.status)">{{ row.status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="total_headers" label="订单数" width="90" />
            <el-table-column prop="total_lines" label="物料数" width="90" />
            <el-table-column prop="source_tag" label="来源" min-width="120" show-overflow-tooltip />
            <el-table-column prop="created_at" label="上传时间" min-width="170">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="error_message" label="错误信息" min-width="180" show-overflow-tooltip />
            <template #empty>暂无 BOM 上传历史</template>
          </el-table>
          <div class="history-pagination">
            <el-pagination
              v-if="bomUploadHistory.length > bomHistoryPageSize"
              background
              small
              layout="total, prev, pager, next"
              :current-page="bomHistoryPage"
              :page-size="bomHistoryPageSize"
              :total="bomUploadHistory.length"
              @current-change="handleBomHistoryPageChange"
            />
          </div>
        </el-tab-pane>

        <el-tab-pane label="功率模型版本历史" name="power_model_versions">
          <div class="history-toolbar">
            <div>
              <h3>功率模型版本历史</h3>
              <p class="history-tip">生效：{{ formatPowerVersionLabel(activePowerModelVersion) }}</p>
            </div>
          </div>
          <el-table v-loading="historyLoading" :data="pagedPowerModelVersions" border stripe size="small" table-layout="auto">
            <el-table-column prop="id" label="版本 ID" width="90" />
            <el-table-column prop="file_name" label="功率文件" min-width="240" show-overflow-tooltip />
            <el-table-column prop="business_version_label" label="业务版本" min-width="140" show-overflow-tooltip />
            <el-table-column prop="parse_status" label="解析状态" width="110">
              <template #default="{ row }">
                <el-tag :type="statusTagType(row.parse_status)">{{ row.parse_status }}</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="is_active" label="生效状态" width="110">
              <template #default="{ row }">
                <el-tag v-if="row.is_active" type="success">当前生效</el-tag>
                <el-tag v-else type="info">未生效</el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="warning_count" label="Warning" width="100" />
            <el-table-column prop="error_count" label="Error" width="90" />
            <el-table-column prop="created_at" label="上传时间" min-width="170">
              <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
            </el-table-column>
            <el-table-column prop="file_hash" label="文件 Hash" min-width="140">
              <template #default="{ row }">{{ formatShortHash(row.file_hash) }}</template>
            </el-table-column>
            <el-table-column label="操作" width="126" fixed="right">
              <template #default="{ row }">
                <el-button
                  size="small"
                  type="primary"
                  :disabled="row.is_active || row.parse_status === 'failed'"
                  :loading="powerModelActivationLoadingId === row.id"
                  @click="activatePowerModelVersion(row.id)"
                >设为生效</el-button>
              </template>
            </el-table-column>
            <template #empty>暂无功率模型版本历史</template>
          </el-table>
          <div class="history-pagination">
            <el-pagination
              v-if="powerModelVersions.length > powerHistoryPageSize"
              background
              small
              layout="total, prev, pager, next"
              :current-page="powerHistoryPage"
              :page-size="powerHistoryPageSize"
              :total="powerModelVersions.length"
              @current-change="handlePowerHistoryPageChange"
            />
          </div>
        </el-tab-pane>
      </el-tabs>
    </section>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  activatePlanPowerModelVersion,
  fetchPlanBomUploadHistory,
  fetchPlanPowerModelVersions,
  uploadPlanBomExcel,
  uploadPlanPowerModel,
  type PlanBomUploadHistoryItem,
  type PlanBomUploadHistoryResponse,
  type PlanPowerModelVersionListResponse,
  type PlanPowerModelVersionSummary,
} from '@/api/planBom'

interface UploadResult {
  success?: boolean
  message?: string
  parsed_orders_count?: number
  parsed_materials_count?: number
  warning_count?: number
  error_count?: number
  next_action?: string
}

interface PowerModelUploadResult {
  success?: boolean
  message?: string
  version?: {
    id?: number
    parse_status?: string
    is_active?: boolean
    error_count?: number
  }
  detail?: {
    sheet_count?: number
    issues?: Array<Record<string, unknown>>
  }
}

const fileInputRef = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const uploadError = ref('')
const uploadSuccessMessage = ref('')
const uploadResult = ref<UploadResult | null>(null)
const bomUploadProgress = ref(0)

const powerModelFileInputRef = ref<HTMLInputElement | null>(null)
const powerModelSelectedFile = ref<File | null>(null)
const powerModelUploading = ref(false)
const powerModelUploadError = ref('')
const powerModelUploadSuccessMessage = ref('')
const uploadPowerModelResult = ref<PowerModelUploadResult | null>(null)
const powerModelUploadProgress = ref(0)

const historyLoading = ref(false)
const historyError = ref('')
const bomUploadHistory = ref<PlanBomUploadHistoryItem[]>([])
const powerModelVersions = ref<PlanPowerModelVersionSummary[]>([])
const powerModelActivationLoadingId = ref<number | null>(null)
const historyActiveTab = ref<'bom_upload_history' | 'power_model_versions'>('bom_upload_history')
const bomHistoryPage = ref(1)
const powerHistoryPage = ref(1)
const bomHistoryPageSize = 8
const powerHistoryPageSize = 8

const activePowerModelVersion = computed(() => powerModelVersions.value.find((item) => item.is_active) || null)

const hasUploadFeedback = computed(
  () => Boolean(uploadSuccessMessage.value || uploadError.value || powerModelUploadSuccessMessage.value || powerModelUploadError.value || uploadResult.value || uploadPowerModelResult.value),
)

/** 功率模型结果卡下一步提示，避免解析失败版本被误读为已生效。 */
const powerModelResultNextAction = computed(() => {
  const result = uploadPowerModelResult.value
  if (!result) return ''
  if (isPowerModelImportFailed(result)) return '已保留历史，未设为生效'
  if (result.version?.is_active) return '已默认生效，可在历史中切换'
  return '已入库，可在历史中设为生效'
})

/** 页面只保留两个主指标，避免指标卡过多导致用户看不出重点。 */
const primaryOverviewCards = computed(() => [
  {
    label: 'BOM 上传批次',
    value: String(bomUploadHistory.value.length),
    description: bomUploadHistory.value.length ? '历史可分页查看' : '等待首次导入',
    tone: 'blue',
  },
  {
    label: '当前生效模型',
    value: activePowerModelVersion.value ? `#${activePowerModelVersion.value.id}` : '未设置',
    description: activePowerModelVersion.value?.business_version_label || activePowerModelVersion.value?.file_name || '上传后可生效',
    tone: activePowerModelVersion.value ? 'violet' : 'amber',
  },
])

/** 次要信息改为轻量 chip，既保留状态又不制造额外指标压力。 */
const secondaryStatusChips = computed(() => {
  const powerIssueCount = powerModelVersions.value.reduce((sum, item) => sum + (item.warning_count || 0) + (item.error_count || 0), 0)
  return [
    { label: '文件隔离', value: 'BOM / 功率模型', tone: 'neutral' },
    { label: '功率模型版本', value: `${powerModelVersions.value.length} 个`, tone: 'violet' },
    { label: '解析提示', value: powerIssueCount ? `${powerIssueCount} 项` : '正常', tone: powerIssueCount ? 'amber' : 'mint' },
  ]
})

const pagedBomUploadHistory = computed(() => paginateHistory(bomUploadHistory.value, bomHistoryPage.value, bomHistoryPageSize))
const pagedPowerModelVersions = computed(() => paginateHistory(powerModelVersions.value, powerHistoryPage.value, powerHistoryPageSize))

onMounted(() => {
  void loadUploadHistory()
})

/** 记录用户选择的 BOM 文件，实际解析仍由后端上传接口完成。 */
function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] || null
  uploadError.value = ''
  uploadSuccessMessage.value = ''
  uploadResult.value = null
  bomUploadProgress.value = 0
}

/** 根据浏览器上报的百分比更新 BOM 上传进度，限制在 0-99，成功响应后再置 100。 */
function handleBomUploadProgress(percentage: number) {
  bomUploadProgress.value = Math.max(0, Math.min(99, percentage))
}

/** 上传 BOM Excel 到真实后端接口，不在前端伪造解析结果。 */
async function uploadFile() {
  if (!selectedFile.value || uploading.value) return
  uploading.value = true
  uploadError.value = ''
  uploadSuccessMessage.value = ''
  uploadResult.value = null
  bomUploadProgress.value = 0
  try {
    const resp = await uploadPlanBomExcel(selectedFile.value, {
      source: 'trial_run_ui',
      overwrite: true,
      remark: '业务试运行页面上传',
      onUploadProgress: handleBomUploadProgress,
    })
    uploadResult.value = unwrapResponseData<UploadResult>(resp)
    bomUploadProgress.value = 100
    void loadUploadHistory()
    if (uploadResult.value?.success === false) {
      uploadError.value = `BOM 上传失败：${uploadResult.value.message || '请检查文件内容。'}`
      return
    }
    uploadSuccessMessage.value = `BOM Excel 上传成功：${uploadResult.value?.message || '已完成解析。'}`
  } catch (error) {
    uploadError.value = `BOM 上传失败：${extractUploadErrorMessage(error)}`
  } finally {
    uploading.value = false
  }
}

/** 记录用户选择的功率模型文件，并清空上一次上传结果。 */
function handlePowerModelFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  powerModelSelectedFile.value = input.files?.[0] || null
  powerModelUploadError.value = ''
  powerModelUploadSuccessMessage.value = ''
  uploadPowerModelResult.value = null
  powerModelUploadProgress.value = 0
}

/** 根据浏览器上报的百分比更新功率模型上传进度，限制在 0-99，成功响应后再置 100。 */
function handlePowerModelUploadProgress(percentage: number) {
  powerModelUploadProgress.value = Math.max(0, Math.min(99, percentage))
}

/** 上传功率模型 xlsm 到后端版本化导入接口；临时管理令牌已移除，权限后续由用户模块统一控制。 */
async function uploadPowerModelFile() {
  if (!powerModelSelectedFile.value || powerModelUploading.value) return
  powerModelUploading.value = true
  powerModelUploadError.value = ''
  powerModelUploadSuccessMessage.value = ''
  uploadPowerModelResult.value = null
  powerModelUploadProgress.value = 0
  try {
    const resp = await uploadPlanPowerModel(powerModelSelectedFile.value, {
      onUploadProgress: handlePowerModelUploadProgress,
    })
    uploadPowerModelResult.value = unwrapResponseData<PowerModelUploadResult>(resp)
    if (isPowerModelImportFailed(uploadPowerModelResult.value)) {
      powerModelUploadProgress.value = Math.max(powerModelUploadProgress.value, 99)
      void loadUploadHistory()
      powerModelUploadError.value = `功率模型解析失败：${uploadPowerModelResult.value.message || '该版本已保留历史，但不会设为生效版本。'}`
      return
    }
    powerModelUploadProgress.value = 100
    void loadUploadHistory()
    powerModelUploadSuccessMessage.value = `功率模型上传成功：${uploadPowerModelResult.value?.message || '已完成版本化导入。'}`
  } catch (error) {
    powerModelUploadError.value = `功率模型上传失败：${extractUploadErrorMessage(error)}`
  } finally {
    powerModelUploading.value = false
  }
}

/** 查询 BOM 文件上传历史和功率模型版本历史，用于页面“历史查看”。 */
async function loadUploadHistory() {
  historyLoading.value = true
  historyError.value = ''
  try {
    const [bomResp, powerResp] = await Promise.all([
      fetchPlanBomUploadHistory(50),
      fetchPlanPowerModelVersions(),
    ])
    const bomPayload = unwrapResponseData<PlanBomUploadHistoryResponse>(bomResp)
    const powerPayload = unwrapResponseData<PlanPowerModelVersionListResponse>(powerResp)
    bomUploadHistory.value = bomPayload.items || []
    powerModelVersions.value = powerPayload.items || []
    bomHistoryPage.value = normalizeCurrentPage(bomUploadHistory.value.length, bomHistoryPage.value, bomHistoryPageSize)
    powerHistoryPage.value = normalizeCurrentPage(powerModelVersions.value.length, powerHistoryPage.value, powerHistoryPageSize)
  } catch {
    historyError.value = '上传历史加载失败：请稍后重试或检查服务状态'
  } finally {
    historyLoading.value = false
  }
}

/** 手动设置某个功率模型版本生效，失败版本由后端拒绝，前端也做禁用提示。 */
async function activatePowerModelVersion(versionId: number) {
  if (powerModelActivationLoadingId.value !== null) return
  powerModelActivationLoadingId.value = versionId
  historyError.value = ''
  try {
    const activatedVersion = unwrapResponseData<PlanPowerModelVersionSummary>(await activatePlanPowerModelVersion(versionId))
    powerModelUploadSuccessMessage.value = `功率模型版本 ${activatedVersion.id || versionId} 已设为当前生效。`
    await loadUploadHistory()
  } catch (error) {
    historyError.value = `功率模型版本生效失败：${extractUploadErrorMessage(error)}`
  } finally {
    powerModelActivationLoadingId.value = null
  }
}

/** 兼容后端 ApiResponse 包装和直接 payload 两种返回。 */
function unwrapResponseData<T>(response: unknown): T {
  const maybeResponse = response as any
  if (maybeResponse?.code !== undefined && maybeResponse.code !== 0) {
    throw new Error(maybeResponse?.message || '后端接口返回失败。')
  }
  if (maybeResponse?.success === false) {
    throw new Error(maybeResponse?.message || '后端接口返回失败。')
  }
  if (maybeResponse?.data === null) {
    throw new Error(maybeResponse?.message || '后端接口未返回有效数据。')
  }
  return (maybeResponse?.data || maybeResponse) as T
}

/** 判断功率模型导入是否为业务失败，防止解析失败版本被误提示为成功。 */
function isPowerModelImportFailed(result: PowerModelUploadResult | null) {
  const version = result?.version
  return result?.success === false || version?.parse_status === 'failed' || Boolean(version?.error_count)
}

/** 提取上传失败提示，优先展示后端返回的业务 message/detail。 */
function extractUploadErrorMessage(error: unknown) {
  const maybeError = error as any
  return (
    maybeError?.response?.data?.message ||
    maybeError?.response?.data?.detail ||
    maybeError?.message ||
    '上传失败，请稍后重试。'
  )
}

function formatFileSize(size: number) {
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}

/** 格式化历史记录时间，保证空值或非法值不会打断页面展示。 */
function formatDate(value?: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleString('zh-CN', { hour12: false })
}

/** 展示短 hash，既能追溯也避免表格过宽。 */
function formatShortHash(value?: string | null) {
  if (!value) return '-'
  return value.length > 12 ? `${value.slice(0, 12)}...` : value
}

/** 根据后端状态选择 Element Plus 标签色。 */
function statusTagType(status?: string) {
  if (status === 'success') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'failed' || status === 'error') return 'danger'
  return 'info'
}

/** 格式化当前生效功率模型标签。 */
function formatPowerVersionLabel(version?: PlanPowerModelVersionSummary | null) {
  if (!version) return '暂无生效版本'
  return `#${version.id} ${version.business_version_label || version.file_name}`
}

/** 对历史数组做前端分页，后端仍保留真实历史接口作为事实来源。 */
function paginateHistory<T>(items: T[], page: number, pageSize: number) {
  const start = (page - 1) * pageSize
  return items.slice(start, start + pageSize)
}

/** 历史记录刷新后矫正当前页，避免删除或过滤后停留在空页。 */
function normalizeCurrentPage(total: number, currentPage: number, pageSize: number) {
  const maxPage = Math.max(1, Math.ceil(total / pageSize))
  return Math.min(Math.max(1, currentPage), maxPage)
}

/** 切换 BOM 上传历史分页。 */
function handleBomHistoryPageChange(page: number) {
  bomHistoryPage.value = page
}

/** 切换功率模型版本历史分页。 */
function handlePowerHistoryPageChange(page: number) {
  powerHistoryPage.value = page
}
</script>

<style scoped>
.bom-page {
  width: 100%;
  max-width: 1180px;
  height: calc(100vh - 64px);
  margin: 0 auto;
  padding: 32px;
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 18px;
  overflow-y: auto;
  overflow-x: hidden;
  font-size: 14px;
  color: var(--text-main);
}

.page-head,
.upload-zone-card,
.history-panel,
.result-card,
.overview-card {
  min-width: 0;
  border: 1px solid rgba(15, 23, 42, 0.08);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: var(--enterprise-ring), var(--enterprise-card-shadow);
}

.enterprise-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 420px);
  gap: 28px;
  padding: 34px;
  background:
    radial-gradient(circle at 12% 0%, var(--accent-blue-soft), transparent 28%),
    radial-gradient(circle at 94% 12%, var(--accent-violet-soft), transparent 30%),
    linear-gradient(135deg, rgba(255, 255, 255, 0.98), rgba(247, 247, 248, 0.92));
}

.page-kicker,
.section-eyebrow,
.guide-label {
  display: inline-flex;
  align-items: center;
  color: var(--enterprise-primary);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.hero-copy h1,
.panel-head h2,
.history-head h2,
.history-toolbar h3 {
  margin: 0;
  color: #0f172a;
}

.hero-copy h1 {
  margin-top: 8px;
  font-size: clamp(28px, 3vw, 40px);
  font-weight: 650;
  letter-spacing: -0.04em;
  line-height: 1.12;
}

.hero-copy p,
.panel-head p,
.history-head p,
.history-tip,
.guide-steps span,
.overview-card em,
.file-info span,
.next-action {
  color: #64748b;
  line-height: 1.55;
}

.hero-copy p {
  max-width: 520px;
  margin: 14px 0 0;
  font-size: 16px;
}

.hero-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 18px;
}

.hero-tags span,
.upload-type-badge {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border-radius: 999px;
  background: #f4f4f5;
  color: #3f3f46;
  font-size: 12px;
  font-weight: 600;
}

.hero-tags span:nth-child(1) {
  background: var(--accent-blue-soft);
  color: #1d4ed8;
}

.hero-tags span:nth-child(2) {
  background: var(--accent-amber-soft);
  color: #92400e;
}

.hero-tags span:nth-child(3) {
  background: var(--accent-violet-soft);
  color: #6d28d9;
}

.primary-overview {
  display: grid;
  min-width: 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  align-self: stretch;
}

.secondary-status-strip {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  min-width: 0;
}

.status-chip {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  min-height: 34px;
  padding: 0 12px;
  border: 1px solid #eceff3;
  border-radius: 999px;
  background: #ffffff;
  color: #64748b;
  box-shadow: var(--enterprise-ring);
  font-size: 12px;
}

.status-chip b {
  color: #111827;
  font-weight: 650;
}

.status-chip--violet {
  border-color: rgba(139, 92, 246, 0.22);
  background: var(--accent-violet-soft);
}

.status-chip--amber {
  border-color: rgba(245, 158, 11, 0.24);
  background: var(--accent-amber-soft);
}

.status-chip--mint {
  border-color: rgba(20, 184, 166, 0.22);
  background: var(--accent-mint-soft);
}

.overview-card {
  position: relative;
  overflow: hidden;
  padding: 16px 18px;
}

.overview-card::before {
  content: '';
  position: absolute;
  inset: 0 auto 0 0;
  width: 4px;
  background: #cbd5e1;
}

.overview-card--blue::before {
  background: var(--accent-blue);
}

.overview-card--violet::before,
.overview-card--power::before {
  background: var(--accent-violet);
}

.overview-card--success::before {
  background: var(--accent-mint);
}

.overview-card--warning::before,
.overview-card--amber::before {
  background: var(--accent-amber);
}

.overview-card span,
.summary-grid span {
  display: block;
  color: #64748b;
  font-size: 12px;
}

.overview-card strong {
  display: block;
  margin-top: 8px;
  color: #0f172a;
  font-size: 26px;
  font-weight: 650;
  letter-spacing: -0.04em;
}

.overview-card em {
  display: block;
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-style: normal;
  font-size: 12px;
}

.hero-metric-strip .overview-card em {
  display: none;
}

.upload-zone-grid {
  display: grid;
  min-width: 0;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 18px;
}

.upload-zone-card {
  padding: 22px;
}

.upload-zone-card--power {
  background:
    linear-gradient(180deg, rgba(251, 255, 252, 0.98), rgba(255, 255, 255, 0.96));
}

.panel-head,
.history-head,
.history-toolbar {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel-head {
  margin-bottom: 18px;
}

.panel-head h2,
.history-head h2 {
  margin-top: 4px;
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -0.02em;
}

.panel-head p,
.history-head p,
.history-tip {
  margin: 6px 0 0;
  font-size: 13px;
}

.upload-type-badge {
  flex: 0 0 auto;
  background: #f1f5f9;
  color: #334155;
}

.upload-type-badge--power {
  background: rgba(47, 110, 66, 0.1);
  color: var(--enterprise-primary);
}

.upload-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.upload-card--stacked {
  align-items: stretch;
  flex-direction: column;
}

.upload-main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
  border-radius: 14px;
  border: 1px dashed rgba(100, 116, 139, 0.32);
  background: #f8fafc;
  padding: 14px;
}

.native-file-input {
  width: 250px;
  max-width: 45%;
  color: #475569;
  font-size: 13px;
}

.file-info {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.file-info strong {
  overflow: hidden;
  color: #0f172a;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.upload-progress {
  display: grid;
  gap: 8px;
  margin-top: 14px;
  color: #475569;
  font-size: 13px;
}

.feedback-stack {
  display: grid;
  min-width: 0;
  gap: 12px;
}

.result-card {
  padding: 20px;
}

.result-title {
  color: #0f172a;
  font-weight: 650;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.summary-grid div {
  border: 1px solid #eef2f7;
  border-radius: 14px;
  padding: 12px;
  background: #f8fafc;
}

.summary-grid strong {
  display: block;
  margin-top: 6px;
  color: #0f172a;
  font-size: 22px;
  font-weight: 650;
}

.next-action {
  margin: 12px 0 0;
  color: var(--enterprise-primary);
}

.power-result-card {
  border-color: rgba(47, 110, 66, 0.2);
  background: #fbfffc;
}

.history-panel {
  display: grid;
  gap: 16px;
  padding: 22px;
}

.history-tabs {
  min-width: 0;
  --el-color-primary: var(--enterprise-primary);
}

:deep(.el-tab-pane) {
  min-width: 0;
  overflow-x: auto;
}

.history-toolbar {
  margin-bottom: 12px;
}

.history-pagination {
  display: flex;
  justify-content: flex-end;
  min-height: 32px;
  margin-top: 14px;
}

:deep(.el-table) {
  border-radius: 14px;
  overflow: hidden;
}

:deep(.el-table th.el-table__cell) {
  background: #f8fafc;
  color: #475569;
  font-weight: 650;
}

:deep(.el-tabs__item) {
  font-weight: 600;
}

@media (max-width: 1180px) {
  .bom-page {
    max-width: none;
  }
}

@media (max-width: 980px) {
  .enterprise-hero,
  .upload-zone-grid,
  .primary-overview {
    grid-template-columns: 1fr;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .bom-page {
    padding: 20px 16px 28px;
  }

  .panel-head,
  .history-head,
  .history-toolbar,
  .upload-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .native-file-input {
    width: 100%;
    max-width: 100%;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
