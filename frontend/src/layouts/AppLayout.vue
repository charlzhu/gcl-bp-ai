<template>
  <el-container class="app-shell">
    <el-aside :width="asideWidth" :class="['aside', { 'aside--collapsed': isAsideCollapsed }]">
      <div class="logo-card">
        <div class="logo-mark">
          <img :src="brandLogoUrl" alt="协鑫集成标识" class="logo-mark__image" />
        </div>
        <div v-if="!isAsideCollapsed" class="logo-copy">
          <div class="logo-title">{{ appTitle }}</div>
          <div class="logo-subtitle">经营计划业务系统</div>
        </div>
      </div>

      <el-menu
        :default-active="activePath"
        :default-openeds="openedMenus"
        router
        class="menu"
      >
        <el-sub-menu index="logistics-data-qa-group">
          <template #title>
            <el-icon><ChatDotRound /></el-icon>
            <span>自然语言问答</span>
          </template>

          <div
            class="qa-menu-launch"
            :class="{ 'qa-menu-launch--active': route.path.startsWith('/logistics/data-qa') && !route.path.startsWith('/logistics/data-qa/history') }"
          >
            <button type="button" class="qa-menu-launch__main" @click="goDataQaPage">
              <el-icon><ChatDotRound /></el-icon>
              <span v-if="!isAsideCollapsed">发起查询</span>
            </button>

            <el-button
              v-if="!isAsideCollapsed"
              text
              circle
              class="qa-menu-launch__create"
              title="新建会话"
              @click.stop="createQaSession"
            >
              <el-icon><Plus /></el-icon>
            </el-button>
          </div>

          <div v-if="!isAsideCollapsed && qaSessionSummaries.length" class="qa-session-list">
            <button
              v-for="session in qaSessionSummaries"
              :key="session.id"
              type="button"
              class="qa-session-item"
              :class="{ 'qa-session-item--active': isQaSessionActive(session.id) }"
              @click="openQaSession(session.id)"
            >
              <div class="qa-session-item__copy">
                <div class="qa-session-item__title">{{ session.title }}</div>
                <div class="qa-session-item__preview">{{ session.preview }}</div>
              </div>

              <el-dropdown
                v-if="isQaSessionActive(session.id)"
                trigger="click"
                @command="handleQaSessionCommand(session, $event)"
              >
                <el-button text class="qa-session-item__menu" @click.stop>
                  <el-icon><MoreFilled /></el-icon>
                </el-button>
                <template #dropdown>
                  <el-dropdown-menu>
                    <el-dropdown-item command="rename">重命名会话</el-dropdown-item>
                    <el-dropdown-item command="delete">删除会话</el-dropdown-item>
                  </el-dropdown-menu>
                </template>
              </el-dropdown>
            </button>
          </div>

          <el-menu-item index="/logistics/data-qa/history">
            <el-icon><Timer /></el-icon>
            <span>{{ isAsideCollapsed ? '历史' : '查询历史' }}</span>
          </el-menu-item>
        </el-sub-menu>
        <el-sub-menu index="query-group">
          <template #title>
            <el-icon><Search /></el-icon>
            <span>条件查询</span>
          </template>
          <el-menu-item index="/structured-query">
            <el-icon><DataBoard /></el-icon>
            <span>物流条件查询</span>
          </el-menu-item>
          <el-menu-item index="/plan-bom/detail-query">
            <el-icon><Files /></el-icon>
            <span>BOM 明细查询</span>
          </el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/tasks">
          <el-icon><Tickets /></el-icon>
          <span>任务与日志</span>
        </el-menu-item>
        <el-menu-item index="/history">
          <el-icon><Timer /></el-icon>
          <span>查询历史</span>
        </el-menu-item>
      </el-menu>

      <div v-if="!isAsideCollapsed" class="aside-footnote">
        <div class="aside-footnote__title">查询提示</div>
        <div class="aside-footnote__desc">建议先从自然语言问答或条件查询入口进入。结果提醒与计算说明会帮助你理解当前统计口径。</div>
      </div>
    </el-aside>

    <el-container class="content-shell">
      <el-header v-if="!hideHeader" class="header">
        <div class="header-left">
          <div class="header-title">{{ headerMeta.title }}</div>
          <div class="header-desc">{{ headerMeta.description }}</div>
        </div>
      </el-header>
      <el-main :class="['main', { 'main--immersive': hideHeader }]">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { ChatDotRound, DataBoard, Files, MoreFilled, Plus, Search, Tickets, Timer } from '@element-plus/icons-vue'
