<template>
  <div class="bom-page">
<!--    <section class="page-intro">-->
<!--      <div class="page-intro__copy">-->
<!--        <div class="page-intro__tag">业务查询</div>-->
<!--        <h2 class="page-intro__title">BOM 明细查询</h2>-->
<!--        <p class="page-intro__desc">用于快速查看订单命中的版本信息与 5 类核心材料，方便业务查询、结果核对和现场汇报。</p>-->
<!--      </div>-->
<!--      <div class="page-intro__note">支持订单号、评审号、订单名称三种查询方式。</div>-->
<!--    </section>-->

    <div class="page-layout">
      <div class="page-main">
        <section class="page-card qa-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">BOM 问答与上传</h3>
              <p class="section-subtitle">支持自然语言查询、业务化追问、拒答解释，以及单个 BOM Excel 上传导入。</p>
            </div>
          </div>

          <div class="qa-actions">
            <el-input
              v-model="qaQuestion"
              type="textarea"
              :rows="3"
              placeholder="例如：订单00104的玻璃、间隙贴膜、焊带、汇流条、接线盒的规格描述？"
            />
            <div class="qa-actions__footer">
              <el-space wrap>
                <el-button type="primary" :loading="qaLoading" round @click="submitQaQuestion">发送问题</el-button>
                <input type="file" accept=".xls,.xlsx,.xlsm" @change="handleUploadInputChange" />
              </el-space>
              <span class="query-actions__hint">上传接口：POST /api/v1/plan-bom/upload</span>
            </div>
          </div>

          <div v-if="uploadResult" class="qa-result">
            <div class="qa-result__title">上传结果</div>
            <div>{{ uploadResult.message || '已返回上传结果' }}</div>
            <div class="mono-block">{{ JSON.stringify(uploadResult, null, 2) }}</div>
          </div>

          <div v-if="qaResult" class="qa-result">
            <div class="qa-result__title">
              {{ qaResult.presentation?.title || qaResult.status?.message || 'BOM 问答结果' }}
              <el-tag size="small" round>{{ qaResult.classification }}</el-tag>
            </div>
            <div class="qa-result__answer">{{ qaResult.presentation?.answer || qaResult.answer_summary }}</div>
            <el-table
              v-if="qaPresentationRows.length"
              class="material-table"
              :data="qaPresentationRows"
              stripe
              size="small"
            >
              <el-table-column
                v-for="column in qaPresentationColumns"
                :key="column"
                :prop="column"
                :label="column"
                min-width="150"
                show-overflow-tooltip
              />
            </el-table>
          </div>

          <el-alert
            v-if="qaError"
            class="candidate-alert"
            type="error"
            :closable="false"
            show-icon
            :title="qaError"
          />
        </section>

        <section class="page-card query-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">查询条件</h3>
              <p class="section-subtitle">
                支持订单号、评审号、订单名称三种入口。遇到多个可能结果时，系统会先请你确认候选项。
              </p>
            </div>
            <el-space wrap class="example-actions">
              <el-button plain round @click="fillExample('2026-00104', '', '')">订单号示例</el-button>
              <el-button plain round @click="fillExample('', 'COEXITO-2026-00067', '')">评审号示例</el-button>
              <el-button plain round @click="fillExample('', '', 'Synapsun')">订单名称示例</el-button>
            </el-space>
          </div>

          <el-form
            ref="formRef"
            :model="formData"
            :rules="formRules"
            label-position="top"
            @submit.prevent
          >
            <div class="query-grid">
              <el-form-item label="订单号" prop="order_no" class="query-grid__item">
                <el-input
                  v-model="formData.order_no"
                  clearable
                  placeholder="例如：2026-00104 或 00106"
                />
              </el-form-item>
              <el-form-item label="评审号" prop="review_no" class="query-grid__item">
                <el-input
                  v-model="formData.review_no"
                  clearable
                  placeholder="例如：COEXITO-2026-00067"
                />
              </el-form-item>
              <el-form-item label="订单名称" prop="order_name" class="query-grid__item">
                <el-input
                  v-model="formData.order_name"
                  clearable
                  placeholder="例如：Synapsun"
                />
              </el-form-item>
            </div>

            <div class="selection-strip" v-if="selectionSummary.length">
              <span class="selection-strip__label">当前已确认条件</span>
              <el-space wrap>
                <el-tag v-for="item in selectionSummary" :key="item.label" effect="plain" round>
                  {{ item.label }}：{{ item.value }}
                </el-tag>
                <el-button link type="primary" @click="clearSelection">清除已确认条件</el-button>
              </el-space>
            </div>

            <div class="query-actions">
              <el-space>
                <el-button type="primary" :loading="loading" round @click="submitQuery">开始查询</el-button>
                <el-button round @click="resetForm">重置</el-button>
              </el-space>
              <div class="query-actions__hint">当前默认展示 5 类核心材料：玻璃、间隙膜、互联条、汇流条、接线盒。</div>
            </div>
          </el-form>
        </section>

        <section v-if="requestError || resultData" class="page-card result-banner" :class="`result-banner--${resultBannerTone}`">
          <div class="result-banner__main">
            <div class="result-banner__status">{{ resultBannerTag }}</div>
            <div class="result-banner__title">{{ resultBannerTitle }}</div>
            <div class="result-banner__desc">{{ resultBannerDescription }}</div>
          </div>
          <div v-if="resultBannerMeta" class="result-banner__meta">{{ resultBannerMeta }}</div>
        </section>

        <section v-if="isCandidateState" class="page-card candidate-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">请先确认候选项</h3>
              <p class="section-subtitle">{{ candidateGuideMessage }}</p>
            </div>
            <el-tag round type="warning">{{ resolveCandidateScopeLabel(resultData?.candidate_scope) }}</el-tag>
          </div>

          <div class="candidate-grid">
            <article
              v-for="candidate in resultData?.candidates || []"
              :key="candidate.order_identity_key + (candidate.file_instance_key || '') + candidate.version_no"
              class="candidate-item"
            >
              <div class="candidate-item__title">{{ candidate.order_display_label || candidate.order_no || '未返回订单号' }}</div>
              <div class="candidate-item__subtitle">{{ candidate.order_name || '未返回订单名称' }}</div>

              <div class="candidate-item__facts">
                <div class="candidate-item__fact">
                  <span>版本</span>
                  <strong>{{ candidate.version_no || '-' }}</strong>
                </div>
                <div class="candidate-item__fact">
                  <span>生效日期</span>
                  <strong>{{ candidate.effective_date || '-' }}</strong>
                </div>
                <div class="candidate-item__fact">
                  <span>来源文件</span>
                  <strong>{{ candidate.raw_file_name || '未返回文件名' }}</strong>
                </div>
              </div>

              <div class="candidate-item__reason">
                <span class="candidate-item__reason-label">需要确认的原因</span>
                <div>{{ candidate.match_reason || candidateGuideReasonFallback }}</div>
              </div>

              <div class="candidate-item__footer">
                <div class="candidate-item__tip">确认后，系统会继续展示你所选结果的明细内容。</div>
                <el-button type="primary" round @click="selectCandidate(candidate)">选择并继续</el-button>
              </div>
            </article>
          </div>

          <el-alert
            v-if="resultData?.response_meta?.candidate_truncated"
            class="candidate-alert"
            type="warning"
            :closable="false"
            show-icon
            title="候选较多，当前列表已按上限截断。建议补充更精确条件，或先从当前候选中选择。"
          />
        </section>

        <section v-else-if="isSuccessState" class="page-card summary-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">查询结果摘要</h3>
              <p class="section-subtitle">先看结论和命中信息，再往下查看材料明细。</p>
            </div>
          </div>

          <div class="summary-grid">
            <article class="summary-tile" v-for="item in businessSummaryCards" :key="item.label">
              <div class="summary-tile__label">{{ item.label }}</div>
              <div class="summary-tile__value">{{ item.value }}</div>
            </article>
          </div>
        </section>

        <section v-else-if="isEmptyState" class="page-card empty-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">没有找到匹配结果</h3>
              <p class="section-subtitle">系统没有找到符合当前条件的 BOM 记录，请检查输入条件后再试。</p>
            </div>
          </div>

          <div class="empty-card__tips">
            <div class="empty-card__tip">可尝试改用订单号、评审号或订单名称重新查询。</div>
            <div class="empty-card__tip" v-if="resultData?.no_result_analysis?.suggestion">
              {{ String(resultData.no_result_analysis.suggestion) }}
            </div>
          </div>
        </section>

        <section v-if="requestError" class="page-card error-card">
          <div class="section-heading">
            <div>
              <h3 class="section-title">查询失败</h3>
              <p class="section-subtitle">请稍后重试；如果持续失败，请联系管理员或技术支持。</p>
            </div>
          </div>
          <div class="error-card__detail">{{ friendlyRequestError }}</div>
        </section>

        <section v-if="isSuccessState" class="materials-section">
          <div class="materials-section__head">
            <div>
              <h3 class="section-title">材料明细</h3>
              <p class="section-subtitle">按 5 类核心材料分组展示，便于快速核对。</p>
            </div>
          </div>

          <article v-for="group in groupedMaterials" :key="group.category" class="page-card material-card">
            <div class="material-card__head">
              <div>
                <h4 class="material-card__title">{{ group.label }}</h4>
                <div class="material-card__subtitle">共 {{ group.items.length }} 条</div>
              </div>
            </div>

            <el-table class="material-table" :data="group.items" stripe size="small">
              <el-table-column prop="material_name" label="物料名称" min-width="180" show-overflow-tooltip />
              <el-table-column prop="description" label="规格描述" min-width="320" show-overflow-tooltip />
              <el-table-column prop="sap_code" label="SAP 编码" min-width="140" show-overflow-tooltip />
              <el-table-column prop="standard_usage" label="标准用量" width="120" />
              <el-table-column prop="unit" label="单位" width="90" />
              <el-table-column prop="production_loss" label="损耗" width="90" />
              <el-table-column prop="remark" label="备注" min-width="160" show-overflow-tooltip />
            </el-table>
          </article>
        </section>

        <section v-if="requestError || resultData" class="page-card advanced-card">
          <el-collapse>
            <el-collapse-item title="查看高级信息" name="technical-info">
              <div class="advanced-grid">
                <div v-for="item in technicalSummary" :key="item.label" class="advanced-item">
                  <div class="advanced-item__label">{{ item.label }}</div>
                  <div class="advanced-item__value" :class="{ 'is-mono': item.mono }">{{ item.value }}</div>
                </div>
              </div>
              <div class="mono-block advanced-raw" v-if="resultData">{{ JSON.stringify(resultData, null, 2) }}</div>
            </el-collapse-item>
          </el-collapse>
        </section>
      </div>

      <aside class="page-side">
        <section class="page-card side-card">
          <div class="side-card__title">查询提示</div>
          <ul class="side-list">
            <li>先输入订单号、评审号或订单名称，再点击开始查询。</li>
            <li>如果出现多个可能结果，请先确认候选项，系统才会继续查询明细。</li>
            <li>建议先查看结果摘要，再往下核对版本信息和材料明细。</li>
          </ul>
        </section>

        <section class="page-card side-card">
          <div class="side-card__title">已确认条件</div>
          <div class="side-chip-list" v-if="selectionSummary.length">
            <span class="soft-chip" v-for="item in selectionSummary" :key="item.label">{{ item.label }}：{{ item.value }}</span>
          </div>
          <div v-else class="side-card__placeholder">暂未确认候选条件，系统将按你输入的查询条件直接检索。</div>
        </section>

        <section class="page-card side-card">
          <div class="side-card__title">结果状态</div>
          <div class="side-card__status">{{ sideStatusTitle }}</div>
          <div class="side-card__message">{{ sideStatusMessage }}</div>
        </section>
      </aside>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import type { FormInstance, FormRules } from 'element-plus'
