<template>
  <section class="bom-page bom-page--clean">
    <section class="bom-hero-card bom-management-panel" aria-label="BOM 数据管理概览">
      <header class="page-head enterprise-hero">
        <div class="hero-copy">
          <div class="page-kicker">数据工作台</div>
          <h1>BOM 文件与功率模型</h1>
          <p>导入与历史分开，先选文件再上传</p>
          <div class="compact-status-row" aria-label="关键状态">
            <span>文件隔离</span>
            <span>历史 {{ bomUploadHistory.length }} 批</span>
            <span>模型{{ activePowerModelVersion ? '已生效' : '未设置' }}</span>
          </div>
        </div>
        <section class="primary-overview" aria-label="核心状态">
          <article v-for="item in primaryOverviewCards" :key="item.label" class="overview-card" :class="`overview-card--${item.tone}`">
            <div class="overview-card__top">
              <span class="overview-card__label">{{ item.label }}</span>
              <i class="overview-card__badge">{{ item.badge }}</i>
            </div>
            <strong class="overview-card__value" :title="item.value">{{ item.value }}</strong>
            <em class="overview-card__desc" :title="item.description">{{ item.description }}</em>
          </article>
        </section>
      </header>
    </section>

    <section class="bom-workspace-card" aria-label="BOM 上传与历史工作区">
      <div class="workspace-card-head">
        <div>
          <span class="section-eyebrow">操作中心</span>
          <h2>数据上传与历史回溯</h2>
        </div>
        <span class="workspace-card-note">上传和历史分区处理</span>
      </div>

      <el-tabs v-model="mainActiveTab" class="management-tabs management-tabs--segmented">
        <el-tab-pane label="上传数据" name="data_import">
          <template #label>
            <span class="workspace-tab-label"><span class="workspace-tab-dot workspace-tab-dot--upload"></span>上传数据</span>
          </template>
          <section class="upload-zone-grid" aria-label="上传操作区">
            <article class="upload-zone-card">
              <div class="panel-head">
                <div>
                  <span class="section-eyebrow">BOM Excel</span>
                  <h2>BOM 文件上传</h2>
                  <p>支持 .xls / .xlsx / .xlsm，可批量导入</p>
                </div>
                <span class="upload-type-badge">BOM</span>
              </div>
              <div class="upload-card">
                <div class="upload-main upload-dropzone">
                  <input
                    ref="fileInputRef"
                    class="native-file-input native-file-input--hidden"
                    type="file"
                    accept=".xls,.xlsx,.xlsm"
                    multiple
                    aria-label="选择 BOM Excel 文件"
                    @change="handleFileChange"
                  />
                  <el-button class="file-picker-button" plain @click="openBomFilePicker">选择 BOM 文件</el-button>
                  <div class="file-info">
                    <strong>{{ selectedBomFileSummary }}</strong>
                    <span>{{ selectedBomFileSizeSummary }}</span>
                  </div>
                </div>
                <el-button
                  class="upload-action-button"
                  type="primary"
                  :disabled="!selectedFiles.length"
                  :loading="uploading"
                  @click="uploadFile"
                >{{ selectedFiles.length ? '上传并解析' : '选择文件后可上传' }}</el-button>
              </div>
              <div v-if="uploading || bomUploadProgress > 0" class="upload-progress">
                <span>BOM 上传进度：{{ bomUploadProgress }}%</span>
                <el-progress :percentage="bomUploadProgress" />
              </div>
            </article>

            <article class="upload-zone-card upload-zone-card--power">
              <div class="panel-head">
                <div>
                  <span class="section-eyebrow">模型版本</span>
                  <h2>功率模型上传</h2>
                  <p>仅支持 .xlsm，生成模型版本</p>
                </div>
                <span class="upload-type-badge upload-type-badge--power">模型</span>
              </div>
              <div class="upload-card upload-card--stacked">
                <div class="upload-main upload-dropzone">
                  <input
                    ref="powerModelFileInputRef"
                    class="native-file-input native-file-input--hidden"
                    type="file"
                    accept=".xlsm"
                    aria-label="选择功率模型 xlsm 文件"
                    @change="handlePowerModelFileChange"
                  />
                  <el-button class="file-picker-button file-picker-button--power" plain @click="openPowerModelFilePicker">选择模型文件</el-button>
                  <div class="file-info">
                    <strong>{{ powerModelSelectedFile?.name || '请选择功率模型 xlsm 文件' }}</strong>
                    <span>{{ powerModelSelectedFile ? formatFileSize(powerModelSelectedFile.size) : '生成模型版本' }}</span>
                  </div>
                </div>
                <el-button
                  class="upload-action-button"
                  type="primary"
                  :disabled="!powerModelSelectedFile"
                  :loading="powerModelUploading"
                  @click="uploadPowerModelFile"
                >{{ powerModelSelectedFile ? '上传功率模型' : '选择模型后可上传' }}</el-button>
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
                  <span>提醒数</span>
                  <strong>{{ uploadResult.warning_count ?? 0 }}</strong>
                </div>
                <div>
                  <span>错误数</span>
                  <strong>{{ uploadResult.error_count ?? 0 }}</strong>
                </div>
              </div>
              <p class="next-action">{{ uploadResult.next_action || '上传完成，可进入智能问答' }}</p>
              <div v-if="uploadBatchResult?.items?.length" class="batch-result-list">
                <div class="result-subtitle">逐文件结果</div>
                <el-table :data="uploadBatchResult.items" size="small" stripe>
                  <el-table-column prop="file_name" label="文件名" min-width="220" show-overflow-tooltip />
                  <el-table-column prop="success" label="状态" width="96">
                    <template #default="{ row }">
                      <el-tag :type="row.success ? 'success' : 'danger'">{{ row.success ? '成功' : '失败' }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="parsed_orders_count" label="订单数" width="92" />
                  <el-table-column prop="parsed_materials_count" label="物料数" width="92" />
                  <el-table-column prop="message" label="结果说明" min-width="220" show-overflow-tooltip />
                </el-table>
              </div>
            </div>

            <div v-if="uploadPowerModelResult" class="result-card power-result-card">
              <div class="result-title">{{ uploadPowerModelResult.message || '功率模型上传处理完成' }}</div>
              <div class="summary-grid">
                <div>
                  <span>版本编号</span>
                  <strong>{{ uploadPowerModelResult.version?.id ?? '-' }}</strong>
                </div>
                <div>
                  <span>解析状态</span>
                  <strong>{{ formatStatusLabel(uploadPowerModelResult.version?.parse_status) }}</strong>
                </div>
                <div>
                  <span>是否生效</span>
                  <strong>{{ uploadPowerModelResult.version?.is_active ? '当前生效' : '未生效' }}</strong>
                </div>
                <div>
                  <span>问题数</span>
                  <strong>{{ uploadPowerModelResult.detail?.issues?.length ?? uploadPowerModelResult.version?.error_count ?? '-' }}</strong>
                </div>
              </div>
              <p class="next-action">{{ powerModelResultNextAction }}</p>
            </div>
          </section>
        </el-tab-pane>

        <el-tab-pane label="查看历史" name="history">
          <template #label>
            <span class="workspace-tab-label"><span class="workspace-tab-dot workspace-tab-dot--history"></span>查看历史</span>
          </template>
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
                      <el-tag :type="statusTagType(row.status)">{{ formatStatusLabel(row.status) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="total_headers" label="订单数" width="90" />
                  <el-table-column prop="total_lines" label="物料数" width="90" />
                  <el-table-column prop="source_tag" label="来源" min-width="120" show-overflow-tooltip>
                    <template #default="{ row }">{{ formatSourceTagLabel(row.source_tag) }}</template>
                  </el-table-column>
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
                    <h3>功率模型版本</h3>
                    <p class="history-tip">生效：{{ formatPowerVersionLabel(activePowerModelVersion) }}</p>
                  </div>
                </div>
                <el-table v-loading="historyLoading" :data="pagedPowerModelVersions" border stripe size="small" table-layout="auto">
                  <el-table-column prop="id" label="版本编号" width="90" />
                  <el-table-column prop="file_name" label="功率文件" min-width="240" show-overflow-tooltip />
                  <el-table-column prop="business_version_label" label="业务版本" min-width="140" show-overflow-tooltip />
                  <el-table-column prop="parse_status" label="解析状态" width="110">
                    <template #default="{ row }">
                      <el-tag :type="statusTagType(row.parse_status)">{{ formatStatusLabel(row.parse_status) }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="is_active" label="生效状态" width="110">
                    <template #default="{ row }">
                      <el-tag v-if="row.is_active" type="success">当前生效</el-tag>
                      <el-tag v-else type="info">未生效</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="warning_count" label="提醒数" width="100" />
                  <el-table-column prop="error_count" label="错误数" width="90" />
                  <el-table-column prop="created_at" label="上传时间" min-width="170">
                    <template #default="{ row }">{{ formatDate(row.created_at) }}</template>
                  </el-table-column>
                  <el-table-column prop="file_hash" label="文件指纹" min-width="140">
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
  uploadPlanBomExcelBatch,
  uploadPlanPowerModel,
  type PlanBomUploadHistoryItem,
  type PlanBomUploadHistoryResponse,
  type PlanPowerModelVersionListResponse,
  type PlanPowerModelVersionSummary,
} from '@/api/planBom'

interface UploadResult {
  success?: boolean
  message?: string
  file_name?: string
  total_files?: number
  success_count?: number
  failed_count?: number
  parsed_orders_count?: number
  parsed_materials_count?: number
  warning_count?: number
  error_count?: number
  next_action?: string
}

interface UploadBatchResult extends UploadResult {
  items?: UploadResult[]
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
const selectedFiles = ref<File[]>([])
const uploading = ref(false)
const uploadError = ref('')
const uploadSuccessMessage = ref('')
const uploadResult = ref<UploadResult | null>(null)
const uploadBatchResult = ref<UploadBatchResult | null>(null)
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
const mainActiveTab = ref<'data_import' | 'history'>('data_import')
const historyActiveTab = ref<'bom_upload_history' | 'power_model_versions'>('bom_upload_history')
const bomHistoryPage = ref(1)
const powerHistoryPage = ref(1)
const bomHistoryPageSize = 8
const powerHistoryPageSize = 8

const activePowerModelVersion = computed(() => powerModelVersions.value.find((item) => item.is_active) || null)

const hasUploadFeedback = computed(
  () => Boolean(uploadSuccessMessage.value || uploadError.value || powerModelUploadSuccessMessage.value || powerModelUploadError.value || uploadResult.value || uploadBatchResult.value || uploadPowerModelResult.value),
)

/** BOM 文件选择摘要：多文件只展示数量，避免长文件名挤压上传卡片。 */
const selectedBomFileSummary = computed(() => {
  if (!selectedFiles.value.length) return '请选择 1 个或多个 BOM Excel 文件'
  if (selectedFiles.value.length === 1) return selectedFiles.value[0].name
  return `已选择 ${selectedFiles.value.length} 个 BOM Excel 文件`
})

/** BOM 文件大小摘要：批量上传展示总大小，便于业务用户预估等待时间。 */
const selectedBomFileSizeSummary = computed(() => {
  if (!selectedFiles.value.length) return '可用于问答，支持批量上传'
  const totalSize = selectedFiles.value.reduce((sum, file) => sum + file.size, 0)
  return selectedFiles.value.length === 1 ? formatFileSize(totalSize) : `合计 ${formatFileSize(totalSize)}`
})

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
    badge: '历史',
    tone: 'blue',
  },
  {
    label: '当前生效模型',
    value: activePowerModelVersion.value?.business_version_label || activePowerModelVersion.value?.file_name || '未设置',
    description: activePowerModelVersion.value ? `版本编号：#${activePowerModelVersion.value.id}` : '上传后可生效',
    badge: activePowerModelVersion.value ? '生效' : '待设置',
    tone: activePowerModelVersion.value ? 'violet' : 'amber',
  },
])

const pagedBomUploadHistory = computed(() => paginateHistory(bomUploadHistory.value, bomHistoryPage.value, bomHistoryPageSize))
const pagedPowerModelVersions = computed(() => paginateHistory(powerModelVersions.value, powerHistoryPage.value, powerHistoryPageSize))

onMounted(() => {
  void loadUploadHistory()
})

/** 打开隐藏的 BOM 文件选择器，保留原生文件 input 能力，同时让上传卡片视觉更统一。 */
function openBomFilePicker() {
  fileInputRef.value?.click()
}

/** 打开隐藏的功率模型文件选择器，避免原生文件框挤压模型文件名展示。 */
function openPowerModelFilePicker() {
  powerModelFileInputRef.value?.click()
}

/** 记录用户选择的 BOM 文件列表，实际解析仍由后端上传接口完成。 */
function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFiles.value = Array.from(input.files || [])
  uploadError.value = ''
  uploadSuccessMessage.value = ''
  uploadResult.value = null
  uploadBatchResult.value = null
  bomUploadProgress.value = 0
}