import { useRoute, useRouter } from 'vue-router'
import brandLogoUrl from '@/assets/gcl-logo.svg'
import {
  buildLogisticsDataQaSessionId,
  getLogisticsDataQaSession,
  getLogisticsDataQaSessionEventName,
  listLogisticsDataQaSessions,
  removeLogisticsDataQaSession,
  renameLogisticsDataQaSession,
  saveLogisticsDataQaSession,
  type LogisticsDataQaSessionRecord,
  type LogisticsDataQaSessionSummary,
} from '@/utils/logisticsDataQaSessions'

const route = useRoute()
const router = useRouter()
const isAsideCollapsed = ref(false)
const qaSessionSummaries = ref<LogisticsDataQaSessionSummary[]>([])

const APP_SHELL_SIDEBAR_TOGGLE_EVENT = 'app-shell:toggle-sidebar'

/** 侧边栏品牌标题固定为业务系统口径，避免继续透出“智能助手”等技术化旧名称。 */
const appTitle = '协鑫集成'

/**
 * 当前左侧主菜单宽度。
 * 说明：
 * 折叠后只保留图标入口，避免正文区被压缩得太碎。
 */
const asideWidth = computed(() => (isAsideCollapsed.value ? '84px' : '236px'))

/** 当前激活菜单。 */
const activePath = computed(() => {
  if (route.path.startsWith('/logistics/data-qa/history')) return '/logistics/data-qa/history'
  if (route.path.startsWith('/logistics/data-qa')) return '/logistics/data-qa'
  return route.path
})

/** 条件查询父菜单和物流数据问答父菜单在对应场景下默认展开。 */
const openedMenus = computed(() => {
  if (isAsideCollapsed.value) {
    return []
  }

  const menus: string[] = []
  if (route.path.startsWith('/logistics/data-qa')) {
    menus.push('logistics-data-qa-group')
  }
  if (route.path === '/structured-query' || route.path.startsWith('/plan-bom/')) {
    menus.push('query-group')
  }
  return menus
})

/**
 * 物流数据问答相关页面使用页内自己的头部与工具栏。
 * 说明：
 * 为了避免出现“系统页头 + 页面页头”重复堆叠，这里对 data-qa 路由隐藏外层页头。
 */
const hideHeader = computed(() => route.path.startsWith('/logistics/data-qa'))

/**
 * 顶部标题按当前路由切换。
 * 说明：
 * 物流页继续保留原有描述，BOM 页面单独给出当前 MVP 边界，避免页头误导。
 */
const headerMeta = computed(() => {
  if (route.path.startsWith('/logistics/data-qa/history')) {
    return {
      title: '查询历史记录',
      description: '查看过去问过的问题和保存下来的结果快照，适合回看、核对与继续导出。',
    }
  }

  if (route.path.startsWith('/logistics/data-qa')) {
    return {
      title: '自然语言问答',
      description: '像持续对话一样提问、查看结果、回看历史并导出内容。当前已正式接入物流数据问答能力。',
    }
  }

  if (route.path.startsWith('/nl-query')) {
    return {
      title: '自然语言查询',
      description: '像对话一样输入业务问题，系统会自动解析条件并返回查询结果。当前已开通物流问答能力，BOM 自然语言问答后续接入。',
    }
  }

  if (route.path.startsWith('/structured-query')) {
    return {
      title: '物流条件查询',
      description: '按时间、客户、物流公司等条件筛选物流结果，适合日常统计核对和条件筛查。',
    }
  }

  if (route.path.startsWith('/plan-bom')) {
    return {
      title: '计划 BOM 明细查询',
      description: '按订单号、评审号或订单名称查看命中版本和核心材料明细，适合业务查询、结果核对和汇报展示。',
    }
  }

  return {
    title: '经营计划查询系统',
    description: '用于查看经营计划相关查询结果，强调查询清晰、结果易读、便于业务使用。',
  }
})

/**
 * 刷新自然语言问答会话摘要。
 * 说明：
 * 左侧主菜单直接复用当前页已有的本地会话能力，不额外新造会话系统。
 */
function refreshQaSessions() {
  qaSessionSummaries.value = listLogisticsDataQaSessions()
}

/**
 * 判断某条会话是否为当前激活会话。
 */
function isQaSessionActive(sessionId: string) {
  return route.path.startsWith('/logistics/data-qa') && route.query.session === sessionId
}

/**
 * 进入自然语言问答正式页。
 */
function goDataQaPage() {
  const activeSessionId = typeof route.query.session === 'string' ? route.query.session : ''
  router.push({
    path: '/logistics/data-qa',
    query: activeSessionId ? { session: activeSessionId } : undefined,
  })
}

/**
 * 从主菜单创建新会话。
 * 说明：
 * 新建按钮放在“发起查询”右侧，满足业务上“查新问题”的直接入口习惯。
 */