import type {
  PlanBomCandidate,
  PlanBomDetailQueryPayload,
  PlanBomDetailQueryResponse,
  PlanBomMaterialItem,
  PlanBomQaResponse,
} from '@/api/planBom'
import { askPlanBomQuestion, fetchPlanBomDetailQuery, uploadPlanBomExcel } from '@/api/planBom'

interface CandidateSelectionState {
  order_identity_key: string
  file_instance_key: string
  version_no: string
}

interface QueryFormData {
  order_no: string
  review_no: string
  order_name: string
}

interface SummaryTile {
  label: string
  value: string
}

const DEFAULT_MATERIAL_CATEGORIES = [
  'glass',
  'gap_film',
  'interconnect_bar',
  'busbar',
  'junction_box',
]

const MATERIAL_CATEGORY_LABELS: Record<string, string> = {
  glass: '玻璃',
  gap_film: '间隙膜',
  interconnect_bar: '互联条',
  busbar: '汇流条',
  junction_box: '接线盒',
}

const formRef = ref<FormInstance>()
const loading = ref(false)
const qaLoading = ref(false)
const requestError = ref('')
const qaError = ref('')
const resultData = ref<PlanBomDetailQueryResponse | null>(null)
const qaQuestion = ref('')
const qaResult = ref<PlanBomQaResponse | null>(null)
const uploadResult = ref<Record<string, any> | null>(null)

