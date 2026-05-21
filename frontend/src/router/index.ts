import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/smart-chat',
  },
  {
    path: '/smart-chat',
    component: () => import('@/views/business-chat/BusinessChatPage.vue'),
  },
  {
    path: '/logistics/data-qa',
    redirect: '/smart-chat',
  },
  {
    path: '/logistics/data-qa/history',
    component: () => import('@/views/logistics-data-qa/LogisticsDataQaHistoryPage.vue'),
  },
  {
    path: '/nl-query',
    component: () => import('@/views/nl-query/NLQueryPage.vue'),
  },
  {
    path: '/structured-query',
    component: () => import('@/views/structured-query/StructuredQueryPage.vue'),
  },
  {
    path: '/tasks',
    component: () => import('@/views/tasks/TaskPage.vue'),
  },
  {
    path: '/history',
    component: () => import('@/views/history/QueryHistoryPage.vue'),
  },
  {
    path: '/detail-view',
    component: () => import('@/views/detail/DetailViewPage.vue'),
  },
  {
    path: '/plan-bom/detail-query',
    component: () => import('@/views/plan-bom/PlanBomDetailQueryPage.vue'),
  },
  {
    path: '/bom-data',
    component: () => import('@/views/plan-bom/BomDataManagementPage.vue'),
  },
  {
    path: '/trial-guide',
    component: () => import('@/views/trial/TrialGuidePage.vue'),
  },
  {
    path: '/isp-data',
    component: () => import('@/views/inventory-sales-production/DataManagementPage.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
