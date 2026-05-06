<template>
  <el-container class="app-shell" data-testid="app-layout">
    <el-aside class="aside" data-testid="app-sidebar">
      <div class="brand" data-testid="app-brand">
        <img :src="brandLogoUrl" alt="协鑫集成标识" class="brand-logo" />
        <div class="brand-copy">
          <div class="brand-title">协鑫集成</div>
          <div class="brand-name">经营计划智能助手</div>
        </div>
      </div>

      <el-menu
        :default-active="activeMenuIndex"
        :default-openeds="['smart-chat']"
        class="menu"
        data-testid="main-navigation"
        @select="handleMenuSelect"
      >
        <el-sub-menu index="smart-chat" class="chat-submenu" data-testid="nav-smart-chat">
          <template #title>
            <el-icon><ChatDotRound /></el-icon>
            <span>智能问答</span>
          </template>
          <el-menu-item index="chat-new" class="chat-new-item" data-testid="nav-new-chat">
            <span class="new-chat-symbol">+</span>
            <span>新建对话</span>
          </el-menu-item>
          <el-menu-item
            v-for="session in chatSessions"
            :key="session.id"
            :index="`chat:${session.id}`"
            class="chat-session-item"
            data-testid="nav-chat-session"
            :data-session-id="session.id"
            @contextmenu.prevent.stop="openSessionMenu($event, session.id)"
          >
            <span class="session-dot" />
            <span class="session-title" :title="session.title">{{ session.title }}</span>
          </el-menu-item>
        </el-sub-menu>
        <el-menu-item index="/bom-data" data-testid="nav-bom-data">
          <el-icon><Files /></el-icon>
          <span>BOM 数据管理</span>
        </el-menu-item>
        <el-menu-item index="/trial-guide" data-testid="nav-trial-guide">
          <el-icon><Guide /></el-icon>
          <span>试运行说明</span>
        </el-menu-item>
      </el-menu>

      <div class="aside-status">
        <span class="status-dot" />
        试运行版
      </div>

      <div
        v-if="contextMenu.visible"
        class="session-context-menu"
        data-testid="session-context-menu"
        :style="{ left: `${contextMenu.x}px`, top: `${contextMenu.y}px` }"
      >
        <button type="button" data-testid="session-rename-action" @click="renameSelectedSession">重命名</button>
        <button type="button" class="danger" data-testid="session-delete-action" @click="deleteSelectedSession">删除</button>
      </div>
    </el-aside>

    <el-container class="content-shell">
      <el-header class="topbar" data-testid="app-topbar">
        <div class="topbar-copy">
          <div class="topbar-title">{{ headerMeta.title }}</div>
        </div>
        <div class="topbar-status">
          <span class="status-dot" />
          小范围试运行
        </div>
      </el-header>
      <el-main class="main" data-testid="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import { ChatDotRound, Files, Guide } from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useRoute, useRouter } from 'vue-router'
import brandLogoUrl from '@/assets/gcl-logo.svg'
import {
  createOrFocusBlankBusinessChatSession,
  ensureBusinessChatSession,
  getActiveBusinessChatSessionId,
  getBusinessChatSessionEventName,
  listBusinessChatSessions,
  removeBusinessChatSession,
  renameBusinessChatSession,
  setActiveBusinessChatSessionId,
  type BusinessChatSessionSummary,
} from '@/utils/businessChatSessions'

const route = useRoute()
const router = useRouter()
const chatSessions = ref<BusinessChatSessionSummary[]>([])
const activeChatSessionId = ref('')
const contextMenu = reactive({
  visible: false,
  x: 0,
  y: 0,
  sessionId: '',
})

/** 当前主导航高亮项，旧路由进入时仍归一到业务主入口。 */
const activePath = computed(() => {
  if (route.path.startsWith('/bom-data') || route.path.startsWith('/plan-bom')) return '/bom-data'
  if (route.path.startsWith('/trial-guide')) return '/trial-guide'
  return '/smart-chat'
})

/** 当前菜单高亮项。智能问答下高亮具体对话窗口。 */
const activeMenuIndex = computed(() => {
  if (activePath.value === '/smart-chat') {
    return activeChatSessionId.value ? `chat:${activeChatSessionId.value}` : 'smart-chat'
  }
  return activePath.value
})