const formData = reactive<QueryFormData>({
  order_no: '',
  review_no: '',
  order_name: '',
})

const selectedCandidate = reactive<CandidateSelectionState>({
  order_identity_key: '',
  file_instance_key: '',
  version_no: '',
})

/**
 * 统一校验至少填写一个查询条件。
 */
function validateAtLeastOneField(_: unknown, __: unknown, callback: (error?: Error) => void) {
  const hasAnyValue = [formData.order_no, formData.review_no, formData.order_name].some((item) => item.trim())
  if (!hasAnyValue) {
    callback(new Error('订单号、评审号、订单名称至少填写一个'))
    return
  }
  callback()
}

const formRules: FormRules<QueryFormData> = {
  order_no: [{ validator: validateAtLeastOneField, trigger: 'blur' }],
  review_no: [{ validator: validateAtLeastOneField, trigger: 'blur' }],
  order_name: [{ validator: validateAtLeastOneField, trigger: 'blur' }],
}

/**
 * 当前已确认条件，用更业务化的标签展示。
 */
const selectionSummary = computed(() => {
  const items: Array<{ label: string; value: string }> = []
  if (selectedCandidate.order_identity_key) {
    items.push({ label: '业务实例', value: selectedCandidate.order_identity_key })
  }
  if (selectedCandidate.file_instance_key) {
    items.push({ label: '文件来源', value: selectedCandidate.file_instance_key })
  }
  if (selectedCandidate.version_no) {
    items.push({ label: '版本', value: selectedCandidate.version_no })
  }
  return items
})