/** 根据浏览器上报的百分比更新 BOM 上传进度，限制在 0-99，成功响应后再置 100。 */
function handleBomUploadProgress(percentage: number) {
  bomUploadProgress.value = Math.max(0, Math.min(99, percentage))
}

/** 上传 BOM Excel 到真实后端接口，支持单选和批量多选，不在前端伪造解析结果。 */
async function uploadFile() {
  if (!selectedFiles.value.length || uploading.value) return
  uploading.value = true
  uploadError.value = ''
  uploadSuccessMessage.value = ''
  uploadResult.value = null
  uploadBatchResult.value = null
  bomUploadProgress.value = 0
  try {
    const resp = await uploadPlanBomExcelBatch(selectedFiles.value, {
      source: 'trial_run_ui',
      overwrite: true,
      remark: '业务试运行页面批量上传',
      onUploadProgress: handleBomUploadProgress,
    })
    uploadBatchResult.value = unwrapResponseData<UploadBatchResult>(resp)
    uploadResult.value = uploadBatchResult.value
    bomUploadProgress.value = 100
    void loadUploadHistory()
    const failedCount = uploadBatchResult.value?.failed_count ?? 0
    if (uploadBatchResult.value?.success === false || failedCount > 0) {
      uploadError.value = `BOM 批量上传存在失败：${uploadBatchResult.value?.message || `失败 ${failedCount} 个文件，请查看逐文件结果。`}`
      return
    }
    uploadSuccessMessage.value = `BOM Excel 批量上传成功：${uploadBatchResult.value?.message || '已完成解析。'}`
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

/** 展示短文件指纹，既能追溯也避免表格过宽。 */
function formatShortHash(value?: string | null) {
  if (!value) return '-'
  return value.length > 12 ? `${value.slice(0, 12)}...` : value
}

/** 根据后端状态选择 Element Plus 标签色。 */
function statusTagType(status?: string | null) {
  const normalized = String(status || '').toLowerCase()
  if (['success', 'succeeded', 'created', 'active', 'ok'].includes(normalized)) return 'success'
  if (['warning', 'parsed_with_warnings'].includes(normalized)) return 'warning'
  if (['failed', 'fail', 'error', 'parse_failed'].includes(normalized)) return 'danger'
  return 'info'
}

/** 把后端状态码转换为业务人员可读的中文状态，避免表格直接暴露 success/failed 等技术值。 */
function formatStatusLabel(status?: string | null) {
  const normalized = String(status || '').toLowerCase()
  const statusLabelMap: Record<string, string> = {
    success: '成功',
    succeeded: '成功',
    ok: '成功',
    warning: '需关注',
    parsed_with_warnings: '需关注',
    failed: '失败',
    fail: '失败',
    error: '失败',
    parse_failed: '失败',
    created: '已创建',
    existing: '已存在',
    pending: '待处理',
    running: '处理中',
    processing: '处理中',
    active: '生效中',
  }
  return statusLabelMap[normalized] || (status ? '系统记录' : '-')
}

/** 把导入来源标签转换成业务语言，避免 manual_import_source 一类内部标识出现在历史表。 */
function formatSourceTagLabel(source?: string | null) {
  const normalized = String(source || '').toLowerCase()
  if (!normalized) return '-'
  if (normalized.includes('manual')) return '手动上传'
  if (normalized.includes('batch')) return '批量上传'
  if (normalized.includes('excel') || normalized === 'xls' || normalized === 'xlsx' || normalized === 'xlsm') return 'Excel 导入'
  if (normalized.includes('system')) return '系统导入'
  return /[a-z_]/i.test(normalized) ? '系统记录' : String(source)
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
  display: grid;
  width: 100%;
  max-width: 1220px;
  height: calc(100vh - 64px);
  align-content: start;
  grid-auto-rows: max-content;
  gap: 20px;
  margin: 0 auto;
  padding: 24px 28px 36px;
  overflow-y: auto;
  overflow-x: hidden;
  font-size: 14px;
  color: var(--text-main);
}

.bom-page--clean {
  background: #f7f9fc;
}

.page-head,
.upload-zone-card,
.history-panel,
.result-card,
.overview-card,
.bom-workspace-card {
  min-width: 0;
}

.bom-management-panel,
.bom-workspace-card,
.upload-zone-card,
.result-card,
.overview-card {
  border: 1px solid rgba(15, 23, 42, 0.08);
  background: rgba(255, 255, 255, 0.96);
}

.bom-management-panel,
.bom-workspace-card {
  min-width: 0;
  overflow: hidden;
  border-radius: 20px;
  box-shadow: 0 10px 28px rgba(15, 23, 42, 0.06), var(--enterprise-ring);
}

.bom-hero-card {
  position: relative;
  isolation: isolate;
  background: #ffffff;
}

.bom-workspace-card {
  padding: 20px 22px 24px;
  background: #ffffff;
}

.enterprise-hero {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(360px, 440px);
  align-items: center;
  gap: 24px;
  padding: 24px 28px;
  background: transparent;
}

.workspace-card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 18px;
  margin-bottom: 18px;
  padding: 0 2px;
}

.workspace-card-head h2 {
  margin: 4px 0 0;
  color: #0f172a;
  font-size: 20px;
  font-weight: 650;
  letter-spacing: -0.015em;
}

.workspace-card-note {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(48, 113, 185, 0.12);
  border-radius: 999px;
  background: rgba(48, 113, 185, 0.04);
  color: #3071b9;
  font-size: 12px;
  font-weight: 600;
}

.page-kicker,
.section-eyebrow {
  display: inline-flex;
  align-items: center;
  color: var(--enterprise-primary);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.02em;
}

.hero-copy h1,
.panel-head h2,
.history-head h2,
.history-toolbar h3 {
  margin: 0;
  color: #0f172a;
}

.hero-copy h1 {
  margin-top: 6px;
  font-size: clamp(26px, 2.4vw, 34px);
  font-weight: 700;
  letter-spacing: -0.025em;
  line-height: 1.12;
}

.hero-copy p,
.panel-head p,
.history-head p,
.history-tip,
.overview-card__desc,
.file-info span,
.next-action {
  color: #64748b;
  line-height: 1.55;
}

.hero-copy p {
  max-width: 520px;
  margin: 8px 0 0;
  font-size: 14px;
}

.compact-status-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 14px;
  color: #64748b;
  font-size: 12px;
}

