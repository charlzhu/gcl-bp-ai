const STORAGE_KEY = 'logistics:last-query-context';
/**
 * 保存最近一次查询上下文，便于在明细页中复用。
 */
export function saveLastQueryContext(payload) {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
}
/**
 * 读取最近一次查询上下文。
 */
export function getLastQueryContext() {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw)
        return null;
    try {
        return JSON.parse(raw);
    }
    catch (_error) {
        return null;
    }
}
/**
 * 清理最近一次查询上下文。
 */
export function clearLastQueryContext() {
    sessionStorage.removeItem(STORAGE_KEY);
}