/**
 * 当前是否处于候选态。
 */
const isCandidateState = computed(() => resultData.value?.query_type === 'candidate_list')

/**
 * 当前是否处于成功态。
 */
const isSuccessState = computed(() => {
  return resultData.value?.query_type === 'detail' && resultData.value.status?.success && (resultData.value.total || 0) > 0
})

/**
 * 当前是否处于空结果态。
 */
const isEmptyState = computed(() => {
  return resultData.value?.query_type === 'detail' && resultData.value.status?.code === 'EMPTY_RESULT'
})

/**
 * 顶部结果结论卡片的语气与颜色。
 * 说明：
 * 这一层只做“查到了没有、是否需要确认”的业务表达，不直出技术状态码。
 */
const resultBannerTone = computed(() => {
  if (requestError.value) return 'error'
  if (isCandidateState.value) return 'warning'
  if (isSuccessState.value) return 'success'
  if (isEmptyState.value) return 'empty'
  return 'neutral'
})

/**
 * 结果结论标签。
 */
const resultBannerTag = computed(() => {
  if (loading.value) return '查询中'
  if (requestError.value) return '查询失败'
  if (isCandidateState.value) return '需要确认'
  if (isSuccessState.value) return '已找到结果'
  if (isEmptyState.value) return '未找到结果'
  return '等待查询'
})

/**
 * 结果结论主标题。
 */
const resultBannerTitle = computed(() => {
  if (requestError.value) return '暂时无法完成查询'
  if (isCandidateState.value) return '存在多个可能结果，请先确认'
  if (isSuccessState.value) return '已找到匹配的 BOM 明细'
  if (isEmptyState.value) return '暂未找到匹配的 BOM 记录'
  return '请先输入查询条件'
})

/**
 * 结果结论说明文案。
 */
const resultBannerDescription = computed(() => {
  if (requestError.value) {
    return '请稍后重试；如果持续失败，请联系管理员或技术支持。'
  }
  if (isCandidateState.value) {
    return candidateGuideMessage.value
  }
  if (isSuccessState.value) {
    return resultData.value?.result_explanation?.summary || '系统已返回对应版本和核心材料明细。'
  }
  if (isEmptyState.value) {
    return '可以尝试更换订单号、评审号或订单名称后重新查询。'
  }
  return '支持按订单号、评审号或订单名称发起查询。'
})

/**
 * 结果结论右侧补充信息。
 */
const resultBannerMeta = computed(() => {
  if (isSuccessState.value) {
    const versionText = resultData.value?.selected_version?.version_no || '-'
    const dateText = resultData.value?.selected_version?.effective_date || '未返回生效日期'
    return `命中版本：${versionText} ｜ 生效日期：${dateText}`
  }
  if (isCandidateState.value) {
    return `待确认候选：${resultData.value?.candidate_total_hint || 0} 条`
  }
  return ''
})

/**
 * 成功态摘要区。
 */
const businessSummaryCards = computed<SummaryTile[]>(() => {
  const selectedVersion = resultData.value?.selected_version
  if (!selectedVersion || !isSuccessState.value) return []

  return [
    { label: '订单号', value: selectedVersion.order_no || '-' },
    { label: '订单名称', value: selectedVersion.order_name || '-' },
    { label: '命中版本', value: selectedVersion.version_no || '-' },
    { label: '生效日期', value: selectedVersion.effective_date || '-' },
    { label: '来源文件', value: selectedVersion.raw_file_name || '-' },
    { label: '材料条数', value: String(resultData.value?.total || 0) },
  ]
})

/**
 * 候选说明文案。
 */
const candidateGuideMessage = computed(() => {
  const scope = resultData.value?.candidate_scope
  if (scope === 'order_identity') {
    return '系统识别到多个业务实例，请先确认你要查看的是哪一个订单实例。'
  }
  if (scope === 'file_instance') {
    return '当前版本下存在多个文件来源，请先确认要查看哪一份文件。'
  }
  if (scope === 'version') {
    return '当前订单存在多个版本，请先确认要查看哪一个版本。'
  }
  return '当前存在多个可能结果，请先选择后再继续查询。'
})

