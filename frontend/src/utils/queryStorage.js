const STORAGE_KEY = 'logistics:last-query-context';
const PAGE_DRAFT_KEY_PREFIX = 'logistics:page-draft:';
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
/**
 * 保存页面草稿。
 * 说明：
 * 查询未提交前，也要尽量保住用户已输入的条件，避免切页后全部丢失。
 */
export function saveQueryPageDraft(payload) {
    const key = `${PAGE_DRAFT_KEY_PREFIX}${payload.sourcePage}`;
    sessionStorage.setItem(key, JSON.stringify(payload));
}
/**
 * 读取页面草稿。
 */
export function getQueryPageDraft(sourcePage) {
    const key = `${PAGE_DRAFT_KEY_PREFIX}${sourcePage}`;
    const raw = sessionStorage.getItem(key);
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
 * 清理指定页面草稿。
 */
export function clearQueryPageDraft(sourcePage) {
    const key = `${PAGE_DRAFT_KEY_PREFIX}${sourcePage}`;
    sessionStorage.removeItem(key);
}