.compact-status-row span,
.upload-type-badge {
  display: inline-flex;
  align-items: center;
  height: 28px;
  padding: 0 10px;
  border: 1px solid rgba(148, 163, 184, 0.22);
  border-radius: 999px;
  background: #ffffff;
  color: #475569;
  font-size: 12px;
  font-weight: 600;
}

.compact-status-row span:first-child {
  border-color: rgba(111, 186, 44, 0.28);
  background: rgba(111, 186, 44, 0.10);
  color: #3f7f18;
}

.primary-overview {
  display: grid;
  min-width: 0;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 14px;
  align-self: stretch;
}

.overview-card {
  position: relative;
  overflow: hidden;
  min-height: 118px;
  padding: 16px;
  border-radius: 16px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.05), var(--enterprise-ring);
}

.overview-card::before {
  content: '';
  position: absolute;
  inset: 0 0 auto;
  height: 3px;
  background: #cbd5e1;
}

.overview-card--blue {
  background: #ffffff;
}

.overview-card--blue::before {
  background: #3071b9;
}

.overview-card--violet,
.overview-card--power {
  background: #ffffff;
}

.overview-card--violet::before,
.overview-card--power::before {
  background: #7c3aed;
}

.overview-card--success::before {
  background: #6fba2c;
}

.overview-card--warning,
.overview-card--amber {
  background: #ffffff;
}

