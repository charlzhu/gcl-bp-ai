import { http } from '@/utils/http';
/**
 * 自然语言查询。
 */
export async function fetchNLQuery(payload) {
    const resp = await http.post('/logistics/nl2query/parse-and-query', payload);
    return resp.data;
}
/**
 * 物流数据问答正式页查询。
 * 说明：
 * 1. 只对接当前已验收通过的 logistics data-qa 后端接口；
 * 2. 返回值保持 ApiResponse 外层结构，页面层自行取 data；
 * 3. 不在前端做任何字段推断或业务补算。
 */
export async function fetchLogisticsDataQaQuery(payload) {
    const resp = await http.post('/logistics/data-qa/query', payload);
    return resp.data;
}
/**
 * 读取物流数据问答历史列表。
 * 说明：
 * 这里直接复用统一查询历史接口，只固定筛选 `DATA_QA`。
 */
export async function fetchLogisticsDataQaHistory(params = {}) {
    return fetchQueryHistory({
        ...params,
        query_type: 'DATA_QA',
    });
}
/**
 * 读取单条物流数据问答历史详情。
 * 说明：
 * 回放优先读取历史快照，不重新执行后端查询。
 */
export async function fetchLogisticsDataQaHistoryDetail(logId) {
    return fetchQueryHistoryDetail(logId);
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
/**
 * 查询单条历史详情。
 */
export async function fetchQueryHistoryDetail(logId) {
    const resp = await http.get(`/sys/query/log/${logId}`);
    return resp.data;
}
