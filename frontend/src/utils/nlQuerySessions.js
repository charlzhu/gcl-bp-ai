const NL_QUERY_SESSION_LIST_KEY = 'logistics:nl-query:sessions';
const NL_QUERY_SESSION_DATA_PREFIX = 'logistics:nl-query:session:';
const NL_QUERY_SESSION_EVENT = 'nl-query-sessions-updated';
/**
 * 读取当前自然语言查询会话摘要列表。
 */
export function listNLQuerySessions() {
    const raw = sessionStorage.getItem(NL_QUERY_SESSION_LIST_KEY);
    if (!raw)
        return [];
    try {
        const parsed = JSON.parse(raw);
        if (!Array.isArray(parsed))
            return [];
        return parsed.filter(isSessionSummary);
    }
    catch (_error) {
        return [];
    }
}
/**
 * 读取指定会话。
 */
export function getNLQuerySession(sessionId) {
    const raw = sessionStorage.getItem(`${NL_QUERY_SESSION_DATA_PREFIX}${sessionId}`);
    if (!raw)
        return null;
    try {
        const parsed = JSON.parse(raw);
        if (!parsed || typeof parsed !== 'object')
            return null;
        return normalizeSessionRecord(parsed);
    }
    catch (_error) {
        return null;
    }
}
/**
 * 保存会话并同步更新侧边栏摘要。
 */
export function saveNLQuerySession(record) {
    const normalized = normalizeSessionRecord(record);
    if (!normalized)
        return;
    sessionStorage.setItem(`${NL_QUERY_SESSION_DATA_PREFIX}${normalized.id}`, JSON.stringify(normalized));
    const summaries = listNLQuerySessions().filter((item) => item.id !== normalized.id);
    summaries.unshift({
        id: normalized.id,
        title: normalized.title,
        updatedAt: normalized.updatedAt,
    });
    sessionStorage.setItem(NL_QUERY_SESSION_LIST_KEY, JSON.stringify(summaries));
    emitNLQuerySessionUpdated();
}
/**
 * 删除指定会话。
 */
export function removeNLQuerySession(sessionId) {
    sessionStorage.removeItem(`${NL_QUERY_SESSION_DATA_PREFIX}${sessionId}`);
    const summaries = listNLQuerySessions().filter((item) => item.id !== sessionId);
    sessionStorage.setItem(NL_QUERY_SESSION_LIST_KEY, JSON.stringify(summaries));
    emitNLQuerySessionUpdated();
}
/**
 * 主动派发会话更新事件，供布局壳和页面同步会话列表。
 */
export function emitNLQuerySessionUpdated() {
    window.dispatchEvent(new CustomEvent(NL_QUERY_SESSION_EVENT));
}
/**
 * 返回自然语言会话更新事件名，供监听方复用。
 */
export function getNLQuerySessionEventName() {
    return NL_QUERY_SESSION_EVENT;
}
/**
 * 生成新会话 ID。
 */
export function buildNLQuerySessionId() {
    return `nl-session-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}
/**
 * 从问题文本生成侧边栏标题。
 * 说明：
 * 标题只取首问前 18 个字符，保证菜单展示稳定，不会每轮提问都跳变。
 */
export function buildNLQuerySessionTitle(question) {
    const normalized = question.trim();
    if (!normalized)
        return '新的自然语言会话';
    return normalized.length > 18 ? `${normalized.slice(0, 18)}…` : normalized;
}
/**
 * 判断摘要结构是否符合预期。
 */
function isSessionSummary(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        return false;
    const raw = value;
    return typeof raw.id === 'string' && typeof raw.title === 'string' && typeof raw.updatedAt === 'string';
}
/**
 * 将任意对象归一化为合法会话结构。
 */
function normalizeSessionRecord(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        return null;
    const raw = value;
    if (typeof raw.id !== 'string' || typeof raw.title !== 'string')
        return null;
    if (!Array.isArray(raw.items))
        return null;
    const items = raw.items.filter(isConversationItem);
    return {
        id: raw.id,
        title: raw.title,
        items,
        updatedAt: typeof raw.updatedAt === 'string' ? raw.updatedAt : new Date().toISOString(),
    };
}
/**
 * 判断单条问答记录是否合法。
 */
function isConversationItem(value) {
    if (!value || typeof value !== 'object' || Array.isArray(value))
        return false;
    const raw = value;
    return (typeof raw.id === 'string' &&
        typeof raw.question === 'string' &&
        typeof raw.askedAt === 'string' &&
        typeof raw.answeredAt === 'string' &&
        typeof raw.showAdvancedInfo === 'boolean' &&
        raw.response !== null &&
        typeof raw.response === 'object' &&
        !Array.isArray(raw.response));
}