.overview-card--warning::before,
.overview-card--amber::before {
  background: #f59e0b;
}

.overview-card__top {
  position: relative;
  z-index: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.overview-card__label,
.summary-grid span {
  display: block;
  color: #64748b;
  font-size: 13px;
  font-weight: 650;
}

.overview-card__badge {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 9px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.82);
  color: #334155;
  font-size: 12px;
  font-style: normal;
  font-weight: 700;
  box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.18);
}

.overview-card__value {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 14px;
  overflow: hidden;
  color: #0f172a;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: clamp(22px, 2vw, 30px);
  font-weight: 700;
  letter-spacing: -0.025em;
  line-height: 1.08;
}

.overview-card__desc {
  position: relative;
  z-index: 1;
  display: block;
  margin-top: 8px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-style: normal;
  font-size: 13px;
  font-weight: 600;
}

.management-tabs {
  min-width: 0;
  padding: 0;
  --el-color-primary: var(--accent-blue);
}

.management-tabs :deep(.el-tabs__header) {
  margin: 0 0 16px;
}

.management-tabs :deep(.el-tabs__nav-wrap::after),
.management-tabs :deep(.el-tabs__active-bar) {
  display: none;
}

.management-tabs :deep(.el-tabs__nav) {
  display: inline-flex;
  gap: 4px;
  padding: 4px;
  border: 1px solid rgba(48, 113, 185, 0.12);
  border-radius: 14px;
  background: #f1f5f9;
  box-shadow: none;
}