/**
 * 候选原因的兜底文案。
 */
const candidateGuideReasonFallback = computed(() => {
  const scope = resultData.value?.candidate_scope
  if (scope === 'order_identity') return '系统找到多个订单实例，需你确认具体对象。'
  if (scope === 'file_instance') return '系统找到多个文件来源，需你确认具体文件。'
  if (scope === 'version') return '系统找到多个版本，需你确认具体版本。'
  return '存在多个可能结果，需要进一步确认。'
})

/**
 * 右侧状态文案。
 */
const sideStatusTitle = computed(() => {
  if (loading.value) return '正在查询'
  if (requestError.value) return '查询失败'
  if (isCandidateState.value) return '等待确认候选项'
  if (isSuccessState.value) return '已找到结果'
  if (isEmptyState.value) return '未找到结果'
  return '等待输入条件'
})

/**
 * 右侧状态提示，面向业务人员说明下一步动作。
 */
const sideStatusMessage = computed(() => {
  if (loading.value) return '系统正在查询，请稍候。'
  if (requestError.value) return '请稍后重试；如果持续失败，请联系管理员或技术支持。'
  if (isCandidateState.value) return '请先在候选项中做出选择，系统才会继续返回最终明细。'
  if (isSuccessState.value) return '第一屏先看命中结果摘要，再往下核对材料明细。'
  if (isEmptyState.value) return '建议更换订单号、评审号或订单名称后重新查询。'
  return '如不确定输入格式，可先点击示例按钮填充查询条件。'
})

/**
 * 按 5 类核心材料分组展示。
 */
const groupedMaterials = computed(() => {
  const groups = DEFAULT_MATERIAL_CATEGORIES.map((category) => ({
    category,
    label: MATERIAL_CATEGORY_LABELS[category] || category,
    items: [] as PlanBomMaterialItem[],
  }))
  const groupMap = new Map(groups.map((item) => [item.category, item]))
  for (const item of resultData.value?.items || []) {
    const category = item.material_category || 'unknown'
    const target = groupMap.get(category)
    if (target) {
      target.items.push(item)
    }
  }
  return groups.filter((item) => item.items.length > 0)
})

/**
 * 错误提示转成更适合业务展示的文案。
 */
const friendlyRequestError = computed(() => {
  if (!requestError.value) return ''
  if (/Network Error/i.test(requestError.value)) {
    return '网络连接异常，请稍后重试；如果持续失败，请联系管理员或技术支持。'
  }
  return requestError.value
})

/**
 * 技术信息折叠区。
 * 说明：
 * 内部键、状态码、查询类型仍然保留，但从主视觉区降级到折叠区。
 */
const technicalSummary = computed(() => {
  const summary: Array<{ label: string; value: string; mono?: boolean }> = []
  if (resultData.value?.status?.code) {
    summary.push({ label: '状态码', value: resultData.value.status.code })
  }
  if (resultData.value?.query_type) {
    summary.push({ label: '结果类型', value: resultData.value.query_type })
  }
  if (resultData.value?.candidate_scope) {
    summary.push({ label: '候选层级', value: resultData.value.candidate_scope })
  }
  if (resultData.value?.selected_version?.file_instance_key) {
    summary.push({
      label: '文件实例键',
      value: resultData.value.selected_version.file_instance_key,
      mono: true,
    })
  }
  if (selectedCandidate.order_identity_key) {
    summary.push({ label: '已锁定业务实例', value: selectedCandidate.order_identity_key, mono: true })
  }
  if (selectedCandidate.file_instance_key) {
    summary.push({ label: '已锁定文件实例', value: selectedCandidate.file_instance_key, mono: true })
  }
  if (selectedCandidate.version_no) {
    summary.push({ label: '已锁定版本', value: selectedCandidate.version_no })
  }
  if (requestError.value) {
    summary.push({ label: '错误信息', value: requestError.value })
  }
  return summary
})

/**
 * BOM 问答 presentation 表格列。
 */
const qaPresentationColumns = computed(() => {
  return qaResult.value?.presentation?.table_spec?.columns || qaResult.value?.result_table?.columns || []
})

/**
 * BOM 问答 presentation 表格行。
 */
const qaPresentationRows = computed(() => {
  return qaResult.value?.presentation?.table_spec?.rows || qaResult.value?.result_table?.rows || []
})

/**
 * 填充演示示例，便于快速联调。
 */
function fillExample(orderNo: string, reviewNo: string, orderName: string) {
  formData.order_no = orderNo
  formData.review_no = reviewNo
  formData.order_name = orderName
  clearSelection()
}

/**
 * 清除候选选择，回到纯表单查询。
 */