function createQaSession() {
  const sessionId = buildLogisticsDataQaSessionId()
  saveLogisticsDataQaSession({
    id: sessionId,
    title: '新建对话',
    preview: '等待开始新的业务问题',
    updatedAt: new Date().toISOString(),
    items: [],
  } satisfies LogisticsDataQaSessionRecord)
  refreshQaSessions()
  router.push({
    path: '/logistics/data-qa',
    query: { session: sessionId },
  })
}

/**
 * 打开指定会话。
 */
function openQaSession(sessionId: string) {
  router.push({
    path: '/logistics/data-qa',
    query: { session: sessionId },
  })
}

/**
 * 处理会话操作命令。
 */
function handleQaSessionCommand(session: LogisticsDataQaSessionSummary, command: string | number | object) {
  if (command === 'rename') {
    renameQaSession(session)
    return
  }
  if (command === 'delete') {
    deleteQaSession(session)
  }
}

/**
 * 重命名菜单中的会话。
 */
async function renameQaSession(session: LogisticsDataQaSessionSummary) {
  try {
    const { value } = await ElMessageBox.prompt('请输入新的会话标题', '重命名会话', {
      inputValue: session.title,
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      inputPlaceholder: '例如：2026年1月发运量',
    })

    const title = String(value || '').trim()
    if (!title) {
      ElMessage.warning('请输入有效的会话标题。')
      return
    }

    renameLogisticsDataQaSession(session.id, title)
    refreshQaSessions()
    ElMessage.success('会话标题已更新。')
  } catch (_error) {
    // 用户主动取消时不提示。
  }
}

/**
 * 删除菜单中的会话。
 */
