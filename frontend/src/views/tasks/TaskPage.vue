<template>
  <div>
    <div class="page-card" style="margin-bottom: 20px">
      <h2 class="page-title">任务与日志</h2>
      <p class="page-subtitle">
        用于查看历史导入任务和系统同步任务，便于前端联调数据链路。
      </p>
      <el-space>
        <el-button type="primary" :loading="loading" @click="loadAll">刷新任务</el-button>
      </el-space>
    </div>

    <el-row :gutter="20">
      <el-col :span="12">
        <div class="page-card">
          <h3 style="margin-top: 0">历史导入任务</h3>
          <el-table :data="normalize(historyTasks)" border stripe>
            <el-table-column prop="task_id" label="任务ID" min-width="180" />
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column prop="created_at" label="时间" min-width="180" />
          </el-table>
          <el-collapse style="margin-top: 12px">
            <el-collapse-item title="查看原始响应" name="1">
              <div class="mono-block">{{ JSON.stringify(historyTasks, null, 2) }}</div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-col>
      <el-col :span="12">
        <div class="page-card">
          <h3 style="margin-top: 0">系统同步任务</h3>
          <el-table :data="normalize(systemTasks)" border stripe>
            <el-table-column prop="task_id" label="任务ID" min-width="180" />
            <el-table-column prop="status" label="状态" width="120" />
            <el-table-column prop="created_at" label="时间" min-width="180" />
          </el-table>
          <el-collapse style="margin-top: 12px">
            <el-collapse-item title="查看原始响应" name="1">
              <div class="mono-block">{{ JSON.stringify(systemTasks, null, 2) }}</div>
            </el-collapse-item>
          </el-collapse>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { fetchHistoryTasks, fetchSystemSyncTasks } from '@/api/logistics'

const loading = ref(false)
const historyTasks = ref<Record<string, any> | null>(null)
const systemTasks = ref<Record<string, any> | null>(null)

/**
 * 将后端返回规范化为表格可展示数组。
 */
function normalize(payload: Record<string, any> | null) {
  if (!payload) return []
  const data = payload.data ?? payload.items ?? payload
  return Array.isArray(data) ? data : []
}

/** 拉取两类任务列表。 */
async function loadAll() {
  loading.value = true
  try {
    const [histResp, sysResp] = await Promise.all([fetchHistoryTasks(), fetchSystemSyncTasks()])
    historyTasks.value = histResp.data ?? histResp
    systemTasks.value = sysResp.data ?? sysResp
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  loadAll()
})
</script>