function clearSelection() {
  selectedCandidate.order_identity_key = ''
  selectedCandidate.file_instance_key = ''
  selectedCandidate.version_no = ''
}

/**
 * 重置表单与页面结果。
 */
function resetForm() {
  formData.order_no = ''
  formData.review_no = ''
  formData.order_name = ''
  clearSelection()
  requestError.value = ''
  resultData.value = null
  formRef.value?.clearValidate()
}

/**
 * 构建查询请求体。
 * 说明：
 * 1. 直接输入只来自 order_no / review_no / order_name；
 * 2. 候选选择后才带内部键和版本号；
 * 3. material_categories 当前固定透传 5 类核心材料。
 */
function buildPayload(): PlanBomDetailQueryPayload {
  return {
    order_no: normalizeText(formData.order_no),
    review_no: normalizeText(formData.review_no),
    order_name: normalizeText(formData.order_name),
    order_identity_key: normalizeText(selectedCandidate.order_identity_key),
    file_instance_key: normalizeText(selectedCandidate.file_instance_key),
    version_no: normalizeText(selectedCandidate.version_no),
    material_categories: [...DEFAULT_MATERIAL_CATEGORIES],
    candidate_limit: 20,
  }
}

/**
 * 发送明细查询请求。
 */
async function doQuery() {
  loading.value = true
  requestError.value = ''
  try {
    const resp = await fetchPlanBomDetailQuery(buildPayload())
    resultData.value =
      typeof resp === 'object' && resp !== null && 'data' in resp
        ? (resp.data as PlanBomDetailQueryResponse)
        : (resp as PlanBomDetailQueryResponse)
  } catch (error: any) {
    requestError.value = error?.response?.data?.message || error?.message || '查询失败，请稍后重试'
    resultData.value = null
  } finally {
    loading.value = false
  }
}

/**
 * 触发表单查询。
 * 说明：
 * 用户主动重新查询时，会清除之前的候选选择，避免把旧内部键带入新条件。
 */
async function submitQuery() {
  try {
    await formRef.value?.validate()
  } catch {
    return
  }
  clearSelection()
  await doQuery()
}

/**
 * 选择候选项后继续查询。
 * 说明：
 * 1. order_identity 候选只锁定业务实例，不提前替后端选版本；
 * 2. version 候选锁定版本；
 * 3. file_instance 候选锁定文件实例；
 * 4. 前端不自行推断唯一结果，只把后端要求的键重新透传。
 */
async function selectCandidate(candidate: PlanBomCandidate) {
  const candidateScope = resultData.value?.candidate_scope
  selectedCandidate.order_identity_key = candidate.order_identity_key || ''

  if (candidateScope === 'file_instance') {
    selectedCandidate.file_instance_key = candidate.file_instance_key || ''
    selectedCandidate.version_no = candidate.version_no || ''
  } else if (candidateScope === 'version') {
    selectedCandidate.file_instance_key = candidate.file_instance_key || ''
    selectedCandidate.version_no = candidate.version_no || ''
  } else {
    selectedCandidate.file_instance_key = ''
    selectedCandidate.version_no = ''
  }

  await doQuery()
}

/**
 * 提交自然语言 BOM 问题。
 */
async function submitQaQuestion() {
  const question = qaQuestion.value.trim()
  if (!question) {
    qaError.value = '请先输入 BOM 问题'
    return
  }
  qaLoading.value = true
  qaError.value = ''
  try {
    const resp = await askPlanBomQuestion({ question })
    qaResult.value =
      typeof resp === 'object' && resp !== null && 'data' in resp
        ? (resp.data as PlanBomQaResponse)
        : (resp as PlanBomQaResponse)
  } catch (error: any) {
    qaError.value = error?.response?.data?.message || error?.message || 'BOM 问答失败，请稍后重试'
    qaResult.value = null
  } finally {
    qaLoading.value = false
  }
}

/**
 * 上传单个 BOM Excel 文件。
 */
async function handleUploadInputChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return
  qaError.value = ''
  try {
    const resp = await uploadPlanBomExcel(file)
    uploadResult.value = typeof resp === 'object' && resp !== null && 'data' in resp ? resp.data : resp
  } catch (error: any) {
    qaError.value = error?.response?.data?.message || error?.message || 'BOM 上传失败，请稍后重试'
  } finally {
    target.value = ''
  }
}

/**
 * 候选类型中文映射。
 */
function resolveCandidateScopeLabel(scope: string | null | undefined) {
  if (scope === 'order_identity') return '业务实例确认'
  if (scope === 'file_instance') return '文件来源确认'
  if (scope === 'version') return '版本确认'
  return scope || '-'
}

/**
 * 文本规整为后端可接受的空值。
 */
