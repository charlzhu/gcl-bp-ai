<template>
  <section class="bom-page">
    <div class="page-head">
      <h1>上传 BOM Excel</h1>
      <p>.xls / .xlsx / .xlsm</p>
    </div>

    <div class="upload-card">
      <div class="upload-main">
        <input ref="fileInputRef" type="file" accept=".xls,.xlsx,.xlsm" @change="handleFileChange" />
        <div class="file-info">
          <strong>{{ selectedFile?.name || '请选择 BOM Excel 文件' }}</strong>
          <span>{{ selectedFile ? formatFileSize(selectedFile.size) : '上传后即可问答' }}</span>
        </div>
      </div>
      <el-button type="primary" :disabled="!selectedFile" :loading="uploading" @click="uploadFile">上传并解析</el-button>
    </div>

    <el-alert
      v-if="uploadError"
      :title="uploadError"
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
      <p class="next-action">{{ uploadResult.next_action || '上传完成后可进入智能问答继续查询。' }}</p>
    </div>

  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { uploadPlanBomExcel } from '@/api/planBom'

interface UploadResult {
  success?: boolean
  message?: string
  parsed_orders_count?: number
  parsed_materials_count?: number
  warning_count?: number
  error_count?: number
  next_action?: string
}

const fileInputRef = ref<HTMLInputElement | null>(null)
const selectedFile = ref<File | null>(null)
const uploading = ref(false)
const uploadError = ref('')
const uploadResult = ref<UploadResult | null>(null)

/** 记录用户选择的 BOM 文件，实际解析仍由后端上传接口完成。 */
function handleFileChange(event: Event) {
  const input = event.target as HTMLInputElement
  selectedFile.value = input.files?.[0] || null
  uploadError.value = ''
  uploadResult.value = null
}

/** 上传 BOM Excel 到真实后端接口，不在前端伪造解析结果。 */
async function uploadFile() {
  if (!selectedFile.value || uploading.value) return
  uploading.value = true
  uploadError.value = ''
  uploadResult.value = null
  try {
    const resp = await uploadPlanBomExcel(selectedFile.value, {
      source: 'trial_run_ui',
      overwrite: true,
      remark: '业务试运行页面上传',
    })
    uploadResult.value = ((resp as any).data || resp) as UploadResult
    if (uploadResult.value?.success === false) {
      uploadError.value = uploadResult.value.message || '上传未成功，请检查文件内容。'
    }
  } catch (error) {
    uploadError.value = error instanceof Error ? error.message : '上传失败，请稍后重试。'
  } finally {
    uploading.value = false
  }
}

function formatFileSize(size: number) {
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
  return `${(size / 1024 / 1024).toFixed(1)} MB`
}
</script>

<style scoped>
.bom-page {
  width: min(880px, calc(100vw - 360px));
  margin: 48px auto 0;
  display: grid;
  gap: 16px;
  font-size: 14px;
}

.page-head,
.upload-card,
.result-card {
  border: 1px solid #e5e7eb;
  border-radius: 16px;
  background: #ffffff;
  padding: 18px 20px;
}

h1,
h2 {
  margin: 0;
  color: #111827;
}

h1 {
  font-size: 24px;
  font-weight: 600;
}

h2 {
  font-size: 18px;
}

p {
  margin: 6px 0 0;
  color: #6b7280;
  line-height: 1.7;
}

.upload-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
}

.upload-main {
  display: flex;
  align-items: center;
  gap: 14px;
  min-width: 0;
}

input {
  width: 240px;
  font-size: 13px;
}

.file-info {
  display: grid;
  gap: 4px;
  min-width: 0;
}

.file-info strong {
  color: #111827;
}

.file-info span {
  color: #6c7e89;
  font-size: 12px;
}

.result-title {
  color: #111827;
  font-weight: 600;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  margin-top: 12px;
}

.summary-grid div {
  border: 1px solid #eef0f3;
  border-radius: 12px;
  padding: 12px;
  background: #fbfcfd;
}

.summary-grid span {
  display: block;
  color: #6d7d88;
  font-size: 12px;
}

.summary-grid strong {
  display: block;
  margin-top: 6px;
  color: #111827;
  font-size: 22px;
}

.next-action {
  color: #3f7b50;
}

@media (max-width: 1100px) {
  .bom-page {
    width: calc(100vw - 32px);
    margin-top: 24px;
  }
}

@media (max-width: 900px) {
  .upload-card {
    align-items: flex-start;
    flex-direction: column;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
