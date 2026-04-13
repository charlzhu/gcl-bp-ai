import { http } from '@/utils/http';
/**
 * 自然语言查询。
 */
export async function fetchNLQuery(payload) {
    const resp = await http.post('/logistics/nl2query/parse-and-query', payload);
    return resp.data;
}
/**
 * 结构化统计查询。
 */
export async function fetchAggregateQuery(payload) {
    const resp = await http.post('/logistics/query-service/aggregate', payload);
    return resp.data;
}
/**
 * 查询历史导入任务列表。
 */
export async function fetchHistoryTasks() {
    const resp = await http.get('/logistics/data/hist/import/tasks');
    return resp.data;
}
/**
 * 查询系统同步任务列表。
 */
export async function fetchSystemSyncTasks() {
    const resp = await http.get('/logistics/data/sys/sync/tasks');
    return resp.data;
}
/**
 * 查询历史记录。
 * 说明：
 * 这里默认对接通用日志接口；如果你的后端接口路径不同，只需要改这个函数。
 */
export async function fetchQueryHistory(params = {}) {
    const resp = await http.get('/sys/query/log', { params });
    return resp.data;
}