function normalizeText(value: string | null | undefined) {
  const text = String(value || '').trim()
  return text || undefined
}
</script>

<style scoped>
.bom-page {
  display: flex;
  flex-direction: column;
  gap: 22px;
}

.page-intro {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 20px;
  padding: 26px 28px;
  border-radius: 24px;
  background: linear-gradient(135deg, #f7fbff 0%, #fbfcf7 100%);
  border: 1px solid #e0eaf2;
  box-shadow: 0 10px 26px rgba(35, 66, 100, 0.05);
}

.page-intro__tag {
  display: inline-flex;
  align-items: center;
  padding: 6px 12px;
  border-radius: 999px;
  background: #edf7e8;
  color: #5d8f2e;
  font-size: 12px;
  font-weight: 700;
}

.page-intro__title {
  margin: 14px 0 0;
  font-size: 34px;
  font-weight: 800;
  color: #153451;
  letter-spacing: 0.01em;
}

.page-intro__desc {
  margin: 10px 0 0;
  max-width: 720px;
  color: #607180;
  font-size: 14px;
  line-height: 1.8;
}

.page-intro__note {
  padding: 12px 16px;
  border-radius: 14px;
  background: #eef6fb;
  color: #4c6884;
  font-size: 12px;
  border: 1px solid #dde8f1;
  white-space: nowrap;
}

.page-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(300px, 0.56fr);
  gap: 24px;
  align-items: start;
}

.page-main,
.page-side {
  display: flex;
  flex-direction: column;
  gap: 18px;
  min-width: 0;
}

.qa-card,
.query-card,
.result-banner,
.candidate-card,
.summary-card,
.empty-card,
.error-card,
.advanced-card,
.material-card,
.side-card {
  background: #ffffff;
  border: 1px solid #e3ebf2;
  box-shadow: 0 10px 24px rgba(35, 66, 100, 0.05);
  border-radius: 20px;
  padding: 20px;
}

.section-heading {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
  margin-bottom: 18px;
}

.section-title {
  margin: 0;
  font-size: 22px;
  font-weight: 800;
  color: #163451;
}

.section-subtitle {
  margin: 8px 0 0;
  color: #667886;
  font-size: 13px;
  line-height: 1.8;
}

.example-actions :deep(.el-button) {
  border-color: #d9e6ef;
  color: #3d6288;
  background: #fbfdff;
}

.qa-card :deep(.el-button--primary),
.query-card :deep(.el-button--primary),
.candidate-card :deep(.el-button--primary) {
  --el-button-bg-color: #3071b9;
  --el-button-border-color: #3071b9;
  --el-button-hover-bg-color: #2966a8;
  --el-button-hover-border-color: #2966a8;
  --el-button-active-bg-color: #245a95;
  --el-button-active-border-color: #245a95;
}

.qa-actions {
  display: grid;
  gap: 12px;
}

.qa-actions__footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  flex-wrap: wrap;
}

.qa-result {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: #f9fbfd;
  border: 1px solid #e9eff4;
  color: #5f7180;
  line-height: 1.8;
}

.qa-result__title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  color: #173653;
  font-weight: 800;
}

.qa-result__answer {
  margin-bottom: 12px;
}

.mono-block {
  margin-top: 10px;
  padding: 12px;
  border-radius: 12px;
  background: #f5f7fa;
  overflow: auto;
  color: #33495f;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  line-height: 1.7;
}

.query-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.query-grid__item {
  margin-bottom: 0;
}

