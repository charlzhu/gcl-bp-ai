import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/logistics/data-qa',
  },
  {
    path: '/logistics/data-qa',
    component: () => import('@/views/logistics-data-qa/LogisticsDataQaPage.vue'),
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
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