async function deleteQaSession(session: LogisticsDataQaSessionSummary) {
  try {
    await ElMessageBox.confirm('删除后，这个会话在当前浏览器会话中将无法继续查看。是否继续？', '删除会话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
  } catch (_error) {
    return
  }

  removeLogisticsDataQaSession(session.id)
  refreshQaSessions()

  const nextSessionId = qaSessionSummaries.value[0]?.id
  if (isQaSessionActive(session.id)) {
    if (nextSessionId) {
      router.replace({
        path: '/logistics/data-qa',
        query: { session: nextSessionId },
      })
    } else {
      router.replace('/logistics/data-qa')
    }
  }

  ElMessage.success('会话已删除。')
}

/**
 * 响应正文区的主菜单缩进按钮。
 * 说明：
 * 当前页内的折叠按钮只负责左侧主菜单，不再作用于页内独立模块。
 */
function handleSidebarToggle() {
  isAsideCollapsed.value = !isAsideCollapsed.value
}

onMounted(() => {
  refreshQaSessions()
  window.addEventListener(getLogisticsDataQaSessionEventName(), refreshQaSessions)
  window.addEventListener(APP_SHELL_SIDEBAR_TOGGLE_EVENT, handleSidebarToggle)
})

onBeforeUnmount(() => {
  window.removeEventListener(getLogisticsDataQaSessionEventName(), refreshQaSessions)
  window.removeEventListener(APP_SHELL_SIDEBAR_TOGGLE_EVENT, handleSidebarToggle)
})
</script>

<style scoped>
.app-shell {
  height: 100vh;
  box-sizing: border-box;
  overflow: hidden;
  padding: 24px;
  gap: 20px;
  background: linear-gradient(180deg, #f5f8fb 0%, #f8fbf7 100%);
}

.aside {
  background: #ffffff;
  border: 1px solid #dfe8ef;
  border-radius: 20px;
  box-shadow: 0 10px 28px rgba(32, 66, 102, 0.06);
  padding: 18px 14px;
  display: flex;
  flex-direction: column;
  min-height: 0;
  transition: width 0.2s ease;
}

.aside--collapsed {
  padding-left: 10px;
  padding-right: 10px;
}

.logo-card {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 10px 10px 18px;
  border-bottom: 1px solid #edf2f6;
  margin-bottom: 8px;
  min-height: 84px;
}

.logo-mark {
  width: 56px;
  height: 56px;
  border-radius: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.8);
}

.logo-mark__image {
  width: 36px;
  height: 36px;
  object-fit: contain;
}

.logo-copy {
  min-width: 0;
}

.logo-title {
  color: #18314b;
  font-size: 15px;
  font-weight: 800;
  line-height: 1.4;
}

.logo-subtitle {
  color: #6e7d87;
  font-size: 12px;
  margin-top: 4px;
}

.menu {
  border-right: none;
  background: transparent;
  flex: 1;
  padding-top: 6px;
}

:deep(.menu .el-menu-item) {
  height: 50px;
  margin: 0 4px 8px;
  border-radius: 16px;
  color: #56667a;
  font-weight: 600;
}

:deep(.menu .el-menu-item .el-icon) {
  margin-right: 10px;
  font-size: 18px;
}

:deep(.menu .el-menu-item.is-active) {
  background: #eef6fb;
  color: #1f5f95;
  box-shadow: inset 3px 0 0 #6fba2c;
}

:deep(.menu .el-menu-item:hover) {
  background: #f5f9fc;
}

:deep(.menu .el-sub-menu__title) {
  height: 50px;
  margin: 0 4px 8px;
  border-radius: 16px;
  color: #56667a;
  font-weight: 700;
}

:deep(.menu .el-sub-menu__title .el-icon) {
  margin-right: 10px;
  font-size: 18px;
}

:deep(.menu .el-sub-menu__title:hover) {
  background: #f5f9fc;
}

:deep(.menu .el-sub-menu .el-menu) {
  background: transparent;
}

:deep(.menu .el-sub-menu .el-menu-item) {
  margin-left: 18px;
}

.qa-menu-launch {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0 8px 8px 22px;
  padding: 4px 2px 4px 0;
  border-radius: 14px;
}

.qa-menu-launch--active {
  background: #f3f8fd;
}

.qa-menu-launch__main {
  flex: 1;
  min-width: 0;
  height: 40px;
  border: none;
  background: transparent;
  border-radius: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 12px;
  color: #56667a;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}

.qa-menu-launch__main:hover {
  background: #f5f9fc;
}

.qa-menu-launch__create {
  flex: none;
  color: #346ea5;
}

.qa-session-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin: 0 8px 10px 22px;
}

.qa-session-item {
  width: 100%;
  border: 1px solid #e3ebf2;
  background: #fafcff;
  border-radius: 14px;
  padding: 10px 10px 10px 12px;
  display: flex;
  align-items: flex-start;
  gap: 8px;
  text-align: left;
  cursor: pointer;
  transition: border-color 0.2s ease, background 0.2s ease, box-shadow 0.2s ease;
}

.qa-session-item:hover {
  border-color: #c7ddef;
  background: #f7fbfe;
}

.qa-session-item--active {
  border-color: #bfd8ec;
  background: #eef6fb;
}

.qa-session-item__copy {
  min-width: 0;
  flex: 1;
}

.qa-session-item__title {
  color: #20364d;
  font-size: 13px;
  font-weight: 700;
  line-height: 1.5;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.qa-session-item__preview {
  margin-top: 4px;
  color: #6f7f8b;
  font-size: 12px;
  line-height: 1.6;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.qa-session-item__menu {
  flex: none;
  margin-top: -2px;
}

.aside-footnote {
  border-radius: 16px;
  padding: 16px;
  background: linear-gradient(180deg, #f8fbff 0%, #f7fbf4 100%);
  border: 1px solid #e4edf2;
  color: #607081;
}

.aside-footnote__title {
  color: #244466;
  font-size: 13px;
  font-weight: 700;
  margin-bottom: 8px;
}

.aside-footnote__desc {
  font-size: 12px;
  line-height: 1.7;
}

.content-shell {
  flex: 1;
  min-width: 0;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.header {
  background: transparent;
  display: flex;
  align-items: center;
  padding: 10px 6px 18px;
  border-bottom: 1px solid #e7edf2;
  margin-bottom: 8px;
}

.header-title {
  font-size: 26px;
  font-weight: 800;
  letter-spacing: 0.01em;
  color: #153451;
}

.header-desc {
  font-size: 13px;
  color: #667987;
  margin-top: 8px;
  max-width: 760px;
  line-height: 1.7;
}

.main {
  flex: 1;
  min-height: 0;
  padding: 0 6px 6px;
}

.main--immersive {
  padding-top: 0;
  overflow: hidden;
}

@media (max-width: 1080px) {
  .app-shell {
    padding: 14px;
    gap: 14px;
  }

  .aside {
    width: 220px !important;
  }

  .aside--collapsed {
    width: 84px !important;
  }

  .header-title {
    font-size: 24px;
  }
}

@media (max-width: 900px) {
  .app-shell {
    display: block;
    height: auto;
    min-height: 100vh;
    overflow: visible;
  }

  .aside {
    width: auto !important;
    margin-bottom: 16px;
  }
}

.aside--collapsed :deep(.menu .el-sub-menu__title span),
.aside--collapsed :deep(.menu .el-menu-item span) {
  display: none;
}

.aside--collapsed :deep(.menu .el-sub-menu__title),
.aside--collapsed :deep(.menu .el-menu-item) {
  justify-content: center;
  padding-left: 0 !important;
}

.aside--collapsed :deep(.menu .el-sub-menu__title .el-icon),
.aside--collapsed :deep(.menu .el-menu-item .el-icon) {
  margin-right: 0;
}
</style>
