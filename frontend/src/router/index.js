import { createRouter, createWebHistory } from 'vue-router';
const routes = [
    {
        path: '/',
        redirect: '/nl-query',
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
];
const router = createRouter({
    history: createWebHistory(),
    routes,
});
export default router;
