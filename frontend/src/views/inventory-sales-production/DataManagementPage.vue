<template>
  <section class="isp-import-page">
    <header class="page-head">
      <h1>产销存数据管理</h1>
      <p>导入业务源数据 Excel，入库后可在经营分析问答中查询</p>
    </header>

    <el-card class="import-card">
      <template #header>
        <span>上传 Excel 文件</span>
      </template>
      <el-upload
        ref="uploadRef"
        drag
        :auto-upload="false"
        :multiple="true"
        accept=".xls,.xlsx,.xlsm"
        :limit="10"
        :on-change="handleFileChange"
        :on-remove="handleFileRemove"
        :file-list="fileList"
      >
        <el-icon class="el-icon--upload"><upload-filled /></el-icon>
        <div class="el-upload__text">
          拖拽文件到此处，或<em>点击选择</em>
        </div>
        <template #tip>
          <div class="el-upload__tip">
            支持 .xls / .xlsx / .xlsm 格式，单次最多 10 个文件，每个 50MB 以内
          </div>
        </template>
      </el-upload>

      <div class="import-actions">
        <el-button
          type="primary"
          :loading="uploading"
          :disabled="fileList.length === 0"
          @click="handleUpload"
        >
          {{ uploading ? '导入中...' : '开始导入' }}
        </el-button>
      </div>
    </el-card>

    <!-- 导入结果 -->
    <el-card v-if="importResults.length > 0" class="result-card">
      <template #header>
        <span>导入结果</span>
      </template>
      <el-table :data="importResults" stripe border style="width: 100%">
        <el-table-column prop="source_file_name" label="文件名" min-width="200" />
        <el-table-column prop="import_status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="row.import_status === 'created' ? 'success' : 'warning'">
              {{ row.import_status === 'created' ? '新增' : '已存在' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="business_year" label="业务年份" width="100" />
        <el-table-column prop="data_cutoff_month" label="截止月份" width="100" />
        <el-table-column prop="sheet_count" label="Sheet 数" width="90" />
        <el-table-column prop="monthly_fact_count" label="事实行数" width="100" />
      </el-table>
    </el-card>

    <!-- 导入历史 -->
    <el-card v-if="history.length > 0" class="history-card">
      <template #header>
        <span>导入历史</span>
      </template>
      <el-table :data="history" stripe border style="width: 100%">
        <el-table-column prop="source_file_name" label="文件名" min-width="200" />
        <el-table-column prop="business_year" label="年份" width="80" />
        <el-table-column prop="sheet_count" label="Sheet 数" width="80" />
        <el-table-column prop="created_at" label="导入时间" width="180" />
        <el-table-column prop="upload_batch_no" label="批次号" width="160" />
      </el-table>
    </el-card>
  </section>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import type { UploadInstance, UploadProps, UploadUserFile } from 'element-plus'
import { ElMessage } from 'element-plus'

import {
  uploadInventorySalesProductionExcel,
  fetchImportHistory,
  type InventorySalesProductionImportReport,
  type ImportHistoryItem,
} from '@/api/inventorySalesProductionImport'

const uploadRef = ref<UploadInstance>()
const fileList = ref<UploadUserFile[]>([])
const uploading = ref(false)
const importResults = ref<InventorySalesProductionImportReport[]>([])
const history = ref<ImportHistoryItem[]>([])

const handleFileChange: UploadProps['onChange'] = (uploadFile) => {
  fileList.value = uploadRef.value?.uploadFiles ?? []
}

const handleFileRemove: UploadProps['onRemove'] = () => {
  fileList.value = uploadRef.value?.uploadFiles ?? []
}

async function handleUpload() {
  const files = uploadRef.value?.uploadFiles ?? []
  if (files.length === 0) return

  uploading.value = true
  importResults.value = []

  for (const f of files) {
    if (!f.raw) continue
    try {
      const report = await uploadInventorySalesProductionExcel(f.raw)
      importResults.value.push(report)
      ElMessage.success(`${f.name} 导入成功`)
    } catch (err: any) {
      ElMessage.error(`${f.name} 导入失败：${err?.message || '未知错误'}`)
    }
  }

  uploading.value = false
  // 刷新历史
  await loadHistory()
}

async function loadHistory() {
  try {
    const resp = await fetchImportHistory()
    history.value = resp.history ?? []
  } catch {
    // 静默失败
  }
}

onMounted(() => {
  loadHistory()
})
</script>

<style scoped>
.isp-import-page {
  padding: 24px;
  max-width: 1000px;
  margin: 0 auto;
}

.page-head {
  margin-bottom: 24px;
}

.page-head h1 {
  font-size: 22px;
  font-weight: 600;
  margin: 0 0 8px;
}

.page-head p {
  color: #666;
  margin: 0;
}

.import-card {
  margin-bottom: 24px;
}

.import-actions {
  margin-top: 16px;
  text-align: center;
}

.result-card,
.history-card {
  margin-bottom: 24px;
}
</style>