.management-tabs :deep(.el-tabs__item) {
  height: 36px;
  padding: 0 16px;
  border-radius: 10px;
  color: #475569;
  font-size: 14px;
  font-weight: 650;
  transition: background-color 0.18s ease, box-shadow 0.18s ease, color 0.18s ease;
}

.management-tabs :deep(.el-tabs__item:hover) {
  color: #3071b9;
}

.management-tabs :deep(.el-tabs__item.is-active) {
  background: #ffffff;
  color: #3071b9;
  box-shadow: 0 6px 14px rgba(48, 113, 185, 0.10), var(--enterprise-ring);
}

.workspace-tab-label {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.workspace-tab-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: #94a3b8;
}

.workspace-tab-dot--upload {
  background: #3071b9;
}

.workspace-tab-dot--history {
  background: #6fba2c;
}

.management-tabs :deep(.el-tab-pane) {
  min-width: 0;
}

.upload-zone-grid {
  display: grid;
  min-width: 0;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
}

.upload-zone-card {
  display: flex;
  min-height: 320px;
  flex-direction: column;
  padding: 20px;
  border-radius: 18px;
  background: #ffffff;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.05), var(--enterprise-ring);
}

.upload-zone-card--power {
  background: #ffffff;
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
  margin-bottom: 16px;
}