.query-actions {
  margin-top: 18px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.query-actions__hint {
  color: #6d7d8a;
  font-size: 12px;
}

.selection-strip {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 16px;
  background: #f7fbf5;
  border: 1px solid #e4eee1;
}

.selection-strip__label {
  display: inline-block;
  margin-right: 10px;
  color: #4f6c3a;
  font-size: 13px;
  font-weight: 700;
}

.result-banner {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
}

.result-banner__status {
  display: inline-flex;
  padding: 6px 12px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}

.result-banner__title {
  margin-top: 14px;
  font-size: 24px;
  font-weight: 800;
  color: #153451;
}

.result-banner__desc {
  margin-top: 10px;
  color: #667886;
  font-size: 14px;
  line-height: 1.8;
}

.result-banner__meta {
  color: #5e7181;
  font-size: 13px;
  line-height: 1.8;
  padding-top: 6px;
  white-space: nowrap;
}

.result-banner--success .result-banner__status {
  background: #edf7e8;
  color: #4b8724;
}

.result-banner--warning .result-banner__status {
  background: #fff4e5;
  color: #a86412;
}

.result-banner--empty .result-banner__status,
.result-banner--neutral .result-banner__status {
  background: #eef5fb;
  color: #4d6886;
}

.result-banner--error .result-banner__status {
  background: #fdecec;
  color: #b44545;
}

.candidate-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.candidate-item {
  padding: 18px;
  border-radius: 18px;
  border: 1px solid #e3ebf2;
  background: #ffffff;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.candidate-item__title {
  font-size: 18px;
  font-weight: 800;
  color: #173653;
}

.candidate-item__subtitle {
  margin-top: 4px;
  color: #687986;
  line-height: 1.7;
}

.candidate-item__facts {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 10px;
}

.candidate-item__fact {
  padding: 12px;
  border-radius: 14px;
  background: #f9fbfd;
  border: 1px solid #e9eff4;
}

.candidate-item__fact span {
  display: block;
  font-size: 12px;
  color: #738290;
  margin-bottom: 6px;
}

.candidate-item__fact strong {
  display: block;
  font-size: 13px;
  line-height: 1.6;
  color: #1a3550;
  word-break: break-word;
}

.candidate-item__reason {
  padding: 12px 14px;
  border-radius: 14px;
  background: #f9fbfd;
  border: 1px solid #e9eff4;
  color: #617281;
  font-size: 13px;
  line-height: 1.75;
}

.candidate-item__reason-label {
  display: block;
  margin-bottom: 6px;
  color: #305f8d;
  font-weight: 700;
}

.candidate-item__footer {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.candidate-item__tip {
  color: #6c7d8c;
  font-size: 12px;
  line-height: 1.7;
}

.candidate-alert {
  margin-top: 16px;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}

.summary-tile {
  padding: 16px 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, #fbfdff 0%, #f8fbf7 100%);
  border: 1px solid #e5edf2;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.7);
}

.summary-tile__label {
  color: #758595;
  font-size: 12px;
  margin-bottom: 10px;
}

.summary-tile__value {
  color: #173653;
  font-size: 16px;
  font-weight: 700;
  line-height: 1.7;
  word-break: break-word;
}

.empty-card__tips {
  display: grid;
  gap: 12px;
}

.empty-card__tip,
.error-card__detail {
  padding: 14px 16px;
  border-radius: 16px;
  background: #f9fbfd;
  border: 1px solid #e9eff4;
  color: #667886;
  line-height: 1.8;
}

.materials-section {
  display: grid;
  gap: 18px;
}

.materials-section__head {
  padding: 0 4px;
}

.material-card__head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.material-card__title {
  margin: 0;
  font-size: 20px;
  font-weight: 800;
  color: #173653;
}

.material-card__subtitle {
  margin-top: 6px;
  color: #708190;
  font-size: 12px;
}

.material-table :deep(.el-table) {
  --el-table-border-color: #e8eef3;
  --el-table-header-bg-color: #f6f9fb;
  --el-table-row-hover-bg-color: #f5f9fc;
}

.material-table :deep(.el-table th.el-table__cell) {
  color: #47627e;
  font-weight: 700;
}

.advanced-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 16px;
}

.advanced-item {
  padding: 12px 14px;
  border-radius: 14px;
  background: #f9fbfd;
  border: 1px solid #e9eff4;
}

.advanced-item__label {
  color: #748595;
  font-size: 12px;
  margin-bottom: 8px;
}

.advanced-item__value {
  color: #173653;
  line-height: 1.7;
  word-break: break-word;
}

.advanced-item__value.is-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
}

.advanced-raw {
  margin-top: 16px;
}

.page-side {
  position: sticky;
  top: 12px;
}

.side-card__title {
  font-size: 18px;
  font-weight: 800;
  color: #173653;
}

.side-card__status {
  margin-top: 14px;
  font-size: 20px;
  font-weight: 800;
  color: #2b6aa8;
}

.side-card__message {
  margin-top: 10px;
  color: #687a88;
  font-size: 13px;
  line-height: 1.8;
}

.side-card__placeholder {
  margin-top: 14px;
  color: #6d7e8c;
  font-size: 13px;
  line-height: 1.8;
}

.side-list {
  margin: 16px 0 0;
  padding-left: 18px;
  color: #6a7b89;
  line-height: 1.9;
}

.side-list li + li {
  margin-top: 8px;
}

.side-chip-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 16px;
}

@media (max-width: 1280px) {
  .summary-grid,
  .candidate-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .candidate-item__facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1180px) {
  .page-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .page-side {
    position: static;
  }
}

@media (max-width: 960px) {
  .page-intro {
    flex-direction: column;
    align-items: flex-start;
  }

  .page-intro__title {
    font-size: 28px;
  }

  .query-grid,
  .summary-grid,
  .advanced-grid {
    grid-template-columns: minmax(0, 1fr);
  }

  .candidate-item__facts {
    grid-template-columns: minmax(0, 1fr);
  }

  .query-actions,
  .result-banner,
  .candidate-item__footer {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>
