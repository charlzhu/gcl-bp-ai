<template>
  <el-container style="min-height: 100vh">
    <el-aside width="240px" class="aside">
      <div class="logo">{{ appTitle }}</div>
      <el-menu :default-active="activePath" router class="menu">
        <el-menu-item index="/nl-query">自然语言查询</el-menu-item>
        <el-menu-item index="/structured-query">条件查询</el-menu-item>
        <el-menu-item index="/tasks">任务与日志</el-menu-item>
        <el-menu-item index="/history">查询历史</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <div class="header-left">
          <div class="header-title">物流一期前端查询页第二版</div>
          <div class="header-desc">在第一版基础上增强结果表格、明细视图和查询历史，便于联调与业务试用。</div>
        </div>
      </el-header>
      <el-main class="main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()

/** 应用标题，来自环境变量，便于后续多环境复用。 */
const appTitle = import.meta.env.VITE_APP_TITLE || '协鑫集成经营计划部智能平台'

/** 当前激活菜单。 */
const activePath = computed(() => route.path)
</script>

<style scoped>
.aside {
  border-right: 1px solid #e5e7eb;
  background: #ffffff;
}
.logo {
  height: 64px;
  display: flex;
  align-items: center;
  padding: 0 18px;
  font-size: 16px;
  font-weight: 700;
  border-bottom: 1px solid #eef2f7;
}
.menu {
  border-right: none;
}
.header {
  background: #ffffff;
  border-bottom: 1px solid #eef2f7;
  display: flex;
  align-items: center;
}
.header-title {
  font-size: 20px;
  font-weight: 700;
}
.header-desc {
  font-size: 13px;
  color: #6b7280;
  margin-top: 4px;
}
.main {
  padding: 20px;
}
</style>