.panel-head h2,
.history-head h2 {
  margin-top: 4px;
  font-size: 20px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.panel-head p,
.history-head p,
.history-tip {
  margin: 6px 0 0;
  font-size: 14px;
}

.upload-type-badge {
  flex: 0 0 auto;
  background: #f1f5f9;
  color: #334155;
}

.upload-type-badge--power {
  background: var(--accent-violet-soft);
  color: #6d28d9;
}

.upload-card {
  display: grid;
  gap: 20px;
  flex: 1;
}

.upload-card--stacked {
  align-items: stretch;
}

.upload-main {
  display: flex;
  align-items: flex-start;
  flex-direction: column;
  justify-content: center;
  gap: 16px;
  min-height: 144px;
  min-width: 0;
  border-radius: 14px;
  border: 1px dashed rgba(100, 116, 139, 0.34);
  background: #f8fafc;
  padding: 18px 20px;
}

.upload-dropzone:hover {
  border-color: rgba(48, 113, 185, 0.34);
  background: #f6faff;
}

.native-file-input {
  width: 250px;
  max-width: 45%;
  color: #475569;
  font-size: 13px;
}

.native-file-input--hidden {
  display: none;
}

.file-picker-button {
  flex: 0 0 auto;
  border-color: rgba(37, 99, 235, 0.22);
  background: #ffffff;
  color: var(--accent-blue);
  font-weight: 650;
  box-shadow: 0 4px 12px rgba(48, 113, 185, 0.08);
}

.file-picker-button--power {
  border-color: rgba(139, 92, 246, 0.24);
  color: #6d28d9;
}

.file-info {
  display: grid;
  gap: 4px;
  width: 100%;
  min-width: 0;
}

.file-info strong {
  overflow: hidden;
  color: #0f172a;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 16px;
}

.upload-progress {
  display: grid;
  gap: 8px;
  margin-top: 12px;
  color: #475569;
  font-size: 13px;
}

.upload-action-button {
  justify-self: flex-start;
  min-width: 160px;
  height: 38px;
  border-radius: 10px;
  font-weight: 650;
}

.upload-action-button.is-disabled,
.upload-action-button.is-disabled:hover,
.upload-action-button.is-disabled:focus {
  border-color: #e2e8f0;
  background: #f1f5f9;
  color: #94a3b8;
}

.feedback-stack {
  display: grid;
  min-width: 0;
  gap: 10px;
  margin-top: 14px;
}

.result-card {
  padding: 16px;
  border-radius: 14px;
  box-shadow: none;
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
  border-radius: 12px;
  padding: 10px;
  background: #f8fafc;
}

.summary-grid strong {
  display: block;
  margin-top: 4px;
  color: #0f172a;
  font-size: 20px;
  font-weight: 650;
}

.next-action {
  margin: 12px 0 0;
  color: var(--enterprise-primary);
}

.batch-result-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.result-subtitle {
  color: #334155;
  font-size: 13px;
  font-weight: 650;
}

.power-result-card {
  border-color: rgba(139, 92, 246, 0.22);
  background: #fbfaff;
}

.history-panel {
  display: grid;
  gap: 14px;
}

.history-tabs {
  min-width: 0;
  --el-color-primary: var(--accent-blue);
}

.history-tabs :deep(.el-tab-pane) {
  min-width: 0;
  overflow-x: auto;
}

.history-toolbar {
  margin-bottom: 10px;
}

.history-pagination {
  display: flex;
  justify-content: flex-end;
  min-height: 32px;
  margin-top: 14px;
}

:deep(.el-table) {
  border-radius: 12px;
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
  .upload-zone-grid {
    grid-template-columns: 1fr;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .bom-page {
    padding: 16px;
  }

  .enterprise-hero,
  .management-tabs {
    padding-right: 16px;
    padding-left: 16px;
  }

  .enterprise-hero,
  .primary-overview {
    grid-template-columns: 1fr;
  }

  .panel-head,
  .history-head,
  .history-toolbar,
  .upload-card,
  .upload-card--stacked,
  .upload-main {
    align-items: flex-start;
    flex-direction: column;
  }

  .upload-card :deep(.el-button),
  .upload-card--stacked :deep(.el-button) {
    width: 100%;
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