/** 顶部标题按业务主模块切换，避免把单一领域名称当平台名称。 */
const headerMeta = computed(() => {
  if (activePath.value === '/bom-data') {
    return {
      title: 'BOM 数据管理',
      description: '',
    }
  }
  if (activePath.value === '/trial-guide') {
    return {
      title: '试运行说明',
      description: '',
    }
  }
  return {
    title: '智能问答',
    description: '',
  }
})

/** 同步本地智能问答会话列表。 */
function refreshChatSessions() {
  const session = ensureBusinessChatSession()
  chatSessions.value = listBusinessChatSessions()
  activeChatSessionId.value = getActiveBusinessChatSessionId() || session.id
}

/** 处理主菜单和二级会话菜单点击。 */
function handleMenuSelect(index: string) {
  closeSessionMenu()
  if (index === 'chat-new') {
    const session = createOrFocusBlankBusinessChatSession()
    activeChatSessionId.value = session.id
    chatSessions.value = listBusinessChatSessions()
    router.push('/smart-chat')
    return
  }
  if (index.startsWith('chat:')) {
    const sessionId = index.slice('chat:'.length)
    setActiveBusinessChatSessionId(sessionId)
    activeChatSessionId.value = sessionId
    router.push('/smart-chat')
    return
  }
  router.push(index)
}

/** 打开会话右键菜单。 */
function openSessionMenu(event: MouseEvent, sessionId: string) {
  contextMenu.visible = true
  contextMenu.x = event.clientX
  contextMenu.y = event.clientY
  contextMenu.sessionId = sessionId
}

/** 关闭会话右键菜单。 */
function closeSessionMenu() {
  contextMenu.visible = false
  contextMenu.sessionId = ''
}

/** 重命名当前右键选中的会话窗口。 */
async function renameSelectedSession() {
  const target = chatSessions.value.find((item) => item.id === contextMenu.sessionId)
  if (!target) return
  closeSessionMenu()
  try {
    const { value } = await ElMessageBox.prompt('请输入新的对话名称', '重命名对话', {
      inputValue: target.title,
      inputPattern: /^.{1,30}$/,
      inputErrorMessage: '名称不能为空，最多 30 个字符',
      confirmButtonText: '保存',
      cancelButtonText: '取消',
    })
    if (renameBusinessChatSession(target.id, value)) {
      refreshChatSessions()
      ElMessage.success('已重命名')
    }
  } catch (_error) {
    // 用户取消时不提示，避免打扰业务操作。
  }
}

/** 删除当前右键选中的会话窗口。 */
async function deleteSelectedSession() {
  const target = chatSessions.value.find((item) => item.id === contextMenu.sessionId)
  if (!target) return
  closeSessionMenu()
  try {
    await ElMessageBox.confirm(`确认删除“${target.title}”？`, '删除对话', {
      confirmButtonText: '删除',
      cancelButtonText: '取消',
      type: 'warning',
    })
    const next = removeBusinessChatSession(target.id)
    activeChatSessionId.value = next.id
    refreshChatSessions()
    router.push('/smart-chat')
    ElMessage.success('已删除')
  } catch (_error) {
    // 用户取消删除时不做额外处理。
  }
}

onMounted(() => {
  refreshChatSessions()
  window.addEventListener(getBusinessChatSessionEventName(), refreshChatSessions)
  window.addEventListener('click', closeSessionMenu)
})

onBeforeUnmount(() => {
  window.removeEventListener(getBusinessChatSessionEventName(), refreshChatSessions)
  window.removeEventListener('click', closeSessionMenu)
})
</script>

<style scoped>
.app-shell {
  height: 100vh;
  box-sizing: border-box;
  background: #ffffff;
  color: #1f2933;
  overflow: hidden;
}

.aside {
  width: 284px;
  height: 100vh;
  border-right: 1px solid #eceff3;
  background: #f7f8fa;
  padding: 18px 12px;
  display: flex;
  flex-direction: column;
}

.brand {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 0 8px 14px;
  border-bottom: 1px solid #e5e7eb;
  margin-bottom: 4px;
}

.brand-logo {
  width: 28px;
  height: 28px;
  object-fit: contain;
}

.brand-copy {
  min-width: 0;
}

.brand-title {
  font-size: 12px;
  color: #7a828c;
  line-height: 1.45;
}

.brand-name {
  font-size: 14px;
  font-weight: 700;
  color: #1f2a37;
  line-height: 1.45;
}

.menu {
  border-right: none;
  background: transparent;
  padding-top: 2px;
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
}

:deep(.menu .el-menu-item) {
  height: 40px;
  border-radius: 10px;
  margin: 0 0 4px;
  color: #374151;
  font-size: 14px;
  font-weight: 500;
}

:deep(.menu .el-menu-item .el-icon) {
  margin-right: 10px;
}

:deep(.menu .el-menu-item.is-active) {
  background: #ebedef;
  color: #111827;
}

:deep(.menu .el-sub-menu__title) {
  height: 40px;
  border-radius: 10px;
  margin: 0 0 4px;
  color: #374151;
  font-size: 14px;
  font-weight: 500;
}

:deep(.menu .el-sub-menu__title:hover),
:deep(.menu .el-menu-item:hover) {
  background: #eef1f4;
}

:deep(.chat-submenu .el-menu) {
  background: transparent;
}

:deep(.chat-submenu .el-menu-item.is-active) {
  background: #e8f0ec;
  color: var(--brand-green-strong);
  position: relative;
}

/* 活跃会话项左侧绿色竖条指示 */
:deep(.chat-submenu .el-menu-item.is-active::before) {
  content: '';
  position: absolute;
  left: 20px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  border-radius: 2px;
  background: var(--brand-green);
}

.chat-new-item {
  color: #4b5563;
}

.new-chat-symbol {
  width: 16px;
  color: #5f8f6b;
  font-size: 18px;
  line-height: 1;
}

.chat-session-item {
  display: flex;
  align-items: center;
  min-width: 0;
}

.session-dot {
  width: 6px;
  height: 6px;
  border-radius: 999px;
  margin-right: 9px;
  background: #b8c2cc;
  flex-shrink: 0;
}

.session-title {
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.session-context-menu {
  position: fixed;
  z-index: 2000;
  display: grid;
  min-width: 112px;
  padding: 6px;
  border: 1px solid #e5e7eb;
  border-radius: var(--radius-md);
  background: #ffffff;
  box-shadow: 0 14px 36px rgba(15, 23, 42, 0.12);
  animation: fadeInUp 0.15s ease-out both;
}

.session-context-menu button {
  border: 0;
  border-radius: var(--radius-sm);
  background: transparent;
  padding: 8px 12px;
  color: #374151;
  font-size: 13px;
  text-align: left;
  cursor: pointer;
  transition: background 0.15s ease;
}

.session-context-menu button:hover {
  background: #f3f4f6;
}

.session-context-menu .danger {
  color: #b42318;
}

.aside-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  width: fit-content;
  margin: 8px;
  padding: 8px 14px;
  border-radius: var(--radius-md);
  background: var(--success-bg);
  font-size: 12px;
  color: var(--brand-green);
  font-weight: 500;
}

.content-shell {
  min-width: 0;
  height: 100vh;
  min-height: 0;
  overflow: hidden;
}

.topbar {
  height: 64px;
  padding: 0 28px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #f0f1f3;
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(12px);
}

.topbar-title {
  font-size: 18px;
  font-weight: 600;
  color: #111827;
  line-height: 1.35;
}

.topbar-status {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 6px 10px;
  border-radius: 999px;
  background: #f3f8f5;
  color: #3f7b50;
  font-size: 12px;
  font-weight: 500;
  white-space: nowrap;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #4b9b52;
}

.main {
  padding: 0;
  min-height: 0;
  overflow: hidden;
}

@media (max-width: 900px) {
  .app-shell {
    flex-direction: column;
  }

  .aside {
    width: auto;
    height: auto;
    border-right: none;
    border-bottom: 1px solid #eceff3;
  }

  .menu {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 8px;
  }

  :deep(.menu .el-menu-item) {
    margin: 0;
    justify-content: center;
  }

  .aside-status {
    display: none;
  }

  .topbar {
    align-items: flex-start;
    gap: 10px;
  }
}
</style>
